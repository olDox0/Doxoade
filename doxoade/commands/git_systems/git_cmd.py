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
from .git_feature import feature_cmd

@click.group('git')
def git_group():
    """🛠  NEXUS-GIT: Gestão profissional de fluxo, upstream e auditoria."""
    pass

git_group.add_command(feature_cmd, 'feature')

@git_group.command('auto')
@click.option('--push/--no-push', '-p/-np', default=True, help='Envia commits locais automaticamente (Padrão: True).')
@click.option('--prefer', type=click.Choice(['remote', 'local', 'interactive']), default='remote', help='Estratégia padrão de resolução.')
@click.pass_context
def git_auto(ctx, push, prefer):
    """
    🤖 Piloto Automático Git: Sincronização inteligente bidirecional (Pull + Push).
    Auto-cura MERGE_HEAD, salva backup preventivo, aplica pull suave e sobe commits no main.
    """
    from doxoade.commands.git_systems.git_engine import GitEngine
    engine = GitEngine(os.getcwd())
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🤖 [AUTOPILOT GIT] Iniciando Reconciliação Soberana (Pull + Push)...{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}Estação Atual:{Fore.RESET} {Fore.YELLOW}{engine.get_station_name().upper()}{Fore.RESET}")
    click.echo(f"  {Fore.WHITE}Branch:{Fore.RESET} {engine.get_current_branch()}\n")
    
    # Executa reconciliação com auto_push ativado por padrão
    res = engine.autopilot(prefer=prefer if prefer != 'interactive' else None, auto_push=push)

    if res['healed_merge']:
        click.echo(f"  {Fore.GREEN}✔ [AUTO-HEAL] Merge travado anterior foi limpo com segurança.{Style.RESET_ALL}")
    
    # 🩺 Novo feedback de cura de branches LAN
    if res.get('healed_lan_branch'):
        click.echo(f"  {Fore.GREEN}✔ [AUTO-HEAL] {res['lan_msg']}{Style.RESET_ALL}")
    if res.get('cleaned_lan_branches'):
        branches_str = ", ".join(res['cleaned_lan_branches'])
        click.echo(f"  {Fore.GREEN}✔ [AUTO-HEAL] Branchs temporárias de LAN removidas: {branches_str}{Style.RESET_ALL}")

    if res['status'] == 'NETWORK_ERROR':
        click.echo(f"\n{Fore.RED}{Style.BRIGHT}✖ [REDE OFFLINE] {res['action_taken']}{Style.RESET_ALL}\n")
        click.echo(f"{Fore.YELLOW}💡 Dica: Verifique sua conexão com o servidor Git ou use 'git pull' nativo para debug.{Style.RESET_ALL}")
        return
    elif res['status'] == 'CONFLICT':
#    if res['status'] == 'CONFLICT':
        from doxoade.commands.git_systems.git_merge import merge as run_merge
        ctx.invoke(run_merge)
        return

    elif res['status'] == 'PULLED':
        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [ATUALIZADO] {res['action_taken']}{Style.RESET_ALL}\n")

    elif res['status'] == 'AHEAD':
        if push:
            engine.autopilot(auto_push=True)
            click.echo(f"{Fore.GREEN}✔ Commits enviados automaticamente para o servidor!{Style.RESET_ALL}\n")
        else:
            click.echo(f"\n{Fore.YELLOW}ℹ [PENDENTE DE ENVIO] {res['action_taken']}{Style.RESET_ALL}")

    elif res['status'] == 'SYNCED':
        click.echo(f"{Fore.GREEN}✔ {res['action_taken']}{Style.RESET_ALL}\n")

def _resolve_target_branch(engine, requested_branch: str = None) -> str:
    """
    Descobre a branch correta para o pull.
    Se nenhuma for passada, prioriza o upstream do branch atual;
    se não houver upstream ou for branch transitória, reconcilia com a branch principal (main/master).
    """
    if requested_branch:
        return requested_branch

    current = engine.get_current_branch()
    
    # Se a máquina estiver numa branch transitória de LAN, normaliza primeiro
    if current in ("dox-live", "dox-live-sync"):
        engine.normalize_transient_branches()
        current = engine.get_current_branch()

    # Verifica se a branch atual existe no origin
    remote_check = _run_git_command(
        ['ls-remote', '--heads', 'origin', current],
        capture_output=True,
        silent_fail=True,
        cwd=str(engine.root)
    )
    if remote_check and remote_check.strip():
        return current

    # Fallback inteligente para branch principal remota (main ou master)
    for main_candidate in ('main', 'master'):
        main_ref = _run_git_command(
            ['ls-remote', '--heads', 'origin', main_candidate],
            capture_output=True,
            silent_fail=True,
            cwd=str(engine.root)
        )
        if main_ref and main_ref.strip():
            return main_candidate

    return current or 'main'

