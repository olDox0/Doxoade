# doxoade/commands/git_systems/git_cmd.py
"""
NEXUS-GIT - Comando Unificado de Gestão Profissional v2.6 (ProDeNov).
Gerencia Pull, Matriz de Colisão Forense, Pull Seletivo e Resolução de Conflitos.
Compliance: PASC-6.1 (Lazy Loading Isolado), OSL-4.
"""
import os
import sys
import click

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger


@click.group('git')
def git_group():
    """🛠  NEXUS-GIT: Gestão profissional de fluxo, upstream e auditoria."""
    pass


@git_group.command('pull')
@click.option('--subscribe', '-s', is_flag=True, help='Subscreve todas as atualizações do servidor preservando modificações locais.')
@click.option('--force', '-f', is_flag=True, help='Força a sincronização global (Reset Hard).')
@click.option('--apply', '-a', is_flag=True, help='Aplica as alterações no disco (sai do modo DRY-RUN).')
@click.option('--conflicts', '-c', is_flag=True, help='Exibe a Matriz de Colisão detalhada (Locais vs Remotos).')
@click.option('--diff', '-d', type=str, help='Exibe o diff forense de um arquivo específico contra o servidor.')
@click.option('--file', '-p', 'target_files', multiple=True, help='Puxa/sobrescreve apenas os arquivos especificados.')
@click.option('--remote', '-r', default='origin', show_default=True, help='Remote de destino.')
@click.option('--branch', '-b', default=None, help='Branch específico (padrão: branch atual).')
@click.pass_context
def pull_cmd(ctx, subscribe, force, apply, conflicts, diff, target_files, remote, branch):
    """
    📥 Sincronização e auditoria forense do repositório.
    Use '--subscribe' para subscrever o Lite XL e novos módulos preservando seus arquivos Git locais.
    """
    from doxoade.commands.git_systems.git_engine import GitEngine

    with ExecutionLogger('git_pull', os.getcwd(), ctx.params) as logger:
        engine = GitEngine(os.getcwd())
        target_branch = branch or engine.get_current_branch()
        is_apply_mode = apply

        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ NEXUS-GIT :: SINCRONIZAÇÃO E AUDITORIA{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Branch:{Fore.RESET} {target_branch} | {Fore.WHITE}Remote:{Fore.RESET} {remote}\n")

        # 1. Fetch preliminar
        engine.fetch_remote(remote=remote, branch=target_branch)

        # ═══════════════════════════════════════════════════════════
        # MODO SUBSCRIÇÃO SEGURA (--subscribe / -s)
        # ═══════════════════════════════════════════════════════════
        if subscribe:
            sub_report = engine.subscribe_safe_remote(remote=remote, branch=target_branch, apply_changes=is_apply_mode)

            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔍 [DRY-RUN] PRÉVIA DE SUBSCRIÇÃO DO SERVIDOR (--subscribe){Style.RESET_ALL}")
                click.echo(f"  • Arquivos que serão subscritos do servidor: {Fore.GREEN}{sub_report['total_to_update']}{Fore.RESET}")
                click.echo(f"  • Modificações locais preservadas intactas : {Fore.CYAN}{len(sub_report['preserved_items'])}{Fore.RESET}")

                if sub_report['safe_items']:
                    click.echo(f"\n  {Fore.WHITE}Módulos a serem incorporados no disco:{Fore.RESET}")
                    for item in sub_report['safe_items'][:12]:
                        click.echo(f"    {Fore.GREEN}+ [SUBSCREVER]{Fore.RESET} {item['file']}")
                    if len(sub_report['safe_items']) > 12:
                        click.echo(f"    {Style.DIM}... e mais {len(sub_report['safe_items']) - 12} arquivos.{Style.RESET_ALL}")

                if sub_report['preserved_items']:
                    click.echo(f"\n  {Fore.WHITE}Seus arquivos locais blindados (não serão tocados):{Fore.RESET}")
                    for item in sub_report['preserved_items']:
                        click.echo(f"    {Fore.CYAN}🛡️  [PRESERVADO]{Fore.RESET} {item['file']}")

                click.echo(f"\n{Fore.YELLOW}💡 Nenhuma alteração gravada. Para subscrever o Lite XL e atualizar o disco:{Fore.RESET}")
                click.echo(f"   {Fore.WHITE}doxoade git pull --subscribe --apply{Fore.RESET}\n")
                return

            # Modo Apply Efetivado
            click.echo(f"{Fore.GREEN}{Style.BRIGHT}✔ [APPLY] SUBSCRIÇÃO CONCLUÍDA COM SUCESSO!{Style.RESET_ALL}")
            click.echo(f"  • Arquivos atualizados no disco : {Fore.GREEN}{len(sub_report['updated_files'])}{Fore.RESET}")
            click.echo(f"  • Seus arquivos locais mantidos : {Fore.CYAN}{len(sub_report['preserved_items'])}{Fore.RESET}\n")
            for f in sub_report['updated_files'][:10]:
                click.echo(f"    {Fore.GREEN}✔ {f}{Fore.RESET}")
            if len(sub_report['updated_files']) > 10:
                click.echo(f"    {Style.DIM}... e mais {len(sub_report['updated_files']) - 10} arquivos atualizados.{Style.RESET_ALL}")
            click.echo(f"\n{Fore.CYAN}O sistema Lite XL está 100% atualizado e seus módulos Git permanecem intactos!{Style.RESET_ALL}\n")
            return

        # ═══════════════════════════════════════════════════════════
        # CASO A: INSPEÇÃO DE DIFF (--diff)
        # ═══════════════════════════════════════════════════════════
        if diff:
            click.echo(f"{Fore.CYAN}🔍 Diff Forense: {Style.BRIGHT}{diff}{Style.RESET_ALL}")
            diff_text = engine.get_file_diff(diff, remote=remote, branch=target_branch)
            for line in diff_text.splitlines():
                if line.startswith('+'): click.echo(Fore.GREEN + line + Style.RESET_ALL)
                elif line.startswith('-'): click.echo(Fore.RED + line + Style.RESET_ALL)
                elif line.startswith('@@'): click.echo(Fore.CYAN + line + Style.RESET_ALL)
                else: click.echo(line)
            click.echo()
            return

        # ═══════════════════════════════════════════════════════════
        # CASO B: MATRIZ DE COLISÃO (--conflicts)
        # ═══════════════════════════════════════════════════════════
        if conflicts:
            matrix = engine.detect_collisions(remote=remote, branch=target_branch)
            click.echo(f"{Fore.CYAN}{Style.BRIGHT}📊 MATRIZ DE IMPACTO E COLISÃO{Style.RESET_ALL}\n")
            if matrix['collisions']:
                click.echo(f"  {Fore.RED}{Style.BRIGHT}🔴 COLISÕES DIRETAS ({matrix['total_collisions']} arquivos):{Style.RESET_ALL}")
                for item in matrix['collisions']:
                    click.echo(f"    {Fore.RED}✖ {item['file']}{Fore.RESET}")
            else:
                click.echo(f"  {Fore.GREEN}✔ Nenhuma colisão direta detectada.{Style.RESET_ALL}")

            click.echo(f"\n  {Fore.GREEN}🟢 ATUALIZAÇÕES DISPONÍVEIS ({matrix['total_safe_remote']} arquivos){Style.RESET_ALL}")
            click.echo(f"  {Fore.YELLOW}🟡 ARQUIVOS LOCAIS EXCLUSIVOS ({matrix['total_local_only']} arquivos){Style.RESET_ALL}\n")
            return

        # ═══════════════════════════════════════════════════════════
        # CASO C: PULL SELETIVO (--file)
        # ═══════════════════════════════════════════════════════════
        if target_files:
            click.echo(f"{Fore.CYAN}🎯 PULL SELETIVO: {len(target_files)} arquivo(s){Style.RESET_ALL}")
            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}[DRY-RUN] Execute com --apply para efetivar:{Fore.RESET}")
                click.echo(f"   doxoade git pull {' '.join(['--file ' + f for f in target_files])} --apply\n")
                return

            res = engine.pull_selective_files(list(target_files), remote=remote, branch=target_branch, apply_changes=True)
            for f in res['success_files']: click.echo(f"  {Fore.GREEN}✔ Atualizado:{Fore.RESET} {f}")
            for f in res['failed_files']: click.echo(f"  {Fore.RED}✖ Falha:{Fore.RESET} {f}")
            click.echo()
            return

        # ═══════════════════════════════════════════════════════════
        # CASO D: FORCE PULL GLOBAL (RESET HARD)
        # ═══════════════════════════════════════════════════════════
        if force:
            report = engine.force_pull_reset(branch=target_branch, remote=remote, apply_changes=is_apply_mode)
            if not report['success']:
                click.echo(f"{Fore.RED}✖ Erro: {report.get('error')}{Fore.RESET}")
                sys.exit(1)

            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔍 [DRY-RUN] PRÉVIA DE RESET HARD GLOBAL{Style.RESET_ALL}")
                click.echo(f"   {Fore.WHITE}doxoade git pull --force --apply{Fore.RESET}\n")
                return

            click.echo(f"{Fore.GREEN}{Style.BRIGHT}✔ [APPLY] Reset Hard global concluído com sucesso!{Style.RESET_ALL}\n")
        else:
            click.echo(f"{Fore.CYAN}Dica de uso recomendada:{Style.RESET_ALL}")
            click.echo(f"  doxoade git pull --subscribe --apply      (Subscreve Lite XL e mantém arquivos Git)")
            click.echo(f"  doxoade git pull --conflicts              (Audita arquivos e colisões)")
            click.echo(f"  doxoade git pull --diff <arquivo>         (Vê o diff de um arquivo)")


@git_group.command('branch')
@click.option('--new', '-n', help='Cria uma nova branch.')
@click.option('--list', '-l', is_flag=True, help='Lista branches.')
@click.option('--done', '-d', help='Finaliza branch.')
def branch_cmd(new, list, done):
    from doxoade.commands.git_systems.git_flow import GitFlowManager
    flow = GitFlowManager(os.getcwd())
    if new: flow.create_branch(new)
    elif list: flow.list_branches()
    elif done: flow.finish_branch(done)


@git_group.command('issues')
@click.option('--sync', '-s', is_flag=True, help='Sincroniza issues.')
def issues_cmd(sync):
    from doxoade.commands.git_systems.git_bridge import GitHubBridge
    bridge = GitHubBridge(os.getcwd())
    bridge.display_issues()


@git_group.command('audit-deps')
@click.option('--fix', is_flag=True, help='Atualiza dependências vulneráveis.')
def audit_deps(fix):
    from doxoade.commands.git_systems.git_health import DependencyGuard
    guard = DependencyGuard(os.getcwd())
    guard.check_health(auto_fix=fix)
