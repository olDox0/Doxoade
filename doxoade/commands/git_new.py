# doxoade/commands/git_new.py
import sys
import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _run_git_command
)

__version__ = "34.1 Alfa (Auto-Reconcile)"

@click.command('git-new')
@click.pass_context
@click.argument('message')
@click.argument('remote_url')
def git_new(ctx, message, remote_url):
    """
    Automatiza a publicação de um novo projeto local em um repositório remoto.
    Tenta reconciliar automaticamente se o remoto não estiver vazio.
    """
    path = '.'
    arguments = ctx.params

    with ExecutionLogger('git-new', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [GIT-NEW] Publicando novo projeto no GitHub ---")
        
        # Passo 1: Adicionar o repositório remoto
        click.echo(Fore.YELLOW + f"Passo 1: Adicionando remote 'origin' -> {remote_url}")
        # Remove origin antigo se existir para garantir que estamos apontando para o lugar certo
        _run_git_command(['remote', 'remove', 'origin'], capture_output=True, silent_fail=True)
        
        if not _run_git_command(['remote', 'add', 'origin', remote_url]):
            msg = "Falha ao adicionar o remote."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            sys.exit(1)
        click.echo(Fore.GREEN + "[OK] Remote configurado.")
    
        # Passo 2: Adicionar todos os arquivos ao staging
        click.echo(Fore.YELLOW + "\nPasso 2: Preparando arquivos (git add)...")
        if not _run_git_command(['add', '.']):
            logger.add_finding('error', "Falha ao executar 'git add .'.")
            sys.exit(1)
        
        # Passo 3: Fazer o commit inicial (se necessário)
        # Verifica se já existe commit para não duplicar ou falhar se nada mudou
        has_commits = _run_git_command(['rev-parse', '--verify', 'HEAD'], capture_output=True, silent_fail=True)
        
        if not has_commits:
            click.echo(Fore.YELLOW + f"\nPasso 3: Criando commit inicial: '{message}'...")
            if not _run_git_command(['commit', '-m', message]):
                logger.add_finding('error', "Falha ao executar 'git commit'.")
                sys.exit(1)
            click.echo(Fore.GREEN + "[OK] Commit criado.")
        else:
            # Se já tem commit, apenas verifica se há mudanças pendentes para commitar
            status = _run_git_command(['status', '--porcelain'], capture_output=True)
            if status and status.strip():
                click.echo(Fore.YELLOW + f"\nPasso 3: Commitando alterações pendentes...")
                _run_git_command(['commit', '-m', message])
                click.echo(Fore.GREEN + "[OK] Alterações commitadas.")
            else:
                click.echo(Fore.GREEN + "\nPasso 3: [PULADO] Nada a commitar (tree clean).")
    
        # Passo 4: Push com Auto-Reconciliação
        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True) or "main"
        current_branch = current_branch.strip()
        
        click.echo(Fore.YELLOW + f"\nPasso 4: Enviando para '{remote_url}' (Branch: {current_branch})...")
        
        # Tenta o push normal primeiro
        if _run_git_command(['push', '--set-upstream', 'origin', current_branch]):
            # SUCESSO NO PRIMEIRO PUSH
            logger.add_finding('info', f"Projeto publicado com sucesso em {remote_url}")
            click.echo(Fore.GREEN + Style.BRIGHT + "\n[GIT-NEW] SUCESSO! Projeto publicado.")
            click.echo(f"Acesse: {remote_url}")
            return

        # SE FALHAR: Tenta Reconciliação (Históricos não relacionados)
        click.echo(Fore.RED + "\n[ALERTA] Push rejeitado. O repositório remoto não está vazio (possui README/License?).")
        click.echo(Fore.CYAN + "   > Iniciando protocolo de reconciliação (Pull --rebase --allow-unrelated)...")
        
        # Pull com flag para permitir misturar históricos
        pull_success = _run_git_command([
            'pull', 'origin', current_branch, 
            '--rebase', 
            '--allow-unrelated-histories'
        ])
        
        if pull_success:
            click.echo(Fore.GREEN + "   > [OK] Históricos fundidos com sucesso.")
            click.echo(Fore.YELLOW + "   > Tentando push novamente...")
            
            if _run_git_command(['push', '--set-upstream', 'origin', current_branch]):
                click.echo(Fore.GREEN + Style.BRIGHT + "\n[GIT-NEW] SUCESSO! Projeto publicado (reconciliado).")
                click.echo(f"Acesse: {remote_url}")
            else:
                msg = "Falha final no push após reconciliação."
                logger.add_finding('error', msg)
                click.echo(Fore.RED + f"[ERRO FATAL] {msg}")
                sys.exit(1)
        else:
            msg = "Falha na reconciliação (Conflito de arquivos?)."
            logger.add_finding('error', msg)
            click.echo(Fore.RED + f"[ERRO] {msg}")
            click.echo(Fore.YELLOW + "Sugestão: Use 'doxoade sync --safe' ou resolva os conflitos manualmente.")
            sys.exit(1)