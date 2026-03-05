# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/hybrid_forge.py
"""
Vulcan HybridForge — Compilação Seletiva por Função.
=====================================================

Visão: um arquivo pode ser impuro mas conter funções puras.
Compilar a função isolada captura o ganho sem o risco do arquivo inteiro.

Pipeline:
  .py  →  [HybridScanner]  →  funções elegíveis
       →  [HybridForge]    →  mini .pyx por arquivo
       →  [VulcanCompiler] →  binário .pyd/.so
       →  [bridge.apply_turbo()] → hot-swap automático

IMPORTANTE — Separação de responsabilidades:
  HybridForge.generate() → só gera o .pyx, NUNCA chama o optimizer.
  O optimizer é chamado pelo vulcan_cmd._run_hybrid_with_optimizer()
  após receber o Path do .pyx. Isso elimina qualquer risco de
  UnboundLocalError por conflito de escopo de variável.

Compliance:
  OSL-4 : cada classe tem responsabilidade única
  OSL-5 : score nunca lança exceção — retorna 0 em caso de dúvida
  OSL-7 : retornos tipados e verificados pelo chamador
  MPoT-3: sem alocação desnecessária no loop de scoring
  PASC-6: fail-graceful em qualquer etapa
"""

from __future__ import annotations

import ast
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes de scoring
# ---------------------------------------------------------------------------

_SCORE_FOR_LOOP          = 3
_SCORE_COMPREHENSION     = 2
_SCORE_ARITHMETIC_LOOP   = 3
_SCORE_AST_WALK          = 2
_SCORE_COLLECTION_ACCESS = 1

_PENALTY_IO              = -999
_PENALTY_SUBPROCESS      = -999
_PENALTY_ASYNC           = -999
_PENALTY_GLOBAL_MUTÁVEL  = -3

_MIN_SCORE = 4

_IO_NAMES = frozenset({
    'open', 'socket', 'connect', 'send', 'recv',
    'read', 'write', 'readline', 'readlines',
    'urlopen', 'urlretrieve', 'requests',
    'subprocess', 'Popen', 'run', 'call', 'check_output',
    'sleep', 'Thread', 'Process', 'Queue',
    'print', 'input',
})

_BAD_DECORATORS = frozenset({
    'click', 'command', 'group', 'option', 'argument',
    'route', 'app', 'staticmethod', 'classmethod',
    'property', 'lru_cache', 'cache', 'wraps',
})

_PYX_HEADER = """\
# cython: language_level=3, boundscheck=False, wraparound=False
# cython: initializedcheck=False, cdivision=True
# --- GERADO PELO HYBRIDFORGE — NÃO EDITAR MANUALMENTE ---
import sys as _sys
import os as _os
import re as _re
import ast as _ast
import json as _json
try:
    from typing import *
except Exception:
    pass
"""

_PYX_HEADER_AGGRESSIVE = """\
# cython: language_level=3, boundscheck=False, wraparound=False
# cython: initializedcheck=False, cdivision=True, nonecheck=False
# cython: overflowcheck=False, infer_types=True, embedsignature=False
# --- VULCAN RETRY-AGGRESSIVE: compilação com máximas otimizações Cython ---
import sys as _sys
import os as _os
import re as _re
import ast as _ast
import json as _json
try:
    from typing import *
except Exception:
    pass
"""

_PYX_STUB = """\
class _Stub:
    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw): return _Stub()
    def __getattr__(self, _): return _Stub()
    def __add__(self, o): return o if isinstance(o, str) else _Stub()
    def __radd__(self, o): return o if isinstance(o, str) else _Stub()
    def __str__(self): return ''
    def __bool__(self): return False
"""


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class FunctionScore:
    """Resultado do scoring de uma função individual."""
    name:       str
    lineno:     int
    score:      int
    eligible:   bool
    reasons:    list[str] = field(default_factory=list)
    source:     str       = ""


