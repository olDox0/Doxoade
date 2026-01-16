# -*- coding: utf-8 -*-
"""
Universal Executor - Aegis v2.0.
Compliance: MPoT-19 (Quarantine), PASC-6.
"""
import os
import sys
from click import command, argument, option, echo, pass_context
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_venv_python_executable

__all__ = ['run', 'flow_command']

@command('run')
@argument('script')
@option('--flow', is_flag=True, help="Executes with Nexus Flow profiling.")
@option('--test-mode', 'is_test_mode', is_flag=True, help="Authorizes quarantined files.")
@pass_context
def run(ctx, script: str, flow: bool, is_test_mode: bool):
    """Executor Universal com Blindagem de Quarentena."""
    from ..tools.security_utils import validate_execution_context
    
    if not script: raise ValueError("Script required.")
    abs_path = os.path.abspath(script)

    with ExecutionLogger('run', abs_path, ctx.params) as _:
        try:
            # 1. Aegis Security Gate
            validate_execution_context(abs_path, is_test_mode)
            
            # 2. Authorization Fuse
            os.environ["DOXOADE_AUTHORIZED_RUN"] = "1"
            
            # 3. Execution
            if flow:
                _execute_with_flow(abs_path)
            else:
                _execute_standard(abs_path)
                
        except PermissionError as e:
            echo(f"\n{Fore.RED}{Style.BRIGHT}🚨 [AEGIS SECURITY BLOCK]{Style.RESET_ALL}")
            echo(f"{Fore.YELLOW}{e}{Style.RESET_ALL}")
            sys.exit(1)
        except Exception as e:
            echo(f"{Fore.RED}[CRASH] Execution failed: {e}{Style.RESET_ALL}")
            sys.exit(1)

def _execute_standard(abs_path: str):
    """Safe subprocess execution."""
    from subprocess import run as sub_run # nosec
    py_exe = _get_venv_python_executable() or sys.executable
    echo(f"{Fore.CYAN}--- [RUN:PYTHON] Executing: {os.path.basename(abs_path)} ---")
    sub_run([py_exe, abs_path], shell=False) # nosec

# doxoade/commands/run.py (Trecho Final Corrigido)

def _execute_with_flow(abs_path: str):
    """Nexus Flow via Probe Manager (MPoT-5)."""
    # MPoT-5: Contrato de Integridade da Entrada
    if not abs_path or not os.path.isabs(abs_path):
        raise ValueError("Contrato Violado: '_execute_with_flow' exige um caminho absoluto.")

    from ..probes.manager import ProbeManager
    root = os.getcwd()
    py_exe = _get_venv_python_executable() or sys.executable
    
    # PASC-6.6: Lazy lookup para evitar importação circular
    from .check import _get_probe_path
    probe_path = _get_probe_path("flow_runner.py")
    
    manager = ProbeManager(py_exe, root)
    manager.execute(probe_path, abs_path)

@command('flow')
@argument('script')
@pass_context
def flow_command(ctx, script):
    """Alias for doxoade run --flow."""
    ctx.invoke(run, script=script, flow=True, is_test_mode=False)