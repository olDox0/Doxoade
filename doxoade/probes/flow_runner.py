# -*- coding: utf-8 -*-
# doxoade/probes/flow_runner.py
import sys
import os
import time
import argparse
import warnings
import linecache
# [DOX-UNUSED] import logging
from colorama import Fore

# Silenciador de interferência
warnings.filterwarnings("ignore", category=RuntimeWarning, module="opcode")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="dis")

C_RESET, C_DIM, C_CYAN = '\033[0m', '\033[2m', '\033[96m'
C_YELLOW, C_GREEN, C_RED = '\033[93m', '\033[92m', '\033[91m'
C_WHITE, C_BORDER, C_MAGENTA = '\033[97m', '\033[90m', '\033[95m'
C_BOLD = '\033[1m'
SEP = f"{C_BORDER}│{C_RESET}"

_STATE = {
    'last_time': time.perf_counter(),
    'last_locals': {},
    'watch_var': None,
    'slow_threshold': 0,
    'script_path': '',
    'last_val_repr': None
}

def _bootstrap_package(script_path):
    """
    Ancoragem de Pacote (MPoT-19).
    Calcula o __package__ e injeta o parent no sys.path para permitir imports relativos.
    """
    abs_path = os.path.abspath(script_path)
    dir_path = os.path.dirname(abs_path)
    
    parts = []
    current = dir_path
    
    # Sobe a árvore procurando por __init__.py para identificar a hierarquia de pacotes
    while os.path.exists(os.path.join(current, '__init__.py')):
        parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current: break # Proteção contra loop infinito em root
        current = parent
            
    # O diretório que não contém __init__.py é a nossa âncora de sys.path
    if current not in sys.path:
        sys.path.insert(0, current)
            
    return ".".join(parts) if parts else ""

def _safe_to_string(val):
    """Inspeção Blindada (Aegis Rule)."""
    try:
        mod_name = getattr(type(val), '__module__', '')
        if 'importlib' in mod_name or '_bootstrap' in mod_name:
            return f"<{type(val).__name__} (Internal)>"
        
        s = str(val).replace('\n', ' ')
        return (s[:22] + "...") if len(s) > 25 else s
    except Exception:
        return "<Unreadable>"

def static_trace_calls(frame, event, arg):
    if event != 'line': return static_trace_calls

    filename = frame.f_code.co_filename
    if filename.startswith('<') or "importlib" in filename or "Lib" in filename:
        return static_trace_calls

    current_time = time.perf_counter()
    elapsed = current_time - _STATE['last_time']
    delta_ms = elapsed * 1000
    _STATE['last_time'] = current_time

    if _STATE['slow_threshold'] > 0 and delta_ms < _STATE['slow_threshold']:
        return static_trace_calls

    time_str = f"{delta_ms:9.1f}ms"
    loc = f" {os.path.basename(filename)}:{frame.f_lineno}".ljust(25)
    code_line = linecache.getline(filename, frame.f_lineno).strip() or "???"
    
    diffs = []
    current_locals = frame.f_locals
    for name in list(current_locals.keys()):
        if name.startswith('__'): continue
        val = current_locals[name]
        
        if _STATE['last_locals'].get(name) != val:
            v_str = _safe_to_string(val)
            diffs.append(f"{C_CYAN}{name}{C_DIM}={C_YELLOW}{v_str}{C_RESET}")
    
    _STATE['last_locals'] = current_locals.copy()
    print(f"{C_BORDER}│{C_RESET} {time_str} {SEP}{C_RED}{loc}{SEP} {code_line[:50].ljust(50)}{SEP} {', '.join(diffs)}")
    
    return static_trace_calls

def run_flow(script_path, watch_var=None, slow_ms=0):
    _STATE['script_path'] = os.path.abspath(script_path)
    _STATE['watch_var'] = watch_var
    _STATE['slow_threshold'] = float(slow_ms or 0)
    
    # 1. Resolve o contexto de pacote (Fix: ImportError)
    pkg_name = _bootstrap_package(_STATE['script_path'])
    
    # 2. Configura Globais para o sandbox
    globs = {
        '__name__': '__main__',
        '__file__': _STATE['script_path'],
        '__package__': pkg_name, # Permite imports relativos
        '__loader__': None,
        '__spec__': None
    }

    print(f"{C_BORDER}{'─'*115}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD} DOXOADE FLOW v2.5 (Bootstrap Gold){C_RESET} | Alvo: {os.path.basename(_STATE['script_path'])}")
    if pkg_name: print(f" {C_WHITE}Contexto de Pacote: {C_YELLOW}{pkg_name}{C_RESET}")
    print(f"{C_BORDER}┌{'─'*11}┬{'─'*25}┬{'─'*50}┬{'─'*25}┐{C_RESET}")

    try:
        with open(_STATE['script_path'], 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        from doxoade.tools.security_utils import restricted_safe_exec
        linecache.checkcache(_STATE['script_path'])
        
        sys.settrace(static_trace_calls)
        try:
            restricted_safe_exec(content, globs, allow_imports=True)
        finally:
            sys.settrace(None)
            
        print(f"{C_BORDER}{'─'*115}{C_RESET}")
        print("--- Trace Finalizado ---")
        
    except Exception:
        # PASC-5.3: Unpacking correto de 3 valores (Fix: ValueError)
        exc_type, exc_val, exc_tb = sys.exc_info()
        print(f"\n{Fore.RED}[CRASH FLOW] {exc_type.__name__ if exc_type else 'Error'}: {exc_val}")
        
        # Se for um erro do sandbox, o problema costuma estar na linha anterior ao crash do trace
        if "Aegis Sandbox Blocked" in str(exc_val):
            print(f"{Fore.YELLOW}DICA: Verifique se o script alvo possui permissão para os imports utilizados.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--watch", default=None)
    parser.add_argument("--slow", default=0)
    args = parser.parse_args()
    run_flow(args.script, args.watch, args.slow)