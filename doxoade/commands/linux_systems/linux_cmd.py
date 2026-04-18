import click
import subprocess
import os
import sys
import threading
import time
from doxoade.tools.doxcolors import colors

PS_BASE = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command']

def get_asset(filename):
    """Localiza ativos subindo 4 níveis até a raiz do projeto."""
    p = os.path.abspath(__file__)
    for _ in range(4): p = os.path.dirname(p)
    return os.path.join(p, 'assets', filename)

def run_win_cmd(cmd_list):
    """Executa comando windows e decodifica com CP850 (Brasil) seguro."""
    proc = subprocess.run(cmd_list, capture_output=True)
    try:
        return proc.stdout.decode('cp850').strip()
    except:
        return proc.stdout.decode('utf-8', errors='replace').strip()

# --- DEFINIÇÃO DO GRUPO (O que causou o erro) ---
@click.group()
def linux_group():
    """Gerenciamento de subsistemas Linux (Doxoade Core)."""
    pass

class DeployUI(threading.Thread):
    """Thread de animação para o Deploy WSL."""
    def __init__(self, frames, message="Deploying"):
        super().__init__(daemon=True)
        self.frames = frames
        self.message = message
        self.running = True
        self.canvas_height = max(len(f.split('\n')) for f in frames) if frames else 0
        self.up_cmd = f"\x1b[{self.canvas_height + 1}A"

    def run(self):
        frame_idx = 0
        sys.stdout.write("\x1b[?25l\n" + ("\n" * self.canvas_height))
        while self.running:
            ui = [self.up_cmd]
            ui.append(f"\r\x1b[K {colors.Fore.CYAN}» {self.message}...{colors.Style.RESET_ALL}\n")
            if self.frames:
                ui.append(self.frames[frame_idx] + "\n")
                frame_idx = (frame_idx + 1) % len(self.frames)
            sys.stdout.write("".join(ui))
            sys.stdout.flush()
            time.sleep(0.08)
        
        # Limpeza final
        sys.stdout.write(self.up_cmd + "\x1b[K" + f" {colors.Fore.SUCCESS}✔ {self.message} Finalizado.{colors.Style.RESET_ALL}\n")
        for _ in range(self.canvas_height): sys.stdout.write("\x1b[2K\n")
        sys.stdout.write(f"\x1b[{self.canvas_height}A\x1b[?25h")
        sys.stdout.flush()

@linux_group.command(name="wsl")
@click.argument('tar_gz_path')
@click.option('--name', default='ArchDev')
@click.option('--path', default='') # Vamos deixar vazio para o padrão ser o home
def wsl_import(tar_gz_path, name, path):
    """Importa a distro com captura total de logs."""
    
    # Se não passou path, cria uma pasta segura nos documentos do usuário
    if not path:
        path = os.path.join(os.environ['USERPROFILE'], 'Documents', 'WSL', name)
    
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        
    abs_tar = os.path.abspath(tar_gz_path)
    
    click.echo(f"[*] Tentando registro: {name}")
    click.echo(f"[*] Origem: {abs_tar}")
    click.echo(f"[*] Destino: {path}")
    
    # Comando formatado como string para shell=True (Mais estável no Windows)
    cmd = f'wsl.exe --import {name} "{path}" "{abs_tar}" --version 2'
    
    try:
        # Usamos stderr=subprocess.STDOUT para mesclar as saídas e não perder mensagens
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        click.echo(result.stdout)
        click.secho(f"[OK] Distro {name} registrada!", fg='green')
    except subprocess.CalledProcessError as e:
        # Agora o erro NÃO vira vazio
        full_error = e.output if e.output else e.stderr
        click.secho(f"\n[FALHA NO WINDOWS KERNEL]", fg='red', bold=True)
        click.echo(full_error)
        
        # Dica de ouro para o usuário
        if "0x80070005" in full_error:
            click.secho("DICA: Erro de Acesso Negado. Tente rodar como Administrador.", fg='yellow')
        elif "0x80040324" in full_error:
             click.secho("DICA: O WSL2 requer virtualização habilitada na BIOS.", fg='yellow')
        elif "HCS_E_SERVICE_NOT_AVAILABLE" in full_error or "0x80040324" in full_error:
                    click.secho("[-] Erro de Serviço HCS: O motor de virtualização não responde.", fg='yellow')
                    click.echo("    SOLUÇÃO: Execute 'wsl --shutdown' e reinicie o seu computador.")
                    click.echo("    Certifique-se que a 'Virtualização' está ativa na BIOS.")
        
        
