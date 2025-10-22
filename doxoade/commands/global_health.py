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
    """Verifica a acessibilidade, conflitos e origem do comando 'doxoade' no PATH."""
    click.echo(Fore.YELLOW + "\n--- 1. Análise de Acessibilidade (PATH) ---")
    
    # --- Utilitário 1: Encontrar todos os executáveis ---
    # CORREÇÃO CRÍTICA: Procuramos por 'doxoade' sem extensão.
    cmd = ['where', 'doxoade'] if os.name == 'nt' else ['which', '-a', 'doxoade']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        executables = result.stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        executables = []

    # --- Fluxo 1: Nenhum comando encontrado ---
    if not executables:
        msg = "O comando 'doxoade' não foi encontrado no PATH do sistema."
        logger.add_finding('error', msg, details="A ferramenta não está universalmente acessível.")
        click.echo(Fore.RED + f"   > [FALHA] {msg}")
        return False, None

    # --- Utilitário 2: Analisar os executáveis encontrados ---
    unique_executables = sorted(list(set(p.lower() for p in executables)))
    
    # --- Fluxo 2: Conflito de múltiplas instalações ---
    if len(unique_executables) > 1:
        details = "\n".join(f"     - {exe}" for exe in unique_executables)
        msg = "Múltiplas instalações DIFERENTES de 'doxoade' encontradas."
        logger.add_finding('error', "Conflito crítico de PATH.", details=details)
        click.echo(Fore.RED + f"   > [FALHA] {msg}")
        click.echo(Fore.WHITE + details)
        return False, None

    executable_path = unique_executables[0]
    
    # --- Fluxo 3: Origem da instalação ---
    parent_dir_name = os.path.basename(os.path.dirname(executable_path))
    if parent_dir_name.lower() not in ['scripts', 'bin']:
        msg = "A instalação aponta para uma pasta de projeto, o que é instável."
        logger.add_finding('warning', "Configuração de PATH não recomendada.", details=f"Origem: {executable_path}")
        click.echo(Fore.YELLOW + f"   > [AVISO] {msg}")
    else:
        click.echo(Fore.GREEN + f"   > [OK] Instalação única encontrada: {executable_path}")
        
    return True, executable_path

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

        click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Diagnóstico Concluído ---")
        if path_ok and deps_ok:
            click.echo(Fore.GREEN + Style.BRIGHT + "[SAUDÁVEL] A instalação da Doxoade está correta e funcional.")
        else:
            logger.add_finding('error', 'A verificação de saúde global encontrou um ou mais problemas.')
            click.echo(Fore.RED + Style.BRIGHT + "[PROBLEMA] Um ou mais problemas foram encontrados. Verifique os detalhes acima.")
            sys.exit(1)