# -*- coding: utf-8 -*-
# doxoade/probes/flow_runner.py
import sys
import os
import time
import argparse
import warnings
from colorama import Fore

# [MPoT-14] Silenciador de interferência do interpretador (Python 3.12+)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="opcode")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="dis")

# CONFIGURAÇÕES TÉCNICAS (Nexus View)
C_RESET, C_DIM, C_CYAN = '\033[0m', '\033[2m', '\033[96m'
C_YELLOW, C_GREEN, C_RED = '\033[93m', '\033[92m', '\033[91m'
C_WHITE, C_BORDER, C_MAGENTA = '\033[97m', '\033[90m', '\033[95m'
C_BOLD = '\033[1m'
SEP = f"{C_BORDER}│{C_RESET}"

# Memória de Rastro (Global para ser acessível pela função estática)
_STATE = {
    'last_time': time.perf_counter(),
    'last_locals': {},
    'watch_var': None,
    'slow_threshold': 0,
    'script_path': '',
    'var_found': False,
    'last_val_repr': None
}

def _bootstrap_path(script_path):
    abs_path = os.path.abspath(script_path)
    parts = abs_path.replace('\\', '/').split('/')
    try:
        idx = parts.index('doxoade')
        project_root = "/".join(parts[:idx])
        if project_root not in sys.path: sys.path.insert(0, project_root)
        package_parts = []
        current = os.path.dirname(abs_path)
        while os.path.exists(os.path.join(current, '__init__.py')):
            package_parts.insert(0, os.path.basename(current))
            current = os.path.dirname(current)
            if os.path.basename(current) == 'doxoade':
                package_parts.insert(0, 'doxoade')
                break
        return ".".join(package_parts) if package_parts else None
    except ValueError: return None

def _format_time(seconds):
    ms = seconds * 1000
    text = f"{ms:.1f}ms".rjust(9)
    if ms > 1000: return f"{C_RED}{seconds:.2f}s  {C_RESET}"
    if ms > 100:  return f"{C_YELLOW}{text} {C_RESET}"
    return f"{C_GREEN}{text} {C_RESET}"

def _check_watch(frame):
    """Monitora mutações de variáveis (Independente do escopo)."""
    if _STATE['watch_var'] in frame.f_locals:
        val = frame.f_locals[_STATE['watch_var']]
        curr_repr = repr(val)
        if curr_repr != _STATE['last_val_repr']:
            print(f"\n🚨 {C_MAGENTA}[MUTAÇÃO]{C_RESET} {_STATE['watch_var']} {C_DIM}at {os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno}")
            print(f"   {C_BOLD}Novo Valor:{C_RESET} {C_YELLOW}{curr_repr[:100]}{C_RESET}")
            _STATE['last_val_repr'] = curr_repr

def static_trace_calls(frame, event, arg):
    """
    Função de rastro principal (Stateless).
    MPoT-1: Protegida contra UnboundLocalError e corrupção de sandbox.
    """
    if event != 'line': return static_trace_calls

    # 1. Filtro de Segurança Imediato (Evita avisos do Python 3.12)
    filename = frame.f_code.co_filename
    if "Lib" in filename or "site-packages" in filename or "probes" in filename:
        return static_trace_calls

    current_time = time.perf_counter()
    elapsed = current_time - _STATE['last_time']
    delta_ms = elapsed * 1000
    _STATE['last_time'] = current_time

    # 2. Processa Watch se ativo
    if _STATE['watch_var']:
        _check_watch(frame)

    # 3. Filtro de Gargalo
    if _STATE['slow_threshold'] > 0 and delta_ms < _STATE['slow_threshold']:
        return static_trace_calls

    # 4. Interface Nexus View
    time_str = _format_time(elapsed)
    loc = f" {os.path.basename(filename)}:{frame.f_lineno}".ljust(25)
    
    try:
        import linecache
        code_line = linecache.getline(filename, frame.f_lineno).strip()
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] static_trace_calls: {e}")
        code_line = "???"
    
    # Diferencial de Variáveis
    diffs = []
    for name, val in frame.f_locals.items():
        if name.startswith('__'): continue
        if _STATE['last_locals'].get(name) != val:
            v_str = str(val).replace('\n', ' ')
            if len(v_str) > 25: v_str = v_str[:22] + "..."
            diffs.append(f"{C_CYAN}{name}{C_DIM}={C_YELLOW}{v_str}{C_RESET}")
    
    _STATE['last_locals'] = frame.f_locals.copy()
    print(f"{C_BORDER}│{C_RESET}{time_str}{SEP}{loc}{SEP} {code_line[:48].ljust(48)}{SEP} {', '.join(diffs)}")
    
    return static_trace_calls

def run_flow(script_path, watch_var=None, slow_ms=0):
    # Garantia de tipo MPoT-5 (Robustez)
    try:
        slow_ms = float(slow_ms)
    except (ValueError, TypeError):
        slow_ms = 0.0

    _STATE['script_path'] = script_path
    _STATE['watch_var'] = watch_var
    _STATE['slow_threshold'] = slow_ms
    
    abs_path = os.path.abspath(script_path)
    package_name = _bootstrap_path(abs_path)
    
    globs = {'__name__': '__main__', '__file__': abs_path, '__package__': package_name}

    # Cabeçalho Nexus Gold
    print(f"{C_BORDER}{'─'*115}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD} DOXOADE FLOW v2.3 (Stateless Gold){C_RESET} | Alvo: {os.path.basename(abs_path)}")
    if int(slow_ms) > 0: print(f" {Fore.YELLOW}⚠️ [ MODO GARGALO ] Exibindo apenas linhas > {slow_ms}ms{C_RESET}")
    print(f"{C_BORDER}┌{'─'*10}┬{'─'*25}┬{'─'*50}┬{'─'*25}┐{C_RESET}")

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        from doxoade.tools.security_utils import restricted_safe_exec
        
        sys.settrace(static_trace_calls)
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
        finally:
            sys.settrace(None)
            
        print(f"{C_BORDER}{'─'*115}{C_RESET}")
        print("--- Trace Finalizado ---")
        
    except Exception as e:
        print(f"\n{Fore.RED}[CRASH FLOW] {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--watch", default=None)
    parser.add_argument("--slow", default=0)
    args = parser.parse_args()
    run_flow(args.script, args.watch, args.slow)