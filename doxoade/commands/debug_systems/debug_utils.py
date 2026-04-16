# doxoade/doxoade/commands/debug_systems/debug_utils.py
"""
Debug Utils v2.1 - PASC-1.2 & MPoT-17.
Environment anchoring and probe orchestration.

Dois construtores de comando separados para evitar contaminação de argv:
  build_probe_command → debug_probe.py  (entende: script mode [args])
  build_flow_command  → flow_runner.py  (entende: --target --base --val etc.)
"""
import sys
import os
import json
import time
import types
import cProfile
import pstats
import traceback
import tracemalloc
import linecache
import io
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
from doxoade.tools.filesystem import _find_project_root

def _bootstrap(script_path):
    """Detecta a raiz do projeto e o nome correto do pacote (Aegis Ready)."""
    abs_path = os.path.abspath(script_path)
    parts = abs_path.replace('\\', '/').split('/')
    try:
        idx = parts.index('doxoade')
        project_root = '/'.join(parts[:idx])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        package_parts = []
        current = os.path.dirname(abs_path)
        while os.path.exists(os.path.join(current, '__init__.py')):
            package_parts.insert(0, os.path.basename(current))
            current = os.path.dirname(current)
            if os.path.basename(current) == 'doxoade':
                package_parts.insert(0, 'doxoade')
                break
        return '.'.join(package_parts) if package_parts else None
    except ValueError as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n')
        exc_trace(exc_tb)
        return None

def _try_activate_lazy(script_path: str) -> None:
    """
    Ativa VulcanLazyFinder no subprocess do debug antes de restricted_safe_exec.

    Busca lazy_policy.json + lazy_loader.py em .doxoade/vulcan/ do projeto alvo.
    Silencioso em caso de ausência ou erro — nunca bloqueia o debug.
    """
    import importlib.util as _ilu
    from pathlib import Path as _P
    root = _find_project_root(os.path.abspath(script_path))
    if not root:
        return
    lazy_policy = _P(root) / '.doxoade' / 'vulcan' / 'lazy_policy.json'
    lazy_src = _P(root) / '.doxoade' / 'vulcan' / 'lazy_loader.py'
    if not (lazy_policy.exists() and lazy_src.exists()):
        return
    try:
        spec = _ilu.spec_from_file_location('_doxoade_vulcan_lazy', str(lazy_src))
        if not (spec and spec.loader):
            return
        ll = _ilu.module_from_spec(spec)
        sys.modules['_doxoade_vulcan_lazy'] = ll
        spec.loader.exec_module(ll)
        ll.install(ll.load_policy(lazy_policy))
    except Exception:
        pass

def safe_serialize(obj, depth=0):
    if depth > 2:
        return '...'
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(x, depth + 1) for x in obj[:5]]
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v, depth + 1) for k, v in list(obj.items())[:5]}
    return str(type(obj).__name__)

def _capture_locals(globs: dict) -> dict:
    captured = {}
    for k, v in globs.items():
        if not k.startswith('__') and (not isinstance(v, types.ModuleType)):
            captured[k] = safe_serialize(v)
    return captured

