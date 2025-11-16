# doxoade/commands/python.py
import sys
import os
import subprocess
import webbrowser
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

# URL oficial para a versão específica do Python.
PYTHON_WINDOWS_URL = "https://www.python.org/downloads/release/python-3124/"

def _install_for_termux(logger):
    """Executa os comandos de instalação do Python para o ambiente Termux."""
    click.echo(Fore.CYAN + "Ambiente Termux detectado. Iniciando a instalação do Python...")
    
    try:
        # É uma boa prática sempre atualizar os pacotes antes de instalar
        click.echo(Fore.WHITE + "   > Atualizando a lista de pacotes (pkg update)...")
        update_result = subprocess.run(
            ['pkg', 'update', '-y'], 
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if update_result.returncode != 0:
            logger.add_finding("WARNING", "Falha ao executar 'pkg update'.", category="INSTALL", details=update_result.stderr)
            click.echo(Fore.YELLOW + "     Aviso: Não foi possível atualizar a lista de pacotes. Continuando com a instalação...")
        
        # Instala o pacote do Python
        click.echo(Fore.WHITE + "   > Instalando o pacote 'python' (pkg install python)...")
        install_result = subprocess.run(
            ['pkg', 'install', 'python', '-y'], 
            capture_output=True, text=True, check=True, encoding='utf-8', errors='replace'
        )
        
        logger.add_finding("INFO", "Python instalado com sucesso via pkg.", category="INSTALL", details=install_result.stdout)
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUCESSO] Python e Pip foram instalados no Termux.")
        click.echo(Fore.WHITE + "Reinicie o Termux e execute 'python --version' para confirmar.")

    except FileNotFoundError:
        msg = "'pkg' não encontrado. Este comando parece não estar rodando em um ambiente Termux padrão."
        logger.add_finding("ERROR", msg, category="INSTALL")
        click.echo(Fore.RED + f"[ERRO] {msg}")
    except subprocess.CalledProcessError as e:
        msg = "O processo de instalação falhou."
        logger.add_finding("ERROR", msg, category="INSTALL", details=e.stderr)
        click.echo(Fore.RED + f"[ERRO] {msg}")
        click.echo(Fore.WHITE + e.stderr)
    except Exception as e:
        logger.add_finding("CRITICAL", "Um erro inesperado ocorreu durante a instalação.", category="INSTALL", details=str(e))
        click.echo(Fore.RED + f"[ERRO INESPERADO] {e}")


@click.command('python')
@click.pass_context
def python(ctx):
    """Ajuda na instalação do Python para Windows ou Termux."""
    arguments = ctx.params
    with ExecutionLogger('python', '.', arguments) as logger:
        
        # Lógica para Windows
        if sys.platform == "win32":
            click.echo(Fore.CYAN + "Ambiente Windows detectado.")
            click.echo(Fore.WHITE + "Abrindo o navegador na página de download do Python 3.12.4 (64-bit)...")
            try:
                webbrowser.open(PYTHON_WINDOWS_URL)
                logger.add_finding("INFO", "Página de download do Python aberta para Windows.", category="INSTALL")
                click.echo(Fore.GREEN + "Navegador aberto. Por favor, baixe e execute o instalador 'Windows installer (64-bit)'.")
                click.echo(Fore.YELLOW + "Lembre-se de marcar a opção 'Add Python to PATH' durante a instalação!")
            except Exception as e:
                logger.add_finding("ERROR", "Não foi possível abrir o navegador.", category="INSTALL", details=str(e))
                click.echo(Fore.RED + f"[ERRO] Não foi possível abrir o navegador. Por favor, acesse manualmente:\n{PYTHON_WINDOWS_URL}")

        # Lógica para Termux/Linux
        elif 'linux' in sys.platform or 'android' in sys.platform:
            # A variável de ambiente 'TERMUX_VERSION' é um indicador confiável
            if 'TERMUX_VERSION' in os.environ:
                _install_for_termux(logger)
            else:
                msg = "Ambiente Linux detectado, mas não é o Termux. A instalação automática não é suportada para esta distribuição."
                details = "Por favor, use o gerenciador de pacotes do seu sistema (ex: 'sudo apt install python3 python3-pip')."
                logger.add_finding("INFO", msg, category="INSTALL", details=details)
                click.echo(Fore.YELLOW + msg)
                click.echo(Fore.WHITE + details)
        
        # Outros sistemas (ex: macOS)
        else:
            msg = f"Sistema operacional '{sys.platform}' não suportado para instalação automática."
            logger.add_finding("WARNING", msg, category="INSTALL")
            click.echo(Fore.YELLOW + msg)