@dataclass
class FileScanResult:
    """Resultado do scan de um arquivo .py completo."""
    file_path:   str
    total_score: int
    candidates:  list[FunctionScore] = field(default_factory=list)
    skipped:     list[FunctionScore] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HybridScanner
# ---------------------------------------------------------------------------

class HybridScanner:
    """
    Analisa um arquivo .py via AST e retorna o score de elegibilidade
    de cada função definida no nível de módulo.

    OSL-5: nenhum método levanta exceção para o chamador.
    """

    def scan(self, file_path: str) -> FileScanResult:
        """Entry-point principal. Retorna FileScanResult mesmo em erro de parse."""
        path   = Path(file_path)
        result = FileScanResult(file_path=str(path), total_score=0)

        try:
            source = path.read_text(encoding='utf-8', errors='ignore')
            tree   = ast.parse(source, filename=str(path))
        except Exception as exc:
            result.skipped.append(
                FunctionScore(name="<parse_error>", lineno=0, score=0,
                              eligible=False, reasons=[str(exc)])
            )
            return result

        lines = source.splitlines()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            fs = self._score_function(node, lines)
            if fs.eligible:
                result.candidates.append(fs)
                result.total_score += fs.score
            else:
                result.skipped.append(fs)

        result.candidates.sort(key=lambda f: f.score, reverse=True)
        return result

    @staticmethod
    def _has_unbound_locals(node: ast.FunctionDef) -> list[str]:
        """
        Detecta variáveis usadas antes de qualquer atribuição na função.
        Cython é mais estrito que Python — trata isso como erro de compilação.

        Usa traversal ordenado por (lineno, col_offset) para detectar corretamente
        casos como: `if not x: x = default` (x Load vem antes de x Store na mesma linha).

        Retorna lista de nomes problemáticos (vazia = função OK).
        """
        # Coleta todos os nós Name com posição, ordenados por (linha, coluna)
        all_names: list = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                all_names.append((
                    child.lineno,
                    child.col_offset,
                    child.id,
                    type(child.ctx).__name__,  # 'Load', 'Store', 'Del'
                ))
        all_names.sort()  # ordena por (linha, col) — garante ordem de execução

        # Nomes já definidos ao entrar na função: argumentos + builtins
        builtins_names: set = set(dir(__builtins__) if not isinstance(__builtins__, dict)
                                  else __builtins__.keys())
        defined: set = builtins_names | {'True', 'False', 'None', 'self', 'cls'}

        for arg in (node.args.args + node.args.posonlyargs +
                    node.args.kwonlyargs + node.args.kw_defaults):
            if isinstance(arg, ast.arg):
                defined.add(arg.arg)
        if node.args.vararg: defined.add(node.args.vararg.arg)
        if node.args.kwarg:  defined.add(node.args.kwarg.arg)

        problems: list = []

        for _line, _col, name, ctx in all_names:
            if ctx == 'Store':
                defined.add(name)
            elif ctx == 'Load':
                if name not in defined:
                    # Verifica se há um Store posterior para este nome
                    # (confirma que era intenção ser local, não global/builtin)
                    has_later_store = any(
                        n == name and c == 'Store' and (l, co) > (_line, _col)
                        for l, co, n, c in all_names
                    )
                    if has_later_store and name not in problems:
                        problems.append(name)

        return problems

    def _score_function(self, node: ast.FunctionDef, lines: list[str]) -> FunctionScore:
        """Calcula o score de uma função e decide elegibilidade."""
        score   = 0
        reasons = []

        if isinstance(node, ast.AsyncFunctionDef):
            return FunctionScore(node.name, node.lineno, _PENALTY_ASYNC,
                                 False, ["async: inelegível"])

        # Verificação de UnboundLocalError antes de qualquer outra coisa
        unbound = self._has_unbound_locals(node)
        if unbound:
            return FunctionScore(
                node.name, node.lineno, 0, False,
                [f"unbound local(s): {', '.join(unbound[:3])} — corrigir antes de compilar"]
            )

        for dec in node.decorator_list:
            dec_name = self._dec_name(dec)
            if dec_name and dec_name.split('.')[0] in _BAD_DECORATORS:
                return FunctionScore(node.name, node.lineno, _PENALTY_IO,
                                     False, [f"decorator inelegível: {dec_name}"])

        has_loop    = False
        inner_arith = False
        inner_ast   = False
        inner_coll  = False

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                fname = self._call_name(child)
                if fname and fname.split('.')[0] in _IO_NAMES:
                    return FunctionScore(node.name, node.lineno, _PENALTY_IO,
                                         False, [f"I/O detectado: {fname}"])

            if isinstance(child, (ast.For, ast.While)):
                has_loop = True
                score   += _SCORE_FOR_LOOP
                reasons.append("for/while loop")

            if isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                score   += _SCORE_COMPREHENSION
                reasons.append("comprehension")

            if has_loop and isinstance(child, (ast.BinOp, ast.AugAssign)):
                if isinstance(getattr(child, 'op', None),
                              (ast.Add, ast.Sub, ast.Mult, ast.Div,
                               ast.Mod, ast.Pow, ast.FloorDiv)):
                    if not inner_arith:
                        inner_arith = True
                        score      += _SCORE_ARITHMETIC_LOOP
                        reasons.append("aritmética em loop")

            if has_loop and isinstance(child, ast.Call):
                cname = self._call_name(child)
                if cname in ('ast.walk', 'isinstance', 'type'):
                    if not inner_ast:
                        inner_ast = True
                        score    += _SCORE_AST_WALK
                        reasons.append("ast.walk/isinstance em loop")

            if has_loop and isinstance(child, ast.Subscript):
                if not inner_coll:
                    inner_coll = True
                    score     += _SCORE_COLLECTION_ACCESS
                    reasons.append("acesso a coleção em loop")

            if isinstance(child, ast.Global):
                score   += _PENALTY_GLOBAL_MUTÁVEL
                reasons.append("global mutável: -3")

        eligible = score >= _MIN_SCORE
        src = self._extract_source(node, lines)

        return FunctionScore(
            name     = node.name,
            lineno   = node.lineno,
            score    = score,
            eligible = eligible,
            reasons  = reasons,
            source   = src,
        )

    @staticmethod
    def _call_name(node: ast.Call) -> Optional[str]:
        try:
            func = node.func
            if isinstance(func, ast.Name):
                return func.id
            if isinstance(func, ast.Attribute):
                obj      = func.value
                obj_name = obj.id if isinstance(obj, ast.Name) else ''
                return f"{obj_name}.{func.attr}" if obj_name else func.attr
        except Exception:
            pass
        return None

    @staticmethod
    def _dec_name(node: ast.expr) -> Optional[str]:
        try:
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                return node.attr
            if isinstance(node, ast.Call):
                return HybridScanner._dec_name(node.func)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_source(node: ast.FunctionDef, lines: list[str]) -> str:
        try:
            start = node.lineno - 1
            end   = getattr(node, 'end_lineno', node.lineno + 10)
            return '\n'.join(lines[start:end])
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# HybridForge
# ---------------------------------------------------------------------------

