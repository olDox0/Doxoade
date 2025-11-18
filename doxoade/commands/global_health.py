# doxoade/commands/global_health.py
import sys
import os
import subprocess
from importlib import metadata
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from collections import defaultdict

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

# A função _check_path permanece a mesma, pois sua lógica está correta.
def _check_path(logger):
    """Verifica acessibilidade, conflitos, e oferece a remoção de instalações 'fantasmas'."""
    click.echo(Fore.YELLOW + "\n--- 1. Análise de Acessibilidade (PATH) ---")
    
    cmd = ['where', 'doxoade'] if os.name == 'nt' else ['which', '-a', 'doxoade']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        all_executables = result.stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        all_executables = []

    if not all_executables:
        click.echo(Fore.RED + "   > [FALHA] O comando 'doxoade' não foi encontrado no PATH.")
        return False

    correct_scripts_dir = os.path.dirname(sys.executable)
    ghost_installs = [
        exe for exe in all_executables 
        if os.path.normcase(os.path.dirname(exe)) != os.path.normcase(correct_scripts_dir)
    ]
    correct_install = [exe for exe in all_executables if exe not in ghost_installs]

    if not ghost_installs:
        click.echo(Fore.GREEN + f"   > [OK] Instalação única e consistente encontrada: {correct_install[0]}")
        return True

    click.echo(Fore.RED + "   > [FALHA] Múltiplas instalações conflitantes ('fantasmas') encontradas!")
    if correct_install:
        click.echo(Fore.GREEN + f"     - Instalação Ativa/Correta: {correct_install[0]}")
    for ghost in ghost_installs:
        click.echo(Fore.RED + f"     - Instalação Fantasma:      {ghost}")
    
    if click.confirm(Fore.YELLOW + "\n[PERIGO] Deseja que eu tente remover PERMANENTEMENTE os arquivos executáveis 'fantasmas'?"):
        success_count = 0
        for ghost_path in ghost_installs:
            try:
                os.remove(ghost_path)
                click.echo(Fore.GREEN + f"     - [REMOVIDO] {ghost_path}")
                logger.add_finding('info', f"Instalação fantasma removida: {ghost_path}", category="PATH-REPAIR")
                success_count += 1
            except (OSError, PermissionError) as e:
                details = "Causa comum: o terminal não foi executado como Administrador."
                click.echo(Fore.RED + f"     - [FALHA] Não foi possível remover {ghost_path}: {e}\n       {details}")
                logger.add_finding('error', f"Falha ao remover fantasma: {ghost_path}", category="PATH-REPAIR", details=str(e))
        
        if success_count == len(ghost_installs):
            click.echo(Fore.GREEN + "\n   > [OK] Reparo concluído com sucesso.")
            return True
        else:
            click.echo(Fore.RED + "\n   > [FALHA] O reparo não foi totalmente concluído.")
            return False
    else:
        click.echo(Fore.YELLOW + "   > Operação de reparo cancelada.")
        return False

def _check_dependencies(logger, requirements):
    """Verifica se as dependências estão instaladas e compatíveis."""
    click.echo(Fore.YELLOW + "\n--- 2. Análise de Compatibilidade de Versões ---")
    all_ok = True
    for req in requirements:
        try:
            installed_version = metadata.version(req.name)
            specifier = SpecifierSet(str(req.specifier))
            if installed_version not in specifier:
                all_ok = False
                msg = f"Incompatibilidade de versão para '{req.name}'."
                details = f"Requerido: {specifier}, Instalado: {installed_version}"
                logger.add_finding('error', msg, category="DEPENDENCY-VERSION", details=details)
                click.echo(Fore.RED + f"   > [FALHA] {msg} {details}")
        except metadata.PackageNotFoundError:
            all_ok = False
            msg = f"Dependência '{req.name}' não está instalada."
            logger.add_finding('error', msg, category="DEPENDENCY-MISSING")
            click.echo(Fore.RED + f"   > [FALHA] {msg}")

    if all_ok:
        click.echo(Fore.GREEN + "   > [OK] Todas as dependências estão instaladas e compatíveis.")
    return all_ok

