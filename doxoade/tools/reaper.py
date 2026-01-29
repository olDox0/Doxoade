# -*- coding: utf-8 -*-
"""
Doxoade Process Reaper - v1.0.
Garante a limpeza de processos órfãos (Anti-Zombie Protocol).
Compliance: MPoT-15, Aegis Rule 17.
"""
import os
import subprocess
import psutil
import signal

def kill_process_tree(pid):
    """Mata recursivamente toda a árvore de processos (MPoT-15)."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        pass

def register_process_guards():
    """Configura sinais de encerramento para evitar fugas."""
    def handler(signum, frame):
        # O reaper será acionado pelo comando run
        pass
    
    if os.name != 'nt':
        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGHUP, handler)