class HybridForge:
    """
    A partir de um FileScanResult, gera um arquivo .pyx contendo
    apenas as funções elegíveis, transformadas para Cython.

    OSL-4: generate() tem UMA responsabilidade — gerar o .pyx.
           O optimizer NÃO é chamado aqui. Fica em vulcan_cmd.py.
    """

    def __init__(self, foundry_dir: str | Path):
        self.foundry = Path(foundry_dir)
        self.foundry.mkdir(parents=True, exist_ok=True)

    def generate(self, scan_result, aggressive_funcs=None):
        """
        Gera o .pyx para as funções candidatas do arquivo escaneado.

        Com aggressive_funcs, funções presentes nesse conjunto recebem
        directives Cython extras que desabilitam checagens de runtime.

        Retorna Path do .pyx gerado, ou None em falha.
        """
        import re
        import hashlib
        from pathlib import Path

        if not scan_result.candidates:
            return None

        abs_path    = Path(scan_result.file_path).resolve()
        path_hash   = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        safe_stem   = re.sub(r'[^a-zA-Z0-9_]', '_', abs_path.stem)
        module_name = f"v_{safe_stem}_{path_hash}"
        output_file = self.foundry / f"{module_name}.pyx"

        try:
            pyx_content = self._build_pyx(
                scan_result.candidates,
                module_name,
                aggressive_funcs=aggressive_funcs or frozenset(),
            )
            output_file.write_text(pyx_content, encoding="utf-8")
            return output_file
        except Exception as exc:
            print(f"\033[31m[HYBRIDFORGE] Erro ao gerar .pyx para {abs_path.name}: {exc}\033[0m")
            return None


    def _build_pyx(self, candidates, module_name, aggressive_funcs=frozenset()):
        """
        Constrói o conteúdo completo do .pyx.

        Se qualquer candidato está em aggressive_funcs, o header global
        usa _PYX_HEADER_AGGRESSIVE (máximas otimizações).
        Cada função marcada recebe também uma tag de comentário [AGGRESSIVE].
        """
        has_aggressive = bool(aggressive_funcs & {f.name for f in candidates})
        header         = _PYX_HEADER_AGGRESSIVE if has_aggressive else _PYX_HEADER

        sections = [
            header,
            _PYX_STUB,
            f"# Módulo     : {module_name}",
            f"# Compilados : {len(candidates)}",
            f"# Agressivos : {', '.join(aggressive_funcs & {f.name for f in candidates}) or 'nenhum'}",
            "",
        ]

        for fs in candidates:
            is_aggressive = fs.name in aggressive_funcs
            transformed   = self._transform_function(fs, aggressive=is_aggressive)
            if transformed:
                sections.append(transformed)
                sections.append("")

        return "\n".join(sections)


    def _transform_function(self, fs, aggressive=False):
        """
        Converte source Python em Cython.

        Com aggressive=True:
          - Adiciona comentário [AGGRESSIVE] no header da função
          - cdivision e nonecheck já estão cobertos pelo header de módulo
          - (expansão futura: injetar `cdef` nos locais numéricos)

        Retorna None em qualquer falha (PASC-6 safe).
        """
        import ast

        if not fs.source:
            return None

        try:
            tree = ast.parse(fs.source)
        except SyntaxError:
            return None

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Remove decoradores e anotações (Cython não aceita alguns)
            node.decorator_list = []
            node.returns        = None

            for arg in (
                *node.args.args,
                *node.args.posonlyargs,
                *node.args.kwonlyargs,
            ):
                arg.annotation = None
            if node.args.vararg:
                node.args.vararg.annotation = None
            if node.args.kwarg:
                node.args.kwarg.annotation  = None

            if not node.name.endswith("_vulcan_optimized"):
                node.name = f"{node.name}_vulcan_optimized"

            ast.fix_missing_locations(node)

            try:
                code = ast.unparse(node)
            except Exception:
                return None

            mode_tag = "[AGGRESSIVE]" if aggressive else "[STANDARD]"
            comment  = (
                f"# {fs.name}  score={fs.score}  {mode_tag}  "
                f"razões: {', '.join(fs.reasons)}"
            )

            return f"{comment}\n{code}"

        return None



