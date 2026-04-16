# doxoade/doxoade/tools/vulcan/opt_benchmark.py
"""
LibOptimizer — Otimizador AST seguro para cópias de fontes de bibliotecas.
==========================================================================

Aplicado à cópia isolada dos .py ANTES do HybridIgnite.
O original no venv NUNCA é tocado.

Transformações (ordenadas do mais para o menos seguro):
  1. DocstringRemover        — remove docstrings de módulo/classe/função
  2. DeadBranchEliminator    — elimina `if False/True/0/1:`, `while False:`
  3. UnusedImportRemover     — remove `import X` nunca referenciado
  4. ImportCombiner          — funde imports consecutivos numa única instrução
  5. GlobalImportAliaser     — aplica alias (as _I1) em imports de nomes longos
  6. SafeLocalNameMinifier   — renomeia variáveis e aliases de forma segura
"""
from __future__ import annotations
import gc
import importlib.util
import sys
import time
import ast
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class FuncResult:
    name: str
    pure_ns: float
    opt_ns: float
    speedup: float
    gain_pct: float
    calls: int
    error: Optional[str] = None

@dataclass
class FileResult:
    path: Path
    opt_path: Optional[Path]
    pure_load_ns: float
    opt_load_ns: float
    load_speedup: float
    pure_size_b: int
    opt_size_b: int
    size_saved_b: int
    funcs: list[FuncResult] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def callable_count(self) -> int:
        return len(self.funcs)

    @property
    def avg_speedup(self) -> float:
        valid = [f.speedup for f in self.funcs if f.error is None and f.speedup > 0]
        return sum(valid) / len(valid) if valid else 1.0

    @property
    def max_speedup(self) -> float:
        valid = [f.speedup for f in self.funcs if f.error is None and f.speedup > 0]
        return min(valid) if valid else 1.0

def _timed_load(py_path: Path, mod_name: str) -> tuple[object, float]:
    """
    Carrega ``py_path`` como módulo ``mod_name`` e retorna (módulo, ns_elapsed).
    Insere temporariamente no sys.modules para permitir imports relativos.
    """
    spec = importlib.util.spec_from_file_location(mod_name, str(py_path))
    if not spec or not spec.loader:
        raise ImportError(f'Não foi possível criar spec para {py_path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter_ns()
        spec.loader.exec_module(mod)
        elapsed = time.perf_counter_ns() - t0
    finally:
        gc.enable()
        sys.modules.pop(mod_name, None)
    return (mod, elapsed)

def _callable_pairs(pure_mod, opt_mod) -> list[tuple[str, object, object]]:
    """Retorna lista de (nome, fn_pure, fn_opt) para callables em comum."""
    pairs = []
    for attr in dir(pure_mod):
        if attr.startswith('_'):
            continue
        p = getattr(pure_mod, attr, None)
        o = getattr(opt_mod, attr, None)
        if callable(p) and callable(o) and (p is not o):
            pairs.append((attr, p, o))
    return pairs
_PROBE_ARGS: dict[int, tuple] = {0: (), 1: (None,), 2: (None, None), 3: (None, None, None)}

def _bench_callable(name: str, pure_fn, opt_fn, rounds: int, calls: int) -> FuncResult:
    """
    Chama pure_fn e opt_fn ``rounds * calls`` vezes cada e mede o tempo médio.

    Estratégia:
      - Descobre aridade automaticamente (inspect.signature).
      - Usa argumentos None/0 se a função não aceitar zero args.
      - Captura TypeError e retorna erro — não trava o benchmark.
    """
    import inspect
    try:
        sig = inspect.signature(pure_fn)
        nreq = sum((1 for p in sig.parameters.values() if p.default is inspect.Parameter.empty and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)))
    except (ValueError, TypeError):
        nreq = 0
    args = _PROBE_ARGS.get(nreq, tuple((None for _ in range(nreq))))

    def _run(fn) -> float:
        best = float('inf')
        for _ in range(rounds):
            gc.disable()
            t0 = time.perf_counter_ns()
            for _ in range(calls):
                try:
                    fn(*args)
                except Exception:
                    pass
            elapsed = time.perf_counter_ns() - t0
            gc.enable()
            best = min(best, elapsed)
        return best / calls
    try:
        pure_ns = _run(pure_fn)
        opt_ns = _run(opt_fn)
        speedup = opt_ns / pure_ns if pure_ns > 0 else 1.0
        return FuncResult(name=name, pure_ns=pure_ns, opt_ns=opt_ns, speedup=speedup, gain_pct=(1.0 - speedup) * 100.0, calls=calls * rounds)
    except Exception as exc:
        return FuncResult(name=name, pure_ns=0, opt_ns=0, speedup=1.0, gain_pct=0.0, calls=0, error=str(exc))

