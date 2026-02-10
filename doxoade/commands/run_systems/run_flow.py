# -*- coding: utf-8 -*-
"""Especialista de Rastro Nexus Flow (PASC 8.5)."""
import os
import click
from colorama import Fore
from ...probes import flow_runner

def execute_flow(path: str, **kwargs):
    """Orquestra a execução com rastro visual Matrix."""
    abs_path = os.path.abspath(path)
    target_file = kwargs.get('target')
    
    # Flags de sensibilidade
    f_val = kwargs.get('flow_val', False)
    f_imp = kwargs.get('flow_import', False)
    f_func = kwargs.get('flow_func', False)
    
    try:
        flow_runner.run_flow(
            abs_path,
            base=True, # Base sempre ativo no modo flow
            val=f_val,
            imp=f_imp,
            func=f_func,
            target_file=target_file
        )
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        click.echo(Fore.RED + f"\n🚨 [NEXUS ERROR] Falha no fluxo unificado: {e}")