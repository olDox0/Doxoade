# -*- coding: utf-8 -*-
"""
Módulo de Reconstrução de Ambiente (Protocolo Fênix).
Automatiza a destruição e recriação do venv a partir do requirements.txt.
Implementa tática de renomeação forçada para contornar bloqueios de arquivo no Windows.
"""

import sys
import os
import subprocess
import shutil
import uuid
# [DOX-UNUSED] from typing import Optional

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _get_venv_python_executable

__version__ = "43.0 Alfa (Resilient-Gold)"

def _remove_venv_resilient(path: str, logger: ExecutionLogger) -> bool:
    """
    Remove o diretório venv de forma resiliente.
    Se a exclusão direta falhar (WinError 5), renomeia a pasta para liberar o caminho.
    """
    if not path or logger is None:
        raise ValueError("Caminho e Logger são obrigatórios para reconstrução.")

    venv_path = os.path.join(path, 'venv')
    if not os.path.isdir(venv_path):
        click.echo(Fore.YELLOW + "   > Venv não encontrado. Pulando limpeza.")
        return True
    
    try:
        click.echo(Fore.WHITE + "   > Removendo diretório 'venv'...")
        shutil.rmtree(venv_path)
        click.echo(Fore.GREEN + "   > [OK] Venv antigo removido.")
        return True
    except (OSError, PermissionError) as e:
        # Tática de Guerra: Se não pode deletar, renomeia para "tirar da frente"
        temp_name = os.path.join(path, f"venv_dead_{uuid.uuid4().hex[:4]}.old")
        try:
            os.rename(venv_path, temp_name)
            # Tenta deletar o renomeado silenciosamente
            shutil.rmtree(temp_name, ignore_errors=True)
            click.echo(Fore.YELLOW + f"   > [AVISO] Venv travado. Movido para {os.path.basename(temp_name)}.")
            return True
        except Exception as rename_err:
            msg = f"Falha catastrófica: venv está bloqueado e não pôde ser movido: {rename_err}"
            logger.add_finding('error', msg, details=str(e))
            click.echo(Fore.RED + f"   > [FALHA] {msg}")
            return False

def _create_venv_safe(path: str, logger: ExecutionLogger) -> bool:
    """Cria um novo ambiente virtual usando o interpretador atual."""
    try:
        click.echo(Fore.WHITE + "   > Criando novo ambiente virtual...")
        # Aegis: Execução segura sem shell=True
        subprocess.run([sys.executable, "-m", "venv", "venv"], 
                     check=True, capture_output=True, cwd=path)
        click.echo(Fore.GREEN + "   > [OK] Novo 'venv' inicializado.")
        return True
    except subprocess.CalledProcessError as e:
        logger.add_finding('error', "Falha na criação do venv.", details=str(e.stderr))
        return False

def _install_requirements_safe(path: str, logger: ExecutionLogger) -> bool:
    """Instala dependências e valida a saúde do pip."""
    req_file = os.path.join(path, 'requirements.txt')
    if not os.path.isfile(req_file):
        click.echo(Fore.YELLOW + "   > Sem 'requirements.txt'. Nenhuma lib instalada.")
        return True

    # Localiza o python do venv recém criado
    venv_python = _get_venv_python_executable(path)
    if not venv_python:
        click.echo(Fore.RED + "   > [FALHA] Não foi possível localizar o Python do novo venv.")
        return False
        
    try:
        # 1. Upgrade Pip
        click.echo(Fore.WHITE + "   > Atualizando pip...")
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], 
                     check=True, capture_output=True, cwd=path)

        # 2. Install Requirements
        click.echo(Fore.WHITE + "   > Sincronizando dependências (isso pode demorar)...")
        subprocess.run([venv_python, "-m", "pip", "install", "-r", req_file], 
                     check=True, capture_output=True, cwd=path)
        
        # 3. Pip Check
        click.echo(Fore.WHITE + "   > Validando consistência do ambiente...")
        check = subprocess.run([venv_python, "-m", "pip", "check"], 
                             capture_output=True, text=True, cwd=path)
        
        if check.returncode == 0:
            click.echo(Fore.GREEN + "   > [OK] Ambiente consistente.")
            return True
        else:
            click.echo(Fore.RED + "   > [AVISO] Inconsistências detectadas:")
            click.echo(Style.DIM + check.stdout)
            return True # Retorna True pois o venv foi criado, embora com avisos
            
    except subprocess.CalledProcessError as e:
        logger.add_finding('error', "Falha no pip install.", details=str(e.stderr))
        return False

@click.command('rebuild')
@click.pass_context
@click.option('--force', '-y', is_flag=True, help="Executa sem confirmação.")
def rebuild(ctx, force):
    """[DESTRUTIVO] Protocolo Fênix: Destrói e recria o ambiente do projeto."""
    path = os.getcwd()
    with ExecutionLogger('rebuild', path, ctx.params) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + f"--- [REBUILD] Reconstruindo: {os.path.basename(path)} ---")
        
        if not force:
            click.echo(Fore.RED + "AVISO: O diretório 'venv' será DELETADO.")
            if not click.confirm(Fore.YELLOW + "Deseja continuar?"):
                click.echo("Operação abortada."); return
        
        # Sequência Fênix
        steps = [
            (Fore.YELLOW + "\n1. Limpeza", lambda: _remove_venv_resilient(path, logger)),
            (Fore.YELLOW + "2. Inicialização", lambda: _create_venv_safe(path, logger)),
            (Fore.YELLOW + "3. Sincronização", lambda: _install_requirements_safe(path, logger))
        ]

        for label, func in steps:
            click.echo(label)
            if not func():
                click.echo(Fore.RED + "\n[ERRO] O processo falhou e foi interrompido.")
                sys.exit(1)
        
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUCESSO] Ambiente restaurado com o Estado de Ouro.")