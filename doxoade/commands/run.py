# doxoade/commands/run.py
import os
import sys
import subprocess
import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _get_venv_python_executable

@click.command('run', context_settings=dict(ignore_unknown_options=True))
@click.pass_context
@click.argument('script_and_args', nargs=-1, type=click.UNPROCESSED)
def run(ctx, script_and_args):
    """Executa um script Python usando o ambiente virtual do projeto."""
    arguments = ctx.params
    with ExecutionLogger('run', '.', arguments) as logger:
        if not script_and_args:
            click.echo(Fore.RED + "[ERRO] Nenhum script especificado. Para ativar o venv, use 'doxoade venv-up'.")
            sys.exit(1)

        venv_python = _get_venv_python_executable()
        if not venv_python:
            msg = "Ambiente virtual 'venv' não foi encontrado."
            logger.add_finding("CRITICAL", msg, category="VENV")
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)

        script_path = script_and_args[0]
        if not os.path.exists(script_path):
            msg = f"Script não encontrado: '{script_path}'."
            logger.add_finding('ERROR', msg, category="FILE-NOT-FOUND")
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)

        command = [venv_python] + list(script_and_args)
        
        click.echo(Fore.CYAN + f"--- Executando '{' '.join(script_and_args)}' ---")
        
        try:
            # Herda o I/O, o que permite interatividade total (input(), etc.)
            result = subprocess.run(command)
            
            click.echo(Fore.CYAN + "--- Execução Finalizada ---")
            
            if result.returncode != 0:
                msg = f"O script terminou com o código de erro {result.returncode}."
                logger.add_finding('ERROR', msg, category="EXECUTION")
                click.echo(Fore.RED + f"[ERRO] {msg}")
                sys.exit(result.returncode)
            else:
                click.echo(Fore.GREEN + "[OK] Script finalizado com sucesso.")

        except KeyboardInterrupt:
            click.echo("\n" + Fore.YELLOW + "[AVISO] Execução interrompida pelo usuário.")
            logger.add_finding("INFO", "Execução interrompida pelo usuário.", category="EXECUTION")
            sys.exit(130)