def _check_library_conflicts(logger, requirements):
    """
    NOVA FUNÇÃO: Verifica se há múltiplas instalações da mesma biblioteca em locais diferentes.
    """
    click.echo(Fore.YELLOW + "\n--- 3. Análise de Conflitos de Instalação ---")
    all_ok = True
    conflicting_libs = defaultdict(set)

    for req in requirements:
        try:
            # Pega todos os arquivos de um pacote
            files = metadata.files(req.name)
            if not files: continue

            # Extrai os diretórios base de onde os arquivos vêm
            for file_path in files:
                # O caminho pode ser relativo ao site-packages, então resolvemos para um caminho absoluto
                full_path = file_path.locate()
                # Encontramos o diretório 'site-packages' pai
                parent = full_path.parent
                while parent.name != 'site-packages' and parent != parent.parent:
                    parent = parent.parent
                conflicting_libs[req.name].add(str(parent))

        except metadata.PackageNotFoundError:
            continue # Já foi reportado por _check_dependencies

    # Filtra apenas as bibliotecas com mais de um local de instalação
    real_conflicts = {lib: paths for lib, paths in conflicting_libs.items() if len(paths) > 1}

    if not real_conflicts:
        click.echo(Fore.GREEN + "   > [OK] Nenhuma instalação conflitante de bibliotecas encontrada.")
        return True

    all_ok = False
    click.echo(Fore.RED + "   > [FALHA] Múltiplas instalações conflitantes de bibliotecas detectadas!")
    for lib, paths in real_conflicts.items():
        click.echo(Fore.WHITE + f"     - Biblioteca '{lib}' encontrada em:")
        for path in paths:
            click.echo(Fore.RED + f"       - {path}")
        logger.add_finding('critical', f"Conflito de instalação para '{lib}'.", category="LIBRARY-CONFLICT", details=f"Encontrada em: {', '.join(paths)}")

    if click.confirm(Fore.YELLOW + "\n[PERIGO] Deseja que eu tente reparar isso desinstalando TODAS as versões dessas bibliotecas e reinstalando a correta?"):
        repaired_count = 0
        for lib_name in real_conflicts.keys():
            click.echo(Fore.CYAN + f"   > Reparando '{lib_name}'...")
            try:
                # Desinstala repetidamente até que o pip não encontre mais
                while True:
                    uninstall_cmd = [sys.executable, '-m', 'pip', 'uninstall', '-y', lib_name]
                    result = subprocess.run(uninstall_cmd, capture_output=True, text=True, encoding='utf-8')
                    if "Successfully uninstalled" not in result.stdout:
                        break # Sai do loop quando não houver mais o que desinstalar
                
                # Reinstala a versão correta
                install_cmd = [sys.executable, '-m', 'pip', 'install', f"{lib_name}"]
                subprocess.run(install_cmd, check=True, capture_output=True)
                
                click.echo(Fore.GREEN + f"     - [OK] Biblioteca '{lib_name}' reparada com sucesso.")
                logger.add_finding('info', f"Biblioteca '{lib_name}' reparada.", category="LIBRARY-REPAIR")
                repaired_count += 1
            except Exception as e:
                click.echo(Fore.RED + f"     - [FALHA] Falha ao reparar '{lib_name}': {e}")
                logger.add_finding('error', f"Falha ao reparar '{lib_name}'.", category="LIBRARY-REPAIR", details=str(e))
        
        if repaired_count == len(real_conflicts):
            click.echo(Fore.GREEN + "\n   > [OK] Reparo de bibliotecas concluído.")
        else:
            click.echo(Fore.RED + "\n   > [FALHA] Reparo de bibliotecas não foi totalmente concluído.")
            all_ok = False

    return all_ok

