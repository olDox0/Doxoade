# DEV.V10-20251021. >>>
# doxoade/commands/global_health.py
# atualizado em 2025/10/21 - Versão do projeto 42(Ver), Versão da função 1.1(Fnc).
# Descrição: Corrige o bug na detecção do PATH ao usar 'where doxoade' (sem extensão)
# para encontrar o executável .exe gerado pelo pip, em vez de procurar por .bat.

import sys
import os
import subprocess
#import shutil
from importlib import metadata
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger

def _check_path(logger):
    """Verifica acessibilidade, conflitos, e oferece a remoção de instalações 'fantasmas'."""
    click.echo(Fore.YELLOW + "\n--- 1. Análise de Acessibilidade (PATH) ---")
    
    # --- UTILITARIO 1: Encontrar todos os executáveis ---
    cmd = ['where', 'doxoade'] if os.name == 'nt' else ['which', '-a', 'doxoade']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        all_executables = result.stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        all_executables = []

    if not all_executables:
        # Lógica para guiar a instalação (não é o foco agora, mas deve existir)
        click.echo(Fore.RED + "   > [FALHA] O comando 'doxoade' não foi encontrado no PATH.")
        return False, None

    # --- UTILITARIO 2: Identificar a instalação correta e os "fantasmas" ---
    # A instalação "correta" é a que está no mesmo diretório de scripts do Python que está nos executando.
    correct_scripts_dir = os.path.dirname(sys.executable)
    ghost_installs = [
        exe for exe in all_executables 
        if os.path.normcase(os.path.dirname(exe)) != os.path.normcase(correct_scripts_dir)
    ]
    correct_install = [
        exe for exe in all_executables if exe not in ghost_installs
    ]

    # --- UTILITARIO 3: Ação de Reparo Interativa ---
    if not ghost_installs:
        click.echo(Fore.GREEN + f"   > [OK] Instalação única e consistente encontrada: {correct_install[0]}")
        return True, correct_install[0]

    # FLUXO 1: Informar o usuário sobre os fantasmas
    click.echo(Fore.RED + f"   > [FALHA] Múltiplas instalações conflitantes ('fantasmas') encontradas!")
    click.echo(Fore.GREEN + f"     - Instalação Ativa/Correta: {correct_install[0]}")
    for ghost in ghost_installs:
        click.echo(Fore.RED + f"     - Instalação Fantasma:      {ghost}")
    
    # FLUXO 2: Solicitar permissão para o reparo
    if click.confirm(Fore.YELLOW + "\n[PERIGO] Deseja que eu tente remover PERMANENTEMENTE os arquivos executáveis 'fantasmas'?"):
        success_count = 0
        click.echo(Fore.CYAN + "   > Iniciando remoção...")
        for ghost_path in ghost_installs:
            try:
                os.remove(ghost_path)
                click.echo(Fore.GREEN + f"     - [REMOVIDO] {ghost_path}")
                logger.add_finding('info', f"Instalação fantasma removida: {ghost_path}")
                success_count += 1
            except (OSError, PermissionError) as e:
                details = "Causa comum: o terminal não foi executado como Administrador."
                click.echo(Fore.RED + f"     - [FALHA] Não foi possível remover {ghost_path}: {e}\n       {details}")
                logger.add_finding('error', f"Falha ao remover fantasma: {ghost_path}", details=str(e))
        
        if success_count == len(ghost_installs):
            click.echo(Fore.GREEN + "\n   > [OK] Reparo concluído com sucesso. O ambiente está limpo.")
            return True, correct_install[0]
        else:
            click.echo(Fore.RED + "\n   > [FALHA] O reparo não foi totalmente concluído. Execute como Administrador e tente novamente.")
            return False, None
    else:
        click.echo(Fore.YELLOW + "   > Operação de reparo cancelada pelo usuário.")
        return False, None

