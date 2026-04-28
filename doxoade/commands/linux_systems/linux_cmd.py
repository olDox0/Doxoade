# -*- coding: utf-8 -*-
import click
import subprocess
import os
import sys
import threading
import time
import winreg
import tempfile
import ctypes
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style, colors
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

def get_vhdx_path(distro_name):
    """Localiza o caminho do VHDX no Registro do Windows."""
    try:
        lxss_path = r"Software\Microsoft\Windows\CurrentVersion\Lxss"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, lxss_path) as key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                guid = winreg.EnumKey(key, i)
                with winreg.OpenKey(key, guid) as subkey:
                    try:
                        name, _ = winreg.QueryValueEx(subkey, "DistributionName")
                        if name.lower() == distro_name.lower():
                            base_path, _ = winreg.QueryValueEx(subkey, "BasePath")
                            return os.path.join(base_path, "ext4.vhdx")
                    except: continue
    except: return None

def run_elevated_diskpart(script_path):
    """Executa o diskpart elevando via CMD (Evita erro de RemoteApp)."""
    # Usamos o ShellExecute no CMD para carregar o ambiente local do sistema
    # O diretório de trabalho é essencial para evitar o 'dummy-entry'
    work_dir = os.path.dirname(script_path)
    params = f'/c "diskpart.exe /s \\"{script_path}\\""'
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "cmd.exe", params, work_dir, 1
    )
    return ret > 32

def run_diskpart_elevated(script_path):
    """Executa o diskpart elevando privilégios via ShellExecuteW."""
    params = f'/s "{script_path}"'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "diskpart.exe", params, None, 1)
    return ret > 32

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

@click.group('wsl', invoke_without_command=True)
@click.option('--distro', '-d', default='doxlinux')
@click.pass_context
def linux_group(ctx, distro):
    if ctx.invoked_subcommand is None:
        os.system(f'start wsl.exe -d {distro}')

@linux_group.command('open')
@click.option('--distro', '-d', default='doxlinux')
def wsl_open(distro):
    """Abre o terminal da distro em uma nova janela."""
    click.echo(f"[*] Invocando terminal {distro}...")
    os.system(f'start wsl.exe -d {distro}')

@linux_group.command('optimize')
@click.option('--name', '-n', default='doxlinux', help='Nome da distro.')
@click.option('--aggressive', is_flag=True, help='Zera blocos vazios para reduzir o VHDX ao máximo.')
def wsl_optimize(name, aggressive):
    """🚀 Otimização Nexus: Redução física real do arquivo VHDX."""
    
    click.secho(f"--- [NEXUS WSL OPTIMIZER] Mantendo {name} ---", fg="cyan", bold=True)

    # 1. Zeragem (Fase Crítica)
    if aggressive:
        click.echo(f"[*] {Fore.YELLOW}Fase 1: Zerando setores órfãos (Modo Turbo)...{Style.RESET_ALL}")
        # O SEGREDO: cat /dev/zero é muito mais rápido que dd no Alpine.
        # SEM capture_output para não travar a RAM do Python.
        wipe_cmd = "cat /dev/zero > /wipefile; sync; rm -f /wipefile"
        
        from doxoade.tools.doxcolors import colors
        with colors.UI.loader(None, interval=0.1) as anim:
            anim.message = "Limpando disco virtual"
            # Rodamos sem capturar saída para o Windows gerenciar o I/O direto
            subprocess.run(["wsl", "-d", name, "-u", "root", "sh", "-c", wipe_cmd], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        click.echo(f"[*] {Fore.YELLOW}Fase 1: Descartando blocos (Trim)...{Style.RESET_ALL}")
        subprocess.run(["wsl", "-d", name, "-u", "root", "fstrim", "-v", "/"], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Localização do VHDX
    vhdx_path = get_vhdx_path(name)
    if not vhdx_path or not os.path.exists(vhdx_path):
        click.secho("❌ Erro: VHDX não localizado.", fg="red")
        return

    size_before = os.path.getsize(vhdx_path) / (1024**3)
    click.echo(f"[*] Disco físico: {size_before:.2f} GB")

    # 3. Shutdown (Sincronizado)
    click.echo(f"[*] {Fore.YELLOW}Fase 2: Encerrando instâncias e liberando arquivo...{Style.RESET_ALL}")
    subprocess.run(["wsl", "--terminate", name], capture_output=True)
    subprocess.run(["wsl", "--shutdown"], capture_output=True)
    time.sleep(5) # Tempo para o Windows soltar o lock

    # 4. Compactação (PowerShell Admin)
    click.echo(f"[*] {Fore.YELLOW}Fase 3: Compactação física (Diskpart)...{Style.RESET_ALL}")
    
    script_content = f'select vdisk file="{vhdx_path}"\nattach vdisk readonly\ncompact vdisk\ndetach vdisk\nexit\n'
    script_path = os.path.join(os.environ['TEMP'], 'dox_compact.txt')
    with open(script_path, 'w') as f: f.write(script_content)

    ps_cmd = f'Start-Process diskpart.exe -ArgumentList "/s {script_path}" -Verb RunAs -Wait'
    
    try:
        # Bypass de execução para evitar erro de política de script do Windows
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], check=True)
    except Exception as e:
        click.secho(f"❌ Falha no Diskpart: {e}", fg="red")
        return
    finally:
        if os.path.exists(script_path): os.remove(script_path)

    # 5. Resultado Final
    click.echo("[*] Validando nova geometria...")
    time.sleep(2)
    size_after = os.path.getsize(vhdx_path) / (1024**3)
    saved_mb = (size_before - size_after) * 1024
    
    click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Otimização Concluída!{Style.RESET_ALL}")
    click.echo(f"   Original : {size_before:.2f} GB")
    click.echo(f"   Final    : {size_after:.2f} GB")
    
    if saved_mb > 5:
        click.secho(f"   Recuperado: {saved_mb:.2f} MB", fg="cyan", bold=True)
    else:
        click.secho("   O disco já estava no limite físico de dados.", fg="white", dim=True)

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