def bench_file(py_path: Path, opt_path: Optional[Path], project_root: Path, *, rounds: int=3, calls: int=100) -> FileResult:
    """Executa benchmark completo (load + callables) para um arquivo."""
    pure_size = py_path.stat().st_size if py_path.exists() else 0
    opt_size = opt_path.stat().st_size if opt_path and opt_path.exists() else 0
    if not opt_path or not opt_path.exists():
        return FileResult(path=py_path, opt_path=None, pure_load_ns=0, opt_load_ns=0, load_speedup=1.0, pure_size_b=pure_size, opt_size_b=0, size_saved_b=0, error="opt_py não encontrado — execute 'doxoade vulcan opt' antes")
    try:
        rel = py_path.relative_to(project_root)
        parent_parts = list(rel.parent.parts)
        pkg_name = '.'.join(parent_parts)
    except ValueError:
        pkg_name = ''
    stem = py_path.stem
    if pkg_name:
        pure_mod_name = f'{pkg_name}._bench_pure_{stem}'
        opt_mod_name = f'{pkg_name}._bench_opt_{stem}'
    else:
        pure_mod_name = f'_bench_pure_{stem}'
        opt_mod_name = f'_bench_opt_{stem}'
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        pure_mod, pure_load = _timed_load(py_path, pure_mod_name)
        opt_mod, opt_load = _timed_load(opt_path, opt_mod_name)
    except Exception as exc:
        return FileResult(path=py_path, opt_path=opt_path, pure_load_ns=0, opt_load_ns=0, load_speedup=1.0, pure_size_b=pure_size, opt_size_b=opt_size, size_saved_b=pure_size - opt_size, error=f'Erro de carregamento: {exc}')
    load_speedup = opt_load / pure_load if pure_load > 0 else 1.0
    pairs = _callable_pairs(pure_mod, opt_mod)
    func_results = [_bench_callable(name, p, o, rounds, calls) for name, p, o in pairs]
    return FileResult(path=py_path, opt_path=opt_path, pure_load_ns=pure_load, opt_load_ns=opt_load, load_speedup=load_speedup, pure_size_b=pure_size, opt_size_b=opt_size, size_saved_b=pure_size - opt_size, funcs=func_results)

def _collect_targets(target: Path, project_root: Path) -> list[tuple[Path, Optional[Path]]]:
    """
    Retorna lista de (py_path, opt_path|None) para o alvo fornecido.
    Suporta arquivo único ou diretório recursivo.
    """
    from doxoade.tools.vulcan.opt_cache import find_opt_py, find_project_root_for

    def _pair(p: Path):
        root = find_project_root_for(p) or project_root
        return (p, find_opt_py(root, p))
    if target.is_file() and target.suffix == '.py':
        return [_pair(target)]
    if target.is_dir():
        return [_pair(p) for p in sorted(target.rglob('*.py')) if not p.name.startswith('_')]
    return []

def run_opt_bench(target: Path | str, project_root: Path | str, *, rounds: int=3, calls: int=100) -> list[FileResult]:
    """
    Executa benchmark para todos os .py em ``target``.
    Retorna lista de FileResult prontos para renderização.
    """
    target = Path(target).resolve()
    project_root = Path(project_root).resolve()
    pairs = _collect_targets(target, project_root)
    return [bench_file(py, opt, project_root=project_root, rounds=rounds, calls=calls) for py, opt in pairs]

def _ns(ns: float) -> str:
    if ns < 1000:
        return f'{ns:.0f} ns'
    if ns < 1000000:
        return f'{ns / 1000:.1f} µs'
    return f'{ns / 1000000:.2f} ms'

def _bar(ratio: float, width: int=20) -> str:
    """Barra comparativa: verde = ganho, vermelho = regressão."""
    gain = 1.0 - ratio
    fill = min(width, max(0, int(abs(gain) * width)))
    if gain > 0:
        return f'\x1b[32m{'█' * fill}\x1b[90m{'░' * (width - fill)}\x1b[0m'
    return f'\x1b[31m{'█' * fill}\x1b[90m{'░' * (width - fill)}\x1b[0m'

def _speedup_label(speedup: float) -> str:
    gain = (1.0 - speedup) * 100
    if gain > 0:
        return f'\x1b[32m▲ {gain:.1f}% mais rápido\x1b[0m'
    if gain < -0.5:
        return f'\x1b[31m▼ {abs(gain):.1f}% mais lento\x1b[0m'
    return '\x1b[90m≈ sem diferença significativa\x1b[0m'

