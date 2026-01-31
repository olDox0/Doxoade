# -*- coding: utf-8 -*-
# doxoade/commands/run.py
"""
Universal Executor - Aegis v2.3 (Target Sniper Ready).
Compliance: MPoT-19, PASC-6.
"""
import sys
import subprocess
import os
import click # FIX: Importação essencial para click.Path
from colorama import Fore, Style
from click import command, argument, option, echo, pass_context
from .debug_utils import get_debug_env
from ..tools.reaper import kill_process_tree
from ..shared_tools import ExecutionLogger, _get_venv_python_executable

@command('run')
@argument('script')
@option('--flow', is_flag=True, help="Execução com rastro de linhas.")
@option('--flow-val', is_flag=True, help="Rastreio de variáveis.")
@option('--flow-import', is_flag=True, help="Rastreio de módulos e I/O.")
@option('--flow-func', is_flag=True, help="Rastreio de funções.")
@option('--file', '-f', type=click.Path(exists=True), help="Monitora apenas este arquivo.")
@option('--test-mode', is_flag=True)
@pass_context
def run(ctx, script: str, flow, flow_val, flow_import, flow_func, file, test_mode):
    """Executor Universal com Lentes Nexus v4.0."""
    from ..tools.security_utils import validate_execution_context
    
    if not script: raise ValueError("Script required.")
    abs_path = os.path.abspath(script)
    
    # Ativa o rastro se qualquer flag for usada ou se um arquivo alvo for definido
    active_flow = any([flow, flow_val, flow_import, flow_func, file])

    with ExecutionLogger('run', abs_path, ctx.params) as _:
        try:
            validate_execution_context(abs_path, test_mode)
            os.environ["DOXOADE_AUTHORIZED_RUN"] = "1"
            
            if active_flow:
                _execute_with_flow(abs_path, ctx.params)
            else:
                _execute_standard(abs_path)
                
        except Exception as e:
            echo(f"\n{Fore.RED}🚨 [RUN ERROR] {e}{Style.RESET_ALL}")
            sys.exit(1)

def _execute_standard(abs_path: str):
    from subprocess import run as sub_run
    py_exe = _get_venv_python_executable() or sys.executable
    echo(f"{Fore.CYAN}--- [RUN:PYTHON] Executing: {os.path.basename(abs_path)} ---")
    sub_run([py_exe, abs_path], shell=False)

def _execute_with_flow(script_path, params):
    from ..probes import flow_runner
    py_exe = _get_venv_python_executable() or sys.executable
    env = get_debug_env(script_path)
    
    cmd = [py_exe, os.path.abspath(flow_runner.__file__), script_path]
    if params.get('flow'): cmd.append("--base")
    if params.get('flow_val'): cmd.append("--val")
    if params.get('flow_import'): cmd.append("--import")
    if params.get('flow_func'): cmd.append("--func")
    if params.get('file'): 
        cmd.extend(["--target", os.path.abspath(params['file'])])
    
    process = None
    try:
        process = subprocess.Popen(cmd, env=env, shell=False)
        process.wait()
    except KeyboardInterrupt:
        echo(f"\n{Fore.YELLOW}[!] Interrupção: Acionando Ceifador...")
    finally:
        if process and process.poll() is None:
            kill_process_tree(process.pid)