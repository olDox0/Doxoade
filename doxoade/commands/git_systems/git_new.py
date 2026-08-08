# doxoade/doxoade/commands/git_systems/git_new.py
import os
import re
import sys
import click
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

__version__ = '35.0 Guardian (Auto-Audit & Autopilot)'

def _get_remote_default_branch():
    """🪽 HERMES: Descobre a branch padrão real do servidor (ex.: main)."""
    out = _run_git_command(['ls-remote', '--symref', 'origin', 'HEAD'], capture_output=True, silent_fail=True)
    if out:
        match = re.search(r'ref:\s+refs/heads/(\S+)\s+HEAD', out)
        if match:
            return match.group(1).strip()
    return None

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

def _auto_quarantine_gitignore(big_files):
    """
    🐺 ANÚBIS: Injeta regras de quarentena no .gitignore automaticamente.
    Impede que o 'git add .' subsequente readicione os arquivos gigantes.
    """
    gitignore_path = '.gitignore'
    quarantine_marker = '# --- Auto-Quarentena Doxoade Guardian ---'
    
    # Evita duplicar se já rodou antes
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            if quarantine_marker in f.read():
                return True # Já está em quarentena

    click.echo(Fore.YELLOW + '\n[ANÚBIS] Aplicando quarentena automática no .gitignore...')
    try:
        with open(gitignore_path, 'a', encoding='utf-8') as gitignore:
            gitignore.write(f'\n{quarantine_marker}\n')
            for f_path, _ in big_files:
                clean_path = f_path.replace('\\', '/')
                gitignore.write(f'{clean_path}\n')
                click.echo(Fore.RED + f'  ✘ Banido: {clean_path}')
        click.echo(Fore.GREEN + '[OK] Regras de exclusão seladas permanentemente.')
        return True
    except IOError as e:
        click.echo(Fore.RED + f'[ERRO] Falha ao escrever no .gitignore: {e}')
        return False

@click.command('git-new')
@click.pass_context
@click.argument('message')
@click.argument('remote_url')
def git_new(ctx, message, remote_url):
    """
    Automatiza a publicação de um projeto com auditoria de arquivos grandes.
    Autopilot: Corrige .gitignore e reconcilia branches (master/main).
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

        # PASSO 0: AUDITORIA (ANÚBIS)
        click.echo(Fore.CYAN + 'Passo 0: Auditando arquivos para o GitHub...')
        big_files = _check_large_files()
        
        if big_files:
            click.echo(Fore.RED + Style.BRIGHT + '\n[ALERTA] Arquivos gigantes detectados (Limite GitHub = 100MB):')
            for f, size in big_files:
                click.echo(Fore.RED + f'  - {f} ({size:.2f} MB)')
            
            # 🛡️ AÇÃO AUTOMÁTICA: Injeta no .gitignore antes de limpar o cache
            if _auto_quarantine_gitignore(big_files):
                click.echo(Fore.CYAN + '[OSÍRIS] Purgando o índice do Git (git rm -r --cached .)...')
                _run_git_command(['rm', '-r', '--cached', '.'], silent_fail=True)
                click.echo(Fore.GREEN + '[OK] Índice limpo. O monstro foi esquecido pelo Git.')
            else:
                click.echo(Fore.YELLOW + '[AVISO] Falha na quarentena. Prosseguindo por conta e risco...')
        else:
            click.echo(Fore.GREEN + '[OK] Nenhum arquivo gigante detectado.')

        # PASSO 1: REMOTE
        click.echo(Fore.YELLOW + f"\nPasso 1: Configurando remote 'origin' -> {remote_url}")
        _run_git_command(['remote', 'remove', 'origin'], capture_output=True, silent_fail=True)
        if not _run_git_command(['remote', 'add', 'origin', remote_url]):
            click.echo(Fore.RED + '[ERRO] Falha ao adicionar remote.')
            sys.exit(1)

        # PASSO 2: STAGE
        click.echo(Fore.YELLOW + 'Passo 2: Preparando arquivos (git add)...')
        _run_git_command(['add', '.'])

        # PASSO 3: COMMIT
        has_commits = _run_git_command(['rev-parse', '--verify', 'HEAD'], capture_output=True, silent_fail=True)
        if not has_commits:
            click.echo(Fore.YELLOW + 'Passo 3: Criando commit inicial...')
            _run_git_command(['commit', '-m', message])
        else:
            status = _run_git_command(['status', '--porcelain'], capture_output=True)
            if status and status.strip():
                click.echo(Fore.YELLOW + 'Passo 3: Commitando alterações pendentes...')
                _run_git_command(['commit', '-m', message])
            else:
                click.echo(Fore.GREEN + 'Passo 3: [PULADO] Nada a commitar (Índice limpo ou sem alterações).')

        # PASSO 4: PUSH INTELIGENTE (HERMES BRIDGE v2 - Default Branch Aware)
        current_branch = (_run_git_command(['branch', '--show-current'], capture_output=True) or 'master').strip()
        default_branch = _get_remote_default_branch()

        click.echo(Fore.YELLOW + f"\nPasso 4: Enviando para '{remote_url}'...")

        # 🪽 HERMES: Se a vitrine do GitHub (default) difere da branch local, unifica ANTES do push
        if default_branch and default_branch != current_branch:
            click.echo(Fore.CYAN + f'   > [HERMES] Branch padrão do remoto: "{default_branch}" (local: "{current_branch}").')
            _run_git_command(['fetch', 'origin', default_branch], silent_fail=True)
            click.echo(Fore.CYAN + f'   > Unificando históricos ({current_branch} + {default_branch})...')
            _run_git_command(['merge', f'origin/{default_branch}', '--allow-unrelated-histories', '--no-edit',
                              '-m', f'Hermes Bridge: unificação {current_branch} -> {default_branch}'], silent_fail=True)

        if _run_git_command(['push', '-u', 'origin', current_branch]):
            # Garante que a VITRINE (default branch) também receba o conteúdo
            if default_branch and default_branch != current_branch:
                _run_git_command(['push', 'origin', f'{current_branch}:{default_branch}'], silent_fail=True)
                click.echo(Fore.GREEN + f'   > [OK] Vitrine "{default_branch}" sincronizada.')
            click.echo(Fore.GREEN + Style.BRIGHT + '\n[GIT-NEW] SUCESSO! Projeto publicado e sincronizado.')
            return

        # Fallbacks de reconciliação (mantidos da v35.0)
        click.echo(Fore.CYAN + '   > Tentando reconciliação (Pull --rebase)...')
        if _run_git_command(['pull', 'origin', current_branch, '--rebase', '--allow-unrelated-histories'], silent_fail=True):
            if _run_git_command(['push', '-u', 'origin', current_branch]):
                click.echo(Fore.GREEN + Style.BRIGHT + '\n[GIT-NEW] SUCESSO! (Reconciliado).')
                return
        click.echo(Fore.RED + '[ERRO FATAL] Push falhou mesmo após todas as tentativas de reconciliação.')
        sys.exit(1)