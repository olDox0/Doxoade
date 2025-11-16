# install.py (Versão Final e Limpa)
import sys
import os
import subprocess
#import platform
from colorama import init, Fore, Style

# Inicializa o colorama
init(autoreset=True)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def print_header(message): print(Style.BRIGHT + Fore.CYAN + f"\n--- {message} ---")
def print_success(message): print(Fore.GREEN + f"[OK] {message}")
def print_warning(message): print(Fore.YELLOW + f"[AVISO] {message}")
def print_error(message): sys.exit(Fore.RED + f"[ERRO] {message}")

def run_pip_install():
    """Executa 'pip install -e .' de forma interativa."""
    try:
        # Usa o mesmo Python que está executando o script de instalação
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", PROJECT_ROOT],
            check=True
        )
        return True
    except (subprocess.CalledProcessError, KeyboardInterrupt):
        return False

def main():
    print_header("Instalador Doxoade para Windows")

    # Passo 1: Instalação via pip
    if not run_pip_install():
        print_error("A instalação via pip falhou. Corrija os erros acima e tente novamente.")
    
    print_success("Doxoade instalado com sucesso em modo editável.")

    # Passo 2: Verificação e guia do PATH
    print_header("Verificando Acesso Universal (PATH)")
    
    # O caminho correto que DEVE estar no PATH
    scripts_path = os.path.join(PROJECT_ROOT, 'venv', 'Scripts')
    doxoade_exe_path = os.path.join(scripts_path, 'doxoade.exe')

    try:
        result = subprocess.run(['where', 'doxoade'], check=True, capture_output=True, text=True)
        found_paths = result.stdout.strip().splitlines()
        
        if any(os.path.normcase(p) == os.path.normcase(doxoade_exe_path) for p in found_paths):
            print_success(f"O comando 'doxoade' está corretamente configurado no seu PATH:\n    {doxoade_exe_path}")
            if len(found_paths) > 1:
                print_warning("Múltiplas versões do 'doxoade' foram encontradas. Isso pode causar conflitos.")
                print("Certifique-se de que o caminho correto tenha prioridade no seu PATH.")
        else:
            print_warning(f"Um 'doxoade' foi encontrado, mas não é o da instalação atual: {found_paths[0]}")
            print_warning(f"Por favor, ajuste seu PATH para priorizar: {scripts_path}")

    except (FileNotFoundError, subprocess.CalledProcessError):
        print_warning("O comando 'doxoade' não foi encontrado no seu PATH.")
        print("   > Para concluir, adicione o seguinte diretório ao seu PATH do sistema:")
        print(Fore.YELLOW + f"     {scripts_path}")
        print("   > Depois, reinicie completamente seu terminal.")

    print(Style.BRIGHT + Fore.CYAN + "\n--- Instalação Concluída! ---")

if __name__ == "__main__":
    main()