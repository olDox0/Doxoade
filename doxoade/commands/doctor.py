# doxoade/commands/doctor.py
import os
import re
import sys
import subprocess
import json
import shutil
import shlex
from pathlib import Path

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _get_venv_python_executable

__version__ = "36.0 Alfa Phoenix (MPoT)"

def detect_windows_store_alias():
    if sys.platform != "win32": return False
    python_path = shutil.which("python")
    if python_path and "WindowsApps" in python_path:
        click.echo(Fore.RED + Style.BRIGHT + "\n[ALERTA CRÍTICO DE AMBIENTE] 'App Execution Alias' Detectado")
        return True
    return False

def _verify_gitignore_logic(target_path, logger):
    """(Versão Direta) Audita o .gitignore."""
    click.echo(Fore.WHITE + "Verificando a lógica do arquivo .gitignore...")
    gitignore_path = os.path.join(target_path, '.gitignore')
    
    if not os.path.isfile(gitignore_path):
        click.echo(Fore.GREEN + "   > [OK] Arquivo .gitignore não encontrado.")
        return

    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        negation_lines = [line for line in lines if line.strip().startswith('!')]
        other_lines = [line for line in lines if not line.strip().startswith('!')]

        if not negation_lines:
            click.echo(Fore.GREEN + "   > [OK] Nenhuma regra de negação (!) encontrada.")
            return

        click.echo(Fore.YELLOW + "   > [INFO] Regras de negação (!) encontradas. Movendo para o final...")
        
        # Backup e Reescrita Segura
        shutil.copy2(gitignore_path, gitignore_path + '.bkp')
        new_content = "".join(other_lines).strip()
        new_content += "\n\n# Exceções (Auto-fixed)\n"
        new_content += "".join(negation_lines).strip() + "\n"

        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.add_finding("INFO", "Arquivo .gitignore foi reorganizado.", category="GIT-CONFIG-REPAIR")
        click.echo(Fore.GREEN + "   > [OK] .gitignore reorganizado.")

    except Exception as e:
        logger.add_finding("ERROR", "Falha ao processar .gitignore.", details=str(e))

def _check_and_create_venv(target_path, logger):
    venv_path = os.path.join(target_path, 'venv')
    click.echo(Fore.WHITE + f"Verificando a existência de '{venv_path}'...")
    if not os.path.isdir(venv_path):
        click.echo(Fore.YELLOW + "   > [AVISO] Ambiente virtual 'venv' não encontrado.")
        if click.confirm(Fore.CYAN + "     Deseja criá-lo agora?"):
            try:
                subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True, capture_output=True, cwd=target_path)
                click.echo(Fore.GREEN + "   > [OK] Ambiente virtual 'venv' criado!")
                return True
            except subprocess.CalledProcessError as e:
                logger.add_finding('error', "Falha ao criar o ambiente virtual.", details=str(e))
                return False
        else: return False
    else:
        click.echo(Fore.GREEN + "   > [OK] Ambiente virtual já existe.")
    return True

def _install_dependencies(target_path, logger):
    requirements_file = os.path.join(target_path, 'requirements.txt')
    if not os.path.isfile(requirements_file): return True

    venv_python = _get_venv_python_executable(target_path)
    if not venv_python:
        click.echo(Fore.RED + "[ERRO] Python do venv não encontrado.")
        return False
        
    click.echo(Fore.WHITE + "Sincronizando dependências...")
    try:
        cmd = [venv_python, '-m', 'pip', 'install', '-r', requirements_file]
        subprocess.run(cmd, check=True, capture_output=True)
        click.echo(Fore.GREEN + "[OK] Dependências sincronizadas.")
        return True
    except subprocess.CalledProcessError as e:
        logger.add_finding('error', "Falha no pip install.", details=str(e))
        return False

def _verify_environment(target_path, logger):
    click.echo(Fore.WHITE + "Verificando integridade do ambiente...")
    venv_python = _get_venv_python_executable(target_path)
    
    # Sonda Inteligente
    _PROBE_SCRIPT = """
import sys, json, importlib.metadata
results = {'installed': [], 'is_isolated': sys.prefix != sys.base_prefix}
try:
    for dist in importlib.metadata.distributions():
        results['installed'].append(dist.metadata['name'].lower())
except: pass
print(json.dumps(results))
"""
    try:
        result = subprocess.run([venv_python, '-c', _PROBE_SCRIPT], capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        
        if not probe_data.get('is_isolated'):
            return {'status': 'error', 'message': 'Venv não está isolado!'}
            
        # Verifica se as "Baterias" (Bandit/Safety) estão instaladas SE este for o projeto Doxoade
        # (Heurística simples: se requirements.txt tiver bandit)
        reqs_path = os.path.join(target_path, 'requirements.txt')
        if os.path.exists(reqs_path):
            with open(reqs_path) as f: reqs = f.read().lower()
            
            installed = set(probe_data['installed'])
            missing = []
            if 'bandit' in reqs and 'bandit' not in installed: missing.append('bandit')
            if 'safety' in reqs and 'safety' not in installed: missing.append('safety')
            
            if missing:
                return {'status': 'warning', 'message': f"Ferramentas de segurança faltando: {', '.join(missing)}"}

        return {'status': 'ok', 'message': 'Ambiente íntegro.'}
    except Exception as e:
        return {'status': 'error', 'message': f"Falha na sonda: {e}"}

def _verify_and_guide_path(logger):
    """Verifica acessibilidade do comando 'doxoade'."""
    cmd = ['where', 'doxoade.bat'] if os.name == 'nt' else ['which', '-a', 'doxoade']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        executables = result.stdout.strip().splitlines()
    except Exception: executables = []

    unique = sorted(list(set(executables)))
    
    if len(unique) > 1:
        logger.add_finding('error', "Conflito de PATH: Múltiplas instalações.", details="\n".join(unique))
        click.echo(Fore.RED + "   > [ERRO] Múltiplas instalações do Doxoade no PATH!")
        return False
        
    if not unique:
        click.echo(Fore.YELLOW + "   > [AVISO] Doxoade não encontrado no PATH global.")
        return False

    click.echo(Fore.GREEN + f"   > [OK] Instalação ativa: {unique[0]}")
    return True

@click.command('doctor')
@click.pass_context
@click.argument('path', type=click.Path(exists=True), default='.')
def doctor(ctx, path):
    """Executa um diagnóstico e reparo do ambiente do projeto."""
    with ExecutionLogger('doctor', path, ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [DOCTOR] Diagnóstico: {os.path.abspath(path)} ---")
        
        # 1. Venv
        if not _check_and_create_venv(path, logger): sys.exit(1)
        
        # 2. Integridade
        res = _verify_environment(path, logger)
        if res['status'] == 'ok':
            click.echo(Fore.GREEN + f"   > [OK] {res['message']}")
        elif res['status'] == 'warning':
            click.echo(Fore.YELLOW + f"   > [AVISO] {res['message']}")
            if click.confirm("     Deseja reparar?"):
                _install_dependencies(path, logger)
        else:
            click.echo(Fore.RED + f"   > [FALHA] {res['message']}")
            
        # 3. Git
        _verify_gitignore_logic(path, logger)
        
        # 4. Global
        _verify_and_guide_path(logger)
        
        click.echo(Fore.GREEN + "\n[FIM] Diagnóstico concluído.")