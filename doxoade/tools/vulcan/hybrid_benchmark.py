# doxoade/doxoade/tools/vulcan/hybrid_benchmark.py
"""
Vulcan HybridBenchmark — Medição de ganho real Python vs Cython.
=================================================================

Mede o speedup real de cada função compilada pelo HybridForge,
comparando execução Python pura vs binário Cython.

Uso via CLI:
    doxoade vulcan benchmark doxoade/tools/
    doxoade vulcan benchmark doxoade/tools/analysis.py --runs 500
    doxoade vulcan benchmark doxoade/tools/ --json > bench_results.json

Saída:
    Tabela com: arquivo | função | Pythodoxoade vulcan ignite doxoade/commands/intelligence_systems/intelligence_engine.py
doxoade vulcan benchmark doxoade/commands/intelligence_systems/n ms | Cython ms | speedup | status

Compliance:
    OSL-4  : única responsabilidade — só mede, não compila
    OSL-5  : falhas de import/execução são capturadas e reportadas como N/A
    PASC-6 : função sem binário é relatada como "não compilada"
"""
from __future__ import annotations
import ast
import hashlib
import importlib.util
import json
import re
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

@dataclass
class FunctionBenchResult:
    """Resultado do benchmark de uma função individual."""
    file_name: str
    func_name: str
    py_ms: Optional[float] = None
    cy_ms: Optional[float] = None
    speedup: Optional[float] = None
    error: Optional[str] = None
    status: str = 'OK'

    @property
    def speedup_label(self) -> str:
        if self.speedup is None:
            return 'N/A'
        return f'{self.speedup:.2f}×'

    @property
    def status_color(self) -> str:
        if self.status != 'OK':
            return '\x1b[33m'
        if self.speedup and self.speedup >= 5.0:
            return '\x1b[32m'
        if self.speedup and self.speedup >= 1.5:
            return '\x1b[36m'
        return '\x1b[37m'

@dataclass
class FileBenchResult:
    """Resultado do benchmark de um arquivo."""
    file_path: str
    functions: list[FunctionBenchResult] = field(default_factory=list)

    @property
    def best_speedup(self) -> Optional[float]:
        valids = [f.speedup for f in self.functions if f.speedup is not None]
        return max(valids) if valids else None

    @property
    def avg_speedup(self) -> Optional[float]:
        valids = [f.speedup for f in self.functions if f.speedup is not None]
        return sum(valids) / len(valids) if valids else None