@git_group.command('pull')
@click.option('--subscribe', '-s', is_flag=True, help='Subscreve todas as atualizações do servidor preservando modificações locais.')
@click.option('--force', '-f', is_flag=True, help='Força a sincronização global (Reset Hard).')
@click.option('--dry-run', is_flag=True, help='Apenas simula o pull sem aplicar no disco.')
@click.option('--apply', '-a', is_flag=True, default=True, help='Aplica as alterações no disco (Padrão: True).')
@click.option('--conflicts', '-c', is_flag=True, help='Exibe a Matriz de Colisão detalhada (Locais vs Remotos).')
@click.option('--diff', '-d', 'diff_file', is_flag=False, flag_value='ALL', default=None, help='Exibe o diff forense.')
@click.option('--file', '-p', 'target_files', multiple=True, help='Puxa/sobrescreve apenas os arquivos especificados.')
@click.option('--remote', '-r', default='origin', show_default=True, help='Remote de destino.')
@click.option('--branch', '-b', default=None, help='Branch específico (padrão: branch principal ou atual).')
@click.pass_context
def pull_cmd(ctx, subscribe, force, dry_run, apply, conflicts, diff_file, target_files, remote, branch):
    """
    📥 Sincronização direta e inteligente do repositório (Smart Multi-Station).
    Puxa e reconcilia com origin/main mesmo entre estações diferentes (PC-A / Bluebaby).
    """
    from doxoade.commands.git_systems.git_engine import GitEngine
    with ExecutionLogger('git_pull', os.getcwd(), ctx.params) as logger:
        engine = GitEngine(os.getcwd())
        
        # 1. Limpeza preventiva Sotéria contra falsos conflitos de DLLs/Janus
        engine.clean_transient_build_artifacts()

        # 2. Resolução da branch soberana (detecta se é main/master e normaliza)
        target_branch = _resolve_target_branch(engine, branch)
        is_apply_mode = not dry_run

        # 3. Auto-cura de merge travado
        if (Path(engine.root) / ".git" / "MERGE_HEAD").exists():
            click.echo(f"{Fore.YELLOW}{Style.BRIGHT}⚠ [AUTO-HEAL] Detectado merge inacabado bloqueando o Git.{Style.RESET_ALL}")
            if is_apply_mode or click.confirm("Deseja auto-curar o estado travado e prosseguir?"):
                engine.heal_stuck_merge()
                click.echo(f"{Fore.GREEN}✔ Estado restaurado com segurança. Continuando...{Fore.RESET}\n")
            else:
                click.echo(f"{Fore.RED}✖ Operação cancelada. Use 'doxoade merge --abort'.{Fore.RESET}")
                return

        # 4. FETCH OBRIGATÓRIO (A fonte da falha do pull clássico)
        fetch_ok, fetch_msg = engine.fetch_remote(remote=remote, branch=target_branch)
        if not fetch_ok:
            click.echo(f"\n{Fore.RED}{Style.BRIGHT}✖ [REDE OFFLINE] Não foi possível contatar '{remote}'.{Style.RESET_ALL}")
            click.echo(f"  ↳ Detalhe: {fetch_msg}\n")
            return

        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}⚡ NEXUS-GIT :: SINCRONIZAÇÃO SOBERANA [{engine.get_station_name().upper()}]{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Branch Alvo:{Fore.RESET} {Fore.YELLOW}{target_branch}{Fore.RESET} | {Fore.WHITE}Remote:{Fore.RESET} {remote}\n")

        # Se a branch local divergir da remota selecionada, alinha a estação
        current_local = engine.get_current_branch()
        if current_local != target_branch:
            click.echo(f"  {Fore.CYAN}ℹ [ESTAÇÃO] Alternando branch local: {current_local} -> {target_branch}{Fore.RESET}")
            _run_git_command(['checkout', target_branch], silent_fail=True, cwd=str(engine.root))

        if diff_file:
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

        if subscribe:
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

        if target_files:
            if not is_apply_mode:
                click.echo(f"{Fore.YELLOW}[DRY-RUN] Execute com --apply para puxar os {len(target_files)} arquivos selecionados.{Fore.RESET}\n")
                return
            res = engine.pull_selective_files(list(target_files), remote=remote, branch=target_branch, apply_changes=True)
            for f in res['success_files']: click.echo(f"  {Fore.GREEN}✔ Atualizado:{Fore.RESET} {f}")
            for f in res['failed_files']: click.echo(f"  {Fore.RED}✖ Falha:{Fore.RESET} {f}")
            return

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

        # Execução padrão do Smart Pull com Snapshot preventivo
        engine.create_safety_snapshot(reason="pre_pull")
        report = engine.smart_pull_sync(remote=remote, branch=target_branch, apply_changes=is_apply_mode)
        
        if is_apply_mode:
            # Garante que os commits remotos recebidos sejam incorporados no working tree
            merge_res = _run_git_command(['merge', f'{remote}/{target_branch}', '--no-edit'], capture_output=True, cwd=str(engine.root))
            if merge_res:
                click.echo(f"{Fore.GREEN}✔ [PULL] Alterações de '{remote}/{target_branch}' integradas com sucesso!{Fore.RESET}\n")
            else:
                # Se houver conflito real, aciona o assistente de merge
                click.echo(f"{Fore.YELLOW}⚠ Conflito de merge detectado. Acionando assistente...{Fore.RESET}")
                from doxoade.commands.git_systems.git_merge import merge as run_merge
                ctx.invoke(run_merge)

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