@linux_group.command(name="setup-dev")
@click.option('--name', required=True)
@click.option('--user', default='doxdev')
def setup_dev(name, user):
    """Configura o ambiente avançado ignorando restrições do Windows."""
    anim_path = get_asset('wsl_deploy.nxa')
    frames = colors.UI.load_animation(anim_path) if os.path.exists(anim_path) else []
    
    ui = DeployUI(frames, message=f"Configurando {name}")
    ui.start()
    
    try:
        # 1. WARM-UP: Garante que o Arch está pronto
        ui.message = "Acordando Kernel Arch"
        subprocess.run(['wsl', '-d', name, '-u', 'root', '--', 'true'], capture_output=True)

        # 2. INJEÇÃO BLINDADA DO WSL.CONF (Sem usar Pipes do PowerShell)
        ui.message = "Injetando wsl.conf"
        # Usamos o printf do linux para escrever o arquivo sem depender do host
        conf_script = f'printf "[boot]\\nsystemd=true\\n\\n[user]\\ndefault={user}\\n" > /etc/wsl.conf'
        res = subprocess.run(['wsl', '-d', name, '-u', 'root', '--', 'sh', '-c', conf_script], capture_output=True)
        
        if res.returncode != 0:
            raise Exception(res.stderr.decode('cp850', errors='replace'))

        # 3. CRIAÇÃO DE USUÁRIO
        ui.message = f"Criando dev: {user}"
        user_script = f"id -u {user} >/dev/null 2>&1 || (useradd -m -G wheel {user} && echo '{user}:1234' | chpasswd)"
        subprocess.run(['wsl', '-d', name, '-u', 'root', '--', 'sh', '-c', user_script], check=True)
        
        # Sudoers
        subprocess.run(['wsl', '-d', name, '-u', 'root', '--', 'sh', '-c', "echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel"], check=True)

        # 4. STACK GRÁFICA E COMPILAÇÃO (O que faltava para o seu GCC)
        ui.message = "Instalando X11, GCC e Python"
        pkg_cmd = "pacman -Syu --noconfirm base-devel libx11 mesa xorg-server-utils python python-pip"
        subprocess.run(['wsl', '-d', name, '-u', 'root', '--', 'sh', '-c', pkg_cmd], capture_output=True)

    except Exception as e:
        sys.stdout.write(f"\n{colors.Fore.ERROR}[FALHA] {e}{colors.Style.RESET_ALL}\n")
    finally:
        ui.running = False
        ui.join()
        click.secho(f"\n[OK] {name} pronto. EXECUTE: wsl --shutdown", fg='yellow')

@linux_group.command(name="check-health")
def check_health():
    """Verifica se o Windows está pronto para o WSL2."""
    click.echo("[*] Iniciando Diagnóstico de Infraestrutura...")
    
    # 1. Verifica Virtualização na BIOS (via systeminfo)
    res = subprocess.run(['systeminfo'], capture_output=True, text=True)
    if "Virtualização habilitada no firmware: Sim" in res.stdout or "Virtualization Enabled In Firmware: Yes" in res.stdout:
        click.secho("[OK] Virtualização na BIOS: ATIVA", fg='green')
    else:
        click.secho("[FALHA] Virtualização na BIOS: DESATIVADA", fg='red')
        click.echo("      -> Vá na BIOS e ative o Intel VT-x ou AMD-V.")

    # 2. Verifica se o BCDEDIT está correto
    res_bcd = subprocess.run(['bcdedit'], capture_output=True, text=True)
    if "hypervisorlaunchtype    Auto" in res_bcd.stdout:
        click.secho("[OK] Hypervisor Launch Type: AUTO", fg='green')
    else:
        click.secho("[!] Hypervisor Launch Type: NÃO CONFIGURADO", fg='yellow')
        click.echo("      -> Execute: bcdedit /set hypervisorlaunchtype auto")
