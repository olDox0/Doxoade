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

def run_command(command):
    """Executa um comando e retorna o resultado."""
    try:
        # Usamos sys.executable para garantir que estamos usando o Python correto
        return subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] O comando falhou. Código de saída: {e.returncode}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        return e
    except FileNotFoundError:
        print(f"[ERRO] Comando '{command[0]}' não encontrado.")
        return None

print("--- Iniciando a instalação do Doxoade ---")

# O comando correto para instalar um projeto com pyproject.toml
# Usa o pip do python que está executando o script.
command = [sys.executable, "-m", "pip", "install", "-e", "."]

print(f"Executando: {' '.join(command)}")
result = run_command(command)

if result and result.returncode == 0:
    print("\n[SUCESSO] Doxoade instalado com sucesso em modo editável.")
    print("O comando 'doxoade' agora deve estar disponível no seu sistema.")
else:
    print("\n[FALHA] A instalação do Doxoade falhou.")

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
    print_header("Iniciando a instalação de sistema da Doxoade")
    
    # --- Utilitario 1: Instalar dependências e o pacote ---
    python_exe = sys.executable
    
    # A MUDANÇA CRÍTICA: Construir o caminho completo para requirements.txt
    requirements_path = os.path.join(PROJECT_ROOT, 'requirements.txt')

    print_header("Passo 1: Instalando dependências...")
    run_command([python_exe, "-m", "pip", "install", "-r", requirements_path], "Falha ao instalar dependências.")
    print_success("Dependências instaladas com sucesso.")

    print_header("Passo 2: Instalando a Doxoade...")
    # A MUDANÇA CRÍTICA: Executar o pip install a partir da raiz do projeto
    run_command([python_exe, "-m", "pip", "install", "--force-reinstall", "."], "Falha ao instalar o pacote Doxoade.", working_directory=PROJECT_ROOT)
    print_success("Doxoade instalada como um pacote de sistema.")

    # --- Utilitario 2: Configurar o PATH ---
    print_header("Passo 3: Verificando a acessibilidade do comando...")
    scripts_path = get_scripts_path(python_exe)
    
    if platform.system() == "Windows":
        if not _add_to_path_windows(scripts_path):
            print_warning("Ação manual necessária para concluir a instalação:")
            print("1. Pesquise por 'Editar as variáveis de ambiente do sistema' e abra.")
            print("2. Clique em 'Variáveis de Ambiente...'.")
            print("3. Em 'Variáveis de sistema', selecione 'Path' e clique em 'Editar...'.")
            print("4. Clique em 'Novo' e cole o seguinte caminho:")
            print(f"   {scripts_path}")
    else: # Linux, macOS, Termux
        shell_config_file = ""
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            shell_config_file = "~/.zshrc"
        elif "bash" in shell:
            shell_config_file = "~/.bashrc"
        elif "fish" in shell:
            shell_config_file = "~/.config/fish/config.fish"
            
        print_warning("Ação manual necessária para concluir a instalação:")
        if shell_config_file:
            print(f"1. Adicione a seguinte linha ao seu arquivo de configuração do shell ({shell_config_file}):")
            if "fish" in shell:
                 print(f"   set -Ua fish_user_paths '{scripts_path}'")
            else:
                 print(f"   export PATH=\"{scripts_path}:$PATH\"")
            print("2. Reinicie seu shell com 'source' ou abrindo um novo terminal.")
        else:
            print("Não foi possível detectar seu shell. Adicione o seguinte diretório ao seu PATH:")
            print(f"   {scripts_path}")


    print("\n--- Instalação Concluída! ---")
    print("IMPORTANTE: FECHE E REABRA SEU TERMINAL para que as alterações no PATH tenham efeito.")

if __name__ == "__main__":
    main()