# DEV.V10-20251021. >>>
# doxoade/commands/rebuild.py
# atualizado em 2025/10/21 - Versão do projeto 42(Ver), Versão da função 1.0(Fnc).
# Descrição: Novo comando 'rebuild' (anteriormente phoenix/cleaning) que automatiza a destruição
# e reconstrução completa de um ambiente virtual de um projeto a partir do requirements.txt.

import sys
import os
import subprocess
import shutil

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _get_venv_python_executable

def _remove_venv(path, logger):
    """Remove de forma segura o diretório venv."""
    venv_path = os.path.join(path, 'venv')
    if not os.path.isdir(venv_path):
        click.echo(Fore.YELLOW + "   > Diretório 'venv' não encontrado. Pulando remoção.")
        return True
    
    try:
        click.echo(Fore.WHITE + "   > Removendo diretório 'venv' existente...")
        shutil.rmtree(venv_path)
        logger.add_finding('info', "Diretório 'venv' antigo removido.")
        click.echo(Fore.GREEN + "   > [OK] 'venv' removido.")
        return True
    except OSError as e:
        msg = f"Não foi possível remover o diretório 'venv': {e}"
        details = "Causa comum: arquivos dentro do venv estão em uso por outro terminal ou processo."
        logger.add_finding('error', msg, details=details)
        click.echo(Fore.RED + f"   > [FALHA] {msg}\n     {details}")
        return False

def _create_venv(path, logger):
    """Cria um novo ambiente virtual."""
    try:
        click.echo(Fore.WHITE + "   > Criando novo ambiente virtual...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True, capture_output=True, cwd=path)
        logger.add_finding('info', "Novo 'venv' criado com sucesso.")
        click.echo(Fore.GREEN + "   > [OK] Novo 'venv' criado.")
        return True
    except subprocess.CalledProcessError as e:
        msg = "Falha ao criar o novo ambiente virtual."
        logger.add_finding('error', msg, details=e.stderr.decode('utf-8', 'ignore'))
        click.echo(Fore.RED + f"   > [FALHA] {msg}")
        return False

def _install_requirements(path, logger):
    """Instala dependências do requirements.txt."""
    req_file = os.path.join(path, 'requirements.txt')
    if not os.path.isfile(req_file):
        click.echo(Fore.YELLOW + "   > 'requirements.txt' não encontrado. Nenhuma dependência para instalar.")
        return True

    venv_python = _get_venv_python_executable()
    if not venv_python:
        logger.add_finding('error', "Não foi possível encontrar o Python do novo venv.")
        click.echo(Fore.RED + "   > [FALHA] Não foi possível encontrar o executável Python do novo venv.")
        return False
        
    try:
        click.echo(Fore.WHITE + "   > Instalando dependências do 'requirements.txt'...")
        cmd = [venv_python, '-m', 'pip', 'install', '-r', req_file]
        subprocess.run(cmd, check=True, capture_output=True, cwd=path)
        logger.add_finding('info', "Dependências do requirements.txt instaladas.")
        click.echo(Fore.GREEN + "   > [OK] Dependências instaladas.")
        return True
    except subprocess.CalledProcessError as e:
        msg = "Falha ao instalar dependências via pip."
        logger.add_finding('error', msg, details=e.stderr.decode('utf-8', 'ignore'))
        click.echo(Fore.RED + f"   > [FALHA] {msg}")
        click.echo(Fore.RED + Style.DIM + e.stderr.decode('utf-8', 'ignore'))
        return False

@click.command('rebuild')
@click.pass_context
@click.option('--force', '-y', is_flag=True, help="Executa a reconstrução sem pedir confirmação.")
def rebuild(ctx, force):
    """[DESTRUTIVO] Recria completamente o ambiente virtual de um projeto."""
    arguments = ctx.params
    path = '.'
    with ExecutionLogger('rebuild', path, arguments) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + "--- [REBUILD] Reconstrução de Ambiente ---")
        click.echo(Fore.RED + Style.BRIGHT + "[AVISO] Esta ação irá DELETAR PERMANENTEMENTE seu diretório 'venv'.")
        
        if not force and not click.confirm(Fore.YELLOW + "Você tem certeza que deseja continuar?"):
            click.echo("Operação cancelada."); return
        
        # --- Utilitário 1: Orquestrar a Reconstrução ---
        # Cada etapa verifica o sucesso da anterior antes de prosseguir.
        click.echo(Fore.YELLOW + "\n--- Passo 1: Limpeza do Ambiente Antigo ---")
        if not _remove_venv(path, logger): sys.exit(1)
        
        click.echo(Fore.YELLOW + "\n--- Passo 2: Criação do Novo Ambiente ---")
        if not _create_venv(path, logger): sys.exit(1)

        click.echo(Fore.YELLOW + "\n--- Passo 3: Sincronização de Dependências ---")
        if not _install_requirements(path, logger): sys.exit(1)
        
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUCESSO] Ambiente reconstruído com sucesso.")
        click.echo(Fore.WHITE + "Por favor, ative o novo ambiente para continuar:")
        if os.name == 'nt':
            click.echo(Fore.CYAN + "  .\\venv\\Scripts\\activate")
        else:
            click.echo(Fore.CYAN + "  source venv/bin/activate")