# doxoade/doxoade/tools/vulcan/hybrid_forge.py
"""
Vulcan HybridForge — Compilação Seletiva por Função.
=====================================================

Visão: um arquivo pode ser impuro mas conter funções puras.
Compilar a função isolada captura o ganho sem o risco do arquivo inteiro.

Pipeline:
  .py  →  [HybridScanner]  →  funções elegíveis
       →[HybridForge]    →  mini .pyx por arquivo
       →  [VulcanCompiler] →  binário .pyd/.so
       →  [bridge.apply_turbo()] → hot-swap automático

Otimização de Hardware (Cache-Aware Architecture):
  - Uso estrito de @dataclass(slots=True) para comprimir o tamanho dos objetos
    na memória (economia de ~60% de RAM por instância).
  - Uso massivo de sys.intern() nos nomes de variáveis e operações da AST
    para forçar comparações de O(1) no endereçamento de ponteiros da CPU e
    aumentar os Cache Hits no L2.

Compliance:
  OSL-4 : cada classe tem responsabilidade única
  OSL-5 : score nunca lança exceção — retorna 0 em caso de dúvida
  OSL-7 : retornos tipados e verificados pelo chamador
  MPoT-3: sem alocação desnecessária no loop de scoring
  PASC-6: fail-graceful em qualquer etapa
"""
from __future__ import annotations
import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
_SCORE_FOR_LOOP = 3
_SCORE_COMPREHENSION = 2
_SCORE_ARITHMETIC_LOOP = 3
_SCORE_AST_WALK = 2
_SCORE_COLLECTION_ACCESS = 1
_PENALTY_IO = -999
_PENALTY_SUBPROCESS = -999
_PENALTY_ASYNC = -999
_PENALTY_GLOBAL_MUTÁVEL = -3
_MIN_SCORE = 4
_IO_NAMES = frozenset(map(sys.intern, {'open', 'socket', 'connect', 'send', 'recv', 'read', 'write', 'readline', 'readlines', 'urlopen', 'urlretrieve', 'requests', 'subprocess', 'Popen', 'run', 'call', 'check_output', 'sleep', 'Thread', 'Process', 'Queue', 'print', 'input'}))
_BAD_DECORATORS = frozenset(map(sys.intern, {'click', 'command', 'group', 'option', 'argument', 'route', 'app', 'staticmethod', 'classmethod', 'property', 'lru_cache', 'cache', 'wraps'}))
_PYX_HEADER = '# cython: language_level=3, boundscheck=False, wraparound=False\n# cython: initializedcheck=False, cdivision=True\n# --- GERADO PELO HYBRIDFORGE — NÃO EDITAR MANUALMENTE ---\nimport sys as _sys\nimport os as _os\nimport re as _re\nimport ast as _ast\nimport json as _json\ntry:\n    from typing import *\nexcept Exception:\n    pass\n'
_PYX_HEADER_AGGRESSIVE = '# cython: language_level=3, boundscheck=False, wraparound=False\n# cython: initializedcheck=False, cdivision=True, nonecheck=False\n# cython: overflowcheck=False, infer_types=True, embedsignature=False\n# --- VULCAN RETRY-AGGRESSIVE: compilação com máximas otimizações Cython ---\nimport sys as _sys\nimport os as _os\nimport re as _re\nimport ast as _ast\nimport json as _json\ntry:\n    from typing import *\nexcept Exception:\n    pass\n'
_PYX_STUB = "class _Stub:\n    def __init__(self, *a, **kw): pass\n    def __call__(self, *a, **kw): return _Stub()\n    def __getattr__(self, _): return _Stub()\n    def __add__(self, o): return o if isinstance(o, str) else _Stub()\n    def __radd__(self, o): return o if isinstance(o, str) else _Stub()\n    def __str__(self): return ''\n    def __bool__(self): return False\n"

@dataclass(slots=True)
class FunctionScore:
    """Resultado do scoring de uma função individual."""
    name: str
    lineno: int
    score: int
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    source: str = ''

@dataclass(slots=True)
class FileScanResult:
    """Resultado do scan de um arquivo .py completo."""
    file_path: str
    total_score: int
    candidates: list[FunctionScore] = field(default_factory=list)
    skipped: list[FunctionScore] = field(default_factory=list)

