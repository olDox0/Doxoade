# -*- coding: utf-8 -*-
"""
Módulo de Auto-cura e Diagnóstico (Protocolo Fênix).
Responsável por garantir a integridade do ambiente de desenvolvimento,
reparar configurações de Git e sincronizar dependências.
"""

import os
import sys
import subprocess # nosec
import json
import shutil
from typing import Dict

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _get_venv_python_executable
from ..tools.pkg_manager import get_best_installer, run_install

__version__ = "36.1 Alfa Phoenix (Gold Standard)"

def detect_windows_store_alias() -> bool:
    """
    Detecta se o Python está sendo mascarado pelo instalador da Windows Store.
    Isso causa falhas silenciosas em subprocessos.
    """
    if sys.platform != "win32":
        return False
        
    python_path = shutil.which("python")
    if python_path and "WindowsApps" in python_path:
        click.echo(Fore.RED + Style.BRIGHT + "\n[ALERTA] 'App Execution Alias' detectado.")
        return True
    return False

def _verify_gitignore_logic(target_path: str, logger: ExecutionLogger) -> None:
    """
    Audita e reorganiza o .gitignore para garantir que exceções (!) 
    estejam sempre no final do arquivo (Padrão Git).
    """
    if not target_path or logger is None:
        raise ValueError("Argumentos obrigatórios ausentes para auditoria de Git.")

    gitignore_path = os.path.join(target_path, '.gitignore')
    if not os.path.isfile(gitignore_path):
        return

    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        negation_lines = [line for line in lines if line.strip().startswith('!')]
        other_lines = [line for line in lines if not line.strip().startswith('!')]

        if not negation_lines:
            return

        # Backup e Reescrita Segura (Protocolo Aegis)
        shutil.copy2(gitignore_path, gitignore_path + '.bkp')
        new_content = "".join(other_lines).strip()
        new_content += "\n\n# Exceções (Auto-fixed pelo Doxoade)\n"
        new_content += "".join(negation_lines).strip() + "\n"

        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.add_finding("INFO", "Gitignore reorganizado.", category="GIT-REPAIR")
        click.echo(Fore.GREEN + "   > [OK] .gitignore reorganizado.")

    except Exception as e:
        logger.add_finding("ERROR", "Falha no .gitignore.", details=str(e))

def _check_and_create_venv(target_path: str, logger: ExecutionLogger) -> bool:
    """Verifica a existência do ambiente virtual e oferece criação automática."""
    if not target_path:
        raise ValueError("Caminho do projeto é obrigatório.")

    venv_path = os.path.join(target_path, 'venv')
    if not os.path.isdir(venv_path):
        click.echo(Fore.YELLOW + f"   > [AVISO] Venv não encontrado em '{venv_path}'.")
        if click.confirm(Fore.CYAN + "     Deseja criar o ambiente agora?"):
            try:
                # Aegis: Execução segura via lista
                subprocess.run([sys.executable, '-m', 'venv', 'venv'], # nosec
                             check=True, capture_output=True, cwd=target_path)
                click.echo(Fore.GREEN + "   > [OK] Venv criado com sucesso.")
                return True
            except subprocess.CalledProcessError as e:
                logger.add_finding('error', "Falha ao criar venv.", details=str(e))
                return False
        return False
    
    click.echo(Fore.GREEN + "   > [OK] Ambiente virtual detectado.")
    return True

def _install_dependencies(target_path: str, logger: ExecutionLogger) -> bool:
    """Sincroniza o requirements.txt com o ambiente virtual."""
    if not target_path:
        raise ValueError("Caminho alvo é obrigatório.")

    reqs_file = os.path.join(target_path, 'requirements.txt')
    if not os.path.isfile(reqs_file):
        return True

    venv_python = _get_venv_python_executable(target_path)
    if not venv_python:
        return False
        
    try:
        subprocess.run([venv_python, '-m', 'pip', 'install', '-r', reqs_file], # nosec
                      check=True, capture_output=True)
        click.echo(Fore.GREEN + "   > [OK] Dependências sincronizadas.")
        return True
    except subprocess.CalledProcessError as e:
        logger.add_finding('error', "Falha no pip install.", details=str(e))
        return False

