# -*- coding: utf-8 -*-
# doxoade/probes/flow_runner.py
import sys, os, time, argparse, warnings, linecache, types
from colorama import Fore

warnings.filterwarnings("ignore", category=RuntimeWarning)

# CONSTANTES NEXUS GOLD
C_RESET = '\033[0m'
C_CYAN, C_YELLOW, C_WHITE = '\033[96m', '\033[93m', '\033[97m'
C_BORDER, C_MAGENTA, C_GREEN = '\033[90m', '\033[95m', '\033[92m'
C_BOLD, C_DIM, C_RED, SEP = '\033[1m', '\033[2m', '\033[91m', f"\033[90m│\033[0m"

_STATE = {
    'last_time': time.perf_counter(),
    'last_locals': {},
    'project_root': '',
    'target_file': None, # [NOVO] Lente de Foco
    'indent_level': 0,
    'flow_base': False, 'flow_val': False, 'flow_import': False, 'flow_func': False,
    'history': [], 'active_pattern': None, 'pattern_idx': 0, 'hidden_count': 0,
}

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
            pattern = h[-size:]
            previous = h[-size*2:-size]
            if pattern == previous:
                _STATE['active_pattern'] = pattern
                _STATE['pattern_idx'] = 1 % size
                _STATE['hidden_count'] = 1
                return True
    return False

def static_trace_calls(frame, event, arg):
    filename = frame.f_code.co_filename
    lineno = frame.f_lineno
    current_id = (filename, lineno)
    
    # 1. Noise Gate (Sistema)
    if filename.startswith('<') or any(x in filename for x in ["importlib", "Lib", "flow_runner"]):
        return None 

    # 2. Sniper Lens (Foco em Arquivo Específico)
    abs_filename = os.path.abspath(filename).replace('\\', '/')
    
    # Se o Chief definiu um alvo, ignoramos qualquer rastro fora dele
    if _STATE['target_file'] and abs_filename != _STATE['target_file']:
        # Mas mantemos o rastreamento ativo para quando o fluxo entrar no arquivo alvo
        return static_trace_calls

    # 3. Project Boundary (Filtro padrão)
    if not abs_filename.startswith(_STATE['project_root']):
        return None

    # --- LÓGICA IRON GATE ---
    if event == 'line':
        if _handle_compression(current_id): return static_trace_calls

    # --- EVENTOS DE FUNÇÃO ---
    if _STATE['flow_func']:
        if event == 'call':
            _flush_iron_gate()
            func = frame.f_code.co_name
            print(f"{C_BORDER}│{C_RESET} {'  '*_STATE['indent_level']}{C_MAGENTA}➔ CALL: {C_BOLD}{func}{C_RESET}")
            _STATE['indent_level'] += 1
        elif event == 'return':
            _flush_iron_gate()
            _STATE['indent_level'] = max(0, _STATE['indent_level'] - 1)
            print(f"{C_BORDER}│{C_RESET} {'  '*_STATE['indent_level']}{C_GREEN}⇠ RETN: {C_BOLD}{frame.f_code.co_name}{C_RESET}")

    if event != 'line': return static_trace_calls

    # --- RENDERIZAÇÃO ---
    line = linecache.getline(filename, lineno).strip()
    
    if _STATE['flow_import'] and ("import " in line or "from " in line):
        print(f"{C_BORDER}│{C_RESET} {' '*7}ms {SEP} {C_YELLOW}[ MÓDULO ] {C_WHITE}{os.path.basename(filename)}:{lineno}{SEP} {line}")

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

    return static_trace_calls

def run_flow(script_path, base, val, imp, func, target_file=None):
    abs_p = os.path.abspath(script_path)
    pkg_name, project_root = _bootstrap_package(abs_p)
    
    # Prepara o alvo do Sniper
    target_abs = os.path.abspath(target_file).replace('\\', '/') if target_file else None

    _STATE.update({
        'project_root': project_root.replace('\\', '/'),
        'target_file': target_abs,
        'flow_base': base, 'flow_val': val, 'flow_import': imp, 'flow_func': func
    })
    
    globs = {
        '__name__': '__main__', '__file__': abs_p, 
        '__package__': pkg_name, '__path__': [os.path.dirname(abs_p)] if pkg_name else None
    }

    print(f"{C_BORDER}{'─'*115}{C_RESET}\n{C_CYAN}{C_BOLD} DOXOADE NEXUS FLOW v4.0 (Target Sniper){C_RESET} | {os.path.basename(abs_p)}")
    if target_abs: print(f" {C_WHITE}Foco Ativo: {C_YELLOW}{os.path.basename(target_abs)}{C_RESET}")
    print(f"{C_BORDER}┌{'─'*11}┬{'─'*25}┬{'─'*50}┬{'─'*25}┐{C_RESET}")

    try:
        with open(abs_p, 'r', encoding='utf-8') as f: content = f.read()
        from doxoade.tools.security_utils import restricted_safe_exec
        sys.settrace(static_trace_calls)
        try: 
            restricted_safe_exec(content, globs, allow_imports=True)
            _flush_iron_gate()
        finally: sys.settrace(None)
    except Exception as e:
        exc_type, exc_val, exc_obj = sys.exc_info()
        print(f"\n{C_RED}[CRASH FLOW] {exc_type.__name__ if exc_type else 'Error'}: {exc_val}{C_RESET}")
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")

def _bootstrap_package(script_path):
    abs_path = os.path.abspath(script_path)
    current = os.path.dirname(abs_path)
    parts = []
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current)); parent = os.path.dirname(current)
        if parent == current: break
        current = parent
    if current not in sys.path: sys.path.insert(0, current)
    return ".".join(parts), current

def _safe_to_string(val):
    try:
        if 'importlib' in getattr(type(val), '__module__', ''): return "<Internal>"
        s = str(val).replace('\n', ' ')
        return s[:25] + "..." if len(s) > 28 else s
    except: return "<Error>"

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("script")
    p.add_argument("--base", action="store_true")
    p.add_argument("--val", action="store_true")
    p.add_argument("--import", dest="imp", action="store_true")
    p.add_argument("--func", action="store_true")
    p.add_argument("--target", default=None) # Flag do Sniper
    args = p.parse_args()
    run_flow(args.script, args.base, args.val, args.imp, args.func, args.target)