class HybridScanner:
    """
    Analisa um arquivo .py via AST e retorna o score de elegibilidade
    de cada função definida no nível de módulo.
    """

    def scan(self, file_path: str) -> FileScanResult:
        path = Path(file_path)
        result = FileScanResult(file_path=str(path), total_score=0)
        try:
            source = path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(source, filename=str(path))
        except Exception as exc:
            result.skipped.append(FunctionScore(name=sys.intern('<parse_error>'), lineno=0, score=0, eligible=False, reasons=[str(exc)]))
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
        all_names: list = []
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                all_names.append((child.lineno, child.col_offset, sys.intern(child.id), sys.intern(type(child.ctx).__name__)))
        all_names.sort()
        builtins_names: set = {sys.intern(k) for k in (dir(__builtins__) if not isinstance(__builtins__, dict) else __builtins__.keys())}
        defined: set = builtins_names | {sys.intern('True'), sys.intern('False'), sys.intern('None'), sys.intern('self'), sys.intern('cls')}
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs + node.args.kw_defaults:
            if isinstance(arg, ast.arg):
                defined.add(sys.intern(arg.arg))
        if node.args.vararg:
            defined.add(sys.intern(node.args.vararg.arg))
        if node.args.kwarg:
            defined.add(sys.intern(node.args.kwarg.arg))
        problems: list = []
        store_ctx = sys.intern('Store')
        load_ctx = sys.intern('Load')
        for _line, _col, name, ctx in all_names:
            if ctx is store_ctx:
                defined.add(name)
            elif ctx is load_ctx:
                if name not in defined:
                    has_later_store = any((n is name and c is store_ctx and ((l, co) > (_line, _col)) for l, co, n, c in all_names))
                    if has_later_store and name not in problems:
                        problems.append(name)
        return problems

    def _score_function(self, node: ast.FunctionDef, lines: list[str]) -> FunctionScore:
        score = 0
        reasons = []
        node_name = sys.intern(node.name)
        if isinstance(node, ast.AsyncFunctionDef):
            return FunctionScore(node_name, node.lineno, _PENALTY_ASYNC, False, [sys.intern('async: inelegível')])
        unbound = self._has_unbound_locals(node)
        if unbound:
            return FunctionScore(node_name, node.lineno, 0, False, [f"unbound local(s): {', '.join(unbound[:3])} — corrigir antes de compilar"])
        for dec in node.decorator_list:
            dec_name = self._dec_name(dec)
            if dec_name and dec_name.split('.')[0] in _BAD_DECORATORS:
                return FunctionScore(node_name, node.lineno, _PENALTY_IO, False, [f'decorator inelegível: {dec_name}'])
        has_loop = False
        inner_arith = False
        inner_ast = False
        inner_coll = False
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                fname = self._call_name(child)
                if fname and fname.split('.')[0] in _IO_NAMES:
                    return FunctionScore(node_name, node.lineno, _PENALTY_IO, False, [f'I/O detectado: {fname}'])
            if isinstance(child, (ast.For, ast.While)):
                has_loop = True
                score += _SCORE_FOR_LOOP
                reasons.append(sys.intern('for/while loop'))
            if isinstance(child, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                score += _SCORE_COMPREHENSION
                reasons.append(sys.intern('comprehension'))
            if has_loop and isinstance(child, (ast.BinOp, ast.AugAssign)):
                if isinstance(getattr(child, 'op', None), (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv)):
                    if not inner_arith:
                        inner_arith = True
                        score += _SCORE_ARITHMETIC_LOOP
                        reasons.append(sys.intern('aritmética em loop'))
            if has_loop and isinstance(child, ast.Call):
                cname = self._call_name(child)
                if cname in ('ast.walk', 'isinstance', 'type'):
                    if not inner_ast:
                        inner_ast = True
                        score += _SCORE_AST_WALK
                        reasons.append(sys.intern('ast.walk/isinstance em loop'))
            if has_loop and isinstance(child, ast.Subscript):
                if not inner_coll:
                    inner_coll = True
                    score += _SCORE_COLLECTION_ACCESS
                    reasons.append(sys.intern('acesso a coleção em loop'))
            if isinstance(child, ast.Global):
                score += _PENALTY_GLOBAL_MUTÁVEL
                reasons.append(sys.intern('global mutável: -3'))
        eligible = score >= _MIN_SCORE
        src = self._extract_source(node, lines)
        _PATH_ONLY_CALLS = frozenset(map(sys.intern, {'dirname', 'abspath', 'normpath', 'join', 'basename', 'splitext', 'exists', 'isfile', 'isdir'}))
        path_calls = sum((1 for child in ast.walk(node) if isinstance(child, ast.Call) and self._call_name(child) in _PATH_ONLY_CALLS))
        total_calls = sum((1 for child in ast.walk(node) if isinstance(child, ast.Call)))
        if total_calls > 0 and path_calls / total_calls > 0.6:
            return FunctionScore(node_name, node.lineno, 0, False, [sys.intern('os.path-heavy: já é C, sem ganho')])
        return FunctionScore(name=node_name, lineno=node.lineno, score=score, eligible=eligible, reasons=reasons, source=src)

    @staticmethod
    def _call_name(node: ast.Call) -> Optional[str]:
        try:
            func = node.func
            if isinstance(func, ast.Name):
                return sys.intern(func.id)
            if isinstance(func, ast.Attribute):
                obj = func.value
                obj_name = obj.id if isinstance(obj, ast.Name) else ''
                if obj_name:
                    return sys.intern(f'{obj_name}.{func.attr}')
                return sys.intern(func.attr)
        except Exception:
            pass
        return None

    @staticmethod
    def _dec_name(node: ast.expr) -> Optional[str]:
        try:
            if isinstance(node, ast.Name):
                return sys.intern(node.id)
            if isinstance(node, ast.Attribute):
                return sys.intern(node.attr)
            if isinstance(node, ast.Call):
                return HybridScanner._dec_name(node.func)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_source(node: ast.FunctionDef, lines: list[str]) -> str:
        try:
            start = node.lineno - 1
            end = getattr(node, 'end_lineno', node.lineno + 10)
            return '\n'.join(lines[start:end])
        except Exception:
            return ''

class HybridForge:
    """
    A partir de um FileScanResult, gera um arquivo .pyx contendo
    apenas as funções elegíveis, transformadas para Cython.
    """

    def __init__(self, foundry_dir: str | Path):
        self.foundry = Path(foundry_dir)
        self.foundry.mkdir(parents=True, exist_ok=True)

    def generate(self, scan_result, aggressive_funcs=None):
        import re
        import hashlib
        from pathlib import Path
        if not scan_result.candidates:
            return None
        abs_path = Path(scan_result.file_path).resolve()
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        safe_stem = re.sub('[^a-zA-Z0-9_]', '_', abs_path.stem)
        module_name = f'v_{safe_stem}_{path_hash}'
        output_file = self.foundry / f'{module_name}.pyx'
        try:
            pyx_content = self._build_pyx(scan_result.candidates, module_name, aggressive_funcs=aggressive_funcs or frozenset())
            output_file.write_text(pyx_content, encoding='utf-8')
            return output_file
        except Exception as exc:
            print(f'\x1b[31m[HYBRIDFORGE] Erro ao gerar .pyx para {abs_path.name}: {exc}\x1b[0m')
            return None

    def _build_pyx(self, candidates, module_name, aggressive_funcs=frozenset()):
        has_aggressive = bool(aggressive_funcs & {f.name for f in candidates})
        header = _PYX_HEADER_AGGRESSIVE if has_aggressive else _PYX_HEADER
        sections = [header, _PYX_STUB, f'# Módulo     : {module_name}', f'# Compilados : {len(candidates)}', f"# Agressivos : {', '.join(aggressive_funcs & {f.name for f in candidates}) or 'nenhum'}', '']
        for fs in candidates:
            is_aggressive = fs.name in aggressive_funcs
            transformed = self._transform_function(fs, aggressive=is_aggressive)
            if transformed:
                sections.append(transformed)
                sections.append('')
        return '\n'.join(sections)

    def _transform_function(self, fs, aggressive=False):
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
            node.decorator_list = []
            node.returns = None
            for arg in (*node.args.args, *node.args.posonlyargs, *node.args.kwonlyargs):
                arg.annotation = None
            if node.args.vararg:
                node.args.vararg.annotation = None
            if node.args.kwarg:
                node.args.kwarg.annotation = None
            if not node.name.endswith('_vulcan_optimized'):
                node.name = f'{node.name}_vulcan_optimized'
            ast.fix_missing_locations(node)
            try:
                code = ast.unparse(node)
            except Exception:
                return None
            mode_tag = '[AGGRESSIVE]' if aggressive else '[STANDARD]'
            comment = f"# {fs.name}  score={fs.score}  {mode_tag}  razões: {', '.join(fs.reasons)}"
            return f'{comment}\n{code}'
        return None

class HybridIgnite:
    """
    Entry-point de alto nível para compilação híbrida via hybrid_ignite().
    """

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()
        self.foundry = self.root / '.doxoade' / 'vulcan' / 'foundry'
        self.bin_dir = self.root / '.doxoade' / 'vulcan' / 'bin'
        self.foundry.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self._scanner = HybridScanner()
        self._forge = HybridForge(self.foundry)

    def run(self, target, force=False, on_progress=None, registry=None, watch=True):
        from pathlib import Path
        target_path = Path(target).resolve()
        files = self._collect_files(target_path)
        report = {'files_scanned': 0, 'files_with_hits': 0, 'functions_compiled': 0, 'functions_skipped': 0, 'functions_excluded': 0, 'functions_aggressive': 0, 'total_score': 0, 'modules_generated': [], 'errors': [], 'watch_results': []}
        for py_file in files:
            report['files_scanned'] += 1
            scan = self._scanner.scan(str(py_file))
            if not scan.candidates:
                report['functions_skipped'] += len(scan.skipped)
                continue
            aggressive_funcs = frozenset()
            if registry is not None:
                excluded = registry.excluded_funcs_for_file(str(py_file))
                aggressive_funcs = registry.aggressive_funcs_for_file(str(py_file))
                before = len(scan.candidates)
                scan.candidates = [c for c in scan.candidates if c.name not in excluded]
                excl_n = before - len(scan.candidates)
                report['functions_excluded'] += excl_n
                report['functions_aggressive'] += len([c for c in scan.candidates if c.name in aggressive_funcs])
                if excl_n:
                    self._log(on_progress, f'   \x1b[31m↷ {py_file.name}: {excl_n} função(ões) excluída(s) pelo registry\x1b[0m')
                agg_active = aggressive_funcs & {c.name for c in scan.candidates}
                if agg_active:
                    self._log(on_progress, f"   \x1b[35m⬡ {py_file.name}: retry-agressivo → {', '.join(sorted(agg_active))}\x1b[0m")
            if not scan.candidates:
                report['functions_skipped'] += len(scan.skipped)
                continue
            report['files_with_hits'] += 1
            report['functions_compiled'] += len(scan.candidates)
            report['functions_skipped'] += len(scan.skipped)
            report['total_score'] += scan.total_score
            self._log_progress(on_progress, scan)
            generated = self._forge.generate(scan, aggressive_funcs=aggressive_funcs)
            if not generated:
                report['errors'].append(f'forge falhou: {py_file.name}')
                continue
            module_name = generated.stem
            report['modules_generated'].append(module_name)
            ok, err = self._compile(module_name)
            if ok:
                self._log(on_progress, f'   \x1b[32m✔\x1b[0m {py_file.name} → {module_name} ({len(scan.candidates)} funcs, score={scan.total_score})')
                if watch and registry is not None:
                    wr = self._post_compile_watch(py_file, module_name, registry)
                    if wr:
                        report['watch_results'].append(wr)
            else:
                report['errors'].append(f'{module_name}: {err}')
                self._log(on_progress, f'   \x1b[31m✘\x1b[0m {py_file.name}: {str(err)[:80]}')
        self._print_summary(report, on_progress)
        return report

    def _post_compile_watch(self, py_file, module_name, registry):
        try:
            from .performance_watcher import PerformanceWatcher
            watcher = PerformanceWatcher(project_root=self.root, foundry=self.foundry, bin_dir=self.bin_dir)
            wr = watcher.evaluate(py_file, module_name, update_registry=True)
            return wr
        except Exception:
            return None

    def _compile(self, module_name: str) -> tuple[bool, Optional[str]]:
        try:
            from .environment import VulcanEnvironment
            from .compiler import VulcanCompiler
            env = VulcanEnvironment(self.root)
            compiler = VulcanCompiler(env)
            return compiler.compile(module_name)
        except Exception as exc:
            return (False, str(exc))

    @staticmethod
    def _collect_files(target: Path) -> list[Path]:
        _IGNORE = frozenset({'__init__', '__main__', 'setup', 'forge', 'compiler', 'autopilot', 'bridge', 'advisor', 'environment', 'core', 'pitstop', 'diagnostic', 'guards', 'lab', 'sentinel', 'meta_finder', 'runtime', 'auto_repair', 'artifact_manager', 'compiler_safe'})
        _IGNORE_DIRS = frozenset({'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade', 'tests', 'pytest_temp_dir'})
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
        path = Path(scan.file_path).name
        lines = [f'   \x1b[33m[HYBRID]\x1b[0m {path} — {len(scan.candidates)} candidato(s):']
        for f in scan.candidates:
            lines.append(f"     • {f.name:<35} score={f.score:>2}  ({', '.join(f.reasons[:3])})")
        callback('\n'.join(lines))

    @staticmethod
    def _log(callback, msg: str):
        if callback:
            callback(msg)
        else:
            print(msg)

    @staticmethod
    def _print_summary(report: dict, callback):
        lines = [f"\n\x1b[36m{'─' * 55}\x1b[0m", '  \x1b[1mHYBRIDFORGE — RESUMO\x1b[0m', f"  Arquivos escaneados  : {report['files_scanned']}", f"  Arquivos com ganho   : {report['files_with_hits']}", f"  Funções compiladas   : {report['functions_compiled']}", f"  Funções ignoradas    : {report['functions_skipped']}", f"  Score acumulado      : {report['total_score']}", f"  Módulos gerados      : {len(report['modules_generated'])}"]
        if report['errors']:
            lines.append(f"  Erros                : {len(report['errors'])}")
            for e in report['errors'][:5]:
                lines.append(f'    └─ {e}')
        lines.append(f"\x1b[36m{'─' * 55}\x1b")