class _LineTimer:
    """
    Profiler de linha baseado em sys.settrace. Zero dependências externas.

    Para cada frame, registra o timestamp no evento 'call'/'line'.
    No próximo evento do mesmo frame, computa o delta e acumula em data[].

    data: {(norm_file, lineno): {'hits': int, 'total_ns': int}}
    """
    __slots__ = ('data', '_last', '_seen_calls')

    def __init__(self):
        self.data = {}
        self._last = {}
        self._seen_calls = set()

    def tracer(self, frame, event, arg):
        fname = os.path.normcase(os.path.abspath(frame.f_code.co_filename))
        lineno = frame.f_lineno
        now_ns = time.perf_counter_ns()
        frame_id = id(frame)
        if event == 'call':
            call_key = (fname, lineno)
            if call_key in self._seen_calls:
                return self.tracer
            self._seen_calls.add(call_key)
            self._last[frame_id] = (fname, lineno, now_ns)
            return self.tracer
        if event in ('return', 'exception'):
            self._commit(frame_id, now_ns)
            self._last.pop(frame_id, None)
            call_key = (fname, lineno)
            self._seen_calls.discard(call_key)
            return self.tracer
        if event == 'line':
            self._commit(frame_id, now_ns)
            self._last[frame_id] = (fname, lineno, now_ns)
            return self.tracer
        return self.tracer

    def top_lines(self, target_file: str, limit: int=20) -> list:
        """
        Retorna as linhas mais lentas do arquivo alvo + de qualquer arquivo
        do projeto (excluindo stdlib e site-packages), ordenadas por total_ns.
        """
        norm_target = os.path.normcase(os.path.abspath(target_file))
        skip = ('site-packages', 'dist-packages', 'lib\\python', 'lib/python')
        results = []
        for (fname, lineno), stat in self.data.items():
            is_target = fname == norm_target
            is_stdlib = any((s in fname for s in skip))
            if not is_target and is_stdlib:
                continue
            content = linecache.getline(fname, lineno).strip()
            results.append({'file': fname, 'line': lineno, 'hits': stat['hits'], 'total_ms': round(stat['total_ns'] / 1000000, 4), 'per_hit_ms': round(stat['total_ns'] / max(1, stat['hits']) / 1000000, 4), 'content': content})
        results.sort(key=lambda x: x['total_ms'], reverse=True)
        return results[:limit]

def _extract_function_stats(profiler: cProfile.Profile, target_file: str, limit: int=15) -> list:
    """
    Extrai estatísticas de função do cProfile como lista de dicts,
    priorizando funções do arquivo alvo e do projeto.
    """
    stream = io.StringIO()
    ps = pstats.Stats(profiler, stream=stream)
    ps.sort_stats('cumulative')
    stats_dict = ps.stats
    norm_target = os.path.normcase(os.path.abspath(target_file))
    skip = ('site-packages', 'dist-packages', 'lib\\python', 'lib/python', '<frozen', '<string>', '{built-in', '{method')
    results = []
    for (fname, lineno, func_name), (prim_calls, total_calls, tt, ct, _callers) in stats_dict.items():
        norm_fname = os.path.normcase(os.path.abspath(fname)) if fname not in ('<string>', '<frozen importlib._bootstrap>') else fname
        is_target = norm_fname == norm_target
        is_noise = any((s in fname for s in skip)) and (not is_target)
        if is_noise:
            continue
        results.append({'name': func_name, 'file': fname, 'lineno': lineno, 'calls': total_calls, 'prim_calls': prim_calls, 'total_ms': round(tt * 1000, 4), 'per_call_ms': round(tt / max(1, total_calls) * 1000, 4), 'cum_ms': round(ct * 1000, 4)})
    results.sort(key=lambda x: x['cum_ms'], reverse=True)
    return results[:limit]

def _extract_memory_stats(snapshot, target_file: str, limit: int=10) -> dict:
    """
    Extrai pico de memória e top alocações do tracemalloc snapshot.
    """
    norm_target = os.path.normcase(os.path.abspath(target_file))
    skip = ('site-packages', 'dist-packages', 'lib\\python', 'lib/python', '<frozen', '<string>')
    stats = snapshot.statistics('lineno')
    top = []
    for stat in stats:
        fname = os.path.normcase(str(stat.traceback[0].filename))
        lineno = stat.traceback[0].lineno
        is_target = fname == norm_target
        is_noise = any((s in fname for s in skip)) and (not is_target)
        if is_noise:
            continue
        content = linecache.getline(str(stat.traceback[0].filename), lineno).strip()
        top.append({'file': str(stat.traceback[0].filename), 'line': lineno, 'size_kb': round(stat.size / 1024, 2), 'count': stat.count, 'content': content})
        if len(top) >= limit:
            break
    return {'peak_mb': 0.0, 'top_allocs': top}

