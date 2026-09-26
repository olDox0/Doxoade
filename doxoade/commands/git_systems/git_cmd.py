# doxoade/commands/git_systems/git_cmd.py
"""
NEXUS-GIT - Comando Unificado de Gestão Profissional v2.6 (ProDeNov).
Gerencia Pull, Matriz de Colisão Forense, Pull Seletivo e Resolução de Conflitos.
Compliance: PASC-6.1 (Lazy Loading Isolado), OSL-4.
"""
import os
import sys
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command
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
@click.option('--diff', '-d', 'diff_file', is_flag=False, flag_value='ALL', default=None, help='Exibe o diff forense (sem argumento: mostra tudo; ou informe o arquivo).')
@click.option('--file', '-p', 'target_files', multiple=True, help='Puxa/sobrescreve apenas os arquivos especificados.')
@click.option('--remote', '-r', default='origin', show_default=True, help='Remote de destino.')
@click.option('--branch', '-b', default=None, help='Branch específico (padrão: branch atual).')
@click.pass_context
def pull_cmd(ctx, subscribe, force, apply, conflicts, diff_file, target_files, remote, branch):
    """
    📥 Sincronização e auditoria forense do repositório (Smart Multi-Station).
    Padrão: Diagnostica e simula (Dry-Run). Use '--apply' para efetivar.
    """
    from doxoade.commands.git_systems.git_engine import GitEngine
    with ExecutionLogger('git_pull', os.getcwd(), ctx.params) as logger:
        engine = GitEngine(os.getcwd())
        target_branch = branch or engine.get_current_branch()
        is_apply_mode = apply

        # 1. Auto-cura ativa de MERGE_HEAD
        if (Path(engine.root) / ".git" / "MERGE_HEAD").exists():
            click.echo(f"{Fore.YELLOW}{Style.BRIGHT}⚠ [AUTO-HEAL] Detectado merge inacabado bloqueando o Git.{Style.RESET_ALL}")
            if is_apply_mode or click.confirm("Deseja auto-curar o estado travado e prosseguir?"):
                engine.heal_stuck_merge()
                click.echo(f"{Fore.GREEN}✔ Estado restaurado com segurança. Continuando...{Fore.RESET}\n")
            else:
                click.echo(f"{Fore.RED}✖ Operação cancelada. Use 'doxoade merge --abort'.{Fore.RESET}")
                return

        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ NEXUS-GIT :: SINCRONIZAÇÃO SOBERANA [{engine.get_station_name().upper()}]{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Branch:{Fore.RESET} {target_branch} | {Fore.WHITE}Remote:{Fore.RESET} {remote}\n")

        # 2. Exibição de Diff Forense (--diff sem argumento ou específico)
        if diff_file:
            engine.fetch_remote(remote=remote, branch=target_branch)
            if diff_file == 'ALL':
                click.echo(f"{Fore.CYAN}🔍 Diff Forense Global contra {remote}/{target_branch}:{Style.RESET_ALL}")
                diff_text = _run_git_command(['diff', f'{remote}/{target_branch}'], capture_output=True, cwd=str(engine.root)) or "Nenhuma diferença."
            else:
                click.echo(f"{Fore.CYAN}🔍 Diff Forense de '{diff_file}':{Style.RESET_ALL}")
                diff_text = engine.get_file_diff(diff_file, remote=remote, branch=target_branch)

            for line in diff_text.splitlines():
                if line.startswith('+'): click.echo(Fore.GREEN + line + Style.RESET_ALL)
                elif line.startswith('-'): click.echo(Fore.RED + line + Style.RESET_ALL)
                elif line.startswith('@@'): click.echo(Fore.CYAN + line + Style.RESET_ALL)
                else: click.echo(line)
            click.echo()
            return

        # 3. Subscrição Segura
        if subscribe:
            engine.fetch_remote(remote=remote, branch=target_branch)
            sub_report = engine.subscribe_safe_remote(remote=remote, branch=target_branch, apply_changes=is_apply_mode)
            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔍 [DRY-RUN] PRÉVIA DE SUBSCRIÇÃO DO SERVIDOR (--subscribe){Style.RESET_ALL}")
                click.echo(f"  • Arquivos que serão subscritos do servidor: {Fore.GREEN}{sub_report['total_to_update']}{Fore.RESET}")
                click.echo(f"  • Modificações locais preservadas intactas : {Fore.CYAN}{len(sub_report['preserved_items'])}{Fore.RESET}")
                click.echo(f"\n{Fore.YELLOW}💡 Para efetivar no disco: doxoade git pull --subscribe --apply{Fore.RESET}\n")
                return

            click.echo(f"{Fore.GREEN}{Style.BRIGHT}✔ [APPLY] SUBSCRIÇÃO CONCLUÍDA!{Style.RESET_ALL}")
            click.echo(f"  • Arquivos atualizados: {len(sub_report['updated_files'])} | Preservados: {len(sub_report['preserved_items'])}\n")
            return

        # 4. Pull Seletivo
        if target_files:
            engine.fetch_remote(remote=remote, branch=target_branch)
            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}[DRY-RUN] Execute com --apply para puxar os {len(target_files)} arquivos selecionados.{Fore.RESET}\n")
                return
            res = engine.pull_selective_files(list(target_files), remote=remote, branch=target_branch, apply_changes=True)
            for f in res['success_files']: click.echo(f"  {Fore.GREEN}✔ Atualizado:{Fore.RESET} {f}")
            for f in res['failed_files']: click.echo(f"  {Fore.RED}✖ Falha:{Fore.RESET} {f}")
            return

        # 5. Reset Hard Forçado
        if force:
            report = engine.force_pull_reset(branch=target_branch, remote=remote, apply_changes=is_apply_mode)
            if not report['success']:
                click.echo(f"{Fore.RED}✖ Erro: {report.get('error')}{Fore.RESET}")
                sys.exit(1)
            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}[DRY-RUN] Use 'doxoade git pull --force --apply' para forçar o estado do servidor.{Fore.RESET}\n")
                return
            click.echo(f"{Fore.GREEN}✔ Reset Hard aplicado com backup prévio em .doxoade/git_recovery/.{Fore.RESET}\n")
            return

        # 6. Fluxo Padrão: Smart Sync Reconciliado
        report = engine.smart_pull_sync(remote=remote, branch=target_branch, apply_changes=is_apply_mode)
        matrix = report['matrix']

        if not is_apply_mode:
            click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔍 [DRY-RUN] ANÁLISE DE IMPACTO MULTI-ESTAÇÃO{Style.RESET_ALL}")
            click.echo(f"  • Servidor tem novidades : {Fore.GREEN}{matrix['total_safe_remote']} arquivo(s){Fore.RESET}")
            click.echo(f"  • Rascunhos locais desta máquina : {Fore.CYAN}{matrix['total_local_only']} arquivo(s){Fore.RESET}")
            if matrix['collisions']:
                click.echo(f"  • {Fore.RED}Colisões diretas (exigem merge): {matrix['total_collisions']} arquivo(s){Fore.RESET}")
                for c in matrix['collisions']:
                    click.echo(f"    {Fore.RED}✖ {c['file']}{Fore.RESET}")
            else:
                click.echo(f"  • {Fore.GREEN}✔ Nenhuma colisão direta detectada.{Fore.RESET}")

            click.echo(f"\n{Fore.YELLOW}💡 Para sincronizar com segurança total:{Fore.RESET}")
            click.echo(f"   {Fore.WHITE}doxoade git pull --apply{Fore.RESET}\n")
            return

        if report['success']:
            click.echo(f"{Fore.GREEN}{Style.BRIGHT}✔ [OK] Repositório sincronizado com sucesso!{Style.RESET_ALL}")
            if report['snapshot']:
                click.echo(f"  {Fore.CYAN}💾 Snapshot de segurança gravado em: {Path(report['snapshot']).name}{Fore.RESET}")
        else:
            click.echo(f"{Fore.RED}✖ {report['action_summary']}{Fore.RESET}")
            if report['has_collisions']:
                click.echo(f"{Fore.YELLOW}💡 Execute 'doxoade merge' para resolver interativamente as colisões.{Fore.RESET}")


