# doxoade/commands/git_new.py
import sys
import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _run_git_command
)

__version__ = "34.0 Alfa"

@click.command('git-new')
@click.pass_context
@click.argument('message')
@click.argument('remote_url')
def git_new(ctx, message, remote_url):
    """
    Automatiza a publicação de um novo projeto local em um repositório remoto VAZIO.
    """
    path = '.'
    arguments = ctx.params

    with ExecutionLogger('git-new', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [GIT-NEW] Publicando novo projeto no GitHub ---")
        
        # Passo 1: Adicionar o repositório remoto
        click.echo(Fore.YELLOW + f"Passo 1: Adicionando remote 'origin' -> {remote_url}")
        if not _run_git_command(['remote', 'add', 'origin', remote_url]):
            msg = "Falha ao adicionar o remote. Motivo comum: o remote 'origin' já existe."
            logger.add_finding('error', msg, details="Se o projeto já tem um remote, use 'doxoade save' e 'git push' para atualizá-lo.")
            click.echo(Fore.RED + f"[ERRO] {msg}")
            click.echo(Fore.YELLOW + "Se o projeto já tem um remote, use 'doxoade save' e 'git push' para atualizá-lo.")
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Remote adicionado com sucesso.")
    
        # Passo 2: Adicionar todos os arquivos ao staging
        click.echo(Fore.YELLOW + "\nPasso 2: Adicionando todos os arquivos ao Git (git add .)...")
        if not _run_git_command(['add', '.']):
            logger.add_finding('error', "Falha ao executar 'git add .'.")
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Arquivos preparados para o commit.")
    
        # Passo 3: Fazer o commit inicial
        click.echo(Fore.YELLOW + f"\nPasso 3: Criando o primeiro commit com a mensagem: '{message}'...")
        if not _run_git_command(['commit', '-m', message]):
            logger.add_finding('error', "Falha ao executar 'git commit'.")
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Commit inicial criado.")
    
        # Passo 4: Fazer o push para o repositório remoto
        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True)
        if not current_branch:
            msg = "Não foi possível determinar o branch atual para o push."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
        
        click.echo(Fore.YELLOW + f"\nPasso 4: Enviando o branch '{current_branch}' para o remote 'origin' (git push)...")
        if not _run_git_command(['push', '--set-upstream', 'origin', current_branch]):
            msg = "Falha ao enviar para o repositório remoto."
            details = "Causas comuns: a URL do repositório está incorreta, você não tem permissão, ou o repositório remoto NÃO ESTÁ VAZIO."
            logger.add_finding('error', msg, details=details)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            click.echo(Fore.YELLOW + details)
            sys.exit(1)
        
        logger.add_finding('info', f"Projeto publicado com sucesso em {remote_url}")
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[GIT-NEW] Projeto publicado com sucesso!")
        click.echo(f"Você pode ver seu repositório em: {remote_url}")