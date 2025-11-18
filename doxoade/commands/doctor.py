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

__version__ = "35.81 Alfa Phoenix"

def _verify_gitignore_logic(target_path, logger):
    """
    (Versão Direta) Audita o .gitignore e oferece para mover as regras de negação (!) para o final.
    """
    click.echo(Fore.WHITE + "Verificando a lógica do arquivo .gitignore...")
    gitignore_path = os.path.join(target_path, '.gitignore')
    
    if not os.path.isfile(gitignore_path):
        click.echo(Fore.GREEN + "   > [OK] Arquivo .gitignore não encontrado. Nenhuma verificação necessária.")
        return

    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Separa as linhas de negação de todo o resto.
        negation_lines = [line for line in lines if line.strip().startswith('!')]
        other_lines = [line for line in lines if not line.strip().startswith('!')]

        # Se não houver regras de negação, não há nada a fazer.
        if not negation_lines:
            click.echo(Fore.GREEN + "   > [OK] Nenhuma regra de negação (!) encontrada no .gitignore.")
            return

        # Se houver regras de negação, oferece para reorganizar por segurança.
        click.echo(Fore.YELLOW + "   > [INFO] Regras de negação (!) foram encontradas no seu .gitignore.")
        click.echo(Fore.CYAN + "     Para garantir que funcionem corretamente, elas devem estar no final do arquivo.")
        
        if click.confirm(Fore.YELLOW + "     Deseja reorganizar o arquivo agora? (Um backup .bkp será criado)"):
            # Ação de backup direta
            backup_path = gitignore_path + '.bkp'
            shutil.copy2(gitignore_path, backup_path)
            click.echo(Fore.WHITE + f"     - Backup do arquivo original salvo em: {os.path.basename(backup_path)}")

            # Constrói o novo conteúdo de forma robusta
            # Junta as outras linhas, removendo espaços extras no final, e adiciona as negações
            new_content = "".join(other_lines).strip()
            new_content += "\n\n# Exceções (movidas para o final para garantir prioridade)\n"
            new_content += "".join(negation_lines).strip() + "\n"

            with open(gitignore_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            msg = "Arquivo .gitignore foi reorganizado com sucesso."
            logger.add_finding("INFO", msg, category="GIT-CONFIG-REPAIR")
            click.echo(Fore.GREEN + f"   > [OK] {msg}")

    except Exception as e:
        logger.add_finding("ERROR", "Falha ao processar o .gitignore.", details=str(e))
        click.echo(Fore.RED + f"   > [ERRO] Não foi possível processar o .gitignore: {e}")

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
    """(Versão Corrigida) Lê o requirements.txt e retorna um conjunto de pacotes necessários."""
    requirements_file = os.path.join(target_path, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        return None, {'status': 'ok', 'message': 'Nenhum requirements.txt para verificar.'}

    packages_required = set()
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # CORREÇÃO: Ignora linhas vazias, comentários e flags como '-e' ou '-r'
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                
                # Extrai apenas o nome do pacote, ignorando versões e extras
                match = re.match(r'^[a-zA-Z0-9_.-]+', line)
                if match:
                    # Normaliza o nome (ex: converte '_' para '-')
                    package_name = match.group(0).lower().replace('_', '-')
                    packages_required.add(package_name)
                    
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
    venv_python = os.path.join(target_path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python')
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
    """
    Verifica acessibilidade, conflitos, ecos e origem da instalação do comando 'doxoade'.
    """
    click.echo(Fore.WHITE + "Verificando a acessibilidade e a saúde da instalação...")

    cmd = ['where', 'doxoade.bat'] if os.name == 'nt' else ['which', '-a', 'doxoade']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        executables = result.stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        executables = []

    # Cenário 1: Nenhum comando encontrado. Guiamos o usuário.
    if not executables:
        # ... (a lógica de guia de instalação que já funciona) ...
        return False

    # A Lógica de Inteligência: De-duplicamos para encontrar os caminhos únicos.
    unique_executables = sorted(list(set(executables)))

    # Cenário 2: Conflito Real. Erro crítico.
    if len(unique_executables) > 1:
        details = "\n".join(f"   - {exe}" for exe in unique_executables)
        click.echo(Fore.RED + "   > [ERRO CRÍTICO] Múltiplas instalações DIFERENTES de 'doxoade' encontradas no seu PATH!")
        click.echo(Fore.CYAN + "     Isso é uma configuração perigosa. Remova as instalações extras ou corrija seu PATH.")
        click.echo(Fore.WHITE + details)
        logger.add_finding('error', "Conflito de PATH: Múltiplas instalações detectadas.", details=details)
        return False

    # Se chegamos aqui, sabemos que há apenas UM caminho de instalação único.
    doxoade_executable = unique_executables[0]

    # Cenário 3: Eco Inofensivo (múltiplas entradas, mas para o mesmo arquivo).
    if len(executables) > len(unique_executables):
        click.echo(Fore.YELLOW + "   > [AVISO DE PATH] A mesma instalação de 'doxoade' foi encontrada várias vezes no seu PATH.")
        click.echo(Fore.CYAN + f"     Isso não é um erro crítico, mas indica uma redundância no PATH. Instalação ativa: {doxoade_executable}")
        logger.add_finding('warning', "PATH duplicado detectado.", details=f"Caminho encontrado: {doxoade_executable}")
    
    # Cenário 4: Verificação de Origem da Única Instalação.
    is_safe_origin = os.path.basename(os.path.dirname(doxoade_executable)).lower() in ['scripts', 'bin']
    
    if not is_safe_origin:
        click.echo(Fore.YELLOW + "   > [AVISO DE CONFIGURAÇÃO] A instalação encontrada aponta diretamente para uma pasta de projeto.")
        click.echo(Fore.CYAN + "     Esta é uma configuração instável e não recomendada. Para uma instalação robusta,")
        click.echo(Fore.CYAN + "     use o 'install.py' e siga as instruções para configurar seu PATH para a pasta 'venv/bin' ou 'venv/Scripts'.")
        logger.add_finding('warning', "Configuração de PATH não recomendada.", details=f"Origem do comando: {doxoade_executable}")
    else:
        click.echo(Fore.GREEN + f"   > [OK] Instalação única e segura de 'doxoade' encontrada em: {doxoade_executable}")

    logger.add_finding('info', "Verificação de acessibilidade concluída.")
    return True

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
            click.echo(Fore.YELLOW + "\n--- Passo 3: Verificando Sanidade do Ambiente de Testes ---")
            _verify_test_environment('.', logger)

            # --- CORREÇÃO: MOVA A CHAMADA PARA CÁ ---
            click.echo(Fore.YELLOW + "\n--- Passo 4: Verificando Configuração do Git ---")
            _verify_gitignore_logic('.', logger)
            # --- FIM DA CORREÇÃO ---
            
            click.echo(Fore.YELLOW + "\n--- Passo Final: Verificando Acessibilidade Global ---")
            _verify_and_guide_path(logger)

            click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
            click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] O ambiente do projeto foi verificado.")
        finally:
            os.chdir(original_dir)
            
def _verify_test_environment(target_path, logger):
    """Diagnostica problemas comuns no ambiente de testes."""
    click.echo(Fore.WHITE + "Verificando sanidade do ambiente de testes...")
    has_issues = False

    # --- UTILITARIO 1: Verificar Conflito de PATH do Pytest ---
    # FLUXO 1: Localizar o executável do pytest dentro do venv.
    venv_pytest_path = os.path.join(target_path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'pytest.exe' if os.name == 'nt' else 'pytest')
    
    # FLUXO 2: Localizar o primeiro executável 'pytest' encontrado no PATH global.
    global_pytest_path = shutil.which('pytest')

    # FLUXO 3: Comparar e alertar se não forem o mesmo.
    if global_pytest_path and os.path.normcase(os.path.abspath(global_pytest_path)) != os.path.normcase(os.path.abspath(venv_pytest_path)):
        has_issues = True
        msg = "Conflito de PATH detectado para o Pytest."
        details = f"O comando 'pytest' aponta para '{global_pytest_path}', mas o do venv é '{venv_pytest_path}'. Use a execução explícita: '.\\venv\\Scripts\\python.exe -m pytest ...'"
        logger.add_finding('warning', msg, details=details)
        click.echo(Fore.YELLOW + f"   > [AVISO] {msg}\n     {details}")

    # --- UTILITARIO 2: Verificar Instalação em Modo Editável ---
    # FLUXO 1: Executar 'pip list -e' para ver os pacotes editáveis.
    venv_python = os.path.join(target_path, 'venv', 'Scripts' if os.name == 'nt' else 'bin', 'python')
    try:
        result = subprocess.run([venv_python, '-m', 'pip', 'list', '-e'], capture_output=True, text=True, check=True, encoding='utf-8')
        # FLUXO 2: Verificar se o caminho do projeto atual está na saída.
        if os.path.abspath(target_path).lower() not in result.stdout.lower():
            has_issues = True
            msg = "Projeto não parece estar instalado em modo editável."
            details = "Isso pode causar 'ImportError' nos testes. Execute: '.\\venv\\Scripts\\python.exe -m pip install -e .'"
            logger.add_finding('warning', msg, details=details)
            click.echo(Fore.YELLOW + f"   > [AVISO] {msg}\n     {details}")
    except subprocess.CalledProcessError:
        pass # Ignora falhas do pip aqui, outros diagnósticos podem pegar.

    # --- UTILITARIO 3: Verificar __init__.py na Raiz ---
    # FLUXO 1: Checar a existência do arquivo na raiz do projeto.
    root_init_file = os.path.join(target_path, '__init__.py')
    if os.path.exists(root_init_file):
        has_issues = True
        msg = "Arquivo '__init__.py' encontrado na raiz do projeto."
        details = "Isso cria um pacote ambíguo e é uma causa comum de 'ImportError' em testes. Recomenda-se a remoção."
        logger.add_finding('error', msg, details=details)
        click.echo(Fore.RED + f"   > [ERRO] {msg}\n     {details}")

    if not has_issues:
        click.echo(Fore.GREEN + "   > [OK] Ambiente de testes parece são.")
        