@git_group.command('branch')
@click.option('--new', '-n', help='Cria uma nova branch.')
@click.option('--list', '-l', is_flag=True, help='Lista branches.')
@click.option('--done', '-d', help='Finaliza branch.')
def branch_cmd(new, list, done):
    """Organiza a árvore genealógica do código (Osíris)."""
    from doxoade.commands.git_systems.git_flow import GitFlowManager
    flow = GitFlowManager(os.getcwd())
    if new: flow.create_branch(new)
    elif list: flow.list_branches()
    elif done: flow.finish_branch(done)


@git_group.command('issues')
@click.option('--sync', '-s', is_flag=True, help='Sincroniza issues.')
def issues_cmd(sync):
    """Conecta com Hermes para buscar ordens do Olimpo (GitHub Issues)."""
    from doxoade.commands.git_systems.git_bridge import GitHubBridge
    bridge = GitHubBridge(os.getcwd())
    bridge.display_issues()


@git_group.command('audit-deps')
@click.option('--fix', is_flag=True, help='Atualiza dependências vulneráveis.')
def audit_deps(fix):
    """O Dependabot do Doxoade: Vigilância de Vulns e Versões."""
    from doxoade.commands.git_systems.git_health import DependencyGuard
    guard = DependencyGuard(os.getcwd())
    guard.check_health(auto_fix=fix)
