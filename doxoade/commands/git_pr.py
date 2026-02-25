import re
import click
from doxoade.tools.doxcolors import Fore
from doxoade.tools.logger import ExecutionLogger
from doxoade.tools.git import _run_git_command


def _current_branch():
    return (_run_git_command(['branch', '--show-current'], capture_output=True) or '').strip()


def _remote_url(remote_name='origin'):
    return (_run_git_command(['remote', 'get-url', remote_name], capture_output=True, silent_fail=True) or '').strip()


def _to_https_remote(url):
    if url.startswith('git@github.com:'):
        return 'https://github.com/' + url.split(':', 1)[1].replace('.git', '')
    if url.startswith('https://github.com/'):
        return url.replace('.git', '')
    return ''


def _build_compare_url(remote_url, branch, base):
    base_url = _to_https_remote(remote_url)
    if not base_url:
        return ''
    return f'{base_url}/compare/{base}...{branch}?expand=1'


def _resolve_base_branch(base):
    """Valida branch base local. Faz fallback para main/master quando necessário."""
    if _run_git_command(['rev-parse', '--verify', base], capture_output=True, silent_fail=True):
        return base
    for fallback in ('main', 'master'):
        if fallback != base and _run_git_command(['rev-parse', '--verify', fallback], capture_output=True, silent_fail=True):
            click.echo(Fore.YELLOW + f"[AVISO] Base '{base}' não encontrada localmente. Usando '{fallback}'.")
            return fallback
    click.echo(Fore.YELLOW + f"[AVISO] Base '{base}' não encontrada. Mantendo valor informado para comparação remota.")
    return base


@click.command('pr')
@click.pass_context
@click.option('--status', 'show_status', is_flag=True, help='Mostra status do branch para abertura de PR.')
@click.option('--push', is_flag=True, help='Faz push da branch atual (set-upstream se necessário).')
@click.option('--open', 'open_url', is_flag=True, help='Exibe URL pronta para abrir PR no GitHub.')
@click.option('--base', default='main', help='Branch base da PR (default: main).')
@click.option('--template', is_flag=True, help='Gera título e bullets com base nos commits locais.')
def pr(ctx, show_status, push, open_url, base, template):
    """Assistente inteligente para preparar pull requests."""
    with ExecutionLogger('pr', '.', ctx.params):
        branch = _current_branch()
        if not branch:
            click.echo(Fore.RED + '[ERRO] Não foi possível detectar o branch atual.')
            return

        base = _resolve_base_branch(base)

        remote = _remote_url('origin')
        tracking = _run_git_command(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], capture_output=True, silent_fail=True)

        if show_status:
            click.echo(Fore.CYAN + f'--- [PR] Diagnóstico da branch {branch} ---')
            status = _run_git_command(['status', '-sb'], capture_output=True) or ''
            click.echo(status if status else '(status indisponível)')
            ahead = _run_git_command(['rev-list', '--count', f'{base}..{branch}'], capture_output=True, silent_fail=True) or '0'
            behind = _run_git_command(['rev-list', '--count', f'{branch}..{base}'], capture_output=True, silent_fail=True) or '0'
            click.echo(Fore.WHITE + f'Commits para PR: {ahead} | Defasagem para {base}: {behind}')

        if push:
            if tracking and tracking.strip():
                ok = _run_git_command(['push'])
            else:
                ok = _run_git_command(['push', '--set-upstream', 'origin', branch])
            if ok:
                click.echo(Fore.GREEN + '[OK] Branch enviada para o remoto.')
            else:
                click.echo(Fore.RED + '[ERRO] Falha no push da branch atual.')
                return

        if template:
            log_text = _run_git_command(['log', '--oneline', f'{base}..{branch}'], capture_output=True, silent_fail=True) or ''
            lines = [line.strip() for line in log_text.splitlines() if line.strip()]
            title = lines[0].split(' ', 1)[1] if lines else f'Atualizações em {branch}'
            click.echo(Fore.CYAN + '\nSugestão de PR:')
            click.echo(f'Título: {title}')
            if lines:
                click.echo('Descrição:')
                for item in lines[:8]:
                    msg = re.sub(r'^[a-f0-9]+\s+', '', item)
                    click.echo(f'- {msg}')
            else:
                click.echo('- Sem commits novos em relação à base selecionada.')

        if open_url:
            compare_url = _build_compare_url(remote, branch, base)
            if compare_url:
                click.echo(Fore.GREEN + 'URL para criar Pull Request:')
                click.echo(compare_url)
            else:
                click.echo(Fore.YELLOW + '[AVISO] Remote não é GitHub HTTPS/SSH reconhecido.')

        if not any([show_status, push, template, open_url]):
            click.echo(ctx.get_help())
