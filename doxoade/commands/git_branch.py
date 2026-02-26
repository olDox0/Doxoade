import sys
import re
import click
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.logger import ExecutionLogger
from doxoade.tools.git import _run_git_command


def _get_current_branch():
    branch = _run_git_command(['branch', '--show-current'], capture_output=True)
    return (branch or '').strip()


def _get_default_base_branch():
    for candidate in ('main', 'master'):
        if _run_git_command(['rev-parse', '--verify', candidate], capture_output=True, silent_fail=True):
            return candidate
    return 'main'


def _render_branches_table():
    """Renderiza lista de branches locais de forma previsível e legível."""
    fmt = '%(if)%(HEAD)%(then)*%(else) %(end)%(refname:short)\t%(upstream:short)\t%(objectname:short)\t%(contents:subject)'
    raw = _run_git_command(['for-each-ref', 'refs/heads', f'--format={fmt}'], capture_output=True) or ''
    if not raw.strip():
        click.echo('(sem branches)')
        return

    click.echo(Fore.WHITE + Style.BRIGHT + 'HEAD Branch                 Upstream                      Hash     Subject' + Style.RESET_ALL)
    for line in raw.splitlines():
        parts = line.split('\t')
        branch_col = parts[0] if len(parts) > 0 else ''
        upstream_col = parts[1] if len(parts) > 1 and parts[1] else '-'
        hash_col = parts[2] if len(parts) > 2 else '-'
        subject_col = parts[3] if len(parts) > 3 else '-'
        click.echo(f"{branch_col:<28} {upstream_col:<29} {hash_col:<8} {subject_col}")


