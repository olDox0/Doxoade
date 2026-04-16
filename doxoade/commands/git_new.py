# doxoade/doxoade/commands/git_new.py
import sys
import os
import click
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
__version__ = '34.2 Guardian (Auto-Audit)'

def _check_large_files(threshold_mb=99):
    """Procura por arquivos que excedem o limite do GitHub (>100MB)."""
    large_files = []
    for root, dirs, files in os.walk('.'):
        if '.git' in root:
            continue
        for f in files:
            fp = os.path.join(root, f)
            try:
                size_mb = os.path.getsize(fp) / (1024 * 1024)
                if size_mb > threshold_mb:
                    large_files.append((fp, size_mb))
            except OSError:
                continue
    return large_files

@click.command('git-new')
@click.pass_context
@click.argument('message')
@click.argument('remote_url')
def git_new(ctx, message, remote_url):
    """
    Automatiza a publicação de um projeto com auditoria de arquivos grandes.
    Tenta reconciliar automaticamente se o remoto não estiver vazio.
    """
    path = '.'
    arguments = ctx.params
    with ExecutionLogger('git-new', path, arguments) as logger:
        click.echo(Fore.CYAN + f'--- [GIT-NEW v{__version__}] Publicando no GitHub ---')
        in_repo = _run_git_command(['rev-parse', '--is-inside-work-tree'], capture_output=True, silent_fail=True)
        if in_repo != 'true':
            child_repos = [d for d in os.listdir('.') if os.path.isdir(os.path.join(d, '.git'))]
            if len(child_repos) == 1:
                os.chdir(child_repos[0])
                click.echo(Fore.CYAN + f'[AUTO] Entrando em: {child_repos[0]}')
            else:
                click.echo(Fore.YELLOW + '[INFO] Inicializando novo repositório Git local...')
                _run_git_command(['init'])
        click.echo(Fore.CYAN + 'Passo 0: Auditando arquivos para o GitHub...')
        big_files = _check_large_files()
        if big_files:
            click.echo(Fore.RED + Style.BRIGHT + '\n[ALERTA] Arquivos gigantes detectados (Limite GitHub = 100MB):')
            for f, size in big_files:
                click.echo(Fore.RED + f'  - {f} ({size:.2f} MB)')
            click.echo(Fore.YELLOW + '\nSugestão: Adicione-os ao .gitignore antes de prosseguir.')
            if click.confirm(Fore.CYAN + 'Deseja que eu limpe o índice (git rm --cached) para forçar o .gitignore?', default=True):
                _run_git_command(['rm', '-r', '--cached', '.'], silent_fail=True)
                click.echo(Fore.GREEN + '[OK] Índice limpo. Agora certifique-se de que o .gitignore está correto.')
            else:
                click.echo(Fore.YELLOW + '[AVISO] Prosseguindo por conta e risco... O push pode falhar.')
        click.echo(Fore.YELLOW + f"\nPasso 1: Configurando remote 'origin' -> {remote_url}")
        _run_git_command(['remote', 'remove', 'origin'], capture_output=True, silent_fail=True)
        if not _run_git_command(['remote', 'add', 'origin', remote_url]):
            click.echo(Fore.RED + '[ERRO] Falha ao adicionar remote.')
            sys.exit(1)
        click.echo(Fore.YELLOW + 'Passo 2: Preparando arquivos (git add)...')
        _run_git_command(['add', '.'])
        has_commits = _run_git_command(['rev-parse', '--verify', 'HEAD'], capture_output=True, silent_fail=True)
        if not has_commits:
            click.echo(Fore.YELLOW + f'Passo 3: Criando commit inicial...')
            _run_git_command(['commit', '-m', message])
        else:
            status = _run_git_command(['status', '--porcelain'], capture_output=True)
            if status and status.strip():
                click.echo(Fore.YELLOW + 'Passo 3: Commitando alterações pendentes...')
                _run_git_command(['commit', '-m', message])
            else:
                click.echo(Fore.GREEN + 'Passo 3: [PULADO] Nada a commitar.')
        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True) or 'master'
        current_branch = current_branch.strip()
        click.echo(Fore.YELLOW + f"\nPasso 4: Enviando para '{remote_url}'...")
        if _run_git_command(['push', '-u', 'origin', current_branch]):
            click.echo(Fore.GREEN + Style.BRIGHT + '\n[GIT-NEW] SUCESSO! Projeto publicado.')
            return
        click.echo(Fore.CYAN + '   > Tentando reconciliação (Pull --rebase)...')
        if _run_git_command(['pull', 'origin', current_branch, '--rebase', '--allow-unrelated-histories']):
            if _run_git_command(['push', '-u', 'origin', current_branch]):
                click.echo(Fore.GREEN + Style.BRIGHT + '\n[GIT-NEW] SUCESSO! (Reconciliado).')
            else:
                click.echo(Fore.RED + '[ERRO FATAL] Push falhou mesmo após reconciliação.')
        else:
            click.echo(Fore.RED + '[ERRO] Falha na fusão de históricos.')