def run_debug(script_path: str):
    abs_path = os.path.abspath(script_path)
    debug_data = {'status': 'unknown', 'variables': {}, 'error': None}
    globs = {'__name__': '__main__', '__file__': abs_path, '__package__': None}
    try:
        sys.stdout.write('\n--- BOOTING AEGIS SANDBOX ---\n')
        sys.stdout.flush()
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        _try_activate_lazy(abs_path)
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
        except (KeyboardInterrupt, SystemExit):
            pass
        debug_data['status'] = 'success'
        debug_data['variables'] = _capture_locals(globs)
        for k, v in globs.items():
            if not k.startswith('__') and (not isinstance(v, types.ModuleType)):
                try:
                    debug_data['variables'][k] = safe_serialize(v)
                except Exception as exc:
                    import logging as _log
                    _log.error(f'[INFRA] run_debug: {exc}')
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n')
        exc_trace(exc_tb)
        debug_data['status'] = 'error'
        debug_data['error'] = str(e)
        _, _, tb = sys.exc_info()
        while tb.tb_next:
            tb = tb.tb_next
        frame = tb.tb_frame
        debug_data['traceback'] = traceback.format_exc()
        debug_data['line'] = tb.tb_lineno
        for k, v in frame.f_locals.items():
            if not k.startswith('__'):
                debug_data['variables'][k] = safe_serialize(v)
    print('\n---DOXOADE-DEBUG-DATA---')
    print(json.dumps(debug_data, ensure_ascii=False))

def get_debug_env(script_path: str) -> dict:
    target_abs = os.path.abspath(script_path)
    project_root = _find_project_root(target_abs)
    doxo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([doxo_dir, os.path.dirname(project_root) if project_root else os.path.dirname(target_abs), env.get('PYTHONPATH', '')])
    env['PYTHONIOENCODING'] = 'utf-8'
    return env

def build_probe_command(python_exe: str, probe_file: str, script: str, mode: str='debug', args: str=None) -> list:
    """
    Protocolo:  python debug_probe.py <script_abs> <mode> [args...]
    mode: 'debug' | 'profile'
    """
    cmd = [python_exe, os.path.abspath(probe_file), os.path.abspath(script), mode]
    if args:
        cmd.extend(args.split())
    return cmd

def run_profile(script_path: str):
    """
    Executa o script com três camadas de instrumentação simultâneas:

      1. _LineTimer (sys.settrace) — tempo por linha, hits, ms/hit
      2. cProfile               — calls, total_time, cumulative por função
      3. tracemalloc             — alocações de memória por linha

    Emite ---DOXOADE-PROFILE-DATA--- com o JSON completo ao fim.
    """
    abs_path = os.path.abspath(script_path)
    profile_data = {'status': 'unknown', 'variables': {}, 'error': None, 'profile': {}}
    globs = {'__name__': '__main__', '__file__': abs_path, '__package__': None}
    line_timer = _LineTimer()
    profiler = cProfile.Profile()
    t0 = time.perf_counter()
    elapsed_ms = 0.0
    mem_snapshot = None
    peak = 0
    try:
        sys.stdout.write('\n--- BOOTING AEGIS PROFILE ENGINE ---\n')
        sys.stdout.flush()
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        _try_activate_lazy(abs_path)
        tracemalloc.start()
        sys.settrace(line_timer.tracer)
        profiler.enable()
        t0 = time.perf_counter()
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
            profile_data['status'] = 'success'
        except BaseException as be:
            if not isinstance(be, (KeyboardInterrupt, SystemExit)):
                profile_data['status'] = 'error'
                profile_data['error'] = str(be)
                profile_data['traceback'] = traceback.format_exc()
            else:
                profile_data['status'] = 'success'
    except BaseException as e:
        profile_data['status'] = 'error'
        profile_data['error'] = str(e)
        profile_data['traceback'] = traceback.format_exc()
    finally:
        import signal
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass
        try:
            profiler.disable()
            sys.settrace(None)
            if tracemalloc.is_tracing():
                _, peak = tracemalloc.get_traced_memory()
                mem_snapshot = tracemalloc.take_snapshot()
                tracemalloc.stop()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            profile_data['variables'] = _capture_locals(globs)
            mem_stats = _extract_memory_stats(mem_snapshot, abs_path) if mem_snapshot else {'peak_mb': 0.0, 'top_allocs': []}
            mem_stats['peak_mb'] = round(peak / 1024 / 1024, 4) if peak else 0.0
            profile_data['profile'] = {'total_ms': round(elapsed_ms, 2), 'lines': line_timer.top_lines(abs_path), 'functions': _extract_function_stats(profiler, abs_path), 'memory': mem_stats}
        except BaseException as fe:
            profile_data['error'] = f'Erro na formatação do perfil: {fe}'
        print('\n---DOXOADE-PROFILE-DATA---')
        print(json.dumps(profile_data, ensure_ascii=False))
        sys.stdout.flush()

