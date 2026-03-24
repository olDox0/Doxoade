# -*- coding: utf-8 -*-
# doxoade/probes/flow_runner.py (v81.8 Gold Fix)
import sys, os, time, argparse, warnings, linecache
from doxoade.tools.doxcolors import Fore
warnings.filterwarnings("ignore", category=RuntimeWarning)
# CONSTANTES NEXUS GOLD
C_RESET = '\033[0m'
C_CYAN, C_YELLOW, C_WHITE = '\033[96m', '\033[93m', '\033[97m'
C_BORDER, C_MAGENTA, C_GREEN = '\033[90m', '\033[95m', '\033[92m'
C_BOLD, C_DIM, C_RED, SEP = '\033[1m', '\033[2m', '\033[91m', "\033[90m│\033[0m"
_STATE = {
    'last_time': time.perf_counter(),
    'last_locals': {},
    'project_root': '',
    'target_file': None,
    'indent_level': 0,
    'flow_base': False, 'flow_val': False, 'flow_import': False, 'flow_func': False,
    'history': [], 'active_pattern': None, 'pattern_idx': 0, 'hidden_count': 0,
    'no_compress': False,   # Iron Gate desativado quando True
}
# --- LÓGICA DE COMPRESSÃO (IRON GATE) ---
def _flush_iron_gate():
    if _STATE['hidden_count'] > 0:
        p_len = len(_STATE['active_pattern'])
        reps = _STATE['hidden_count'] // p_len
        p_desc = " ➔ ".join([str(id[1]) for id in _STATE['active_pattern']])
        print(f"{C_BORDER}│{C_RESET} {C_DIM}         [ 🔄 LOOP: {p_desc} repetido {reps+1:03}x omitido ]{C_RESET}")
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
        else: _flush_iron_gate()
    _STATE['history'].append(current_id)
    h = _STATE['history']
    if len(h) > 20: h.pop(0)
    for size in range(1, 7):
        if len(h) >= size * 2:
            pattern = h[-size:]  # OBJ-REDUCE: slice→memoryview
            previous = h[-size*2:-size]  # OBJ-REDUCE: slice→memoryview
            if pattern == previous:
                _STATE['active_pattern'] = pattern
                _STATE['pattern_idx'] = 1 % size
                _STATE['hidden_count'] = 1
                return True
    return False
# --- MOTOR DE RASTRO (REATOR PRINCIPAL) ---
def static_trace_calls(frame, event, arg):
    """Tratador de eventos de rastro (Refatorado v81.8)."""
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    # 1. Noise Gate (Filtro de Sistema e Sniper)
    if _should_skip_trace(filename):
        return None
    # 2. Iron Gate (Compressão de Loops) — desativado com --no-compress
    if event == 'line' and not _STATE['no_compress'] and _handle_compression((filename, lineno)):
        return static_trace_calls
    # 3. UI Dispatcher (A função que estava faltando!)
    _render_trace_event(frame, event)
    
    return static_trace_calls
def _should_skip_trace(filename: str) -> bool:
    """Verifica se o rastro deve ser ignorado (Noise Gate)."""
    if filename.startswith('<') or any(x in filename for x in ["importlib", "Lib", "flow_runner"]):
        return True
    
    abs_filename = os.path.abspath(filename).replace('\\', '/')
    
    # Sniper Lens: Se o Chief focou em um arquivo, ignora o resto
    if _STATE['target_file'] and abs_filename != _STATE['target_file']:
        return True
        
    return not abs_filename.startswith(_STATE['project_root'])
