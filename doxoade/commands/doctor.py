# doxoade/commands/doctor.py
import os
import re
import sys
import subprocess
import json
import shutil
from pathlib import Path

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

__version__ = "35.5 Alfa (Phoenix)"

def _check_and_create_venv(target_path, logger):
    venv_path = os.path.join(target_path, 'venv')
    click.echo(Fore.WHITE + f"Verificando a existência de '{venv_path}'...")
    if not os.path.isdir(venv_path):
        click.echo(Fore.YELLOW + "   > [AVISO] Ambiente virtual 'venv' não encontrado.")
        if click.confirm(Fore.CYAN + "     Deseja criá-lo agora?"):
            try:
                click.echo(Fore.WHITE + "     Criando ambiente virtual...")
                subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True, capture_output=True, cwd=target_path)
                click.echo(Fore.GREEN + "   > [OK] Ambiente virtual 'venv' criado com sucesso!")
                logger.add_finding('info', 'Ambiente virtual criado com sucesso.')
                return True
            except subprocess.CalledProcessError:
                details = "Falha no subprocesso ao criar venv."
                logger.add_finding('error', "Falha ao criar o ambiente virtual.", details=details)
                click.echo(Fore.RED + f"[ERRO] Falha ao criar o venv: {details}")
                return False
        else:
            click.echo("Operação cancelada."); return False
    else:
        click.echo(Fore.GREEN + "   > [OK] Ambiente virtual já existe.")
    return True

