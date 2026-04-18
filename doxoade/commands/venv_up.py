# doxoade/doxoade/commands/venv_up.py
import os
import click
from doxoade.tools.vulcan.bridge import vulcan_bridge
from doxoade.tools.filesystem import _get_venv_python_executable

@click.command('venv-up')
@click.option('--title', help='Título da janela')
@click.option('--admin', is_flag=True, help='Forçar privilégios de Administrador')
def venv_up(title, admin):
    """Inicia shell com venv e elevação de privilégios correta."""
    _execute_activation(title, admin)

def _execute_activation(title, admin):
    venv_python = _get_venv_python_executable()
    if not venv_python:
        click.secho(' Venv não localizado.', fg='red')
        return
    current_dir = os.path.normpath(os.getcwd())
    activate_bat = os.path.normpath(os.path.join(os.path.dirname(venv_python), 'activate.bat'))
    window_title = title or f'DOXOADE_{os.path.basename(current_dir)}'
    if os.name == 'nt':
        if admin:
            params = f'/k "cd /d "{current_dir}" && title {window_title} && "{activate_bat}""'
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'cmd.exe', params, None, 1)
        else:
            import subprocess
            subprocess.Popen(cwd=current_dir, creationflags=16)
vulcan_bridge.apply_turbo('venv_up', globals())