@click.command('branch')
@click.pass_context
@click.option('--list', 'list_branches', is_flag=True, help='Lista branches locais com rastreamento.')
@click.option('--create', help='Cria uma branch e já faz checkout nela.')
@click.option('--switch', 'switch_to', help='Troca para uma branch existente.')
@click.option('--delete', 'delete_branch', help='Remove uma branch local.')
@click.option('--force-delete', is_flag=True, help='Força remoção da branch local (--delete).')
@click.option('--cleanup-merged', is_flag=True, help='Remove branches já mergeadas no branch base.')
@click.option('--base', default=None, help='Branch base para análises de merge (padrão: main/master).')
@click.option('--drop-commits', type=int, help='Apaga os últimos N commits da branch atual (reset --hard HEAD~N).')
@click.option('--origin', 'origin_guard', help='Publica HEAD em origin/<base> com guarda de hash remoto (ex.: --origin b935a7f).')
@click.option('--yes', is_flag=True, help='Não pede confirmação em operações destrutivas.')
def branch(ctx, list_branches, create, switch_to, delete_branch, force_delete, cleanup_merged, base, drop_commits, origin_guard, yes):
    """Gerencia branches e histórico local de forma assistida."""
    with ExecutionLogger('branch', '.', ctx.params) as logger:
        if list_branches:
            click.echo(Fore.CYAN + '--- [BRANCH] Status das branches locais ---')
            _run_git_command(['fetch', '--all', '--prune'], capture_output=True, silent_fail=True)
            _render_branches_table()
            return

        if create:
            click.echo(Fore.CYAN + f"Criando branch '{create}'...")
            if not _run_git_command(['checkout', '-b', create]):
                logger.add_finding('error', 'Falha ao criar branch.')
                sys.exit(1)
            click.echo(Fore.GREEN + f"[OK] Branch '{create}' criada e selecionada.")
            return

        if switch_to:
            click.echo(Fore.CYAN + f"Trocando para branch '{switch_to}'...")
            if not _run_git_command(['checkout', switch_to]):
                logger.add_finding('error', 'Falha ao trocar de branch.')
                sys.exit(1)
            click.echo(Fore.GREEN + '[OK] Branch ativa atualizada.')
            return

        if delete_branch:
            current = _get_current_branch()
            if delete_branch == current:
                click.echo(Fore.RED + '[ERRO] Não é permitido remover a branch atual.')
                sys.exit(1)

            if not yes and not click.confirm(Fore.YELLOW + f"Confirma remoção da branch local '{delete_branch}'?"):
                click.echo(Fore.YELLOW + '[BRANCH] Operação cancelada.')
                return

            delete_flag = '-D' if force_delete else '-d'
            if not _run_git_command(['branch', delete_flag, delete_branch]):
                logger.add_finding('error', f'Falha ao remover branch {delete_branch}.')
                sys.exit(1)
            click.echo(Fore.GREEN + f"[OK] Branch '{delete_branch}' removida.")
            return

        if cleanup_merged:
            base_branch = base or _get_default_base_branch()
            click.echo(Fore.CYAN + f"Limpando branches já mergeadas em '{base_branch}'...")
            merged = _run_git_command(['branch', '--merged', base_branch], capture_output=True) or ''
            candidates = []
            current = _get_current_branch()
            for line in merged.splitlines():
                branch_name = line.replace('*', '').strip()
                if branch_name and branch_name not in {base_branch, current}:
                    candidates.append(branch_name)

            if not candidates:
                click.echo(Fore.GREEN + '[OK] Nenhuma branch mergeada para limpar.')
                return

            click.echo(Fore.YELLOW + 'Branches candidatas: ' + ', '.join(candidates))
            if not yes and not click.confirm('Deseja remover todas essas branches locais?'):
                click.echo(Fore.YELLOW + '[BRANCH] Operação cancelada.')
                return

            removed = 0
            for name in candidates:
                if _run_git_command(['branch', '-d', name], silent_fail=True):
                    removed += 1
            click.echo(Fore.GREEN + f'[OK] {removed} branch(es) removida(s).')
            return

        if drop_commits is not None:
            if drop_commits <= 0:
                click.echo(Fore.RED + '[ERRO] --drop-commits precisa ser maior que zero.')
                sys.exit(1)

            current = _get_current_branch() or 'HEAD'
            click.echo(Fore.RED + Style.BRIGHT + f"Modo destrutivo: apagar {drop_commits} commit(s) da branch '{current}'.")
            preview = _run_git_command(['log', '--oneline', f'-{drop_commits}'], capture_output=True, silent_fail=True) or ''
            if preview:
                click.echo(Fore.YELLOW + 'Commits que serão descartados:')
                click.echo(preview)

            if not yes and not click.confirm('Confirma reset --hard? Esta ação não pode ser desfeita facilmente.'):
                click.echo(Fore.YELLOW + '[BRANCH] Operação cancelada.')
                return

            if not _run_git_command(['reset', '--hard', f'HEAD~{drop_commits}']):
                logger.add_finding('error', 'Falha ao apagar commits com reset --hard.')
                sys.exit(1)
            click.echo(Fore.GREEN + '[OK] Histórico local reescrito com sucesso.')
            return

        if origin_guard:
            base_branch = base or _get_default_base_branch()

            local_branch_ref = f"refs/heads/{base_branch}"
            remote_branch_ref = f"refs/remotes/origin/{base_branch}"
            has_local_base = bool(_run_git_command(['show-ref', '--verify', '--quiet', local_branch_ref], silent_fail=True))
            has_remote_base = bool(_run_git_command(['show-ref', '--verify', '--quiet', remote_branch_ref], silent_fail=True))

            if not (has_local_base or has_remote_base):
                if re.fullmatch(r'[0-9a-fA-F]{7,40}', base_branch):
                    click.echo(Fore.RED + "[ERRO] '--base' espera nome de branch, não hash de commit.")
                    click.echo(Fore.YELLOW + "Exemplo correto: doxoade branch --base main --origin <hash_remoto>")
                else:
                    click.echo(Fore.RED + f"[ERRO] Branch base '{base_branch}' não existe (local/remoto).")
                sys.exit(1)

            remote_ref = f"origin/{base_branch}"
            click.echo(Fore.CYAN + f"Sincronização segura: HEAD -> {remote_ref} (guard={origin_guard})")

            _run_git_command(['fetch', 'origin', base_branch], capture_output=True, silent_fail=True)
            remote_hash = _run_git_command(['rev-parse', remote_ref], capture_output=True, silent_fail=True)
            if not remote_hash:
                logger.add_finding('error', f'Falha ao ler hash remoto de {remote_ref}.')
                click.echo(Fore.RED + f"[ERRO] Não foi possível obter o hash atual de {remote_ref}.")
                sys.exit(1)

            remote_hash = remote_hash.strip()
            guard = origin_guard.strip().lower()
            if not remote_hash.lower().startswith(guard):
                click.echo(Fore.RED + f"[ERRO] Guarda não confere. Remoto atual: {remote_hash[:12]}")
                click.echo(Fore.YELLOW + "Dica: rode 'git log origin/{base} -n 1 --oneline' e tente novamente.".format(base=base_branch))
                sys.exit(1)

            if not yes:
                try:
                    if not click.confirm(f"Confirmar push seguro para origin/{base_branch} usando --force-with-lease?"):
                        click.echo(Fore.YELLOW + '[BRANCH] Operação cancelada.')
                        return
                except click.Abort:
                    click.echo(Fore.YELLOW + "[BRANCH] Confirmação abortada (modo não interativo?). Use --yes para prosseguir.")
                    return

            lease = f"refs/heads/{base_branch}:{remote_hash}"
            if not _run_git_command([
                'push', '--force-with-lease=' + lease,
                'origin', f'HEAD:refs/heads/{base_branch}'
            ]):
                logger.add_finding('error', 'Falha no push seguro para origin.')
                click.echo(Fore.RED + '[ERRO] Push seguro falhou. O remoto pode ter mudado.')
                sys.exit(1)

            click.echo(Fore.GREEN + f"[OK] origin/{base_branch} atualizado com segurança.")
            return

        click.echo(ctx.get_help())
