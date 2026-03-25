# -*- coding: utf-8 -*-
# doxoade/probes/debug_probe.py
"""
Debug Probe v2.5 - Aegis Forensic Engine (Noise Gate Ativo).
Modo autópsia + modo perfil profundo com isolamento cirúrgico de projeto.
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


# ─── BOOTSTRAP ───────────────────────────────────────────────────────────────

def _resolve_package(abs_path: str):
    parts   =[]
    current = os.path.dirname(abs_path)

    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    project_root = current
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    package_name = '.'.join(parts) if parts else None
    return package_name, project_root


# ─── SERIALIZAÇÃO ────────────────────────────────────────────────────────────

def safe_serialize(obj, depth=0):
    if depth > 2: return "..."
    if isinstance(obj, (str, int, float, bool, type(None))): return obj
    if isinstance(obj, (list, tuple)): return [safe_serialize(x, depth + 1) for x in obj[:5]]
    if isinstance(obj, dict):          return {str(k): safe_serialize(v, depth + 1) for k, v in list(obj.items())[:5]}
    return str(type(obj).__name__)


def _capture_locals(globs: dict) -> dict:
    captured = {}
    for k, v in globs.items():
        if not k.startswith('__') and not isinstance(v, types.ModuleType):
            captured[k] = safe_serialize(v)
    return captured


# ─── LINE TIMER (sys.settrace) ────────────────────────────────────────────────

class _LineTimer:
    __slots__ = ('data', '_last', 'target_file', 'project_root')

    def __init__(self, target_file: str, project_root: str):
        self.data: dict = {}
        self._last: dict = {}
        self.target_file = os.path.normcase(os.path.abspath(target_file))
        self.project_root = os.path.normcase(os.path.abspath(project_root))

    def tracer(self, frame, event, arg):
        raw_fname = frame.f_code.co_filename
        
        # Traduz compilações em memória (exec) para o arquivo alvo
        if raw_fname in ('<sandbox>', '<string>'):
            raw_fname = self.target_file
        elif raw_fname == '~' or raw_fname.startswith('<frozen'):
            return self.tracer

        fname = os.path.normcase(os.path.abspath(raw_fname))
        
        # --- NOISE GATE ---
        is_target = (fname == self.target_file)
        if not is_target:
            # Rejeita arquivos fora da raiz do projeto (ex: stdlib queue.py, ast.py)
            if not fname.startswith(self.project_root):
                return self.tracer
            # Rejeita componentes internos do motor
            skip = ('security_utils', 'debug_probe', 'doxoade', 'site-packages', 'lib\\python', 'lib/python')
            if any(s in fname for s in skip):
                return self.tracer

        lineno   = frame.f_lineno
        now_ns   = time.perf_counter_ns()
        frame_id = id(frame)

        if event == 'call':
            self._last[frame_id] = (fname, lineno, now_ns)
            return self.tracer

        if event == 'line':
            self._commit(frame_id, now_ns)
            self._last[frame_id] = (fname, lineno, now_ns)
            return self.tracer

        if event in ('return', 'exception'):
            self._commit(frame_id, now_ns)
            self._last.pop(frame_id, None)
            return self.tracer

        return self.tracer

    def _commit(self, frame_id: int, now_ns: int):
        if frame_id not in self._last:
            return
        prev_file, prev_line, prev_ts = self._last[frame_id]
        key   = (prev_file, prev_line)
        entry = self.data.setdefault(key, {'hits': 0, 'total_ns': 0})
        entry['hits']     += 1
        entry['total_ns'] += now_ns - prev_ts

    def top_lines(self, limit: int = 20) -> list:
        results =[]
        for (fname, lineno), stat in self.data.items():
            content = linecache.getline(fname, lineno).strip()
            results.append({
                'file':       fname,
                'line':       lineno,
                'hits':       stat['hits'],
                'total_ms':   round(stat['total_ns'] / 1_000_000, 4),
                'per_hit_ms': round(stat['total_ns'] / max(1, stat['hits']) / 1_000_000, 4),
                'content':    content,
            })
        results.sort(key=lambda x: x['total_ms'], reverse=True)
        return results[:limit]


# ─── FUNÇÃO STATS (cProfile) ─────────────────────────────────────────────────

def _extract_function_stats(profiler: cProfile.Profile, target_file: str, project_root: str, limit: int = 15) -> list:
    stream = io.StringIO()
    ps     = pstats.Stats(profiler, stream=stream)
    ps.sort_stats('cumulative')

    stats_dict  = ps.stats
    norm_target = os.path.normcase(os.path.abspath(target_file))
    norm_root   = os.path.normcase(os.path.abspath(project_root))
    
    skip = ('site-packages', 'dist-packages', 'lib\\python', 'lib/python',
            '{built-in', '{method', 'security_utils', 'debug_probe', 'doxoade')

    results =[]
    for (fname, lineno, func_name), (prim_calls, total_calls, tt, ct, _callers) in stats_dict.items():
        if fname in ('<sandbox>', '<string>'):
            fname = target_file

        if fname == '~' or fname.startswith('<frozen'):
            continue

        norm_fname = os.path.normcase(os.path.abspath(fname))
        is_target  = (norm_fname == norm_target)
        
        is_noise = False
        if not is_target:
            if not norm_fname.startswith(norm_root):
                is_noise = True
            if any(s in fname or s in norm_fname for s in skip):
                is_noise = True

        if is_noise:
            continue

        results.append({
            'name':          func_name,
            'file':          fname,
            'lineno':        lineno,
            'calls':         total_calls,
            'prim_calls':    prim_calls,
            'total_ms':      round(tt  * 1000, 4),
            'per_call_ms':   round(tt  / max(1, total_calls) * 1000, 4),
            'cum_ms':        round(ct  * 1000, 4),
        })

    results.sort(key=lambda x: x['cum_ms'], reverse=True)
    return results[:limit]


# ─── MEMORY STATS (tracemalloc) ──────────────────────────────────────────────

def _extract_memory_stats(snapshot, target_file: str, project_root: str, limit: int = 10) -> dict:
    norm_target = os.path.normcase(os.path.abspath(target_file))
    norm_root   = os.path.normcase(os.path.abspath(project_root))
    skip        = ('site-packages', 'dist-packages', 'lib\\python', 'lib/python',
                   'security_utils', 'debug_probe', 'doxoade')

    stats = snapshot.statistics('lineno')
    top   =[]
    for stat in stats:
        raw_fname = str(stat.traceback[0].filename)
        if raw_fname in ('<sandbox>', '<string>'):
            raw_fname = target_file
            
        if raw_fname == '~' or raw_fname.startswith('<frozen'):
            continue

        fname = os.path.normcase(os.path.abspath(raw_fname))
        is_target = (fname == norm_target)
        
        is_noise = False
        if not is_target:
            if not fname.startswith(norm_root):
                is_noise = True
            if any(s in raw_fname or s in fname for s in skip):
                is_noise = True

        if is_noise:
            continue

        lineno  = stat.traceback[0].lineno
        content = linecache.getline(raw_fname, lineno).strip()
        top.append({
            'file':     raw_fname,
            'line':     lineno,
            'size_kb':  round(stat.size / 1024, 2),
            'count':    stat.count,
            'content':  content,
        })
        if len(top) >= limit:
            break

    return {
        'peak_mb': 0.0,
        'top_allocs': top,
    }


# ─── MODO AUTÓPSIA ───────────────────────────────────────────────────────────

def run_debug(script_path: str):
    abs_path   = os.path.abspath(script_path)
    pkg_name, _ = _resolve_package(abs_path)
    debug_data = {'status': 'unknown', 'variables': {}, 'error': None}
    globs      = {
        '__name__':    '__main__',
        '__file__':    abs_path,
        '__package__': pkg_name,
    }
    try:
        sys.stdout.write("\n--- BOOTING AEGIS SANDBOX ---\n")
        sys.stdout.flush()
        from doxoade.tools.security_utils import restricted_safe_exec
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        restricted_safe_exec(content, globs, allow_imports=True)

        debug_data['status']    = 'success'
        debug_data['variables'] = _capture_locals(globs)
        for k, v in globs.items():
            if not k.startswith('__') and not isinstance(v, types.ModuleType):
                try:
                    debug_data['variables'][k] = safe_serialize(v)
                except Exception as exc:
                    import logging as _log
                    _log.error(f"[INFRA] run_debug: {exc}")

    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n")
        exc_trace(exc_tb)
        debug_data['status']    = 'error'
        debug_data['error']     = str(e)
        _, _, tb                = sys.exc_info()
        while tb.tb_next: tb   = tb.tb_next
        frame                   = tb.tb_frame
        debug_data['traceback'] = traceback.format_exc()
        debug_data['line']      = tb.tb_lineno
        for k, v in frame.f_locals.items():
            if not k.startswith('__'):
                debug_data['variables'][k] = safe_serialize(v)

    print("\n---DOXOADE-DEBUG-DATA---")
    print(json.dumps(debug_data, ensure_ascii=False))


# ─── MODO PERFIL PROFUNDO ─────────────────────────────────────────────────────

def run_profile(script_path: str):
    abs_path = os.path.abspath(script_path)
    pkg_name, project_root = _resolve_package(abs_path)
    
    profile_data = {
        'status':    'unknown',
        'variables': {},
        'error':     None,
        'profile':   {},
    }
    globs = {
        '__name__':    '__main__',
        '__file__':    abs_path,
        '__package__': pkg_name,
    }

    line_timer = _LineTimer(abs_path, project_root)
    profiler   = cProfile.Profile()

    try:
        sys.stdout.write("\n--- BOOTING AEGIS PROFILE ENGINE ---\n")
        sys.stdout.flush()

        from doxoade.tools.security_utils import restricted_safe_exec
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tracemalloc.start()
        sys.settrace(line_timer.tracer)
        profiler.enable()

        t0 = time.perf_counter()
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
        finally:
            profiler.disable()
            sys.settrace(None)
            _, peak = tracemalloc.get_traced_memory()
            mem_snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()
        elapsed_ms = (time.perf_counter() - t0) * 1000

        profile_data['status']    = 'success'
        profile_data['variables'] = _capture_locals(globs)

        mem_stats              = _extract_memory_stats(mem_snapshot, abs_path, project_root)
        mem_stats['peak_mb']   = round(peak / 1024 / 1024, 4)

        profile_data['profile'] = {
            'total_ms':  round(elapsed_ms, 2),
            'lines':     line_timer.top_lines(),
            'functions': _extract_function_stats(profiler, abs_path, project_root),
            'memory':    mem_stats,
        }

    except Exception as e:
        profiler.disable()
        sys.settrace(None)
        if tracemalloc.is_tracing():
            tracemalloc.stop()

        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n")
        exc_trace(exc_tb)

        profile_data['status']    = 'error'
        profile_data['error']     = str(e)
        _, _, tb                  = sys.exc_info()
        if tb:
            while tb.tb_next: tb  = tb.tb_next
            frame                 = tb.tb_frame
            profile_data['traceback'] = traceback.format_exc()
            profile_data['line']      = tb.tb_lineno
            for k, v in frame.f_locals.items():
                if not k.startswith('__'):
                    profile_data['variables'][k] = safe_serialize(v)

        profile_data['profile'] = {
            'total_ms':  0,
            'lines':     line_timer.top_lines(),
            'functions':[],
            'memory':    {'peak_mb': 0.0, 'top_allocs':[]},
        }

    print("\n---DOXOADE-PROFILE-DATA---")
    print(json.dumps(profile_data, ensure_ascii=False))


# ─── MODO AUTÓPSIA DE MEMÓRIA ──────────────────────────────────────────────────

def run_memory(script_path: str):
    """Executa o script isolando a autópsia profunda de memória."""
    # ATENÇÃO: Importação corrigida com caminho absoluto!
    from doxoade.commands.debug_systems.debug_memory import get_memory_composition, get_allocation_tracebacks
    import tracemalloc
    import json
    import traceback
    
    abs_path = os.path.abspath(script_path)
    pkg_name, project_root = _resolve_package(abs_path)  # <--- INJETA A RESOLUÇÃO DA ÁRVORE
    mem_data = {'status': 'unknown', 'error': None, 'memory': {}}
    globs = {'__name__': '__main__', '__file__': abs_path, '__package__': pkg_name} # <--- INJETA O PACOTE

    try:
        sys.stdout.write("\n--- BOOTING AEGIS MEMORY FORENSICS ---\n")
        sys.stdout.flush()

        from doxoade.tools.security_utils import restricted_safe_exec
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Inicia o rastreador de memória com capacidade para salvar a árvore de chamadas (frames = 10)
        tracemalloc.start(10)
        
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
            mem_data['status'] = 'success'
        except BaseException as be:
            if not isinstance(be, (KeyboardInterrupt, SystemExit)):
                mem_data['status'] = 'error'
                mem_data['error']  = str(be)
            else:
                mem_data['status'] = 'success'

    except BaseException as e:
        mem_data['status'] = 'error'
        mem_data['error']  = str(e)

    finally:
        import signal
        try: signal.signal(signal.SIGINT, signal.SIG_IGN)
        except Exception: pass

        try:
            snapshot = tracemalloc.take_snapshot()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            mem_data['memory'] = {
                'peak_mb': round(peak / 1024 / 1024, 4) if peak else 0.0,
                'composition': get_memory_composition(limit=15),
                'tracebacks': get_allocation_tracebacks(snapshot, limit=5)
            }
        except BaseException as fe:
            mem_data['error'] = f"Erro na formatação da memória: {fe}"

        print("\n---DOXOADE-MEMORY-DATA---")
        print(json.dumps(mem_data, ensure_ascii=False))
        sys.stdout.flush()


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    script_to_run = sys.argv[1]
    mode          = sys.argv[2] if len(sys.argv) > 2 else 'debug'

    # Injeta os argumentos corretamente no sys.argv global
    sys.argv = [script_to_run] + sys.argv[3:]

    if mode == 'profile':
        run_profile(script_to_run)
    elif mode == 'memory':          # <-- O SEGREDO ESTÁ AQUI
        run_memory(script_to_run)   # Chama a nova função de memória
    else:
        run_debug(script_to_run)    # Cai aqui se não for profile nem memory