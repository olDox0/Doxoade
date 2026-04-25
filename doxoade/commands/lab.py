# -*- coding: utf-8 -*-
import click
import subprocess
import os
import base64
import time
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

# --- SUITE DE CENÁRIOS DE TESTE REAL ---
MISSOES_NEXUS = [
    ("Auditoria de API", "apicheck ."), # Ele vai procurar apicheck.json na raiz
    ("Julgamento de Ma'at", "audit ."),
    ("Automação Pipeline", "auto -f PipelineHelp.txt"), # Usa o arquivo que você já tem
    ("Mapeamento Git", "branch --list"),
    ("Canonização Gold", "canonize --all --run-tests"),
    ("Check Integridade", "check . --fast"),
    ("Telemetria Nexus", "telemetry -n 5"),
    # Usamos o comando 'list' que vamos criar abaixo
    ("Inteligência Scan", "intelligence list ."),
    ("Doxcolors Anim", "doxcolors play assets/loading.nxa"), # Removido --duration
]

VETORES_REAIS = {
    "telemetry": "-n 1",
    "check": "--fast doxoade/commands/check_systems/",
    "intelligence list": ".",  # Agora chamamos o novo comando list
    "intelligence recover": "--help",
    "compress file": ".",      # Ajustado para o novo comando 'file'
    "webcheck": "--help",
    "config fix": "--help",
}

def _sep(label: str = "", width: int = 60, color: str = "cyan") -> None:
    line = f"─{'─' * (width - 2)}─"
    if label:
        pad = max(0, width - len(label) - 4)
        line = f"─ {label} {'─' * pad}"
    click.secho(line, fg=color)

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

    def run(self, cmd_args, timeout=60):
        # PYTHONPATH e Encoding garantidos para o Alpine
        full_cmd = f"cd {self.project_root_linux} && export PYTHONPATH=. && export PYTHONIOENCODING=utf-8 && python3 -m doxoade {cmd_args}"
        enc = base64.b64encode(full_cmd.encode()).decode()
        if "check" in cmd_args or "canonize" in cmd_args:
            timeout = 180 
        try:
            res = subprocess.run(["wsl", "-d", self.distro, "sh", "-c", f"echo {enc} | base64 -d | sh"], 
                                 capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "TIMEOUT"

@click.group('lab')
def lab_group():
    """🧪 Nexus Lab: Sandbox de alta segurança."""
    pass

@lab_group.command('run-suite')
@click.option('--distro', default='doxlinux')
def lab_run_suite(distro):
    """🚀 Mission Suite: Executa cenários programados de alto impacto."""
    lab = NexusLab(distro)
    _sep("PREPARANDO SANDBOX")
    lab.sync()
    
    _sep("EXECUTANDO MISSÕES CRÍTICAS")
    
    passed = 0
    for titulo, cmd in MISSOES_NEXUS:
        t0 = time.time()
        click.echo(f"🎯 {Fore.CYAN}{titulo.ljust(25)}{Style.RESET_ALL} ", nl=False)
        
        code, out, err = lab.run(cmd)
        dur = time.time() - t0
        
        if code == 0:
            click.secho(f"PASS ({dur:.2f}s)", fg="green", bold=True)
            passed += 1
            # Mostra as duas últimas linhas do sucesso para confirmar que houve saída real
            last_lines = "\n".join(out.strip().splitlines()[-2:])
            if last_lines:
                click.echo(f"   {Style.DIM}{last_lines}{Style.RESET_ALL}")
        else:
            click.secho(f"FAIL ({dur:.2f}s)", fg="red", bold=True)
            relevant_error = err.strip().splitlines()[-1] if err else "Erro silencioso ou Crash"
            click.echo(f"   {Fore.YELLOW}└─ Fatal: {relevant_error}{Style.RESET_ALL}")

    _sep("RELATÓRIO DE MISSÃO")
    color = "green" if passed == len(MISSOES_NEXUS) else "red"
    click.secho(f"Sucesso: {passed}/{len(MISSOES_NEXUS)} missões cumpridas.", fg=color, bold=True)

@lab_group.command('bulk-test')
@click.option('--distro', default='doxlinux')
def lab_bulk_test(distro):
    """(Legado) Varredura de carga para verificar entrypoints."""
    from doxoade.cli import cli
    lab = NexusLab(distro)
    click.echo("🔄 Sincronizando Snapshot...")
    lab.sync()

    all_cmds = []
    def collect(group, prefix=""):
        ctx = click.Context(group)
        for name in group.list_commands(ctx):
            full = f"{prefix} {name}".strip()
            all_cmds.append(full)
            sub = group.get_command(ctx, name)
            if isinstance(sub, click.Group): collect(sub, full)
    collect(cli)

    _sep(f"AUDITANDO {len(all_cmds)} COMANDOS NO ALPINE")
    results = []
    with click.progressbar(all_cmds) as bar:
        for cmd in bar:
            args = VETORES_REAIS.get(cmd, "--help")
            code, out, err = lab.run(f"{cmd} {args}")
            sample = (out.strip() if out else err.strip()).replace('\n', ' ')[:50]
            results.append({"cmd": cmd, "code": code, "sample": sample, "err": err})

    for r in results:
        color = Fore.GREEN if r['code'] == 0 else Fore.RED
        if r['code'] != 0:
            click.echo(f"{color}✘ {r['cmd'].ljust(30)}{Style.RESET_ALL} | {r['err'].splitlines()[-1] if r['err'] else 'Error'}")
        else:
            click.echo(f"{Fore.GREEN}✔ {r['cmd'].ljust(30)}{Style.RESET_ALL} | {r['sample']}...")

    passed = sum(1 for r in results if r['code'] == 0)
    _sep(f"SAÚDE: {passed}/{len(all_cmds)}")

@lab_group.command('bootstrap')
@click.option('--distro', default='doxlinux')
def lab_bootstrap(distro):
    """Garante todas as dependências no Alpine (incluindo Web e AST)."""
    lab = NexusLab(distro)
    # Adicionado: py3-beautifulsoup4, py3-requests, py3-toml, py3-packaging
    pkgs = [
        "rsync", "python3", "py3-pip", "build-base", "py3-click", 
        "py3-colorama", "py3-psutil", "py3-rich", "py3-yaml", 
        "py3-pathspec", "py3-beautifulsoup4", "py3-requests", "py3-toml"
    ]
    repo = "--repository=http://dl-cdn.alpinelinux.org/alpine/v3.20/main --repository=http://dl-cdn.alpinelinux.org/alpine/v3.20/community"
    click.echo("🔧 Provisionando ambiente completo...")
    subprocess.run(["wsl", "-d", distro, "-u", "root", "sh", "-c", f"apk add --no-cache {repo} {' '.join(pkgs)}"])
    # Esprima e CSSUtils geralmente precisam de pip no Alpine
    subprocess.run(["wsl", "-d", distro, "sh", "-c", "pip install esprima cssutils --break-system-packages"], capture_output=True)

@lab_group.command('deep-test')
@click.option('--distro', default='doxlinux')
def lab_deep_test_legacy(distro):
    ctx = click.get_current_context()
    ctx.invoke(lab_bulk_test, distro=distro)