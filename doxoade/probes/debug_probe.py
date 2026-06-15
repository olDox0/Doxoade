# -*- coding: utf-8 -*-
# doxoade/doxoade/probes/debug_probe.py
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

_MARKER_DEBUG = '---DOXOADE-DEBUG-DATA---'

# --- AUXILIARES TÁTICOS ---

def _resolve_package(abs_path: str):
    parts = []
    current = os.path.dirname(abs_path)
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current: break
        current = parent
    project_root = current
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    package_name = '.'.join(parts) if parts else None
    return (package_name, project_root)

def safe_serialize(obj, depth=0):
    if depth > 1: return str(type(obj).__name__)
    if isinstance(obj, (str, int, float, bool, type(None))): return str(obj)
    if isinstance(obj, (list, tuple)): return f"[{len(obj)} items]"
    if isinstance(obj, dict): return f"{{ {len(obj)} keys }}"
    return str(type(obj).__name__)

def _capture_locals(f_locals):
    return {k: safe_serialize(v) for k, v in f_locals.items() if not k.startswith('__')}

def _emit_data(marker, data_dict):
    """Emissão Industrial com Marcadores Unificados."""
    payload = json.dumps(data_dict, ensure_ascii=False)
    sys.stdout.write(f"\n{marker}\n{payload}\n")
    sys.stdout.flush()

# --- MOTORES DE EXTRAÇÃO ---

def _extract_function_stats(profiler, target_file, project_root):
    stream = io.StringIO()
    ps = pstats.Stats(profiler, stream=stream)
    stats_dict = ps.stats
    results = []
    norm_target = os.path.normcase(os.path.abspath(target_file))
    norm_root = os.path.normcase(os.path.abspath(project_root))
    
    for (fname, lineno, func_name), (prim_calls, total_calls, tt, ct, _) in stats_dict.items():
        curr_fname = os.path.normcase(os.path.abspath(fname)) if os.path.exists(fname) else fname
        if not curr_fname.startswith(norm_root) and curr_fname != norm_target:
            continue
        results.append({
            'name': func_name, 'file': fname, 'lineno': lineno, 
            'calls': total_calls, 'total_ms': round(tt * 1000, 4),
            'per_call_ms': round((tt / max(1, total_calls)) * 1000, 4),
            'cum_ms': round(ct * 1000, 4)
        })
    return sorted(results, key=lambda x: x['cum_ms'], reverse=True)[:15]

def _extract_memory_stats(snapshot, target_file, project_root):
    stats = snapshot.statistics('lineno')
    top = []
    norm_root = os.path.normcase(os.path.abspath(project_root))
    for stat in stats:
        frame = stat.traceback[0]
        fname = frame.filename
        if not os.path.normcase(os.path.abspath(fname)).startswith(norm_root):
            continue
        top.append({
            'file': fname, 'line': frame.lineno, 
            'size_kb': round(stat.size / 1024, 2), 
            'count': stat.count, 
            'content': linecache.getline(fname, frame.lineno).strip()
        })
    return top[:10]

# --- SENTINELA DE RASTRO ---