def _verify_environment(target_path: str) -> Dict[str, str]:
    """
    Executa uma sonda isolada no venv para verificar isolamento e ferramentas.
    Removido parâmetro 'logger' não utilizado (Fix Deepcheck).
    """
    venv_python = _get_venv_python_executable(target_path)
    if not venv_python:
        return {'status': 'error', 'message': 'Executável do venv não encontrado.'}
    
    probe_script = (
        "import sys, json, importlib.metadata; "
        "res = {'isolated': sys.prefix != sys.base_prefix, 'libs': [d.metadata['name'].lower() for d in importlib.metadata.distributions()]}; "
        "print(json.dumps(res))"
    )
    
    try:
        result = subprocess.run([venv_python, '-c', probe_script], # nosec
                              capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        if not data.get('isolated'):
            return {'status': 'error', 'message': 'O ambiente não é isolado (System Python).'}
            
        return {'status': 'ok', 'message': 'Ambiente íntegro e isolado.'}
    except Exception as e:
        return {'status': 'error', 'message': f"Falha na sonda: {str(e)}"}

def _verify_and_guide_path(logger: ExecutionLogger) -> bool:
    """Detecta conflitos de múltiplas instalações no PATH global."""
    if logger is None:
        raise ValueError("Logger é obrigatório para auditoria de PATH.")

    cmd = ['where', 'doxoade.bat'] if os.name == 'nt' else ['which', '-a', 'doxoade']
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, shell=False) # nosec
        paths = list(set(res.stdout.strip().splitlines()))
    except Exception:
        paths = []

    if len(paths) > 1:
        logger.add_finding('error', "Múltiplas instalações no PATH.", details="\n".join(paths))
        click.echo(Fore.RED + "   > [ERRO] Conflito detectado: múltiplas versões no PATH.")
        return False
        
    if not paths:
        click.echo(Fore.YELLOW + "   > [AVISO] Doxoade não está no seu PATH global.")
        return False

    click.echo(Fore.GREEN + f"   > [OK] Instalação ativa: {paths[0]}")
    return True

def _ensure_uv_on_termux():
    """Verifica e sugere instalação do UV no ambiente Termux."""
    if os.path.exists("/data/data/com.termux"):
        if not shutil.which("uv"):
            click.echo(Fore.YELLOW + "   [!] UV não detectado. No Termux: 'pkg install uv' para máxima performance.")

def _repair_dependencies(target_path, logger):
    """Usa o UV para sincronizar dependências de forma ultra-rápida."""
    req_file = os.path.join(target_path, "requirements.txt")
    if not os.path.exists(req_file):
        return

    installer = get_best_installer()
    click.echo(Fore.CYAN + f"   > Sincronizando dependências via {installer.upper()}...")
    
    venv_py = _get_venv_python_executable(target_path)
    res = run_install(["-r", req_file], venv_python=venv_py)
    
    if isinstance(res, Exception):
        logger.add_finding("ERROR", f"Falha na instalação: {res}", category="ENVIRONMENT")
    else:
        click.echo(Fore.GREEN + f"   [OK] Ambiente curado via {installer.upper()}.")

@click.command('doctor')
@click.pass_context
@click.argument('path', type=click.Path(exists=True), default='.')
def doctor(ctx, path):
    """Executa o diagnóstico completo de saúde do projeto."""
    abs_path = os.path.abspath(path)
    with ExecutionLogger('doctor', abs_path, ctx.params) as logger:
        click.echo(Fore.BLUE + Style.BRIGHT + f"--- [DOCTOR] Analisando saúde de: {path} ---")
        
        # 1. Verificação de Venv
        _ensure_uv_on_termux()
        if not _check_and_create_venv(path, logger):
            click.echo(Fore.RED + "   Abordando: Ambiente virtual inválido.")
            return

        # 2. Verificação de Sonda
        status_env = _verify_environment(path)
        color = Fore.GREEN if status_env['status'] == 'ok' else Fore.RED
        click.echo(color + f"   > [{status_env['status'].upper()}] {status_env['message']}")
            
        # 3. Lógica de Reparo
        _verify_gitignore_logic(path, logger)
        _verify_and_guide_path(logger)
        _repair_dependencies(abs_path, logger)
        
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[FIM] Saúde do projeto verificada.")