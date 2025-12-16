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
                
                # [SECURITY FIX] Removemos shell=True e usamos listas de argumentos
                if admin:
                    if not _is_admin():
                        click.echo(Fore.YELLOW + "AVISO: Privilégios de administrador são necessários.")
                        click.echo(Fore.YELLOW + "Uma janela de confirmação (UAC) será exibida.")
                        
                        # Montamos o comando do PowerShell para elevar o CMD
                        # Nota: ArgumentList ainda precisa de aspas internas escapadas, mas
                        # rodamos o powershell em si sem shell=True.
                        ps_args = (
                            f'Start-Process cmd.exe -Verb RunAs '
                            f'-ArgumentList \'/k cd /d "{current_directory}" && title {window_title} && "{activate_script}"\''
                        )
                        
                        # Executa o powershell diretamente, sem CMD no meio
                        subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps_args], check=True)
                    else:
                        # Já é admin, abre nova janela nativamente
                        # CREATE_NEW_CONSOLE (0x10) permite abrir nova janela sem usar 'start' ou shell=True
                        subprocess.Popen(
                            ['cmd.exe', '/k', f'title {window_title} && "{activate_script}"'], 
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
                            cwd=current_directory
                        )
                else:
                    # Execução normal sem privilégios (Nova Janela Segura)
                    subprocess.Popen(
                        ['cmd.exe', '/k', f'title {window_title} && "{activate_script}"'], 
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                        cwd=current_directory
                    )
            
            else: # Linux/macOS/Termux
                activate_cmd = os.path.join(os.path.dirname(venv_python), 'activate')
                # Montamos o comando bash composto
                bash_cmd = f"source {activate_cmd}; exec $SHELL"
                
                if admin:
                    click.echo(Fore.YELLOW + "Tentando iniciar o shell com 'sudo'.")
                    # Usamos lista para evitar shell injection no comando sudo
                    subprocess.run([
                        'sudo', '-E', 'gnome-terminal', '--', '/bin/bash', '-c', bash_cmd
                    ])
                else:
                    # Tenta gnome-terminal (padrão Ubuntu/Debian)
                    # TODO: Adicionar detecção para xterm, konsole, etc.
                    try:
                        subprocess.run([
                            'gnome-terminal', '--', '/bin/bash', '-c', bash_cmd
                        ])
                    except FileNotFoundError:
                        # Fallback para execução no shell atual se não tiver GUI
                        click.echo(Fore.YELLOW + "Terminal GUI não encontrado. Iniciando subshell no terminal atual...")
                        subprocess.run(['/bin/bash', '-c', bash_cmd])

            logger.add_finding("INFO", f"Shell interativo iniciado. Admin: {admin}", category="SHELL")
        except Exception as e:
            logger.add_finding("ERROR", "Falha ao iniciar o shell.", category="SHELL", details=str(e))
            click.echo(Fore.RED + f"Não foi possível iniciar o novo shell: {e}")