class HybridBenchmark:
    """
    Mede speedup real de funções compiladas pelo HybridForge.

    Estratégia:
      1. Localiza o binário Cython (.pyd/.so) para o arquivo
      2. Carrega o módulo Python original e o binário
      3. Gera fixtures de entrada adequadas via FunctionProber
      4. Executa N vezes cada versão e mede tempo médio
      5. Calcula speedup e reporta
    """

    def __init__(self, project_root: str | Path, runs: int=200):
        self.root = Path(project_root).resolve()
        self.bin_dir = self.root / '.doxoade' / 'vulcan' / 'bin'
        self.runs = runs
        self._ext = '.pyd' if os.name == 'nt' else '.so'
        self._prober = FunctionProber()

    def run(self, target: str | Path, output_json: bool=False, min_speedup: float=1.1) -> list[FileBenchResult]:
        """
        Benchmarka todas as funções compiladas no target (arquivo ou dir).
        Retorna lista de FileBenchResult.
        min_speedup: speedup mínimo para não ser marcado como REGRESSÃO.
        """
        target_path = Path(target).resolve()
        py_files = self._collect_py_files(target_path)
        all_results: list[FileBenchResult] = []
        for py_file in py_files:
            binary = self._find_binary(py_file)
            if not binary:
                continue
            try:
                file_result = self._benchmark_file(py_file, binary)
            except BaseException as exc:
                file_result = FileBenchResult(file_path=str(py_file))
                file_result.functions.append(FunctionBenchResult(file_name=py_file.name, func_name='<crash>', status='ERROR', error=f'benchmark abortado: {type(exc).__name__}: {exc}'))
            if file_result.functions:
                all_results.append(file_result)
        if output_json:
            self._print_json(all_results)
        else:
            self._print_table(all_results, min_speedup=min_speedup)
        return all_results

    def _benchmark_file(self, py_file: Path, binary: Path) -> FileBenchResult:
        result = FileBenchResult(file_path=str(py_file))
        py_module = self._load_py_module(py_file)
        if py_module is None:
            result.functions.append(FunctionBenchResult(file_name=py_file.name, func_name='<module>', status='ERROR', error='falha ao carregar módulo Python'))
            return result
        cy_module, load_err = self._load_binary(binary)
        if cy_module is None:
            result.functions.append(FunctionBenchResult(file_name=py_file.name, func_name='<binary>', status='ERROR', error=f'falha ao carregar {binary.name}: {load_err[:200]}'))
            return result
        for attr_name in dir(py_module):
            if not hasattr(cy_module, attr_name):
                try:
                    setattr(cy_module, attr_name, getattr(py_module, attr_name))
                except (AttributeError, TypeError):
                    pass
        _common_injections = {'Path': __import__('pathlib').Path, 'os': __import__('os'), 're': __import__('re'), 'ast': __import__('ast'), 'json': __import__('json'), 'sys': __import__('sys')}
        for _k, _v in _common_injections.items():
            if not hasattr(cy_module, _k):
                try:
                    setattr(cy_module, _k, _v)
                except (AttributeError, TypeError):
                    pass
        cy_funcs = {name.replace('_vulcan_optimized', ''): getattr(cy_module, name) for name in dir(cy_module) if name.endswith('_vulcan_optimized') and callable(getattr(cy_module, name))}
        for orig_name, cy_func in cy_funcs.items():
            py_func = getattr(py_module, orig_name, None)
            if py_func is None or not callable(py_func):
                result.functions.append(FunctionBenchResult(file_name=py_file.name, func_name=orig_name, status='NO_BINARY', error='função Python não encontrada no módulo original'))
                continue
            bench = self._bench_pair(py_file.name, orig_name, py_func, cy_func)
            result.functions.append(bench)
        return result

    def _bench_pair(self, file_name: str, func_name: str, py_func: Callable, cy_func: Callable) -> FunctionBenchResult:
        """Mede py_func vs cy_func com fixtures geradas automaticamente."""
        result = FunctionBenchResult(file_name=file_name, func_name=func_name)
        try:
            fixture = self._prober.generate_fixture(py_func)
        except Exception as e:
            result.status = 'WARMUP_FAIL'
            result.error = f'fixture: {e}'
            return result
        import io as _io, sys as _sys

        class _SuppressIO:
            """Context manager que silencia stdout e stderr."""

            def __enter__(self):
                self._old_stdout = _sys.stdout
                self._old_stderr = _sys.stderr
                _sys.stdout = _io.StringIO()
                _sys.stderr = _io.StringIO()
                return self

            def __exit__(self, *_):
                _sys.stdout = self._old_stdout
                _sys.stderr = self._old_stderr
        try:
            with _SuppressIO():
                for _ in range(3):
                    py_func(*fixture)
                    try:
                        cy_func(*fixture)
                    except TypeError as te:
                        te_msg = str(te)
                        if 'argument' in te_msg and 'given' in te_msg and (len(fixture) > 1):
                            cy_func(*fixture[:1])
                        else:
                            raise
        except SystemExit:
            result.status = 'WARMUP_FAIL'
            result.error = 'função encerra processo (click/sys.exit)'
            return result
        except Exception as e:
            result.status = 'WARMUP_FAIL'
            result.error = f'warmup: {e}'
            return result
        cy_fixture = fixture
        try:
            with _SuppressIO():
                cy_func(*fixture)
        except TypeError as te:
            if 'argument' in str(te) and 'given' in str(te) and (len(fixture) > 1):
                cy_fixture = fixture[:len(fixture) - 1]
        try:
            with _SuppressIO():
                t0 = time.perf_counter()
                for _ in range(self.runs):
                    py_func(*fixture)
                result.py_ms = (time.perf_counter() - t0) * 1000 / self.runs
        except SystemExit:
            result.status = 'ERROR'
            result.error = 'python exec: sys.exit durante medição'
            return result
        except Exception as e:
            result.status = 'ERROR'
            result.error = f'python exec: {e}'
            return result
        try:
            with _SuppressIO():
                t0 = time.perf_counter()
                for _ in range(self.runs):
                    cy_func(*cy_fixture)
                result.cy_ms = (time.perf_counter() - t0) * 1000 / self.runs
        except SystemExit:
            result.status = 'ERROR'
            result.error = 'cython exec: sys.exit durante medição'
            return result
        if result.cy_ms and result.cy_ms > 0:
            result.speedup = result.py_ms / result.cy_ms
        else:
            result.speedup = None
            result.status = 'ERROR'
            result.error = 'cy_ms = 0'
        return result

    def _find_binary(self, py_file: Path) -> Optional[Path]:
        """
        Localiza o binário compilado para um arquivo .py.

        Suporta nomes com tag CPython (ex: v_filesystem_ad611b.cp311-win_amd64.pyd)
        e nomes simples (v_filesystem_ad611b.pyd / .so).
        Usa glob para encontrar qualquer variante — solução para Windows.
        """
        abs_path = py_file.resolve()
        path_hash = hashlib.sha256(str(abs_path).encode()).hexdigest()[:6]
        stem = abs_path.stem
        prefix = f'v_{stem}_{path_hash}'
        if not self.bin_dir.exists():
            return None
        for ext in ('.pyd', '.so'):
            candidates = list(self.bin_dir.glob(f'{prefix}*{ext}'))
            if candidates:
                return max(candidates, key=lambda p: p.stat().st_mtime)
        for ext in ('.pyd', '.so'):
            candidates = [p for p in self.bin_dir.glob(f'v_{stem}_*{ext}') if re.match(f'v_{re.escape(stem)}_[0-9a-f]{{6}}', p.stem.split('.')[0])]
            if candidates:
                return max(candidates, key=lambda p: p.stat().st_mtime)
        return None

    @staticmethod
    def _load_py_module(py_file: Path):
        """
        Carrega módulo Python via importlib.

        Estratégia em 3 tentativas, da mais robusta para a mais simples:

        1. Importação como membro do pacote real (doxoade.commands.check_systems.check_engine)
           → Resolve todos os imports relativos e absolutos corretamente.
           → Só funciona se o módulo já estiver instalado/no sys.path como pacote.

        2. Carregamento via spec com __package__ configurado e projeto no sys.path
           → Para módulos com imports relativos não ainda instalados.

        3. Carregamento direto (sem contexto de pacote)
           → Para módulos standalone sem imports relativos.

        Retorna o módulo ou None em falha.
        """
        import sys as _sys
        project_markers = {'pyproject.toml', 'setup.py', 'setup.cfg'}
        root = py_file.parent
        while root != root.parent:
            if any(((root / m).exists() for m in project_markers)):
                if str(root) not in _sys.path:
                    _sys.path.insert(0, str(root))
                break
            root = root.parent

        def _derive_module_name(p):
            """Sobe no filesystem procurando doxoade/ e monta o dotted name."""
            parts = []
            cur = p
            while True:
                parts.insert(0, cur.stem if cur == p else cur.name)
                parent = cur.parent
                if parent == cur:
                    return None
                if not (parent / '__init__.py').exists():
                    if str(parent) in _sys.path or any((Path(sp) == parent for sp in _sys.path)):
                        return '.'.join(parts)
                    return None
                cur = parent
        mod_name = _derive_module_name(py_file)
        if mod_name:
            try:
                import importlib as _il
                return _il.import_module(mod_name)
            except Exception:
                import traceback
                traceback.print_exc()
                pass
        package_dir = py_file.parent
        package_name = f'_bench_pkg_{py_file.parent.name}'
        bench_name = f'{package_name}.{py_file.stem}'
        added_paths = []
        created_init = False
        try:

            def _find_pkg_root(p):
                markers = {'pyproject.toml', 'setup.py', 'setup.cfg'}
                for parent in [p, *p.parents]:
                    if any(((parent / m).exists() for m in markers)):
                        return parent
                    if (parent / '__init__.py').exists() and parent.parent != parent:
                        continue
                    if not (parent / '__init__.py').exists():
                        return parent
                return p.parent
            pkg_root = _find_pkg_root(py_file)
            for inject_dir in [str(pkg_root), str(package_dir.parent), str(package_dir)]:
                if inject_dir not in _sys.path:
                    _sys.path.insert(0, inject_dir)
                    added_paths.append(inject_dir)
            init_file = package_dir / '__init__.py'
            if not init_file.exists():
                try:
                    init_file.write_text('', encoding='utf-8')
                    created_init = True
                except Exception:
                    pass
            spec = importlib.util.spec_from_file_location(bench_name, str(py_file), submodule_search_locations=[str(package_dir)])
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                module.__package__ = package_name
                _sys.modules.setdefault(package_name, module)
                _sys.modules[bench_name] = module
                try:
                    spec.loader.exec_module(module)
                    return module
                except Exception:
                    pass
                finally:
                    _sys.modules.pop(bench_name, None)
                    _sys.modules.pop(package_name, None)
            spec2 = importlib.util.spec_from_file_location(f'_bench_py_{py_file.stem}', str(py_file))
            if spec2 and spec2.loader:
                m2 = importlib.util.module_from_spec(spec2)
                spec2.loader.exec_module(m2)
                return m2
        except Exception:
            return None
        finally:
            for p in added_paths:
                try:
                    _sys.path.remove(p)
                except ValueError:
                    pass
            if created_init:
                try:
                    init_file.unlink(missing_ok=True)
                except Exception:
                    pass
        return None

    @staticmethod
    def _load_binary(binary: Path):
        """
        Carrega binário Cython via importlib.
        Retorna (module, None) ou (None, error_str).

        CRÍTICO: o module_name passado ao spec DEVE ser o nome real do módulo
        (sem prefixo nem sufixo extra), pois o Python usa esse nome para
        chamar PyInit_<module_name> dentro do .pyd.

        v_filesystem_ad611b.cp312-win_amd64.pyd → PyInit_v_filesystem_ad611b
        """
        import sys as _sys
        raw_stem = binary.stem
        module_name = raw_stem.split('.')[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(binary))
            if not spec or not spec.loader:
                return (None, 'spec_from_file_location retornou None')
            module = importlib.util.module_from_spec(spec)
            _sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return (module, None)
        except (ImportError, ModuleNotFoundError) as e:
            err_msg = str(e)
            if 'relative import' in err_msg or 'attempted relative' in err_msg:
                return (None, 'binário desatualizado — imports relativos embutidos. Recompile: --hybrid --force')
            return (None, f'{type(e).__name__}: {e}')
        except TypeError as e:
            err_msg = str(e)
            if 'is a field but has no type annotation' in err_msg:
                return (None, 'binário desatualizado — dataclass field sem anotação (forge antigo). Recompile: --hybrid --force')
            return (None, f'TypeError: {e}')
        except Exception as e:
            return (None, f'{type(e).__name__}: {e}')
        finally:
            _sys.modules.pop(module_name, None)

    @staticmethod
    def _collect_py_files(target: Path) -> list[Path]:
        _IGNORE_DIRS = frozenset({'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade'})
        _IGNORE_STEMS = frozenset({'__init__', '__main__', 'setup', 'hybrid_forge', 'hybrid_optimizer', 'hybrid_benchmark', 'forge', 'compiler', 'autopilot', 'bridge', 'advisor'})
        if target.is_file():
            return [target] if target.stem not in _IGNORE_STEMS else []
        files = []
        for root, dirs, filenames in os.walk(str(target)):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for f in filenames:
                p = Path(root) / f
                if p.suffix == '.py' and p.stem not in _IGNORE_STEMS:
                    files.append(p)
        return files

    @staticmethod
    def _print_table(results: list[FileBenchResult], min_speedup: float=1.1):
        if not results:
            print('\n  [VULCAN] Nenhuma funcao benchmarkada.')
            print("  Dica: execute '--hybrid' antes do benchmark.")
            import inspect
            bin_dir_path = None
            try:
                frame = inspect.currentframe()
                outer = frame.f_back.f_locals if frame and frame.f_back else {}
                self_obj = outer.get('self')
                if self_obj and hasattr(self_obj, 'bin_dir'):
                    bin_dir_path = self_obj.bin_dir
            except Exception:
                pass
            print('\n\x1b[33m  Nenhuma função benchmarkada. Execute --hybrid primeiro.\x1b[0m')
            if bin_dir_path:
                if bin_dir_path.exists():
                    binaries = list(bin_dir_path.glob('*.pyd')) + list(bin_dir_path.glob('*.so'))
                    if binaries:
                        print(f'\x1b[36m  Binários encontrados em {bin_dir_path}:\x1b[0m')
                        for b in sorted(binaries)[:10]:
                            print(f'    {b.name}')
                        print('\x1b[33m  (hash do path não coincide — tente passar o diretório raiz)\x1b[0m')
                    else:
                        print(f'\x1b[33m  bin_dir vazio: {bin_dir_path}\x1b[0m')
                else:
                    print(f'\x1b[33m  bin_dir não existe: {bin_dir_path}\x1b[0m')
            return
        RESET = '\x1b[0m'
        BOLD = '\x1b[1m'
        CYAN = '\x1b[36m'
        DIM = '\x1b[2m'
        print(f"\n{CYAN}{'─' * 70}{RESET}")
        print(f'{BOLD}  VULCAN HYBRID BENCHMARK{RESET}')
        print(f"{CYAN}{'─' * 70}{RESET}")
        print(f"  {'Arquivo':<20} {'Função':<35} {'Py ms':>7} {'Cy ms':>7} {'Speedup':>8}  Status")
        print(f"{DIM}  {'─' * 20} {'─' * 35} {'─' * 7} {'─' * 7} {'─' * 8}  {'─' * 12}{RESET}")
        regressions = 0
        total_speedup = 0.0
        total_ok = 0
        for file_res in results:
            fname = Path(file_res.file_path).name[:20]
            for f in file_res.functions:
                col = f.status_color
                spd = f.speedup_label
                py_s = f'{f.py_ms:.3f}' if f.py_ms is not None else 'N/A'
                cy_s = f'{f.cy_ms:.3f}' if f.cy_ms is not None else 'N/A'
                err = f' ({f.error[:120]})' if f.error else ''
                print(f'  {fname:<20} {f.func_name:<35} {py_s:>7} {cy_s:>7} {col}{spd:>8}{RESET}  {f.status}{DIM}{err}{RESET}')
                if f.speedup:
                    total_speedup += f.speedup
                    total_ok += 1
                    if f.speedup < min_speedup and f.status == 'OK':
                        print(f"  {DIM}{'':20} {'':35} {'':7} {'':7} \x1b[33m{'':>8}  ⚠ REGRESSÃO: speedup {f.speedup:.2f}× < {min_speedup}× — candidato a exclusão{RESET}")
        print(f"{CYAN}{'─' * 70}{RESET}")
        if total_ok > 0:
            avg = total_speedup / total_ok
            bar = _speedup_bar(avg)
            regressions = sum((1 for fr in results for f in fr.functions if f.speedup and f.speedup < min_speedup and (f.status == 'OK')))
            print(f'  {BOLD}Speedup médio : {avg:.2f}×  {bar}{RESET}')
            print(f'  Funções OK    : {total_ok}')
            if regressions:
                print(f'  \x1b[33m⚠ Regressões  : {regressions} função(ões) abaixo de {min_speedup}×{RESET}')
                print(f'  \x1b[33m  Use --save para persistir e excluir do próximo --hybrid{RESET}')
        stale_bins = [f'{Path(fr.file_path).name}' for fr in results for f in fr.functions if f.status == 'ERROR' and f.error and ('desatualizado' in (f.error or '') or 'Recompile' in (f.error or ''))]
        if stale_bins:
            unique_stale = sorted(set(stale_bins))
            print(f'  \x1b[33m⚠ Binários desatualizados: {len(unique_stale)} arquivo(s){RESET}')
            for s in unique_stale[:5]:
                print(f'    \x1b[33m└─ {s}{RESET}')
            print(f'  \x1b[36m  → doxoade vulcan ignite <path> --hybrid --force{RESET}')
        print(f"{CYAN}{'─' * 70}{RESET}\n")

    @staticmethod
    def _print_json(results: list[FileBenchResult]):
        data = []
        for file_res in results:
            for f in file_res.functions:
                data.append({'file': file_res.file_path, 'func': f.func_name, 'py_ms': f.py_ms, 'cy_ms': f.cy_ms, 'speedup': f.speedup, 'status': f.status, 'error': f.error})
        print(json.dumps(data, indent=2, ensure_ascii=False))

