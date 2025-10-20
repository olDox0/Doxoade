# doxoade/commands/git_clean.py
import os
import sys
import fnmatch

import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _run_git_command

__version__ = "37.3 Alfa (Hardening)"

def _read_gitignore(path, logger):
    """Lê e processa os padrões do arquivo .gitignore."""
    gitignore_path = os.path.join(path, '.gitignore')
    if not os.path.exists(gitignore_path):
        logger.add_finding('error', "Arquivo .gitignore não encontrado.")
        return None
    try:
        with open(gitignore_path, 'r', encoding='utf-8', errors='replace') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except IOError as e:
        logger.add_finding('error', f"Não foi possível ler o .gitignore: {e}")
        return None

def _find_mismatched_files(ignore_patterns, logger):
    """Encontra arquivos rastreados pelo Git que correspondem aos padrões ignorados."""
    tracked_files_str = _run_git_command(['ls-files'], capture_output=True)
    if tracked_files_str is None:
        logger.add_finding('error', "Falha ao listar os arquivos rastreados pelo Git.")
        return None
    
    tracked_files = tracked_files_str.splitlines()
    files_to_remove = set()
    for pattern in ignore_patterns:
        normalized_pattern = pattern + '*' if pattern.endswith('/') else pattern
        matches = fnmatch.filter(tracked_files, normalized_pattern)
        files_to_remove.update(matches)
    return sorted(list(files_to_remove))

def _untrack_files(files_to_remove, logger):
    """Executa 'git rm --cached' para cada arquivo e verifica o sucesso."""
    click.echo(Fore.CYAN + "Removendo arquivos do índice do Git...")
    success_count = 0
    for f in files_to_remove:
        if _run_git_command(['rm', '--cached', f]):
            success_count += 1
    
    if success_count == len(files_to_remove):
        logger.add_finding('info', f"{success_count} arquivos removidos do rastreamento.", details=", ".join(files_to_remove))
        click.echo(Fore.GREEN + "\n[OK] Arquivos removidos do rastreamento.")
        click.echo(Fore.YELLOW + "Suas alterações foram preparadas (staged). Finalize com 'doxoade save'.")
        return True
    else:
        logger.add_finding('error', "Ocorreu um erro ao remover um ou mais arquivos do índice.")
        click.echo(Fore.RED + "[ERRO] Falha ao remover um ou mais arquivos.")
        return False

@click.command('git-clean')
@click.pass_context
def git_clean(ctx):
    """Força a remoção de arquivos já rastreados que correspondem ao .gitignore."""
    path = '.'
    arguments = ctx.params
    with ExecutionLogger('git-clean', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [GIT-CLEAN] Procurando por arquivos rastreados indevidamente ---")
        
        ignore_patterns = _read_gitignore(path, logger)
        if ignore_patterns is None: sys.exit(1)

        files_to_remove = _find_mismatched_files(ignore_patterns, logger)
        if files_to_remove is None: sys.exit(1)

        if not files_to_remove:
            click.echo(Fore.GREEN + "[OK] Nenhum arquivo rastreado indevidamente encontrado."); return
    
        click.echo(Fore.YELLOW + "\nArquivos rastreados que correspondem ao .gitignore:")
        for f in files_to_remove:
            click.echo(f"  - {f}")
        
        if click.confirm(Fore.RED + "\nDeseja parar de rastrear (untrack) TODOS estes arquivos?"):
            if not _untrack_files(files_to_remove, logger):
                sys.exit(1)