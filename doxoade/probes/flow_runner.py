# doxoade/doxoade/probes/flow_runner.py
import sys, os, time, argparse, warnings, linecache
from doxoade.tools.doxcolors import Fore
from doxoade.tools.aegis.aegis_utils import restricted_safe_exec
from .debug_probe import _LineTimer
warnings.filterwarnings('ignore', category=RuntimeWarning)
C_RESET = '\x1b[0m'
C_CYAN, C_YELLOW, C_WHITE = ('\x1b[96m', '\x1b[93m', '\x1b[97m')
C_BORDER, C_MAGENTA, C_GREEN = ('\x1b[90m', '\x1b[95m', '\x1b[92m')
C_BOLD, C_DIM, C_RED, SEP = ('\x1b[1m', '\x1b[2m', '\x1b[91m', '\x1b[90m│\x1b[0m')
_STATE = {'last_time': time.perf_counter(), 'last_locals': {}, 'project_root': '', 'target_file': None, 'indent_level': 0, 'flow_base': False, 'flow_val': False, 'flow_import': False, 'flow_func': False, 'history': [], 'active_pattern': None, 'pattern_idx': 0, 'hidden_count': 0, 'no_compress': False}

def _flush_iron_gate():
    if _STATE['hidden_count'] > 0:
        p_len = len(_STATE['active_pattern'])
        reps = _STATE['hidden_count'] // p_len
        p_desc = ' ➔ '.join([str(id[1]) for id in _STATE['active_pattern']])
        print(f'{C_BORDER}│{C_RESET} {C_DIM}         [ 🔄 LOOP: {p_desc} repetido {reps + 1:03}x omitido ]{C_RESET}')
    _STATE['active_pattern'] = None
    _STATE['hidden_count'] = 0
    _STATE['pattern_idx'] = 0
    _STATE['history'] = []

def _handle_compression(current_id):
    if _STATE['active_pattern']:
        expected = _STATE['active_pattern'][_STATE['pattern_idx']]
        if current_id == expected:
            _STATE['hidden_count'] += 1
            _STATE['pattern_idx'] = (_STATE['pattern_idx'] + 1) % len(_STATE['active_pattern'])
            return True
        else:
            _flush_iron_gate()
    _STATE['history'].append(current_id)
    h = _STATE['history']
    if len(h) > 20:
        h.pop(0)
    for size in range(1, 7):
        if len(h) >= size * 2:
            pattern = h[-size:]
            previous = h[-size * 2:-size]
            if pattern == previous:
                _STATE['active_pattern'] = pattern
                _STATE['pattern_idx'] = 1 % size
                _STATE['hidden_count'] = 1
                return True
    return False

def static_trace_calls(frame, event, arg):
    """Tratador de eventos de rastro (Refatorado v81.8)."""
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    if _should_skip_trace(filename):
        return None
    if event == 'line' and (not _STATE['no_compress']) and _handle_compression((filename, lineno)):
        return static_trace_calls
    _render_trace_event(frame, event)
    return static_trace_calls

def _should_skip_trace(filename: str) -> bool:
    """Verifica se o rastro deve ser ignorado (Noise Gate)."""
    if filename.startswith('<') or any((x in filename for x in ['importlib', 'Lib', 'flow_runner'])):
        return True
    abs_filename = os.path.abspath(filename).replace('\\', '/')
    if _STATE['target_file'] and abs_filename != _STATE['target_file']:
        return True
    return not abs_filename.startswith(_STATE['project_root'])

def _render_trace_event(frame, event):
    """Especialista de Renderização UI (PASC 8.5)."""
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    line = linecache.getline(filename, lineno).strip()
    if _STATE['flow_func']:
        if event == 'call':
            _flush_iron_gate()
            func = frame.f_code.co_name
            print(f'{C_BORDER}│{C_RESET} {'  ' * _STATE['indent_level']}{C_MAGENTA}➔ CALL: {C_BOLD}{func}{C_RESET}')
            _STATE['indent_level'] += 1
            return
        elif event == 'return':
            _flush_iron_gate()
            _STATE['indent_level'] = max(0, _STATE['indent_level'] - 1)
            print(f'{C_BORDER}│{C_RESET} {'  ' * _STATE['indent_level']}{C_GREEN}⇠ RETN: {C_BOLD}{frame.f_code.co_name}{C_RESET}')
            return
    if event != 'line':
        return
    if _STATE['flow_import'] and ('import ' in line or 'from ' in line):
        print(f'{C_BORDER}│{C_RESET} {' ' * 7}ms {SEP} {C_YELLOW}[ MÓDULO ] {C_WHITE}{os.path.basename(filename)}:{lineno}{SEP} {line}')
    if _STATE['flow_base'] or _STATE['flow_val']:
        now = time.perf_counter()
        ms = (now - _STATE['last_time']) * 1000
        _STATE['last_time'] = now
        diffs = []
        if _STATE['flow_val']:
            for k, v in list(frame.f_locals.items()):
                if k.startswith('__') or k in ['self', 'cls']:
                    continue
                if _STATE['last_locals'].get(k) != v:
                    diffs.append(f'{C_CYAN}{k}{C_DIM}={C_YELLOW}{_safe_to_string(v)}{C_RESET}')
            _STATE['last_locals'] = frame.f_locals.copy()
        loc = f'{'  ' * _STATE['indent_level']}{os.path.basename(filename)}:{lineno}'.ljust(25)
        print(f'{C_BORDER}│{C_RESET} {ms:7.1f}ms {SEP} {C_WHITE}{loc}{SEP} {line[:50].ljust(50)} {SEP} {', '.join(diffs)}')