class FunctionProber:
    """
    Gera argumentos de entrada para funções a partir da sua assinatura.

    Estratégia por nome de parâmetro:
      - file_path / path / src → string de caminho válido
      - findings / items / results → lista de dicts de exemplo
      - content / source / text → string Python de amostra
      - tree / node → ast.Module de amostra
      - func_node → ast.FunctionDef de amostra
      - lines → lista de strings
      - defaults numéricos e bool para o restante
    """
    _SAMPLE_CODE = "import os\nimport sys\ndef hello(name: str) -> str:\n    return f'hello {name}'\nclass Foo:\n    def __init__(self):\n        self.x = 0\n    def bar(self, n):\n        total = 0\n        for i in range(n):\n            total += i\n        return total\n"
    _SAMPLE_FINDINGS = [{'severity': 'WARNING', 'category': 'UNUSED', 'message': 'unused var x', 'file': 'test.py', 'line': 10, 'finding_hash': 'abc123'}, {'severity': 'ERROR', 'category': 'SYNTAX', 'message': 'invalid syntax', 'file': 'test.py', 'line': 20, 'finding_hash': 'def456'}]

    def generate_fixture(self, func: Callable) -> tuple:
        """
        Gera uma tupla de argumentos posicionais para a função.
        Filtra *args e **kwargs — não são posicionais fixos.
        """
        import inspect
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())
        except (ValueError, TypeError):
            return ()
        args = []
        for p in params:
            if p.name in ('self', 'cls'):
                continue
            if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            args.append(self._infer_arg(p.name, p.annotation, p.default))
        return tuple(args)

    def _infer_arg(self, name: str, annotation, default) -> Any:
        """Infere valor adequado pelo nome do parâmetro."""
        import inspect
        if default is not inspect.Parameter.empty:
            return default
        import inspect as _insp
        n = name.lower()

        def _ann_class_name(ann) -> str:
            if ann is _insp.Parameter.empty or ann is None:
                return ''
            if isinstance(ann, type):
                return ann.__name__
            s = str(ann).strip().strip('\'"<>')
            return s.split('.')[-1].strip('\'"<> ')
        ann_name = _ann_class_name(annotation)
        if n == 'state' or ann_name in ('CheckState',):
            try:
                state_obj = type('CheckState', (), {'root': '.', 'target_path': '.', 'target_files': [], 'findings': list(self._SAMPLE_FINDINGS), 'alb_files': [], 'summary': {'errors': 1, 'warnings': 1, 'critical': 0}, 'is_full_power': False, 'clones_active': False, 'register_finding': lambda self_inner, f: self_inner.findings.append(f), 'sync_summary': lambda self_inner: None})()
                state_obj.findings = list(self._SAMPLE_FINDINGS)
                return state_obj
            except Exception:
                pass
        if n in ('tree', 'node', 'module'):
            return ast.parse(self._SAMPLE_CODE)
        if 'func_node' in n or n == 'func':
            tree = ast.parse(self._SAMPLE_CODE)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node
            return ast.parse('def f(): pass').body[0]
        if n in ('content', 'source', 'code', 'text', 'pyx_code', 'pyx_source'):
            return self._SAMPLE_CODE
        if n in ('file_path', 'path', 'src', 'filename', 'file'):
            return __file__
        if n in ('findings', 'items', 'results', 'all_findings'):
            return list(self._SAMPLE_FINDINGS)
        if n in ('lines', 'content_lines', 'file_lines'):
            return self._SAMPLE_CODE.splitlines()
        if n in ('templates',):
            return []
        if n in ('line_number', 'lineno', 'line', 'line_num'):
            return 5
        if n in ('context_lines', 'context'):
            return 2
        if n in ('complexity', 'hits', 'count', 'n', 'size'):
            return 10
        if n in ('is_test_mode', 'allow_imports', 'force', 'show_code'):
            return False
        if n in ('project_root', 'project_path', 'root_path'):
            return str(Path(__file__).resolve().parents[3])
        if n in ('taint_map', 'tainted', 'imports'):
            return {'x': 'input', 'y': 'sys.argv'}
        if 'config' in n or n.endswith('_cfg') or n.endswith('_conf'):
            return {'ignore_patterns': [], 'extensions': ['.py'], 'exclude_dirs': [], 'max_file_size': 1048576, 'project_root': str(Path(__file__).resolve().parents[0])}
        if n in ('ignore_patterns', 'patterns'):
            return []
        if n in ('extensions', 'exts'):
            return ['.py']
        if n in ('exclude_dirs', 'skip_dirs'):
            return []
        if n.endswith(('_name', '_key', '_label', '_tag', '_id', '_slug')):
            return 'sample'
        if annotation == str:
            return ''
        if annotation == int:
            return 0
        if annotation == bool:
            return False
        if annotation == list:
            return []
        if annotation == dict:
            return {}
        return None

def _speedup_bar(speedup: float) -> str:
    """Barra visual de speedup."""
    filled = min(int(speedup * 2), 20)
    bar = '█' * filled + '░' * (20 - filled)
    if speedup >= 10:
        color = '\x1b[32m'
    elif speedup >= 3:
        color = '\x1b[36m'
    else:
        color = '\x1b[37m'
    return f'{color}[{bar}]\x1b[0m'

def run_benchmark(project_root: str | Path, target: str | Path, runs: int=200, output_json: bool=False, min_speedup: float=1.1) -> list[FileBenchResult]:
    """Entry-point chamado pelo vulcan_cmd benchmark."""
    bench = HybridBenchmark(project_root=project_root, runs=runs)
    return bench.run(target=target, output_json=output_json, min_speedup=min_speedup)