def build_flow_command(python_exe: str, runner_file: str, script: str, watch: str=None, bottleneck: bool=False, no_compress: bool=False, args: str=None) -> list:
    """
    Protocolo nativo do flow_runner (argparse):
        flow_runner.py [--base] [--val] [--no-compress] [--target TARGET] script

    --watch   → --target + --val
    --bottleneck → --base
    --no-compress → --no-compress  (desativa Iron Gate no flow_runner)
    """
    cmd = [python_exe, os.path.abspath(runner_file)]
    if watch:
        cmd.extend(['--target', watch])
        cmd.append('--val')
    elif bottleneck:
        cmd.append('--base')
    if no_compress:
        cmd.append('--no-compress')
    cmd.append(os.path.abspath(script))
    if args:
        cmd.extend(args.split())
    return cmd

def run_memory(script_path: str):
    """Executa o script isolando a autópsia profunda de memória."""
    from .debug_memory import get_memory_composition, get_allocation_tracebacks
    import tracemalloc
    import json
    import traceback
    abs_path = os.path.abspath(script_path)
    mem_data = {'status': 'unknown', 'error': None, 'memory': {}}
    globs = {'__name__': '__main__', '__file__': abs_path, '__package__': None}
    try:
        sys.stdout.write('\n--- BOOTING AEGIS MEMORY FORENSICS ---\n')
        sys.stdout.flush()
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        _try_activate_lazy(abs_path)
        tracemalloc.start(10)
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
            mem_data['status'] = 'success'
        except BaseException as be:
            if not isinstance(be, (KeyboardInterrupt, SystemExit)):
                mem_data['status'] = 'error'
                mem_data['error'] = str(be)
            else:
                mem_data['status'] = 'success'
    except BaseException as e:
        mem_data['status'] = 'error'
        mem_data['error'] = str(e)
    finally:
        import signal
        try:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception:
            pass
        try:
            snapshot = tracemalloc.take_snapshot()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            mem_data['memory'] = {'peak_mb': round(peak / 1024 / 1024, 4) if peak else 0.0, 'composition': get_memory_composition(limit=15), 'tracebacks': get_allocation_tracebacks(snapshot, limit=5)}
        except BaseException as fe:
            mem_data['error'] = f'Erro na formatação da memória: {fe}'
        print('\n---DOXOADE-MEMORY-DATA---')
        print(json.dumps(mem_data, ensure_ascii=False))
        sys.stdout.flush()
if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
    script_to_run = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'debug'
    sys.argv = [script_to_run] + sys.argv[3:]
    if mode == 'profile':
        run_profile(script_to_run)
    elif mode == 'memory':
        run_memory(script_to_run)
    else:
        run_debug(script_to_run)
