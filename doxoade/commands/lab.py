# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/lab.py
import click
import subprocess
import os
import sys
import textwrap
import base64
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

class NexusLab:
    def __init__(self, distro="doxlinux"):
        self.distro = distro
        self.project_root_win = _find_project_root(os.getcwd())
        self.project_root_linux = self._get_linux_path(self.project_root_win)

    def _get_linux_path(self, win_path):
        try:
            return subprocess.check_output(
                ['wsl', '-d', self.distro, 'wslpath', '-a', win_path.replace('\\', '/')], 
                text=True, encoding='utf-8'
            ).strip()
        except: return None

    def bootstrap(self, force=False):
        """Garante que o ambiente Alpine tenha todas as bibliotecas Nexus."""
        # Verificamos os módulos essenciais para o Doxoade dar o boot
        check_cmd = "python3 -c 'import click, colorama, psutil, rich' 2>/dev/null"
        res = subprocess.run(["wsl", "-d", self.distro, "sh", "-c", check_cmd], capture_output=True)
        
        if res.returncode != 0 or force:
            click.echo(f"{Fore.YELLOW}🔧 Provisionando pacotes nativos no Alpine...{Style.RESET_ALL}")
            
            # Lista de pacotes essenciais (mapeados do seu código)
            pkgs = [
                "bubblewrap", "python3", "py3-pip", "git", "bash",
                "py3-click",    # CLI
                "py3-colorama", # Cores
                "py3-psutil",   # Telemetria/Processos
                "py3-rich",     # Interface/Tabelas
                "py3-requests", # API/Bridge
                "py3-yaml",     # Configurações
            ]
            
            setup_cmd = f"apk add --no-cache {' '.join(pkgs)} > /dev/null"
            subprocess.run(["wsl", "-d", self.distro, "-u", "root", "sh", "-c", setup_cmd])
            
            click.echo(f"{Fore.GREEN}✔ Ambiente provisionado.{Style.RESET_ALL}")

@click.group('lab')
def lab_group():
    """🧪 Nexus Lab: Sandbox de alta segurança."""
    pass

@lab_group.command('test-suite')
@click.option('--distro', default='doxlinux')
@click.option('--stop-on-fail', is_flag=True)
def lab_test_suite(distro, stop_on_fail):
    """🧪 Mass Test: Suite Ultra-Veloz."""
    lab = NexusLab(distro)
    lab.bootstrap()

    test_cases = [
        ("Help Principal", "python3 -m doxoade --help"),
        ("Version Check", "python3 -m doxoade --version"),
        ("Scan Command", "python3 -m doxoade lab scan --help"),
    ]

    click.echo(f"\n{Fore.MAGENTA}🚀 Iniciando Suite de Testes no Alpine...{Style.RESET_ALL}\n")

    for name, cmd in test_cases:
        click.echo(f"Testing: {Fore.CYAN}{name.ljust(25)}{Style.RESET_ALL} ", nl=False)
        
        run_script = f"""
        cd "{lab.project_root_linux}"
        export PYTHONPATH=.
        {cmd}
        """
        
        enc_run = base64.b64encode(run_script.encode('utf-8')).decode('utf-8')
        final_cmd = ["wsl", "-d", distro, "-u", "root", "sh", "-c", f"echo {enc_run} | base64 -d | sh"]
        
        try:
            process = subprocess.run(final_cmd, capture_output=True, text=True, timeout=20)
            if process.returncode == 0:
                click.echo(f"{Fore.GREEN}[ PASS ]{Style.RESET_ALL}")
            else:
                click.echo(f"{Fore.RED}[ FAIL ]{Style.RESET_ALL}")
                click.echo(f"\n{Fore.YELLOW}--- DETALHES ---{Style.RESET_ALL}\n{process.stderr}\n")
                if stop_on_fail: break
        except Exception as e:
            click.echo(f"{Fore.RED}[ ERROR ] {e}{Style.RESET_ALL}")
            
@lab_group.command('bootstrap')
@click.option('--distro', default='doxlinux')
@click.option('--force', is_flag=True, help='Força a reinstalação de todas as dependências.')
def lab_bootstrap_cmd(distro, force):
    """Instala/Atualiza os componentes da jaula no WSL."""
    lab = NexusLab(distro)
    lab.bootstrap(force=force)