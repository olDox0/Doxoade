# -*- coding: utf-8 -*-
import click
import subprocess
import os
import base64
import time
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

# --- CONFIGURAÇÃO DE VETORES PARA EXECUÇÃO REAL ---
VETORES_REAIS = {
    "check": "doxoade/cli.py --fast",
    # O segredo: usamos -- para dizer "os caminhos acabaram, agora vem o comando"
    "intelligence": "-- . list", 
    "intelligence recover": "-- .",
    "config fix": "--help",
    "compress": "--help", 
    "webcheck": "--help",
    "audit": ".",
    "vulcan doctor": "",
}

# --- HELPERS ---
def _sep(label: str = "", width: int = 60, color: str = "cyan") -> None:
    line = f"─{'─' * (width - 2)}─"
    if label:
        pad = max(0, width - len(label) - 4)
        line = f"─ {label} {'─' * pad}"
    click.secho(line, fg=color)

# --- CORE ENGINE ---
class NexusLab:
    def __init__(self, distro="doxlinux"):
        self.distro = distro
        self.project_root_win = _find_project_root(os.getcwd())
        self.project_root_linux = "/tmp/nexus_audit"
        self.wsl_path = self._get_wsl_path(self.project_root_win)

    def _get_wsl_path(self, win_path):
        try:
            return subprocess.check_output(['wsl', '-d', self.distro, 'wslpath', '-a', str(win_path).replace('\\', '/')], text=True).strip()
        except: return None

    def sync(self):
        ignores = ['venv', '.git', '__pycache__', '.pytest_cache', 'dist', '*.egg-info']
        excl = " ".join([f'--exclude="{p}"' for p in ignores])
        cmd = f"mkdir -p {self.project_root_linux} && rsync -am --delete {excl} '{self.wsl_path}/' {self.project_root_linux}/"
        subprocess.run(["wsl", "-d", self.distro, "sh", "-c", cmd], check=True)

    def run(self, cmd_args, timeout=40):
        full_cmd = f"cd {self.project_root_linux} && export PYTHONPATH=. && python3 -m doxoade {cmd_args}"
        enc = base64.b64encode(full_cmd.encode()).decode()
        try:
            res = subprocess.run(["wsl", "-d", self.distro, "sh", "-c", f"echo {enc} | base64 -d | sh"], 
                                 capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')
            return res.returncode, res.stdout, res.stderr
        except Exception as e:
            return -1, "", str(e)

# --- CLI COMMANDS ---
@click.group('lab')
def lab_group():
    """🧪 Nexus Lab: Auditoria de Massa em Sandbox."""
    pass

@lab_group.command('bulk-test')
@click.option('--distro', default='doxlinux')
@click.option('--limit', default=139)
def lab_bulk_test(distro, limit):
    """🚀 Varredura em Massa: Testa a lógica real de TODOS os comandos."""
    try:
        from doxoade.cli import cli
    except Exception as e:
        click.secho(f"FATAL: {e}", fg="red")
        return

    lab = NexusLab(distro)
    click.echo("🔄 Sincronizando Snapshot...")
    lab.sync()

    all_cmds = []
    def collect(group, prefix=""):
        ctx = click.Context(group)
        try:
            for name in group.list_commands(ctx):
                full = f"{prefix} {name}".strip()
                all_cmds.append(full)
                sub = group.get_command(ctx, name)
                if isinstance(sub, click.Group): collect(sub, full)
        except: pass
    collect(cli)
    all_cmds = all_cmds[:limit]

    _sep(f"EXECUTANDO {len(all_cmds)} TESTES NO ALPINE")
    
    results = []
    with click.progressbar(all_cmds, label="Auditando") as bar:
        for cmd_name in bar:
            args = VETORES_REAIS.get(cmd_name, "--help")
            code, out, err = lab.run(f"{cmd_name} {args}")
            sample = (out.strip() if out else err.strip()).replace('\n', ' ')[:50]
            results.append({"cmd": cmd_name, "code": code, "sample": sample, "err": err})

    for r in results:
        if r['code'] == 0:
            click.echo(f"{Fore.GREEN}✔ {r['cmd'].ljust(30)}{Style.RESET_ALL} | {r['sample']}...")
        else:
            err_line = r['err'].strip().splitlines()[-1] if r['err'] else "Erro"
            click.echo(f"{Fore.RED}✘ {r['cmd'].ljust(30)}{Style.RESET_ALL} | {Fore.YELLOW}{err_line[:60]}{Style.RESET_ALL}")

    passed = sum(1 for r in results if r['code'] == 0)
    _sep(f"SAÚDE FINAL: {passed}/{len(all_cmds)}")

@lab_group.command('bootstrap')
@click.option('--distro', default='doxlinux')
def lab_bootstrap(distro):
    lab = NexusLab(distro)
    pkgs = "rsync python3 py3-pip build-base py3-click py3-colorama py3-psutil py3-rich py3-yaml py3-pathspec"
    repo = "--repository=http://dl-cdn.alpinelinux.org/alpine/v3.20/main --repository=http://dl-cdn.alpinelinux.org/alpine/v3.20/community"
    subprocess.run(["wsl", "-d", distro, "-u", "root", "sh", "-c", f"apk add --no-cache {repo} {pkgs}"])

@lab_group.command('deep-test')
@click.option('--distro', default='doxlinux')
def lab_deep_test_legacy(distro):
    ctx = click.get_current_context()
    ctx.invoke(lab_bulk_test, distro=distro)