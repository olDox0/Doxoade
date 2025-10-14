# doxoade/commands/git_clean.py
import os
import sys
import fnmatch

import click
from colorama import Fore

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _run_git_command
)

__version__ = "34.0 Alfa"

@click.command('git-clean')
@click.pass_context
def git_clean(ctx):
    """Força a remoção de arquivos já rastreados que correspondem ao .gitignore."""
    path = '.'
    arguments = ctx.params

    with ExecutionLogger('git-clean', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [GIT-CLEAN] Procurando por arquivos rastreados indevidamente ---")
        
        gitignore_path = '.gitignore'
        if not os.path.exists(gitignore_path):
            msg = "Arquivo .gitignore não encontrado no diretório atual."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)

        try:
            with open(gitignore_path, 'r', encoding='utf-8', errors='replace') as f:
                ignore_patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except Exception as e:
            msg = f"Não foi possível ler o arquivo .gitignore: {e}"
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
        
        tracked_files_str = _run_git_command(['ls-files'], capture_output=True)
        if tracked_files_str is None:
            sys.exit(1)
        tracked_files = tracked_files_str.splitlines()
    
        files_to_remove = []
        for pattern in ignore_patterns:
            if pattern.endswith('/'):
                pattern += '*'
            matches = fnmatch.filter(tracked_files, pattern)
            if matches:
                files_to_remove.extend(matches)
        
        files_to_remove = sorted(list(set(files_to_remove)))

        if not files_to_remove:
            click.echo(Fore.GREEN + "[OK] Nenhum arquivo rastreado indevidamente encontrado. Seu repositório está limpo!")
            return
    
        click.echo(Fore.YELLOW + "\nOs seguintes arquivos estão sendo rastreados pelo Git, mas correspondem a padrões no seu .gitignore:")
        for f in files_to_remove:
            click.echo(f"  - {f}")
        
        if click.confirm(Fore.RED + "\nVocê tem certeza de que deseja parar de rastrear (untrack) TODOS estes arquivos?", abort=True):
            click.echo(Fore.CYAN + "Removendo arquivos do índice do Git...")
            success = True
            for f in files_to_remove:
                if not _run_git_command(['rm', '--cached', f]):
                    success = False
            
            if success:
                logger.add_finding('info', f"{len(files_to_remove)} arquivos removidos do rastreamento.", details=", ".join(files_to_remove))
                click.echo(Fore.GREEN + "\n[OK] Arquivos removidos do rastreamento com sucesso.")
                click.echo(Fore.YELLOW + "Suas alterações foram preparadas (staged).")
                click.echo(Fore.YELLOW + "Para finalizar, execute o seguinte comando:")
                click.echo(Fore.CYAN + '  doxoade save "Limpeza de arquivos ignorados"')
            else:
                logger.add_finding('error', "Ocorreu um erro ao remover um ou mais arquivos do índice do Git.")
                click.echo(Fore.RED + "[ERRO] Ocorreu um erro ao remover um ou mais arquivos.")
                sys.exit(1)