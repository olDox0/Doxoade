# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/hybrid_forge.py
"""
Vulcan HybridForge — Compilação Seletiva por Função.
=================================================================================================================

Visão: arquivos pode ser impuro mas conter funções puras.
Compilar função isolada captura ganho sem o risco do arquivo inteiro.

Pipeline:
  .py  →  [HybridScanner]           →  funções elegíveis
       →  [HybridForge]             →  mini .pyx por arquivo
       →  [VulcanCompiler]          →  binário .pyd/.so
       →  [bridge.apply_turbo()]    → hot-swap automático

IMPORTANTE — Separação de responsabilidades:
  HybridForge.generate() → só gera .pyx, NUNCA chama o optimizer.
  optimizer é chamado pelo vulcan_cmd._run_hybrid_with_optimizer()
  após receber Path de .pyx. Isso elimina qualquer risco de
  UnboundLocalError por conflito de escopo de variável.
"""

from __future__ import annotations
import ast, hashlib, os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# =========================== Constantes de scoring ===========================

_SCORE_FOR_LOOP          = 3;   _SCORE_COMPREHENSION     = 2
_SCORE_ARITHMETIC_LOOP   = 3;   _SCORE_AST_WALK          = 2
_SCORE_COLLECTION_ACCESS = 1

_PENALTY_IO              = -999;    _PENALTY_SUBPROCESS      = -999
_PENALTY_ASYNC           = -999;    _PENALTY_GLOBAL_MUTÁVEL  = -3

_MIN_SCORE = 4