def _install_dependencies(target_path, logger):
    requirements_file = os.path.join(target_path, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        click.echo(Fore.YELLOW + "[INFO] 'requirements.txt' não encontrado. Pulando instalação.")
        return True

    venv_python = os.path.join(target_path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python.exe' if os.name == 'nt' else 'python')
    if not os.path.isfile(venv_python):
        logger.add_finding('error', "Executável Python do venv não encontrado.")
        click.echo(Fore.RED + "[ERRO] Executável Python do venv não encontrado.")
        return False
        
    click.echo(Fore.WHITE + "Sincronizando dependências do 'requirements.txt'...")
    try:
        cmd = [venv_python, '-m', 'pip', 'install', '-r', requirements_file]
        result = subprocess.run(cmd, check=True, capture_output=True)
        logger.add_finding('info', 'Sincronização de dependências concluída.', details=result.stdout.decode('utf-8', 'ignore'))
        click.echo(Fore.GREEN + "[OK] Dependências sincronizadas com sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        details = e.stderr.decode('utf-8', 'ignore')
        logger.add_finding('error', "Falha ao instalar dependências via pip.", details=details)
        click.echo(Fore.RED + "[ERRO] Falha ao instalar as dependências.")
        click.echo(Fore.WHITE + Style.DIM + e.stdout.decode('utf-8', 'ignore'))
        click.echo(Fore.RED + Style.DIM + details)
        return False

def _prepare_verification_data(target_path, logger):
    """Lê o requirements.txt e prepara os dados para a sonda."""
    requirements_file = os.path.join(target_path, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        return None, {'status': 'ok', 'message': 'Nenhum requirements.txt para verificar.'}

    packages_required = set()
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    match = re.match(r'^[a-zA-Z0-9_-]+', line)
                    if match:
                        packages_required.add(match.group(0).lower().replace('_', '-'))
        return packages_required, None
    except IOError as e:
        logger.add_finding('error', f"Não foi possível ler o requirements.txt: {e}")
        return None, {'status': 'error', 'message': f"Não foi possível ler o requirements.txt: {e}"}

def _run_verification_probe(target_path, packages_required, logger):
    """Executa a Sonda Inteligente e analisa seus resultados."""
    _PROBE_SCRIPT = """
import sys, json
from importlib import metadata
results = {'installed_packages': set(), 'is_isolated': False}
for dist in metadata.distributions():
    try:
        pkg_name = dist.metadata['name'].lower().replace('_', '-')
        results['installed_packages'].add(pkg_name)
    except Exception:
        continue
results['is_isolated'] = sys.prefix != sys.base_prefix
results['installed_packages'] = list(results['installed_packages'])
print(json.dumps(results))
"""
    venv_python_exe = 'python.exe' if os.name == 'nt' else 'python'
    venv_python = os.path.join(target_path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', venv_python_exe)
    try:
        result = subprocess.run([venv_python, '-c', _PROBE_SCRIPT], capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        
        if not probe_data.get('is_isolated'):
            return {'status': 'error', 'message': 'Ambiente virtual não está devidamente isolado!'}
        
        installed_packages = set(probe_data.get('installed_packages', []))
        missing_packages = packages_required - installed_packages
        
        if missing_packages:
            return {'status': 'error', 'message': f"Pacotes não encontrados: {', '.join(sorted(list(missing_packages)))}"}

        return {'status': 'ok', 'message': 'Dependências OK e ambiente isolado.'}
    except subprocess.CalledProcessError as e:
        details = f"STDOUT: {e.stdout}\nSTDERR: {e.stderr}"
        logger.add_finding('error', "A sonda de verificação falhou.", details=details)
        return {'status': 'error', 'message': f"A sonda falhou. Detalhes: {e.stderr}"}
    except Exception as e:
        logger.add_finding('error', "Falha desconhecida na sonda.", details=str(e))
        return {'status': 'error', 'message': f"Falha desconhecida na sonda: {e}"}

def _verify_environment(target_path, logger):
    """Orquestra a verificação do ambiente."""
    click.echo(Fore.WHITE + "Verificando integridade do ambiente...")
    
    packages_required, early_exit_status = _prepare_verification_data(target_path, logger)
    if early_exit_status:
        return early_exit_status

    return _run_verification_probe(target_path, packages_required, logger)

def _find_doxoade_root():
    """Encontra o caminho absoluto para a raiz do projeto doxoade."""
    current_path = Path(__file__).resolve().parent
    while current_path != current_path.parent:
        if (current_path / "run_doxoade.py").exists() or (current_path / "doxoade.bat").exists():
            return current_path
        current_path = current_path.parent
    return None

def _verify_and_guide_path(logger):
    """Verifica o PATH e guia o usuário com o caminho correto da doxoade."""
    click.echo(Fore.WHITE + "Verificando a acessibilidade do comando principal...")

    executable_name = "doxoade.bat" if os.name == 'nt' else "doxoade"
    
    if shutil.which(executable_name):
        click.echo(Fore.GREEN + f"   > [OK] Comando '{executable_name}' encontrado no PATH.")
        logger.add_finding('info', f"Comando '{executable_name}' acessível via PATH.")
        return True
    else:
        doxoade_root = _find_doxoade_root()
        if not doxoade_root:
            click.echo(Fore.RED + "   > [ERRO CRÍTICO] Não foi possível localizar o diretório raiz da doxoade para fornecer o guia.")
            return False

        click.echo(Fore.YELLOW + f"   > [AVISO] O comando '{executable_name}' não foi encontrado no seu PATH global.")
        logger.add_finding('warning', f"Comando '{executable_name}' não está no PATH do sistema.")

        click.echo(Fore.CYAN + "\n--- GUIA DE INSTALAÇÃO UNIVERSAL ---")
        if os.name == 'nt':
            click.echo("Para tornar a 'doxoade' acessível de qualquer lugar no Windows:")
            click.echo("1. Adicione o seguinte caminho à sua variável de ambiente 'Path':")
            click.echo(Fore.WHITE + Style.BRIGHT + f"   {doxoade_root}")
            click.echo("2. FECHE E REABRA seu terminal para aplicar a alteração.")
        else:
            run_doxoade_path = doxoade_root / 'run_doxoade.py'
            click.echo("Para tornar a 'doxoade' acessível no Linux, macOS ou Termux:")
            click.echo("1. Adicione a seguinte linha ao seu arquivo ~/.bashrc ou ~/.zshrc:")
            click.echo(Fore.WHITE + Style.BRIGHT + f"   alias doxoade='python {run_doxoade_path}'")
            click.echo("2. Execute 'source ~/.bashrc' ou FECHE E REABRA seu terminal.")
        return False

@click.command('doctor')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False, resolve_path=True), default='.', required=False)
def doctor(ctx, path):
    """Executa um diagnóstico e reparo do ambiente do projeto."""
    arguments = ctx.params
    with ExecutionLogger('doctor', path, arguments) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + f"--- [DOCTOR] Iniciando diagnóstico para: {os.path.abspath(path)} ---")
        
        original_dir = os.getcwd()
        try:
            os.chdir(path)

            click.echo(Fore.YELLOW + "\n--- Passo 1: Verificando Ambiente Virtual ---")
            if not _check_and_create_venv('.', logger): sys.exit(1)
            
            click.echo(Fore.YELLOW + "\n--- Passo 2: Verificando a Integridade do Ambiente ---")
            verification = _verify_environment('.', logger)
            
            if verification.get('status') != 'ok':
                click.echo(Fore.RED + f"   > [FALHA] {verification.get('message', 'Erro desconhecido.')}")
                logger.add_finding('warning', "Verificação inicial falhou.", details=verification.get('message'))
                if click.confirm(Fore.CYAN + "\n     Deseja tentar reparar o ambiente?"):
                    click.echo(Fore.YELLOW + "\n--- Passo 3: Reparando Dependências ---")
                    if not _install_dependencies('.', logger): sys.exit(1)
                    
                    click.echo(Fore.YELLOW + "\n--- Passo 4: Verificando novamente após o reparo... ---")
                    post_repair_verification = _verify_environment('.', logger)
                    if post_repair_verification.get('status') == 'ok':
                        click.echo(Fore.GREEN + "   > [OK] Reparo bem-sucedido.")
                    else:
                        details = post_repair_verification.get('message')
                        click.echo(Fore.RED + f"   > [FALHA PÓS-REPARO] {details}")
                        logger.add_finding('error', "Verificação pós-reparo falhou.", details=details)
                        sys.exit(1)
                else: return
            else:
                click.echo(Fore.GREEN + f"   > [OK] {verification.get('message')}")

            # Passo Final: Acessibilidade Global
            click.echo(Fore.YELLOW + "\n--- Passo Final: Verificando Acessibilidade Global ---")
            _verify_and_guide_path(logger)

            click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
            click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] O ambiente do projeto foi verificado.")
        finally:
            os.chdir(original_dir)