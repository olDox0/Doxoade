# -*- coding: utf-8 -*-
import click
import subprocess
import os
import sys
import base64
import json
import time
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

# --- HELPERS ---

def _sep(label: str = "", width: int = 60, color: str = "cyan") -> None:
    line = f"─{'─' * (width - 2)}─"
    if label:
        pad = max(0, width - len(label) - 4)
        line = f"─ {label} {'─' * pad}"
    click.secho(line, fg=color)

def get_click_commands(group, prefix="", ctx=None):
    cmds = []
    if ctx is None: ctx = click.Context(group)
    try:
        for name in group.list_commands(ctx):
            full_name = f"{prefix} {name}".strip()
            cmds.append(full_name)
            sub_cmd = group.get_command(ctx, name)
            if isinstance(sub_cmd, click.Group):
                cmds.extend(get_click_commands(sub_cmd, full_name, ctx))
    except: pass
    return cmds

# --- CORE ---

class NexusLab:
    def __init__(self, distro="doxlinux"):
        self.distro = distro
        self.project_root_win = _find_project_root(os.getcwd())
        self.project_root_linux = self._get_linux_path(self.project_root_win)

    def _get_linux_path(self, win_path):
        try:
            return subprocess.check_output(
                ['wsl', '-d', self.distro, 'wslpath', '-a', str(win_path).replace('\\', '/')], 
                text=True, encoding='utf-8'
            ).strip()
        except: return None

    def sync_sandbox(self):
        """Sincronização de alta performance com Barra de Progresso Real."""
        ignores = ['venv', '.git', '__pycache__', '.pytest_cache', 'build', 'dist', '*.egg-info', '.doxoade_cache']
        exclude_args = " ".join([f'--exclude="{p}"' for p in ignores])

        # 1. Limpeza inicial silenciosa
        subprocess.run(["wsl", "-d", self.distro, "-u", "root", "sh", "-c", 
                       "rm -rf /usr/lib/python3*/site-packages/doxoade* /tmp/nexus_audit"], capture_output=True)

        click.secho(f"📦 Preparando Snapshot Nexus...", fg="cyan")
        
        # 2. Comando para contar arquivos (para a barra de progresso ser real)
        count_cmd = f'find "{self.project_root_linux}/" -type f | wc -l'
        try:
            total_files = int(subprocess.check_output(["wsl", "-d", self.distro, "sh", "-c", count_cmd], text=True).strip())
        except:
            total_files = 1000 # Fallback

        # 3. RSYNC com captura de progresso
        # Usamos -i para listar cada arquivo sincronizado
        sync_cmd = f'mkdir -p /tmp/nexus_audit && rsync -amvi --delete {exclude_args} "{self.project_root_linux}/" /tmp/nexus_audit/'
        
        process = subprocess.Popen(["wsl", "-d", self.distro, "sh", "-c", sync_cmd], 
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')

        with click.progressbar(length=total_files, label="🚀 Sincronizando", 
                               fill_char="█", empty_char="░", color="cyan") as bar:
            for line in process.stdout:
                # O rsync com -vi imprime o nome do arquivo quando ele é transferido/checado
                if any(x in line for x in ['<', '>', 'f', 'd']):
                    bar.update(1)
            process.wait()

        click.secho(f"✔ Snapshot estabilizado em /tmp/nexus_audit.", fg="green")
        time.sleep(0.5) # Pausa para o kernel assentar

    def verify_sync(self):
        """Verificação robusta sem base64 (evita problemas de aspas no shell)."""
        # Testamos o import diretamente via PYTHONPATH
        # O segredo: usamos aspas simples externas e duplas internas no shell do Linux
        check_cmd = (
            "export PYTHONPATH=/tmp/nexus_audit && "
            "python3 -c 'import sys, os; sys.path.insert(0, \"/tmp/nexus_audit\"); "
            "import doxoade; print(\"OK|\" + os.path.realpath(doxoade.__file__))'"
        )
        
        try:
            res = subprocess.run(["wsl", "-d", self.distro, "sh", "-c", check_cmd], 
                                 capture_output=True, text=True, encoding='utf-8', timeout=10)
            
            if "OK|" in res.stdout:
                return True, res.stdout.split('|')[1].strip()
            
            error_detail = res.stderr if res.stderr else res.stdout
            return False, error_detail.strip() if error_detail else "Caminho não encontrado no PYTHONPATH"
        except subprocess.TimeoutExpired:
            return False, "Timeout na resposta do Linux"

    def bootstrap(self, force=False):
        """Garante rsync e dependências."""
        check_cmd = "rsync --version > /dev/null 2>&1"
        if subprocess.run(["wsl", "-d", self.distro, "sh", "-c", check_cmd]).returncode != 0 or force:
            click.echo(f"{Fore.YELLOW}🔧 Provisionando ambiente de auditoria (rsync)...{Style.RESET_ALL}")
            pkgs = ["rsync", "python3", "py3-pip", "build-base", "py3-click", "py3-colorama", "py3-psutil", "py3-rich", "py3-yaml"]
            repo = "--repository=http://dl-cdn.alpinelinux.org/alpine/v3.20/main --repository=http://dl-cdn.alpinelinux.org/alpine/v3.20/community"
            subprocess.run(["wsl", "-d", self.distro, "-u", "root", "sh", "-c", f"apk add --no-cache {repo} {' '.join(pkgs)}"])

# --- CLI COMMANDS ---

@click.group('lab')
def lab_group():
    """🧪 Nexus Lab: Sandbox de alta segurança."""
    pass

@lab_group.command('audit-all')
@click.option('--distro', default='doxlinux')
@click.option('--output', type=click.Path(), help='Salva o relatório em JSON.')
def lab_audit_all(distro, output):
    """🔍 Auditoria Total: Executa todos os comandos no Sandbox Linux."""
    from doxoade.cli import cli 
    
    lab = NexusLab(distro)
    lab.bootstrap()
    
    _sep("NEXUS SANDBOX SYNC")
    lab.sync_sandbox()
    
    ok, path = lab.verify_sync()
    if not ok:
        click.secho(f"\n❌ ERRO DE SINCRONIA!", fg="red", bold=True)
        click.echo(f"O Linux está carregando: {Fore.YELLOW}{path}{Style.RESET_ALL}")
        click.echo("Tente rodar: doxoade lab bootstrap --force")
        return
    
    click.secho(f"✅ Sincronia Ativa: {path}", fg="green")
    
    all_cmds = get_click_commands(cli)
    _sep("NEXUS INTEGRITY AUDIT")
    click.echo(f"📋 Testando {len(all_cmds)} comandos...\n")

    results = []
    passed = 0
    
    with click.progressbar(all_cmds, label="Processando Auditoria", 
                           fill_char="█", empty_char="░", color="magenta") as bar:
        for cmd_name in bar:
            t0 = time.time()
            shell_cmd = f"cd /tmp/nexus_audit && export PYTHONPATH=. && python3 -m doxoade {cmd_name} --help"
            enc_cmd = base64.b64encode(shell_cmd.encode('utf-8')).decode()
            wsl_exec = ["wsl", "-d", distro, "sh", "-c", f"echo {enc_cmd} | base64 -d | sh"]
            
            try:
                proc = subprocess.run(wsl_exec, capture_output=True, text=True, 
                                      encoding='utf-8', errors='replace', timeout=15)
                
                status = "OK" if proc.returncode == 0 else "FAIL"
                if proc.returncode == 0: passed += 1
                
                results.append({
                    "command": cmd_name,
                    "status": status,
                    "duration": (time.time() - t0) * 1000,
                    "error": proc.stderr if status == "FAIL" else ""
                })
            except Exception:
                results.append({"command": cmd_name, "status": "TIMEOUT", "duration": 15000, "error": "Timeout"})

    # --- RELATÓRIO FINAL ---
    click.echo("\n" + "─"*60)
    for res in results:
        if res['status'] == "OK":
            click.echo(f"{Fore.GREEN}✔ {res['command'].ljust(35)}{Style.RESET_ALL} | {res['duration']:6.0f}ms")
        else:
            click.echo(f"{Fore.RED}✘ {res['command'].ljust(35)}{Style.RESET_ALL} | {res['duration']:6.0f}ms")
            err = res['error'].split('\n')[0][:70] if res['error'] else "Erro desconhecido"
            click.echo(f"   {Fore.YELLOW}└─ {err}{Style.RESET_ALL}")

    _sep("RESULTADO FINAL")
    score_color = Fore.GREEN if passed == len(all_cmds) else Fore.RED
    click.echo(f"Saúde: {score_color}{passed}/{len(all_cmds)} comandos operacionais{Style.RESET_ALL}")
    
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4, ensure_ascii=False)

@lab_group.command('bootstrap')
@click.option('--distro', default='doxlinux')
@click.option('--force', is_flag=True)
def lab_bootstrap_cmd(distro, force):
    """Instala rsync e pacotes base no Alpine."""
    lab = NexusLab(distro)
    lab.bootstrap(force=force)