def _render_trace_event(frame, event):
    """Especialista de Renderização UI (PASC 8.5)."""
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    line = linecache.getline(filename, lineno).strip()
    # --- EVENTOS DE FUNÇÃO (CALL/RETURN) ---
    if _STATE['flow_func']:
        if event == 'call':
            _flush_iron_gate()
            func = frame.f_code.co_name
            print(f"{C_BORDER}│{C_RESET} {'  '*_STATE['indent_level']}{C_MAGENTA}➔ CALL: {C_BOLD}{func}{C_RESET}")
            _STATE['indent_level'] += 1
            return
        elif event == 'return':
            _flush_iron_gate()
            _STATE['indent_level'] = max(0, _STATE['indent_level'] - 1)
            print(f"{C_BORDER}│{C_RESET} {'  '*_STATE['indent_level']}{C_GREEN}⇠ RETN: {C_BOLD}{frame.f_code.co_name}{C_RESET}")
            return
    if event != 'line': return
    # --- EVENTOS DE MÓDULO (IMPORT) ---
    if _STATE['flow_import'] and ("import " in line or "from " in line):
        print(f"{C_BORDER}│{C_RESET} {' '*7}ms {SEP} {C_YELLOW}[ MÓDULO ] {C_WHITE}{os.path.basename(filename)}:{lineno}{SEP} {line}")
    # --- EVENTOS DE LINHA E VALORES ---
    if _STATE['flow_base'] or _STATE['flow_val']:
        now = time.perf_counter()
        ms = (now - _STATE['last_time']) * 1000
        _STATE['last_time'] = now
        diffs = []
        if _STATE['flow_val']:
            for k, v in list(frame.f_locals.items()):
                if k.startswith('__') or k in ['self', 'cls']: continue
                if _STATE['last_locals'].get(k) != v:
                    diffs.append(f"{C_CYAN}{k}{C_DIM}={C_YELLOW}{_safe_to_string(v)}{C_RESET}")
            _STATE['last_locals'] = frame.f_locals.copy()
        loc = f"{'  '*_STATE['indent_level']}{os.path.basename(filename)}:{lineno}".ljust(25)
        print(f"{C_BORDER}│{C_RESET} {ms:7.1f}ms {SEP} {C_WHITE}{loc}{SEP} {line[:50].ljust(50)} {SEP} {', '.join(diffs)}")
# --- BOOTSTRAP E AUXILIARES ---
def run_flow(script_path, base, val, imp, func, target_file=None, no_compress=False):
    abs_p = os.path.abspath(script_path)
    pkg_name, project_root = _bootstrap_package(abs_p)
    
    _STATE.update({
        'project_root': project_root.replace('\\', '/'),
        'target_file': os.path.abspath(target_file).replace('\\', '/') if target_file else None,
        'flow_base': base, 'flow_val': val, 'flow_import': imp, 'flow_func': func,
        'last_time': time.perf_counter(),
        'no_compress': no_compress,
    })
    
    globs = {
        '__name__': '__main__', '__file__': abs_p, 
        '__package__': pkg_name, '__path__': [os.path.dirname(abs_p)] if pkg_name else None
    }
    print(f"{C_BORDER}{'─'*115}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD} DOXOADE NEXUS FLOW v4.1 (Stability Fix){C_RESET} | {os.path.basename(abs_p)}")
    print(f"{C_BORDER}┌{'─'*11}┬{'─'*25}┬{'─'*50}┬{'─'*25}┐{C_RESET}")
    try:
        with open(abs_p, 'r', encoding='utf-8') as f:
            content = f.read()
        
        from doxoade.tools.security_utils import restricted_safe_exec
        sys.settrace(static_trace_calls)
        try: 
            restricted_safe_exec(content, globs, allow_imports=True, filename=abs_p)
            _flush_iron_gate()
        finally: 
            sys.settrace(None)
    except Exception as e:
        exc_type, exc_val, _ = sys.exc_info()
        print(f"\n{Fore.RED}[CRASH FLOW] {exc_type.__name__ if exc_type else 'Error'}: {exc_val}{C_RESET}")
        raise e
def _bootstrap_package(script_path):
    abs_path = os.path.abspath(script_path)
    current = os.path.dirname(abs_path)
    parts = []
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current: break
        current = parent
    if current not in sys.path: sys.path.insert(0, current)
    return ".".join(parts), current
def _safe_to_string(val):
    try:
        if 'importlib' in getattr(type(val), '__module__', ''): return "<Internal>"
        s = str(val).replace('\n', ' ')
        return s[:25] + "..." if len(s) > 28 else s
    except Exception as e:
        print(f"\033[0;33m _safe_to_string - Exception: {e}")
        return "<Error>"
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("script")
    p.add_argument("--base", action="store_true")
    p.add_argument("--val", action="store_true")
    p.add_argument("--import", dest="imp", action="store_true")
    p.add_argument("--func", action="store_true")
    p.add_argument("--target", default=None)
    p.add_argument("--no-compress", dest="no_compress", action="store_true",
                   help="Desativa compressão de loops (Iron Gate).")
    
    args, remaining = p.parse_known_args()
    # Injeta os argumentos restantes no sys.argv para que o script alvo consiga lê-los
    sys.argv =[os.path.abspath(args.script)] + remaining
    
    run_flow(args.script, args.base, args.val, args.imp, args.func,
             args.target, no_compress=args.no_compress)