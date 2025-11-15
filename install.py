# DEV.V10-20251021. >>>
# atualizado em 2025/10/21 - Versão do projeto 42(Ver), Versão da função 2.1(Fnc).
# Descrição: Corrige o bug "No such file or directory" ao fazer todos os caminhos de arquivo (requirements.txt, etc.)
# serem relativos à localização do próprio script 'install.py', garantindo que ele possa ser executado de qualquer lugar.
import sys
import os
import subprocess
import platform
#import shutil

# --- Configurações ---
# A MUDANÇA CRÍTICA: O PROJECT_ROOT agora é a localização do script.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Funções Auxiliares de Saída ---
def print_header(message): print(f"\n--- {message} ---")
def print_success(message): print(f"[OK] {message}")
def print_warning(message): print(f"[AVISO] {message}")
def print_error(message, details=""):
    print(f"[ERRO] {message}")
    if details: print(details)
    sys.exit(1)

def run_command_interactive(command):
    """
    Executa um comando e transmite sua saída (stdout/stderr) em tempo real.
    Retorna o código de saída do processo.
    """
    try:
        process = subprocess.run(
            command, check=True, text=True, encoding='utf-8'
        )
        return process.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n[ERRO] O comando falhou com o código de saída: {e.returncode}", file=sys.stderr)
        return e.returncode
    except FileNotFoundError:
        print(f"[ERRO] Comando '{command[0]}' não encontrado.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[AVISO] Instalação interrompida pelo usuário.", file=sys.stderr)
        return 130

def get_scripts_path(python_executable):
    """Encontra o diretório 'Scripts' ou 'bin' de um interpretador Python."""
    if platform.system() == "Windows":
        return os.path.join(os.path.dirname(python_executable), "Scripts")
    else:
        return os.path.join(os.path.dirname(python_executable), "bin")

def _add_to_path_windows(scripts_path):
    """Tenta adicionar o caminho ao PATH do sistema no Windows usando setx."""
    print(f"Tentando adicionar '{scripts_path}' ao PATH do sistema (requer privilégios de admin)...")
    try:
        current_path = subprocess.check_output('echo %PATH%', shell=True).decode().strip()
        if scripts_path in current_path:
            print_success("O caminho já está configurado no PATH do sistema.")
            return True
        
        command = ['setx', '/M', 'PATH', f'{current_path};{scripts_path}']
        subprocess.run(command, capture_output=True, text=True, check=True)
        print_success("PATH do sistema atualizado com sucesso!")
        return True
    except subprocess.CalledProcessError:
        print_warning("Falha ao modificar o PATH automaticamente.")
        print("   > Causa Provável: Este script não foi executado como Administrador.")
        return False
        
def main():
    print_header("Iniciando a instalação do Doxoade")

    # --- Passo 1: Instalar o projeto e suas dependências ---
    # O comando correto para instalar um projeto moderno com pyproject.toml
    command = [sys.executable, "-m", "pip", "install", "-e", "."]
    print(f"Executando: {' '.join(command)}\n")
    
    exit_code = run_command_interactive(command)

    if exit_code != 0:
        print_error("A instalação do Doxoade não foi concluída.")
        sys.exit(exit_code)

    print_success("Doxoade instalado com sucesso em modo editável.")

    # --- Passo 2: Ajudar o usuário a configurar o PATH (se necessário) ---
    print_header("Passo 2: Verificando a acessibilidade do comando")
    scripts_path = get_scripts_path(sys.executable)
    
    # Lógica para verificar se o comando já está acessível
    try:
        subprocess.run(['doxoade', '--version'], check=True, capture_output=True)
        print_success("O comando 'doxoade' já está acessível no seu PATH.")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print_warning("O comando 'doxoade' pode não estar acessível globalmente.")
        if platform.system() == "Windows":
            print("   > Para torná-lo acessível, adicione o seguinte diretório ao seu PATH do sistema:")
            print(f"     {scripts_path}")
        else: # Linux, macOS, Termux
            shell = os.environ.get("SHELL", "")
            if "bash" in shell or "zsh" in shell:
                config_file = "~/.bashrc" if "bash" in shell else "~/.zshrc"
                print(f"   > Para torná-lo acessível, adicione a seguinte linha ao seu arquivo '{config_file}':")
                print(f"     export PATH=\"{scripts_path}:$PATH\"")
                print(f"   > Depois, reinicie seu terminal ou execute: source {config_file}")
            else:
                print("   > Para torná-lo acessível, adicione o seguinte diretório ao seu PATH:")
                print(f"     {scripts_path}")

    print("\n--- Instalação Concluída! ---")
    print("Se você precisou alterar o PATH, lembre-se de reiniciar seu terminal.")

if __name__ == "__main__":
    main()