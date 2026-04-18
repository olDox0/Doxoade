import os
import click
import ctypes
import subprocess

@click.group()
def shell_group():
    """Comandos de acesso ao terminal e subsistemas."""
    pass

@shell_group.command(name='terminal')
@click.option('--admin', is_flag=True, help='Abrir como Administrador')
def terminal(admin):
    """Abre um novo terminal (CMD) no diretório atual."""
    current_dir = os.getcwd()
    if os.name == 'nt':
        if admin:
            # ShellExecuteW com 'runas' abre o processo elevado
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/k "cd /d {current_dir}"', None, 1)
        else:
            # Abre terminal comum em nova janela
            os.system(f'start cmd.exe /k "cd /d {current_dir}"')

@shell_group.command(name='wsl-shell')
@click.option('--distro', default='doxlinux', help='Nome da distro')
def wsl_shell(distro):
    """Abre o shell do WSL (Alpine/Arch) em uma nova janela."""
    click.echo(f"[*] Invocando terminal {distro}...")
    if os.name == 'nt':
        # Abre o Windows Terminal ou CMD rodando o WSL
        os.system(f'start wsl.exe -d {distro}')