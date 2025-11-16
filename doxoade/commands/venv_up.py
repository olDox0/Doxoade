# doxoade/commands/venv_up.py
import os
import sys
import subprocess
import click
import ctypes
from colorama import Fore

from ..shared_tools import ExecutionLogger, _get_venv_python_executable

def _is_admin():
    """Verifica se o script está rodando com privilégios de administrador no Windows."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        # Se a biblioteca ctypes não estiver disponível, assume que não é admin.
        return False

@click.command('venv-up')
@click.pass_context
@click.option('--title', help="Define um título customizado para a nova janela do shell.")
@click.option('--admin', is_flag=True, help="Tenta iniciar o novo shell com privilégios de administrador.")
def venv_up(ctx, title, admin):
    """Inicia um novo shell com o ambiente virtual do projeto ativado."""
    arguments = ctx.params
    with ExecutionLogger('venv-up', '.', arguments) as logger:
        venv_python = _get_venv_python_executable()
        if not venv_python:
            click.echo(Fore.RED + "[ERRO] Ambiente virtual 'venv' não foi encontrado.")
            sys.exit(1)

        current_directory = os.getcwd()
        project_name = os.path.basename(current_directory)
        window_title = title or f"Doxoade VENV: {project_name}"

        click.echo(Fore.CYAN + "Iniciando um novo shell com o ambiente virtual ativado...")
        
        try:
            if sys.platform == "win32":
                activate_script = os.path.join(os.path.dirname(venv_python), 'activate.bat')
                
                if admin:
                    if not _is_admin():
                        click.echo(Fore.YELLOW + "AVISO: Privilégios de administrador são necessários.")
                        click.echo(Fore.YELLOW + "Uma janela de confirmação (UAC) será exibida.")
                        
                        # --- INÍCIO DA CORREÇÃO ---
                        # 1. Adicionado -NoProfile para evitar o erro de política de execução.
                        # 2. Adicionado 'cd /d ...' para garantir que o novo shell inicie no diretório correto.
                        #    O '&&' encadeia os comandos.
                        command = (
                            f'powershell.exe -NoProfile -Command "Start-Process cmd.exe -Verb RunAs '
                            f'-ArgumentList \'/k cd /d \\"{current_directory}\\" && title {window_title} && \\"{activate_script}\\"\'"'
                        )
                        subprocess.run(command, shell=True)
                        # --- FIM DA CORREÇÃO ---
                    else:
                        # Se já somos admin, podemos usar 'start' que já funciona corretamente.
                        subprocess.run(f'start "{window_title}" cmd.exe /k "{activate_script}"', shell=True)
                else:
                    # Execução normal sem privilégios
                    subprocess.run(f'start "{window_title}" cmd.exe /k "{activate_script}"', shell=True)
            
            else: # Linux/macOS/Termux
                # A lógica de 'admin' em Linux geralmente envolve 'sudo'
                shell_cmd = f"source {os.path.join(os.path.dirname(venv_python), 'activate')}; exec $SHELL"
                if admin:
                    click.echo(Fore.YELLOW + "Tentando iniciar o shell com 'sudo'. Pode ser necessário digitar sua senha.")
                    subprocess.run(f'sudo -E gnome-terminal -- /bin/bash -c "{shell_cmd}"', shell=True)
                else:
                    subprocess.run(f'gnome-terminal -- /bin/bash -c "{shell_cmd}"', shell=True)

            logger.add_finding("INFO", f"Shell interativo iniciado. Admin: {admin}", category="SHELL")
        except Exception as e:
            logger.add_finding("ERROR", "Falha ao iniciar o shell.", category="SHELL", details=str(e))
            click.echo(Fore.RED + f"Não foi possível iniciar o novo shell: {e}")