# ---------------------------------------------------------------------------
# HybridIgnite
# ---------------------------------------------------------------------------

class HybridIgnite:
    """
    Entry-point de alto nível para compilação híbrida via hybrid_ignite().
    O optimizer NÃO é invocado aqui — fica em vulcan_cmd._run_hybrid_with_optimizer.
    """

    def __init__(self, project_root: str | Path):
        self.root    = Path(project_root).resolve()
        self.foundry = self.root / ".doxoade" / "vulcan" / "foundry"
        self.bin_dir = self.root / ".doxoade" / "vulcan" / "bin"
        self.foundry.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        self._scanner = HybridScanner()
        self._forge   = HybridForge(self.foundry)

    def run(
        self,
        target,
        force      = False,
        on_progress = None,
        registry   = None,    # RegressionRegistry | None
        watch      = True,    # True = mede performance após compilar
    ):
        """
        Escaneia target e compila funções elegíveis.

        registry (RegressionRegistry):
          • Funções com status 'excluded'         → removidas dos candidatos
          • Funções com status 'retry_aggressive' → compiladas com header agressivo
          • Após compilar cada módulo             → PerformanceWatcher mede e
                                                    atualiza o registry

        watch (bool):
          Se True, chama _post_compile_watch() após cada compilação bem-sucedida.
        """
        from pathlib import Path

        target_path = Path(target).resolve()
        files       = self._collect_files(target_path)

        report = {
            "files_scanned":        0,
            "files_with_hits":      0,
            "functions_compiled":   0,
            "functions_skipped":    0,
            "functions_excluded":   0,
            "functions_aggressive": 0,
            "total_score":          0,
            "modules_generated":    [],
            "errors":               [],
            "watch_results":        [],
        }

        for py_file in files:
            report["files_scanned"] += 1
            scan = self._scanner.scan(str(py_file))

            if not scan.candidates:
                report["functions_skipped"] += len(scan.skipped)
                continue

            # ── Filtra via registry ───────────────────────────────────────────────
            aggressive_funcs = frozenset()

            if registry is not None:
                excluded         = registry.excluded_funcs_for_file(str(py_file))
                aggressive_funcs = registry.aggressive_funcs_for_file(str(py_file))

                before          = len(scan.candidates)
                scan.candidates = [c for c in scan.candidates if c.name not in excluded]
                excl_n          = before - len(scan.candidates)

                report["functions_excluded"]  += excl_n
                report["functions_aggressive"] += len(
                    [c for c in scan.candidates if c.name in aggressive_funcs]
                )

                if excl_n:
                    self._log(on_progress,
                        f"   \033[31m↷ {py_file.name}: "
                        f"{excl_n} função(ões) excluída(s) pelo registry\033[0m"
                    )
                agg_active = aggressive_funcs & {c.name for c in scan.candidates}
                if agg_active:
                    self._log(on_progress,
                        f"   \033[35m⬡ {py_file.name}: "
                        f"retry-agressivo → {', '.join(sorted(agg_active))}\033[0m"
                    )

            if not scan.candidates:
                report["functions_skipped"] += len(scan.skipped)
                continue

            report["files_with_hits"]    += 1
            report["functions_compiled"] += len(scan.candidates)
            report["functions_skipped"]  += len(scan.skipped)
            report["total_score"]        += scan.total_score

            self._log_progress(on_progress, scan)

            # ── Gera e compila .pyx ───────────────────────────────────────────────
            generated = self._forge.generate(scan, aggressive_funcs=aggressive_funcs)
            if not generated:
                report["errors"].append(f"forge falhou: {py_file.name}")
                continue

            module_name = generated.stem
            report["modules_generated"].append(module_name)

            ok, err = self._compile(module_name)

            if ok:
                self._log(on_progress,
                    f"   \033[32m✔\033[0m {py_file.name} → {module_name} "
                    f"({len(scan.candidates)} funcs, score={scan.total_score})"
                )
                # ── Avaliação pós-compilação ──────────────────────────────────────
                if watch and registry is not None:
                    wr = self._post_compile_watch(py_file, module_name, registry)
                    if wr:
                        report["watch_results"].append(wr)
            else:
                report["errors"].append(f"{module_name}: {err}")
                self._log(on_progress,
                    f"   \033[31m✘\033[0m {py_file.name}: {str(err)[:80]}"
                )

        self._print_summary(report, on_progress)
        return report


    def _post_compile_watch(self, py_file, module_name, registry):
        """
        Chama o PerformanceWatcher para medir a performance real
        após uma compilação bem-sucedida e atualizar o registry.

        Retorna WatchResult ou None em caso de erro.
        """
        try:
            from .performance_watcher import PerformanceWatcher

            watcher = PerformanceWatcher(
                project_root = self.root,
                foundry      = self.foundry,   # .pyx intermediários
                bin_dir      = self.bin_dir,   # .so/.pyd compilados
            )
            wr = watcher.evaluate(py_file, module_name, update_registry=True)
            return wr
        except Exception:
            return None


    def _compile(self, module_name: str) -> tuple[bool, Optional[str]]:
        """PASC-6: retorna (False, erro) em vez de levantar exceção."""
        try:
            from .environment import VulcanEnvironment
            from .compiler    import VulcanCompiler

            env      = VulcanEnvironment(self.root)
            compiler = VulcanCompiler(env)
            return compiler.compile(module_name)
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _collect_files(target: Path) -> list[Path]:
        _IGNORE = frozenset({
            '__init__', '__main__', 'setup',
            'forge', 'compiler', 'autopilot',
            'bridge', 'advisor', 'environment', 'core', 'pitstop',
            'diagnostic', 'guards', 'lab', 'sentinel', 'meta_finder',
            'runtime', 'auto_repair', 'artifact_manager', 'compiler_safe',
        })
        _IGNORE_DIRS = frozenset({
            'venv', '.git', '__pycache__', 'build', 'dist',
            '.doxoade', 'tests', 'pytest_temp_dir',
        })

        if target.is_file() and target.suffix == '.py':
            return [target] if target.stem not in _IGNORE else []

        files = []
        for root, dirs, filenames in os.walk(str(target)):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for fname in filenames:
                if not fname.endswith('.py'):
                    continue
                stem = Path(fname).stem
                if stem in _IGNORE:
                    continue
                files.append(Path(root) / fname)
        return files

    @staticmethod
    def _log_progress(callback, scan: FileScanResult):
        if not callback:
            return
        path  = Path(scan.file_path).name
        lines = [f"   \033[33m[HYBRID]\033[0m {path} — "
                 f"{len(scan.candidates)} candidato(s):"]
        for f in scan.candidates:
            lines.append(
                f"     • {f.name:<35} score={f.score:>2}  "
                f"({', '.join(f.reasons[:3])})"
            )
        callback('\n'.join(lines))

    @staticmethod
    def _log(callback, msg: str):
        if callback:
            callback(msg)
        else:
            print(msg)

    @staticmethod
    def _print_summary(report: dict, callback):
        lines = [
            f"\n\033[36m{'─' * 55}\033[0m",
            "  \033[1mHYBRIDFORGE — RESUMO\033[0m",
            f"  Arquivos escaneados  : {report['files_scanned']}",
            f"  Arquivos com ganho   : {report['files_with_hits']}",
            f"  Funções compiladas   : {report['functions_compiled']}",
            f"  Funções ignoradas    : {report['functions_skipped']}",
            f"  Score acumulado      : {report['total_score']}",
            f"  Módulos gerados      : {len(report['modules_generated'])}",
        ]
        if report["errors"]:
            lines.append(f"  Erros                : {len(report['errors'])}")
            for e in report["errors"][:5]:
                lines.append(f"    └─ {e}")
        lines.append(f"\033[36m{'─' * 55}\033[0m")
        msg = '\n'.join(lines)
        if callback:
            callback(msg)
        else:
            print(msg)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def hybrid_scan_file(file_path: str) -> FileScanResult:
    """Escaneia um arquivo e retorna o relatório de scoring. Sem efeito colateral."""
    return HybridScanner().scan(file_path)


def hybrid_ignite(
    project_root: str | Path,
    target:       str | Path,
    force:        bool = False,
    on_progress        = None,
) -> dict:
    """Entry-point legado — chama HybridIgnite.run() SEM optimizer."""
    return HybridIgnite(project_root).run(target, force=force, on_progress=on_progress)