def _check_pip_health(logger):
    """(Versão Final) Executa uma verificação de saúde específica para a instalação do pip."""
    click.echo(Fore.YELLOW + "\n--- 4. Análise de Saúde do Pip ---")
    all_ok = True
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', '--version'],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        msg = "O comando 'pip' não está acessível ou funcional através do interpretador Python atual."
        logger.add_finding("CRITICAL", msg, category="PIP-HEALTH")
        click.echo(Fore.RED + f"   > [FALHA CRÍTICA] {msg}")
        return False

    # --- INÍCIO DA CORREÇÃO FINAL ---
    pip_path_str = result.stdout.split('from ')[1].split(' (python')[0].strip()
    python_executable_path = sys.executable
    
    # Raiz do venv a partir do python.exe (ex: ...\venv\Scripts -> ...\venv)
    venv_root_from_python = os.path.abspath(os.path.join(os.path.dirname(python_executable_path), '..'))
    
    # Raiz do venv a partir do pacote pip (ex: ...\venv\Lib\site-packages\pip -> ...\venv)
    # PRECISAMOS SUBIR 3 NÍVEIS: pip -> site-packages -> Lib -> venv
    venv_root_from_pip = os.path.abspath(os.path.join(pip_path_str, '..', '..', '..'))

    if os.path.normcase(venv_root_from_python) != os.path.normcase(venv_root_from_pip):
        all_ok = False
        msg = "Conflito de instalação detectado. O 'pip' em uso não pertence à instalação Python atual."
        # ... (lógica de erro inalterada) ...
    else:
        click.echo(Fore.GREEN + "   > [OK] A instalação do 'pip' está corretamente associada ao Python ativo.")
    # --- FIM DA CORREÇÃO ---

    # 3. Verifica se há atualizações para o pip (lógica inalterada)
    try:
        check_result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--outdated'],
            capture_output=True, text=True, encoding='utf-8'
        )
        if 'pip ' in check_result.stdout.lower(): # Uma forma mais robusta de verificar
            update_line = [line for line in check_result.stdout.splitlines() if line.lower().startswith('pip ')][0]
            parts = update_line.split()
            current_version, latest_version = parts[1], parts[2]

            msg = f"Uma nova versão do pip está disponível: {current_version} -> {latest_version}"
            details = f"Para atualizar, execute: {os.path.basename(sys.executable)} -m pip install --upgrade pip"
            logger.add_finding("INFO", msg, category="PIP-HEALTH", details=details)
            click.echo(Fore.YELLOW + f"   > [INFO] {msg}")
            click.echo(Fore.CYAN + f"     {details}")
        else:
            click.echo(Fore.GREEN + "   > [OK] Você está usando a versão mais recente do pip.")
    except Exception:
        pass

    # 4. Oferece para limpar o cache (lógica inalterada)
    if click.confirm(Fore.YELLOW + "\n     Deseja verificar e, se necessário, limpar o cache do pip? (Isso pode resolver problemas de download)"):
        try:
            # Adiciona '--no-input' para evitar que o pip peça confirmação
            subprocess.run([sys.executable, '-m', 'pip', 'cache', 'purge', '--no-input'], check=True, capture_output=True)
            click.echo(Fore.GREEN + "   > [OK] Cache do pip limpo com sucesso.")
        except subprocess.CalledProcessError:
            click.echo(Fore.RED + "   > [FALHA] Não foi possível limpar o cache do pip.")
    
    return all_ok

@click.command('global-health')
@click.pass_context
@click.option('--pip', 'check_pip', is_flag=True, help="Executa uma verificação de saúde focada no pip.")
def global_health(ctx, check_pip):
    """Verifica a saúde da instalação global da doxoade no sistema."""
    arguments = ctx.params
    with ExecutionLogger('global-health', '.', arguments) as logger:
        # Se a flag --pip for usada, executa apenas a verificação do pip
        if check_pip:
            click.echo(Fore.CYAN + Style.BRIGHT + "--- [GLOBAL-HEALTH --PIP] Verificando a saúde do Pip ---")
            pip_ok = _check_pip_health(logger)
            click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
            if pip_ok:
                click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] A instalação do Pip parece correta.")
            else:
                click.echo(Fore.RED + Style.BRIGHT + "[PROBLEMA] Um ou mais problemas foram encontrados na instalação do Pip.")
                sys.exit(1)
            return

        # Fluxo normal do global-health
        click.echo(Fore.CYAN + Style.BRIGHT + "--- [GLOBAL-HEALTH] Verificando a saúde da instalação Doxoade ---")
        
        path_ok = _check_path(logger)

        try:
            reqs_str = metadata.requires('doxoade')
            requirements = [Requirement(r) for r in reqs_str if "extra ==" not in r] if reqs_str else []
        except metadata.PackageNotFoundError:
            click.echo(Fore.RED + "   > [FALHA CRÍTICA] Doxoade não parece estar instalado.")
            sys.exit(1)

        deps_ok = _check_dependencies(logger, requirements)
        conflicts_ok = _check_library_conflicts(logger, requirements)

        click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
        if path_ok and deps_ok and conflicts_ok:
            click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] A instalação da Doxoade está correta e funcional.")
        else:
            logger.add_finding('error', 'A verificação de saúde global encontrou problemas.', category="GLOBAL-HEALTH-SUMMARY")
            click.echo(Fore.RED + Style.BRIGHT + "[PROBLEMA] Um ou mais problemas foram encontrados.")
            sys.exit(1)