_IO_NAMES = frozenset({
    'open','socket','connect','send','recv','read','write',
    'readline','readlines','urlopen','urlretrieve','requests',
    'subprocess','Popen','run','call','check_output',
    'sleep','Thread','Process','Queue','print','input',
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
except Exception as e:
    print(f"\033[31m ■ Erro: {e}")
    traceback.print_tb(e.__traceback__)
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

# =========================== Estruturas de dados ===========================

@dataclass
class FunctionScore:
    """Resultado do scoring de uma função individual."""
    name:       str;    lineno:     int
    score:      int;    eligible:   bool
    reasons:    list[str] = field(default_factory=list)
    source:     str       = ""


@dataclass
class FileScanResult:
    """Resultado do scan de um arquivo .py completo."""
    file_path:   str;   total_score: int
    candidates:  list[FunctionScore] = field(default_factory=list)
    skipped:     list[FunctionScore] = field(default_factory=list)

# =========================== HybridScanner ===========================

class HybridScanner:
    """ Analisa arquivo .py via AST e retorna score de cada função definida no nível de módulo. """

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
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
            fs = self._score_function(node, lines)
            if fs.eligible:
                result.candidates.append(fs);    result.total_score += fs.score
            else:
                result.skipped.append(fs)

        result.candidates.sort(key=lambda f: f.score, reverse=True)
        return result

    def _score_function(self, node: ast.FunctionDef, lines: list[str]) -> FunctionScore:
        """Calcula o score de uma função e decide elegibilidade."""
        score   = 0;     reasons = []

        if isinstance(node, ast.AsyncFunctionDef):
            return FunctionScore(node.name, node.lineno, _PENALTY_ASYNC,
                                 False, ["async: inelegível"])

        for dec in node.decorator_list:
            dec_name = self._dec_name(dec)
            if dec_name and dec_name.split('.')[0] in _BAD_DECORATORS:
                return FunctionScore(node.name, node.lineno, _PENALTY_IO,
                                     False, [f"decorator inelegível: {dec_name}"])

        has_loop    = False;   inner_arith = False
        inner_ast   = False;   inner_coll  = False

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                fname = self._call_name(child)
                if fname and fname.split('.')[0] in _IO_NAMES:
                    return FunctionScore(node.name, node.lineno, _PENALTY_IO,
                                         False, [f"I/O detectado: {fname}"])

            if isinstance(child, (ast.For, ast.While)):
                has_loop = True;
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
            name     = node.name,   lineno   = node.lineno,
            score    = score,       eligible = eligible,
            reasons  = reasons,     source   = src,
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
        except Exception as e:
            print(f"\033[31m ■ Erro: {e}")
            traceback.print_tb(e.__traceback__)
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
        except Exception as e:
            print(f"\033[31m ■ Erro: {e}")
            traceback.print_tb(e.__traceback__)

        return None

    @staticmethod
    def _extract_source(node: ast.FunctionDef, lines: list[str]) -> str:
        try:
            start = node.lineno - 1
            end   = getattr(node, 'end_lineno', node.lineno + 10)
            return '\n'.join(lines[start:end])
        except Exception:
            return ""

# =========================== HybridForge ===========================

class HybridForge:
    """
    A partir de um FileScanResult, gera um arquivo .pyx contendo
    apenas as funções elegíveis, transformadas para Cython.
    """

    def __init__(self, foundry_dir: str | Path):
        self.foundry = Path(foundry_dir)
        self.foundry.mkdir(parents=True, exist_ok=True)

    def generate(self, scan_result: FileScanResult) -> Optional[Path]:
        """
        Gera o .pyx para as funções elegíveis do arquivo escaneado.
        Retorna o Path do .pyx gerado, ou None em falha.
        NÃO chama optimize_pyx_file — sem risco de UnboundLocalError.
        """
        if not scan_result.candidates: return None

        abs_path    = Path(scan_result.file_path).resolve()
        path_hash   = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        module_name = f"v_{abs_path.stem}_{path_hash}"

        # Nome de variável diferente de 'pyx_path' para zero ambiguidade
        output_file = self.foundry / f"{module_name}.pyx"

        try:
            pyx_content = self._build_pyx(scan_result.candidates, module_name)
            output_file.write_text(pyx_content, encoding='utf-8')
            return output_file   # retorna Path limpo
        except Exception as exc:
            print(f"\033[31m[HYBRIDFORGE] Erro ao gerar .pyx para "
                  f"{abs_path.name}: {exc}\033[0m")
            return None

    def _build_pyx(self, candidates: list[FunctionScore], module_name: str) -> str:
        """Monta o conteúdo completo do .pyx."""
        sections = [
            _PYX_HEADER,
            _PYX_STUB,
            f"# Módulo: {module_name}",
            f"# Funções compiladas: {len(candidates)}",
            f"# Scores: {', '.join(f'{f.name}={f.score}' for f in candidates)}",
            "",
        ]

        for func_score in candidates:
            transformed = self._transform_function(func_score)
            if transformed:
                sections.append(transformed)
                sections.append("")

        return '\n'.join(sections)

    def _transform_function(self, fs: FunctionScore) -> Optional[str]:
        """
        Transforma o source Python para forma compatível com Cython.
        Remove anotações de tipo, decoradores, renomeia com _vulcan_optimized.
        """
        if not fs.source: return None

        try:
            tree = ast.parse(fs.source)
        except SyntaxError: return None

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            node.decorator_list = []
            node.returns        = None
            for arg in (*node.args.args,
                        *node.args.posonlyargs,
                        *node.args.kwonlyargs):
                arg.annotation = None
                
            if node.args.vararg:    node.args.vararg.annotation = None
            if node.args.kwarg:     node.args.kwarg.annotation  = None

            if not node.name.endswith('_vulcan_optimized'):
                node.name = f"{node.name}_vulcan_optimized"

            ast.fix_missing_locations(node)

            try:
                code = ast.unparse(node)
            except Exception: return None

            header = (f"# origem: {fs.name}  |  score: {fs.score}  "
                      f"|  razões: {', '.join(fs.reasons)}")
            return f"{header}\n{code}"
        return None

# =========================== HybridIgnite ===========================

class HybridIgnite:
    """ Entry-point de alto nível para compilação híbrida via hybrid_ignite().
    O optimizer NÃO é invocado aqui — fica em vulcan_cmd._run_hybrid_with_optimizer. """

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
        target:      str | Path,
        force:       bool = False,
        on_progress       = None,
    ) -> dict:
        """Escaneia target, compila funções elegíveis sem optimizer."""
        target_path = Path(target).resolve()
        files       = self._collect_files(target_path)

        report = {
            "files_scanned":       0,    "files_with_hits":     0,
            "functions_compiled":  0,   "functions_skipped":   0,
            "total_score":         0,
            
            "modules_generated":   [],  "errors":              [],
        }

        for py_file in files:
            report["files_scanned"] += 1
            scan = self._scanner.scan(str(py_file))

            if not scan.candidates:
                report["functions_skipped"] += len(scan.skipped)
                continue

            report["files_with_hits"]    += 1
            report["functions_compiled"] += len(scan.candidates)
            report["functions_skipped"]  += len(scan.skipped)
            report["total_score"]        += scan.total_score

            self._log_progress(on_progress, scan)

            generated = self._forge.generate(scan)   # retorna Path ou None
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
            else:
                report["errors"].append(f"{module_name}: {err}")
                self._log(on_progress,
                    f"   \033[31m✘\033[0m {py_file.name}: {str(err)[:80]}"
                )

        self._print_summary(report, on_progress)
        return report

    def _compile(self, module_name: str) -> tuple[bool, Optional[str]]:
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
            '__init__', '__main__', 'setup', 'forge', 'compiler', 'autopilot',
            'bridge', 'advisor', 'environment', 'core', 'pitstop',
            'diagnostic', 'guards', 'lab', 'sentinel', 'meta_finder',
            'runtime', 'auto_repair', 'artifact_manager', 'compiler_safe',
        })
        _IGNORE_DIRS = frozenset({'venv','.git','__pycache__','build','dist','.doxoade','tests','pytest_temp_dir',})

        if target.is_file() and target.suffix == '.py':
            return [target] if target.stem not in _IGNORE else []

        files = []
        for root, dirs, filenames in os.walk(str(target)):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for fname in filenames:
                if not fname.endswith('.py'): continue
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
    def _print_summary(repr: dict, callback):
        lines = [
            "\n\033[36m{'─' * 55}\033[0m", f"  \033[1mHYBRIDFORGE — RESUMO\033[0m",
            f"  Arquivos escaneados  : {repr['files_scanned']}",
            f"  Arquivos com ganho   : {repr['files_with_hits']}",
            f"  Funções compiladas   : {repr['functions_compiled']}",
            f"  Funções ignoradas    : {repr['functions_skipped']}",
            f"  Score acumulado      : {repr['total_score']}",
            f"  Módulos gerados      : {len(repr['modules_generated'])}",
        ]
        if repr["errors"]:
            lines.append(f"  Erros                : {len(repr['errors'])}")
            for e in repr["errors"][:5]:
                lines.append(f"    └─ {e}")
        lines.append(f"\033[36m{'─' * 55}\033[0m")
        msg = '\n'.join(lines)
        if callback:
            callback(msg)
        else:
            print(msg)

# =========================== API pública ===========================

def hybrid_scan_file(file_path: str) -> FileScanResult:
    """Escaneia um arquivo e retorna o relatório de scoring. Sem efeito colateral."""
    return HybridScanner().scan(file_path)

def hybrid_ignite(
    project_root: str | Path,       target:       str | Path,
    force:        bool = False,     on_progress        = None,
) -> dict:
    """Entry-point legado — chama HybridIgnite.run() SEM optimizer."""
    return HybridIgnite(project_root).run(target, force=force, on_progress=on_progress)