def _check_dependencies(logger):
    """Verifica se as dependências da doxoade estão instaladas e com versões compatíveis."""
    click.echo(Fore.YELLOW + "\n--- 2. Análise de Dependências Internas ---")
    all_ok = True
    try:
        # --- Utilitário 1: Obter requisitos da própria instalação ---
        reqs_str = metadata.requires('doxoade')
        if not reqs_str:
            logger.add_finding('warning', "Não foi possível ler os metadados de dependência da doxoade.")
            click.echo(Fore.YELLOW, "   > [AVISO] Não foi possível verificar as dependências.")
            return True # Não é um erro fatal

        requirements = [Requirement(r) for r in reqs_str if "extra == 'dev'" not in r] # Ignora extras de dev

        # --- Utilitário 2: Verificar cada requisito ---
        for req in requirements:
            try:
                # --- Fluxo 1: Verificar se o pacote está instalado ---
                installed_version = metadata.version(req.name)
                specifier = SpecifierSet(str(req.specifier))
                # --- Fluxo 2: Verificar se a versão satisfaz a especificação ---
                if installed_version not in specifier:
                    all_ok = False
                    msg = f"Incompatibilidade de versão para '{req.name}'."
                    details = f"Requerido: {specifier}, Instalado: {installed_version}"
                    logger.add_finding('error', msg, details=details)
                    click.echo(Fore.RED + f"   > [FALHA] {msg} {details}")
            except metadata.PackageNotFoundError:
                all_ok = False
                msg = f"Dependência '{req.name}' não está instalada."
                logger.add_finding('error', msg)
                click.echo(Fore.RED + f"   > [FALHA] {msg}")

    except Exception as e:
        logger.add_finding('error', "Falha ao analisar as dependências da doxoade.", details=str(e))
        click.echo(Fore.RED + f"   > [FALHA] Ocorreu um erro ao verificar as dependências: {e}")
        return False

    if all_ok:
        click.echo(Fore.GREEN + "   > [OK] Todas as dependências estão instaladas e compatíveis.")
    return all_ok

@click.command('global-health')
@click.pass_context
def global_health(ctx):
    """Verifica a saúde da instalação global da doxoade no sistema."""
    arguments = ctx.params
    with ExecutionLogger('global-health', '.', arguments) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + "--- [GLOBAL-HEALTH] Verificando a saúde da instalação Doxoade ---")
        
        path_ok, _ = _check_path(logger)
        deps_ok = _check_dependencies(logger)

        integrity_ok = _verify_installation_integrity(logger)

        click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
        if path_ok and deps_ok and integrity_ok:
            click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] A instalação da Doxoade está correta e funcional.")
        else:
            logger.add_finding('error', 'A verificação de saúde global encontrou um ou mais problemas.')
            click.echo(Fore.RED + Style.BRIGHT + "[PROBLEMA] Um ou mais problemas foram encontrados. Verifique os detalhes acima.")
            sys.exit(1)
            
def _verify_installation_integrity(logger):
    """Executa uma sonda para garantir que as dependências principais são importáveis."""
    click.echo(Fore.YELLOW + "\n--- 3. Análise de Integridade da Instalação ---")
    
    # Sonda que tenta importar os pacotes mais fundamentais.
    _PROBE_SCRIPT = "import click; import colorama; import subprocess; print('OK')"
    
    try:
        # Usa sys.executable para garantir que estamos testando o Python
        # que está executando a própria doxoade.
        result = subprocess.run(
            [sys.executable, "-c", _PROBE_SCRIPT],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        if "OK" in result.stdout:
            click.echo(Fore.GREEN + "   > [OK] Dependências principais estão íntegras.")
            return True
        else:
            raise subprocess.CalledProcessError(1, "cmd", stdout=result.stdout, stderr=result.stderr)
            
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        msg = "Ambiente da doxoade parece corrompido. Dependências principais falharam ao importar."
        details = f"Recomendação: Execute um reparo forçado com pip:\n   > {os.path.basename(sys.executable)} -m pip install --force-reinstall -r requirements.txt"
        logger.add_finding('critical', msg, details=details)
        click.echo(Fore.RED + f"   > [FALHA CRÍTICA] {msg}")
        click.echo(Fore.CYAN + f"     {details}")
        return False