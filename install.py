# -*- coding: utf-8 -*-
"""
Doxoade Universal Installer - Chief Gold Edition.
Projetado para instalação segura e resiliente em Windows, Linux e Android (Termux).
Conformidade: MPoT-7, PASC-6.3, Aegis-Protocol.
"""

import sys
import os
import shutil
from subprocess import run, CalledProcessError  # nosec
from colorama import init, Fore, Style

# Inicializa o colorama
init(autoreset=True)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def print_header(message: str):
    """Exibe cabeçalhos destacados no terminal (MPoT-4)."""
    print(Style.BRIGHT + Fore.CYAN + f"\n--- {message} ---")

def print_success(message: str):
    """Exibe mensagens de sucesso confirmadas (MPoT-4)."""
    print(Fore.GREEN + f"[OK] {message}")

def print_warning(message: str):
    """Exibe avisos que requerem atenção do usuário (MPoT-4)."""
    print(Fore.YELLOW + f"[AVISO] {message}")

def print_error(message: str):
    """Finaliza a execução em caso de falha crítica (MPoT-15)."""
    sys.exit(Fore.RED + f"[ERRO] {message}")

def check_termux_environment() -> bool:
    """Detecta ambiente Termux e valida ferramentas de build para ARM."""
    is_termux = "com.termux" in sys.executable or os.path.exists("/data/data/com.termux")
    if is_termux:
        print_header("Ambiente Termux (Android/ARM) Detectado")
        
        # Lista de binários vitais para evitar o erro que você teve
        required_tools = ["clang", "cmake", "ninja"]
        missing = [tool for tool in required_tools if not shutil.which(tool)]
        
        if missing:
            print(Fore.RED + f"[CRÍTICO] Ferramentas de build ausentes: {', '.join(missing)}")
            print(Fore.YELLOW + "Para corrigir, execute:")
            print(Fore.CYAN + f"    pkg install {' '.join(missing)} ndk-sysroot python-numpy")
            print_error("Instalação abortada para prevenir falha de compilação em ARM.")
            
        print_success("Ferramentas de build nativas detectadas.")
    return is_termux

def run_pip_install() -> bool:
    """Executa a instalação em modo editável (Verbose Lookup)."""
    try:
        # PASC-6.2: Chamada direta da função 'run' importada explicitamente
        run(
            [sys.executable, "-m", "pip", "install", "-e", PROJECT_ROOT],
            check=True,
            shell=False  # nosec
        )
        return True
    except (CalledProcessError, KeyboardInterrupt):
        return False

def main():
    """Orquestrador do bootstrapping (MPoT-17)."""
    config_exists = os.path.exists(os.path.join(PROJECT_ROOT, "pyproject.toml"))
    if not config_exists:
        raise RuntimeError("Integridade Falhou: pyproject.toml não encontrado na raiz.")

    check_termux_environment()
    
    label = "Universal" if not os.name == 'nt' else "Windows"
    print_header(f"Instalador Doxoade {label} (Chief-Gold)")

    if not run_pip_install():
        print_error("A instalação falhou. Verifique logs do pip.")
    
    print_success("Doxoade instalado em modo editável.")

    print_header("Verificando Rastreabilidade (PATH)")
    
    scripts_dir = "Scripts" if os.name == 'nt' else "bin"
    bin_name = "doxoade.exe" if os.name == 'nt' else "doxoade"
    
    scripts_path = os.path.join(PROJECT_ROOT, 'venv', scripts_dir)
    target_exe = os.path.join(scripts_path, bin_name)

    found_path = shutil.which("doxoade")

    if found_path:
        if os.path.normcase(found_path) == os.path.normcase(target_exe):
            print_success(f"Binário detectado e verificado:\n    {found_path}")
        else:
            print_warning(f"Conflito detectado: {found_path}")
            print(f"   > Priorize a nova instalação no PATH: {scripts_path}")
    else:
        print_warning("Binário não mapeado no PATH global.")
        print(f"   > Adicione manualmente: {scripts_path}")

    print(Style.BRIGHT + Fore.CYAN + "\n--- Instalação Concluída! ---")

if __name__ == "__main__":
    main()