def _render_file_entry(r: 'FileResult', *, verbose: bool, show_funcs: bool) -> list[float]:
    """Renderiza uma entrada de arquivo. Retorna lista de speedups coletados."""
    name = r.path.name
    print(f'\n  \x1b[1m{name}\x1b[0m')
    if r.error:
        print(f'    \x1b[31m✘ {r.error}\x1b[0m')
        return []
    pct_saved = r.size_saved_b / r.pure_size_b * 100 if r.pure_size_b else 0
    print(f'    Tamanho   : {r.pure_size_b:>6} B  →  {r.opt_size_b:>6} B   \x1b[32m(-{r.size_saved_b} B, -{pct_saved:.1f}%)\x1b[0m')
    print(f'    Carga     : {_ns(r.pure_load_ns):>10}  →  {_ns(r.opt_load_ns):>10}   {_bar(r.load_speedup)}  {_speedup_label(r.load_speedup)}')
    valid_funcs = [f for f in r.funcs if f.error is None]
    if not valid_funcs:
        print('    Callables : nenhum callable testável encontrado')
        return []
    print(f'    Callables : {r.callable_count:>3} medidos   ganho médio: {_speedup_label(r.avg_speedup)}')
    if show_funcs and verbose:
        for fn in sorted(valid_funcs, key=lambda x: x.speedup):
            print(f'      {fn.name:<30} puro={_ns(fn.pure_ns):>10}  opt={_ns(fn.opt_ns):>10}  {_bar(fn.speedup)}  {_speedup_label(fn.speedup)}')
    return [f.speedup for f in valid_funcs]

def _render_summary(results: list['FileResult'], all_speedups: list[float], total_pure: int, total_opt: int, total_saved: int, sep: str, head: str, rst: str) -> None:
    """Renderiza o bloco de resumo global."""
    print(f'\n{sep}')
    print(f'{head}  RESUMO{rst}')
    if total_pure:
        pct = total_saved / total_pure * 100 if total_pure else 0
        print(f'  Código     : {total_pure:>7} B  →  {total_opt:>7} B   \x1b[32m(-{total_saved} B, -{pct:.1f}%)\x1b[0m')
    if all_speedups:
        global_avg = sum(all_speedups) / len(all_speedups)
        global_best = min(all_speedups)
        print(f'  Speedup    : médio {_speedup_label(global_avg)}   melhor {_speedup_label(global_best)}')
    files_ok = sum((1 for r in results if not r.error))
    files_err = len(results) - files_ok
    print(f'  Arquivos   : {files_ok} ok  {files_err} erro(s)')
    if files_err:
        print(f"\n  \x1b[33m⚠  {files_err} arquivo(s) sem opt_py — execute 'doxoade vulcan opt <alvo>' para gerar.\x1b[0m")
    print(sep)

def render_results(results: list[FileResult], *, verbose: bool=False, show_funcs: bool=True, csv_out: Optional[Path]=None) -> None:
    """Renderiza resultados no terminal com estilo Vulcan."""
    SEP = '\x1b[36m' + '─' * 62 + '\x1b[0m'
    HEAD = '\x1b[1;36m'
    RST = '\x1b[0m'
    print(f'\n{HEAD}  ⬡ VULCAN OPT-BENCH — Python Puro vs Otimizado{RST}')
    print(SEP)
    all_speedups = []
    total_pure = total_opt = total_saved = 0
    for r in results:
        speedups = _render_file_entry(r, verbose=verbose, show_funcs=show_funcs)
        all_speedups.extend(speedups)
        if not r.error:
            total_pure += r.pure_size_b
            total_opt += r.opt_size_b
            total_saved += r.size_saved_b
    _render_summary(results, all_speedups, total_pure, total_opt, total_saved, SEP, HEAD, RST)
    if csv_out:
        _write_csv(results, csv_out)
        print(f'  CSV salvo em: {csv_out}')

def _write_csv(results: list[FileResult], path: Path) -> None:
    import csv
    rows = []
    for r in results:
        if r.error:
            rows.append({'file': r.path.name, 'func': '', 'pure_ns': '', 'opt_ns': '', 'speedup': '', 'gain_pct': '', 'error': r.error})
            continue
        for f in r.funcs:
            rows.append({'file': r.path.name, 'func': f.name, 'pure_ns': f'{f.pure_ns:.2f}', 'opt_ns': f'{f.opt_ns:.2f}', 'speedup': f'{f.speedup:.4f}', 'gain_pct': f'{f.gain_pct:.2f}', 'error': f.error or ''})
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