def run_flow(path, **kwargs):
    """Execução de rastro para ARQUIVOS externos (.py)."""
    abs_path = os.path.abspath(path)
    project_root = os.path.dirname(abs_path)
    
    # Prepara o ambiente de execução (Simula o script original)
    with open(abs_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Instancia o timer em modo normal (Noise Gate Ativo)
    timer = _LineTimer(target_file=abs_path, project_root=project_root, internal_mode=False)
    
    # Injeta a sonda
    sys.settrace(timer.tracer)
    from doxoade.tools.aegis.aegis_core import nexus_exec
    try:
        # Executa o código no escopo global
        globs = {'__file__': abs_path, '__name__': '__main__'}
        nexus_exec(code, globs)
    finally:
        sys.settrace(None)
        _render_flow_results(timer)

def _bootstrap_package(script_path):
    abs_path = os.path.abspath(script_path)
    current = os.path.dirname(abs_path)
    parts = []
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    if current not in sys.path:
        sys.path.insert(0, current)
    return ('.'.join(parts), current)

def _safe_to_string(val):
    try:
        if 'importlib' in getattr(type(val), '__module__', ''):
            return '<Internal>'
        s = str(val).replace('\n', ' ')
        return s[:25] + '...' if len(s) > 28 else s
    except Exception as e:
        print(f'\x1b[0;33m _safe_to_string - Exception: {e}')
        return '<Error>'
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('script')
    p.add_argument('--base', action='store_true')
    p.add_argument('--val', action='store_true')
    p.add_argument('--import', dest='imp', action='store_true')
    p.add_argument('--func', action='store_true')
    p.add_argument('--target', default=None)
    p.add_argument('--no-compress', dest='no_compress', action='store_true', help='Desativa compressão de loops (Iron Gate).')
    args, remaining = p.parse_known_args()
    sys.argv = [os.path.abspath(args.script)] + remaining
    run_flow(args.script, args.base, args.val, args.imp, args.func, args.target, no_compress=args.no_compress)

def run_flow_internal(callback):
    import sys, os
    from .debug_probe import _LineTimer
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    timer = _LineTimer(
        target_file="internal_cmd", 
        project_root=project_root, 
        internal_mode=True, 
        live_flow=True # Habilita o Matrix Style
    )
    
    # PONTE PARA A THREAD DA ANIMAÇÃO
    sys._doxoade_current_tracer = timer.tracer
    
    sys.settrace(timer.tracer)
    try:
        callback()
    finally:
        sys.settrace(None)
        if hasattr(sys, '_doxoade_current_tracer'):
            del sys._doxoade_current_tracer

def _render_flow_results(timer):
    from doxoade.tools.doxcolors import Fore, Style
    # Agora o método top_lines existe!
    stats = timer.top_lines(limit=15)
    
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🌊 NEXUS FLOW: Tabela de Performance (Top 15){Style.RESET_ALL}")
    print(f"{Fore.WHITE}{'MS TOTAL':>10} | {'LOCALIZAÇÃO':<30} | {'CONTEÚDO'}{Style.RESET_ALL}")
    
    for s in stats:
        file_short = os.path.basename(s['file'])
        t_color = Fore.RED if s['total_ms'] > 50 else Fore.CYAN
        print(f"{t_color}{s['total_ms']:>8.2f}ms {Fore.WHITE}│ {Fore.YELLOW}{file_short}:{s['line']:<25} {Fore.WHITE}│ {s['content'][:60]}{Style.RESET_ALL}")