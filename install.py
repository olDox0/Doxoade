import sys
import os
import subprocess
import platform
from pathlib import Path

# --- Configurações ---
VENV_DIR = "venv"
REQUIREMENTS_FILE = "requirements.txt"
PROJECT_ROOT = Path(__file__).resolve().parent

def print_header(message):
    print(f"\n--- {message} ---")

def print_success(message):
    print(f"[OK] {message}")

def print_warning(message):
    print(f"[AVISO] {message}")

def print_error(message):
    print(f"[ERRO] {message}")
    sys.exit(1)

def run_command(command, cwd=None, error_message=""):
    """Executa um comando e aborta em caso de erro."""
    try:
        # Usamos capture_output=True para suprimir a saída a menos que haja um erro
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore', cwd=cwd)
        return process
    except subprocess.CalledProcessError as e:
        print_error(error_message or f"O comando '{' '.join(command)}' falhou.")
        print(e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print_error(f"Comando não encontrado: {command[0]}. Certifique-se de que o Python está no seu PATH.")
        sys.exit(1)

def get_shell_config_file():
    """Detecta o arquivo de configuração do shell do usuário."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    if "bash" in shell:
        return Path.home() / ".bashrc"
    # Fallback para outros shells baseados em sh
    return Path.home() / ".profile"

def update_shell_config(config_file, venv_bin_path):
    """Adiciona o PATH ao arquivo de configuração do shell de forma idempotente."""
    config_file.touch()
    
    with open(config_file, "r") as f:
        lines = f.readlines()

    # Marcadores
    start_marker = "# START DOXOADE CONFIG\n"
    end_marker = "# END DOXOADE CONFIG\n"
    
    # A nova linha de configuração que queremos garantir que exista
    path_export_line = f'export PATH="{venv_bin_path}:$PATH"\n'
    
    # Lógica de idempotência: se o bloco já existe e está correto, não fazemos nada.
    try:
        start_index = lines.index(start_marker)
        end_index = lines.index(end_marker)
        # Verifica se a linha correta já está dentro do bloco
        if path_export_line in lines[start_index:end_index]:
            print_success(f"Configuração do PATH já está correta em: {config_file}")
            return
    except ValueError:
        # Bloco não encontrado, continuaremos para criá-lo.
        pass

    # Se chegamos aqui, o bloco está ausente ou incorreto, então o reconstruímos.
    print_warning(f"Atualizando a configuração da Doxoade em {config_file}...")
    new_lines = []
    in_doxoade_block = False
    for line in lines:
        if line == start_marker:
            in_doxoade_block = True
            continue
        if line == end_marker:
            in_doxoade_block = False
            continue
        if not in_doxoade_block:
            new_lines.append(line)

    new_lines.append("\n")
    new_lines.append(start_marker)
    new_lines.append(path_export_line)
    new_lines.append(end_marker)

    with open(config_file, "w") as f:
        f.writelines(new_lines)
    
    print_success(f"Configuração do PATH foi escrita em: {config_file}")

def main():
    print_header("Iniciando a instalação robusta da Doxoade")

    # Passo 1: Criar o Ambiente Virtual
    if not os.path.isdir(VENV_DIR):
        print_header("Passo 1: Criando Ambiente Virtual")
        run_command([sys.executable, "-m", "venv", VENV_DIR], error_message="Falha ao criar o ambiente virtual.")
        print_success(f"Ambiente virtual '{VENV_DIR}' criado.")
    else:
        print_success("Ambiente virtual já existente.")

    # Passo 2: Determinar o Caminho do Python do Venv
    if platform.system() == "Windows":
        venv_python = os.path.join(PROJECT_ROOT, VENV_DIR, 'Scripts', 'python.exe')
    else:
        venv_python = os.path.join(PROJECT_ROOT, VENV_DIR, 'bin', 'python')

    # Passo 3: Instalar Dependências no Venv
    print_header("Passo 2: Instalando dependências no venv")
    run_command([venv_python, "-m", "pip", "install", "--upgrade", "pip"], error_message="Falha ao atualizar o pip.")
    run_command([venv_python, "-m", "pip", "install", "-r", REQUIREMENTS_FILE], error_message="Falha ao instalar as dependências do requirements.txt.")
    print_success("Dependências instaladas com sucesso.")

    # Passo 4: Instalar a Doxoade em Modo Editável
    print_header("Passo 3: Instalando a Doxoade")
    run_command([venv_python, "-m", "pip", "install", "-e", "."], error_message="Falha ao instalar a Doxoade.")
    print_success("Doxoade instalada com sucesso no ambiente virtual.")

    # Passo 5: Configuração Universal Automatizada
    print_header("Passo 4: Configurando o Acesso Universal")
    if platform.system() == "Windows":
        # No Windows, a modificação do PATH é mais complexa e perigosa. Guiar é mais seguro.
        venv_scripts_path = PROJECT_ROOT / VENV_DIR / "Scripts"
        print_warning("Ação manual necessária para concluir a instalação no Windows:")
        print("1. Pesquise por 'Editar as variáveis de ambiente do sistema' e abra.")
        print("2. Clique em 'Variáveis de Ambiente...'.")
        print("3. Em 'Variáveis de usuário', selecione 'Path' e clique em 'Editar...'.")
        print("4. Clique em 'Novo' e cole o seguinte caminho:")
        print(f"   {venv_scripts_path}")
    else: # Linux, macOS, Termux - Automação Segura
        venv_bin_path = PROJECT_ROOT / VENV_DIR / "bin"
        config_file = get_shell_config_file()
        update_shell_config(config_file, venv_bin_path)

    print("\n--- Instalação Concluída! ---")
    print("IMPORTANTE: FECHE E REABRA SEU TERMINAL (ou execute 'source ~/.bashrc') para que as mudanças tenham efeito.")

if __name__ == "__main__":
    main()