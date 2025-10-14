# doxoade/commands/git_workflow.py
import sys
#import re

import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _run_git_command

__version__ = "34.0 Alfa"

@click.command('release')
@click.pass_context
@click.argument('version')
@click.argument('message')
@click.option('--remote', default='origin', help='Nome do remote Git.')
def release(ctx, version, message, remote):
    """Cria e publica uma tag Git para formalizar uma nova versão."""
    with ExecutionLogger('release', '.', ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [RELEASE] Criando tag Git para versão {version} ---")
        if not _run_git_command(['tag', version, '-a', '-m', message]):
            logger.add_finding('error', 'Falha ao criar a tag Git local.')
            sys.exit(1)
        
        click.echo(Fore.GREEN + f"[OK] Tag Git '{version}' criada com sucesso.")
        
        if _run_git_command(['push', remote, version]):
            click.echo(Fore.GREEN + f"[OK] Tag '{version}' enviada para o remote '{remote}'.")
        else:
            logger.add_finding('warning', f"Falha ao enviar a tag para o remote '{remote}'.")

@click.command('sync')
@click.pass_context
@click.option('--remote', default='origin', help='Nome do remote Git.')
def sync(ctx, remote):
    """Sincroniza o branch local atual com o branch remoto (git pull && git push)."""
    with ExecutionLogger('sync', '.', ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [SYNC] Sincronizando branch com o remote '{remote}' ---")

        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True)
        if not current_branch:
            logger.add_finding('error', "Não foi possível determinar o branch atual.")
            sys.exit(1)
        
        click.echo(Fore.YELLOW + "\nPasso 1: Puxando as últimas alterações (git pull)...")
        if not _run_git_command(['pull', '--no-edit', remote, current_branch]):
            logger.add_finding('error', "Falha ao executar 'git pull'.")
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Repositório local atualizado.")

        click.echo(Fore.YELLOW + "\nPasso 2: Enviando alterações locais (git push)...")
        if "ahead" not in _run_git_command(['status', '-sb'], capture_output=True):
            click.echo(Fore.GREEN + "[OK] Nenhum commit local para enviar.")
        elif not _run_git_command(['push', remote, current_branch]):
            logger.add_finding('error', "Falha ao executar 'git push'.")
            sys.exit(1)
        else:
            click.echo(Fore.GREEN + "[OK] Commits locais enviados com sucesso.")