class _LineTimer:
    __slots__ = ('data', '_last', 'target_file', 'project_root', 'live_flow', 'last_vars', 'watch_vars', 'internal_mode')

    def __init__(self, target_file, project_root, live_flow=True, watch_vars=False, internal_mode=False):
        self.data = {}
        self._last = {}
        self.target_file = target_file
        self.project_root = os.path.abspath(project_root).replace('\\', '/').lower()
        self.live_flow = live_flow
        self.watch_vars = watch_vars
        self.internal_mode = internal_mode
        self.last_vars = {}

    def tracer(self, frame, event, arg):
        if event != 'line': return self.tracer
        raw_fname = frame.f_code.co_filename
        norm_fname = raw_fname.replace('\\', '/').lower()
        
        if 'site-packages' in norm_fname or '/lib/' in norm_fname or norm_fname.startswith('<'):
            return self.tracer
            
        # 2. Whitelist: Só permite rastro se estiver na pasta do projeto
        if not norm_fname.startswith(self.project_root):
            return self.tracer
        
        # Filtro de Domínio
        if not self.internal_mode:
            if raw_fname.startswith('<'): return self.tracer
            abs_fname = os.path.abspath(raw_fname).replace('\\', '/')
            if not abs_fname.lower().startswith(self.project_root): return self.tracer
            if any(x in abs_fname.lower() for x in ['debug_probe', 'flow_runner', 'site-packages']):
                return self.tracer
        
        lineno = frame.f_lineno
        content = linecache.getline(raw_fname, lineno).strip()
        if not content: return self.tracer

        # [PLATINUM] Vigilância de Variáveis à prova de falhas
        meta = ""
        if self.watch_vars:
            curr_vars = {k: v for k, v in frame.f_locals.items() if not k.startswith('__')}
            diffs = []
            for k, v in curr_vars.items():
                if self.last_vars.get(k) is not v:
                    try:
                        # [FIX] Tenta converter para string, se falhar, usa o tipo
                        val_repr = str(v)
                    except:
                        val_repr = f"<{type(v).__name__}>"
                    
                    diffs.append(f"\x1b[36m{k}\x1b[0m=\x1b[33m{val_repr[:20]}\x1b[0m")
                    self.last_vars[k] = v
            if diffs: meta = "  " + " ".join(diffs)

        if self.live_flow:
            f_short = os.path.basename(raw_fname)
            sys.stdout.write(f"\x1b[32m{f_short:<18}\x1b[0m │ \x1b[93m{lineno:<4}\x1b[0m │ {content}{meta}\n")
            sys.stdout.flush()

    def top_lines(self, limit=15):
        res = []
        for (f, l), s in self.data.items():
            ms = s['total_ns'] / 1_000_000
            res.append({'file': f, 'line': l, 'hits': s['hits'], 'total_ms': round(ms, 4), 
                        'content': linecache.getline(f, l).strip()})
        return sorted(res, key=lambda x: x['total_ms'], reverse=True)[:limit]

# --- ENTRY POINTS ---

def run_debug(script_path):
    abs_path = os.path.abspath(script_path)
    globs = {'__name__': '__main__', '__file__': abs_path}
    try:
        restricted_safe_exec(open(abs_path).read(), globs, allow_imports=True, filename=abs_path)
        _emit_data(_MARKER_DEBUG, {'status': 'success', 'variables': _capture_locals(globs)})
    except Exception as e:
        tb = sys.exc_info()[2]
        while tb and tb.tb_next: tb = tb.tb_next
        _emit_data(_MARKER_DEBUG, {'status': 'error', 'error': str(e), 'variables': _capture_locals(tb.tb_frame.f_locals), 'line': tb.tb_lineno})

def run_profile(script_path):
    abs_path = os.path.abspath(script_path)
    pkg_name, project_root = _resolve_package(abs_path)
    line_timer = _LineTimer(abs_path, project_root, live_flow=False)
    profiler = cProfile.Profile()
    tracemalloc.start()
    sys.settrace(line_timer.tracer)
    profiler.enable()
    t0 = time.perf_counter()
    try:
        restricted_safe_exec(open(abs_path).read(), {'__name__': '__main__', '__file__': abs_path}, allow_imports=True)
    except: pass
    profiler.disable()
    sys.settrace(None)
    _, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    _emit_data('---DOXOADE-PROFILE-DATA---', {
        'status': 'success',
        'profile': {
            'total_ms': round((time.perf_counter() - t0) * 1000, 2),
            'lines': line_timer.top_lines(),
            'functions': _extract_function_stats(profiler, abs_path, project_root),
            'memory': {'peak_mb': round(peak/1048576, 3), 'top_allocs': _extract_memory_stats(snapshot, abs_path, project_root)}
        }
    })

def run_memory(script_path):
    from doxoade.commands.debug_systems.debug_memory import get_memory_composition, get_allocation_tracebacks
    abs_path = os.path.abspath(script_path)
    pkg_name, project_root = _resolve_package(abs_path)
    tracemalloc.start(10)
    try:
        restricted_safe_exec(open(abs_path).read(), {'__name__': '__main__', '__file__': abs_path}, allow_imports=True)
    except: pass
    snapshot = tracemalloc.take_snapshot()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    _emit_data('---DOXOADE-MEMORY-DATA---', {
        'status': 'success',
        'memory': {
            'peak_mb': round(peak/1048576, 3), 
            'composition': get_memory_composition(), 
            'tracebacks': get_allocation_tracebacks(snapshot)
        }
    })

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(1)
    script_to_run = os.path.abspath(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'debug'
    sys.argv = [script_to_run] + sys.argv[3:]
    if mode == 'profile': run_profile(script_to_run)
    elif mode == 'memory': run_memory(script_to_run)
    else: run_debug(script_to_run)