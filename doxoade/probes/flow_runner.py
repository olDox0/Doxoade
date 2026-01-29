# -*- coding: utf-8 -*-
# doxoade/probes/flow_runner.py
import sys, os, time, argparse, warnings, linecache, types

warnings.filterwarnings("ignore", category=RuntimeWarning)

# CONSTANTES NEXUS GOLD
C_RESET, C_CYAN, C_YELLOW = '\033[0m', '\033[96m', '\033[93m'
C_WHITE, C_BORDER, C_MAGENTA, C_GREEN = '\033[97m', '\033[90m', '\033[95m', '\033[92m'
C_BOLD, C_DIM, C_RED, SEP = '\033[1m', '\033[2m', '\033[91m', f"\033[90m│\033[0m"

_STATE = {
    'last_time': time.perf_counter(),
    'last_locals': {},
    'project_root': '',
    'indent_level': 0,
    'flow_base': False, 'flow_val': False, 'flow_import': False, 'flow_func': False
}

def _bootstrap_package_context(script_path):
    """Virtualiza o ambiente de pacote para permitir imports relativos (MPoT-19)."""
    abs_path = os.path.abspath(script_path)
    dir_path = os.path.dirname(abs_path)
    
    parts = []
    current = dir_path
    # Sobe a árvore procurando a raiz do projeto (onde param os __init__.py)
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current: break
        current = parent
            
    # Define a âncora real do projeto no sys.path
    if current not in sys.path:
        sys.path.insert(0, current)
        
    pkg_name = ".".join(parts)
    
    # [VITAL] Cria entradas fantasmas no sys.modules para o Python aceitar o pacote
    if pkg_name:
        temp_name = ""
        for p in parts:
            temp_name = f"{temp_name}.{p}" if temp_name else p
            if temp_name not in sys.modules:
                m = types.ModuleType(temp_name)
                m.__path__ = [os.path.join(current, *temp_name.split('.'))]
                sys.modules[temp_name] = m
                
    return pkg_name, current

def static_trace_calls(frame, event, arg):
    filename = frame.f_code.co_filename
    
    # [CURTO-CIRCUITO DE PERFORMANCE]
    # Se sair do projeto ou entrar em Lib/venv, retorna None (Aborta rastro nessa ramificação)
    if filename.startswith('<') or "importlib" in filename or "Lib" in filename or "site-packages" in filename:
        return None 

    abs_filename = os.path.abspath(filename).replace('\\', '/')
    if _STATE['project_root'] and not abs_filename.startswith(_STATE['project_root']):
        return None

    now = time.perf_counter()
    ms = (now - _STATE['last_time']) * 1000
    _STATE['last_time'] = now

    # --- LENTE: FUNCTION ---
    if _STATE['flow_func']:
        if event == 'call':
            func = frame.f_code.co_name
            print(f"{C_BORDER}│{C_RESET} {'  '*_STATE['indent_level']}{C_MAGENTA}➔ CALL: {C_BOLD}{func}{C_RESET}")
            _STATE['indent_level'] += 1
        elif event == 'return':
            _STATE['indent_level'] = max(0, _STATE['indent_level'] - 1)
            print(f"{C_BORDER}│{C_RESET} {'  '*_STATE['indent_level']}{C_GREEN}⇠ RETN: {C_BOLD}{frame.f_code.co_name}{C_RESET}")

    if event != 'line': return static_trace_calls

    # --- LENTE: IMPORT/IO ---
    line = linecache.getline(filename, frame.f_lineno).strip()
    is_import = "import " in line or "from " in line
    
    if _STATE['flow_import'] and is_import:
        loc = f"{os.path.basename(filename)}:{frame.f_lineno}".ljust(25)
        print(f"{C_BORDER}│{C_RESET} {ms:7.1f}ms {SEP} {C_YELLOW}[ MÓDULO ] {C_WHITE}{loc}{SEP} {line}")
        return static_trace_calls # Para aqui se for apenas lente de import

    # --- LENTE: PROCESSAMENTO (Apenas se --base ou --val) ---
    if _STATE['flow_base'] or _STATE['flow_val']:
        diffs = []
        if _STATE['flow_val']:
            for k, v in list(frame.f_locals.items()):
                if k.startswith('__') or k in ['self', 'cls']: continue
                if _STATE['last_locals'].get(k) != v:
                    diffs.append(f"{C_CYAN}{k}{C_DIM}={C_YELLOW}{_safe_to_string(v)}{C_RESET}")
            _STATE['last_locals'] = frame.f_locals.copy()

        loc = f"{'  '*_STATE['indent_level']}{os.path.basename(filename)}:{frame.f_lineno}".ljust(25)
        print(f"{C_BORDER}│{C_RESET} {ms:7.1f}ms {SEP} {C_WHITE}{loc}{SEP} {line[:50].ljust(50)} {SEP} {', '.join(diffs)}")

    return static_trace_calls

def run_flow(script_path, base, val, imp, func):
    abs_p = os.path.abspath(script_path)
    pkg_name, project_root = _bootstrap_package_context(abs_p)
    
    _STATE.update({
        'project_root': project_root.replace('\\', '/'),
        'flow_base': base, 'flow_val': val, 'flow_import': imp, 'flow_func': func
    })
    
    # Define __name__ como o caminho do pacote para o Python aceitar imports relativos
    module_name = f"{pkg_name}.{os.path.basename(abs_p)[:-3]}" if pkg_name else "__main__"
    globs = {
        '__name__': '__main__', 
        '__file__': abs_p, 
        '__package__': pkg_name,
        '__path__': [os.path.dirname(abs_p)] if pkg_name else None
    }

    print(f"{C_BORDER}{'─'*115}{C_RESET}\n{C_CYAN}{C_BOLD} DOXOADE NEXUS FLOW v3.3{C_RESET} | {os.path.basename(abs_p)}\n{C_BORDER}┌{'─'*11}┬{'─'*25}┬{'─'*50}┬{'─'*25}┐{C_RESET}")

    try:
        with open(abs_p, 'r', encoding='utf-8') as f: content = f.read()
        from doxoade.tools.security_utils import restricted_safe_exec
        sys.settrace(static_trace_calls)
        try: restricted_safe_exec(content, globs, allow_imports=True)
        finally: sys.settrace(None)
    except Exception:
        exc_type, exc_val, _ = sys.exc_info()
        print(f"\n{C_RED}[CRASH] {exc_type.__name__}: {exc_val}{C_RESET}")

def _safe_to_string(val):
    try:
        if 'importlib' in getattr(type(val), '__module__', ''): return "<Internal>"
        s = str(val).replace('\n', ' ')
        return (s[:25] + "...") if len(s) > 28 else s
    except: return "<Error>"

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("script")
    p.add_argument("--base", action="store_true")
    p.add_argument("--val", action="store_true")
    p.add_argument("--import", dest="imp", action="store_true")
    p.add_argument("--func", action="store_true")
    args = p.parse_args()
    run_flow(args.script, args.base, args.val, args.imp, args.func)