class SafeLocalNameMinifier(ast.NodeTransformer):
    """
    Minifica variáveis locais de forma segura.
    Ignora parâmetros, globals, nonlocals e funções que usam introspecção.
    """

    def __init__(self):
        super().__init__()
        self._name_generator = self._short_name_generator()
        self.scope_maps = []

    def _short_name_generator(self):
        """Gera nomes curtos: _a, _b ... _z, _aa, _ab..."""
        chars = string.ascii_lowercase
        yield from (f'_{c}' for c in chars)
        import itertools
        for length in itertools.count(2):
            for p in itertools.product(chars, repeat=length):
                yield f'_{''.join(p)}'

    class _VarCollector(ast.NodeVisitor):

        def __init__(self, excluded_names):
            self.local_vars = set()
            self.excluded = set(excluded_names)
            self.is_unsafe = False
            self.globals_nonlocals = set()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in {'locals', 'vars', 'eval', 'exec'}:
                self.is_unsafe = True
            self.generic_visit(node)

        def visit_Global(self, node):
            self.globals_nonlocals.update(node.names)

        def visit_Nonlocal(self, node):
            self.globals_nonlocals.update(node.names)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store) and node.id not in self.excluded:
                self.local_vars.add(node.id)

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    if name not in self.excluded:
                        self.local_vars.add(name)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    if name not in self.excluded:
                        self.local_vars.add(name)

        def visit_FunctionDef(self, node):
            pass

        def visit_ClassDef(self, node):
            pass

    def visit_Import(self, node):
        if self.scope_maps:
            current_map = self.scope_maps[-1]
            for alias in node.names:
                orig_name = alias.asname or alias.name
                if orig_name in current_map and '.' not in alias.name:
                    alias.asname = current_map[orig_name]
        return node

    def visit_ImportFrom(self, node):
        if self.scope_maps:
            current_map = self.scope_maps[-1]
            for alias in node.names:
                orig_name = alias.asname or alias.name
                if orig_name in current_map:
                    alias.asname = current_map[orig_name]
        return node

    def visit_FunctionDef(self, node):
        excluded = set()
        args = node.args
        for arg in args.args + getattr(args, 'kwonlyargs', []) + getattr(args, 'posonlyargs', []):
            excluded.add(arg.arg)
        if args.vararg:
            excluded.add(args.vararg.arg)
        if args.kwarg:
            excluded.add(args.kwarg.arg)
        collector = self._VarCollector(excluded)
        for stmt in node.body:
            collector.visit(stmt)
        rename_map = {}
        if not collector.is_unsafe:
            safe_targets = collector.local_vars - collector.globals_nonlocals
            for var in sorted(safe_targets):
                rename_map[var] = next(self._name_generator)
        self.scope_maps.append(rename_map)
        node.body = [self.visit(stmt) for stmt in node.body]
        self.scope_maps.pop()
        return node

    def visit_Name(self, node):
        if self.scope_maps:
            current_map = self.scope_maps[-1]
            if node.id in current_map:
                node.id = current_map[node.id]
        return node

def compact_lines_safely(code: str) -> str:
    """
    Agrupa instruções simples na mesma linha com ';' 
    aproveitando a previsibilidade absoluta do ast.unparse().
    """
    lines = code.split('\n')
    if not lines:
        return ''
    out_lines = []
    current_line = lines[0]

    def get_indent(s):
        return len(s) - len(s.lstrip())
    compound_keywords = ('if ', 'for ', 'while ', 'def ', 'class ', 'try:', 'with ', 'elif ', 'else:', 'except', 'finally:', '@', 'async ', 'match ', 'case ')
    in_multiline = False
    for i in range(1, len(lines)):
        nxt = lines[i]
        if not nxt.strip():
            continue
        if nxt.count('"""') % 2 != 0 or nxt.count("'''") % 2 != 0:
            in_multiline = not in_multiline
        curr_indent = get_indent(current_line)
        nxt_indent = get_indent(nxt)
        is_compound_curr = current_line.lstrip().startswith(compound_keywords)
        is_compound_nxt = nxt.lstrip().startswith(compound_keywords)
        ends_with_colon = current_line.rstrip().endswith(':')
        if curr_indent == nxt_indent and curr_indent > 0 and (not in_multiline) and (not ends_with_colon) and (not is_compound_curr) and (not is_compound_nxt):
            current_line = current_line + '; ' + nxt.lstrip()
        else:
            out_lines.append(current_line)
            current_line = nxt
    out_lines.append(current_line)
    return '\n'.join(out_lines)