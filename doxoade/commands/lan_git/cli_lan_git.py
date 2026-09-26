# doxoade\commands\lan_git\cli_lan_git.py
""" Interface de Linha de Comando (CLI) para o Sistema LAN Git Doxoade Multi-Silos.
Implementa Auto-Matching de Projetos (Zero Erro Humano), Live Mirroring e UAC. """

import os
import sys
import time
import re
import json
import threading
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import click

from doxoade.commands.lan_git.network_lan_git.interfaces_lan_git import LANInterfaceDetector
from doxoade.commands.lan_git.network_lan_git.git_firewall_guard import GitFirewallGuard
from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import GitManifestExtractor
from doxoade.commands.lan_git.discovery_lan_git.beacon_lan_git import LANBeaconHost, LANBeaconClient
from doxoade.commands.lan_git.discovery_lan_git.scanner_lan_git import LANDirectScanner
from doxoade.commands.lan_git.transport_lan_git.git_daemon_server import GitDaemonServer
from doxoade.commands.lan_git.transport_lan_git.git_http_server import GitHTTPServer
from doxoade.commands.lan_git.client_lan_git.git_sync_engine import GitSyncEngine
from doxoade.commands.lan_git.web_lan_git.portal_server_lan_git import LANWebPortal

# Importação defensiva do ProjectResolver com fallback inline
try:
    from doxoade.commands.lan_git.discovery_lan_git.project_resolver_lan_git import ProjectResolver
except Exception:
    class ProjectResolver:
        @classmethod
        def resolve_project_path(cls, query, start="."):
            abs_p = os.path.abspath(query if query else start)
            return os.path.exists(abs_p), abs_p, None
        @classmethod
        def list_available_projects(cls, start="."):
            return []


def _fuzzy_clean_name(name: str) -> str:
    """Normaliza nomes para casar 'Sysutils_proj' com 'Projeto SysUtils'."""
    clean = name.lower()
    clean = re.sub(r"^(projeto|project)[-_\s]+", "", clean)
    clean = re.sub(r"[-_\s]+(proj|project|silo)$", "", clean)
    clean = re.sub(r"[-_\s.]+", "", clean)
    return clean.strip()


@click.group(name="lan-git")
def lan_git_cli():
    """Sistema de Sincronização P2P, Multi-Silos e Compartilhamento Local Git."""
    pass


# =====================================================================
# COMANDO: LIST (LISTAR SILOS LOCAIS)
# =====================================================================
@lan_git_cli.command(name="list")
def cmd_list():
    """Lista todos os Silos e Projetos Git disponíveis no workspace local."""
    click.secho("============================================================", fg="cyan")
    click.secho("             SILOS E PROJETOS LOCAIS (WORKSPACE)", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")

    projects = ProjectResolver.list_available_projects()
    if not projects:
        click.secho("[AVISO] Nenhum repositório Git localizado no workspace.", fg="yellow")
        return

    click.echo(f"Foram localizados {len(projects)} projeto(s) Git:\n")
    for idx, p in enumerate(projects, 1):
        click.echo(f" [{idx}] {click.style(p['name'], bold=True)} ({p['branch']} @ {p['commit']})")
        click.echo(f"     Caminho: {click.style(p['path'], fg='white')}")
    click.secho("============================================================", fg="cyan")


# =====================================================================
# COMANDO: SHARE (HOST MULTI-PROJETOS)
# =====================================================================
@lan_git_cli.command(name="share")
@click.argument("repo_path", default=".", type=click.Path(exists=False))
@click.option("--project", "-p", default=None, help="Nome simplificado do projeto alvo (ex: sysutils).")
@click.option("--port", default=9418, help="Porta TCP do servidor Git.")
@click.option("--http-port", default=8080, help="Porta TCP do Smart HTTP.")
@click.option("--udp-port", default=54545, help="Porta UDP para anúncio Discovery.")
@click.option("--live", is_flag=True, help="Ativa modo Live Mirror (Espelha rascunhos em memória sem commit).")
def cmd_share(repo_path: str, project: Optional[str], port: int, http_port: int, udp_port: int, live: bool):
    """Compartilha o repositório atual ou um projeto específico (-p) na rede local.
        ex: PC-A: doxoade lan-git share -p sysutils --live
            PC-B: doxoade lan-git pull
            
            doxoade lan-git share
    """
    target_query = project if project else repo_path
    ok, resolved_path, err = ProjectResolver.resolve_project_path(target_query)

    if not ok or not resolved_path:
        click.secho(f"[ERRO] {err}", fg="red")
        return

    abs_path = os.path.abspath(resolved_path)
    primary_iface = LANInterfaceDetector.get_primary_interface()

    if not primary_iface:
        click.secho("[ERRO CRÍTICO] Nenhuma interface de rede física ativa foi detectada.", fg="red")
        return

    host_ip = primary_iface["ip"]

    manifest = GitManifestExtractor.extract(abs_path, host_ip=host_ip, port=port, transport="git_daemon", live=live)
    if not manifest:
        click.secho(f"[ERRO] O caminho '{abs_path}' não é um repositório Git válido.", fg="red")
        return

    daemon_server = GitDaemonServer(abs_path, port=port)
    daemon_server.start()

    # 🛡️ Em modo Live ou se não for interativo, usa chave padrão da malha sem travar o terminal
    portal_password = os.environ.get("DOXOADE_LAN_PASSWORD", "doxoade_lan_mesh") if live else None
    if not portal_password:
        portal_password = click.prompt("Senha do portal web", hide_input=True, confirmation_prompt=True, default="doxoade")

    portal_server = LANWebPortal(abs_path, password=portal_password, host_ip=host_ip, port=http_port)
    portal_server.start()

    beacon = LANBeaconHost(manifest, udp_port=udp_port)
    beacon_thread = threading.Thread(target=beacon.start, daemon=True)
    beacon_thread.start()

    mode_title = "MODO ESPELHO AO VIVO (LIVE MIRROR)" if live else "MODO SERVIDOR (HOST)"
    header_color = "magenta" if live else "green"

    click.secho("============================================================", fg="cyan")
    click.secho(f"             DOXOADE LAN GIT - {mode_title}", fg=header_color, bold=True)
    click.secho("============================================================", fg="cyan")
    click.echo(f"  Silo/Projeto: {click.style(manifest.repo_name, bold=True)}")
    click.echo(f"  Diretório   : {abs_path}")
    click.echo(f"  Branch/Alvo : {manifest.branch} [{manifest.short_commit}]")
    click.echo(f"  Mensagem    : {manifest.commit_message}")
    click.echo(f"  Interface   : {primary_iface['interface']} ({host_ip})")
    click.echo(f"  Dual Serv.  : Daemon ({port}) | Smart HTTP ({http_port})")
    click.echo(f"  Discovery   : UDP Broadcast (Porta {udp_port})")
    if live:
        click.secho("  Estado      : ESPELHAMENTO DE MEMÓRIA ATIVO (Sem commits no Git)", fg="yellow", bold=True)
    click.secho("============================================================", fg="cyan")
    click.secho("📡 Telemetria Ativa. Aguardando conexões na rede... (Ctrl+C para encerrar)\n", fg="yellow")

    last_shadow_commit = manifest.head_commit

    try:
        while True:
            if live:
                new_manifest = GitManifestExtractor.extract(abs_path, host_ip=host_ip, port=port, transport="git_daemon", live=True)
                if new_manifest:
                    beacon.update_manifest(new_manifest)
                    if new_manifest.head_commit != last_shadow_commit:
                        last_shadow_commit = new_manifest.head_commit
                        timestamp_str = time.strftime("%H:%M:%S")
                        click.secho(f"  [{timestamp_str}] ⚡ [LIVE-SYNC] {new_manifest.dirty_count} alteração(ões) salva(s) no editor -> Shadow Ref: {new_manifest.short_commit}", fg="magenta", bold=True)
            time.sleep(3.0)
    except KeyboardInterrupt:
        click.echo("\n[INFO] Encerrando servidores e liberando portas...")
    finally:
        beacon.stop()
        daemon_server.stop()
        if 'portal_server' in locals() and portal_server:
            portal_server.stop()
        click.secho("[OK] Servidores finalizados com segurança.", fg="green")

# =====================================================================
# COMANDO: WEB (PORTAL MULTI-PROJETOS E CLONE HTTP)
# =====================================================================
@lan_git_cli.command(name="web")
@click.argument("repo_path", default=".", type=click.Path(exists=False))
@click.option("--project", "-p", default=None, help="Nome simplificado do projeto alvo (ex: ORN).")
@click.option("--password", "-p_pass", default=None, help="Senha do portal web (se omitida em modo normal, será solicitada).")
@click.option("--port", default=8080, help="Porta HTTP do portal web.")
@click.option("--clone", is_flag=True, help="Modo Clone Rápido: sobe Smart HTTP direto para download sem travar por senha.")
@click.option("--profile", is_flag=True, help="Ativa telemetria de rede e medição de latência em tempo real.")
def cmd_web(repo_path: str, project: Optional[str], password: Optional[str],
            port: int, clone: bool, profile: bool):
    """Inicia o Portal Web & Smart HTTP para download e clone de qualquer Silo/Projeto."""
    target_query = project if project else repo_path
    ok, resolved_path, err = ProjectResolver.resolve_project_path(target_query)

    if not ok or not resolved_path:
        click.secho(f"[ERRO] {err}", fg="red")
        return

    abs_path = os.path.abspath(resolved_path)
    primary_iface = LANInterfaceDetector.get_primary_interface()

    if not primary_iface:
        click.secho("[ERRO CRÍTICO] Nenhuma interface de rede física detectada.", fg="red")
        return

    host_ip = primary_iface["ip"]

    # Se estiver em modo --clone, define chave padrão e avisa na tela
    is_open_clone = clone
    if clone and not password:
        #password = "dox"
        password = click.prompt("Senha do portal web", hide_input=True, confirmation_prompt=True)
    elif not password:
        password = click.prompt("Senha do portal web", hide_input=True, confirmation_prompt=True)

    portal = LANWebPortal(abs_path, password=password, host_ip=host_ip, port=port, profile=profile)
#    portal = LANWebPortal(abs_path, password=password, host_ip=host_ip, port=port, open_mode=is_open_clone)

    ok, err = portal.start()
    if not ok:
        click.secho(f"[ERRO] {err}", fg="red")
        return

    if profile:
        click.secho("  Telemetria  : PROFILING ATIVO (Medindo latências e SSE)", fg="magenta", bold=True)

    repo_name = os.path.basename(abs_path)
    click.secho("============================================================", fg="cyan")
    click.secho("          DOXOADE LAN WEB & SMART HTTP CLONE HUB", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")
    click.echo(f"  Silo/Projeto: {click.style(repo_name, bold=True)}")
    click.echo(f"  Diretório   : {abs_path}")
    click.echo(f"  Link Portal : {click.style(f'http://{host_ip}:{port}', fg='bright_yellow', bold=True)}")
    if is_open_clone:
        click.secho(f"  Acesso Rápido: ABERTO / Senha pré-definida: 'dox'", fg="green", bold=True)

    click.secho("\n📋 [COMANDO PRONTO PARA O BABYBLUE / PC-B]:", fg="magenta", bold=True)
    # ⚡ Aspas obrigatórias para suportar espaços no nome
    click.secho(f'  doxoade lan-git clone "{repo_name}" . --web --host {host_ip}', fg="yellow", bold=True)
    click.secho("  (Ou navegue no browser acima para baixar ZIP ou usar o Bloco de Notas)", fg="white")
    click.secho("============================================================", fg="cyan")

    stop_signal = threading.Event()
    try:
        # Permite ao Windows interceptar o Ctrl+C com resposta imediata
        while not stop_signal.is_set():
            stop_signal.wait(timeout=0.5)
    except KeyboardInterrupt:
        click.echo("\n[INFO] Encerrando Portal Web e liberando portas...")
    finally:
        portal.stop()
        click.secho("[OK] Portal Web finalizado com segurança.", fg="green")

# =====================================================================
# COMANDO: DISCOVER (CLIENT)
# =====================================================================
@lan_git_cli.command(name="discover")
@click.option("--udp-port", default=54545, help="Porta UDP de descoberta.")
@click.option("--timeout", default=2.0, help="Tempo limite de escuta em segundos.")
@click.option("--scan", is_flag=True, help="Ativa varredura direta de sub-rede.")
def cmd_discover(udp_port: int, timeout: float, scan: bool):
    """Procura por repositórios compartilhados na rede local."""
    click.echo(f"🔍 Procurando peers na rede local (Janela: {timeout}s)...")

    peers = []
    if scan:
        peers = LANDirectScanner.scan_subnet(udp_port=udp_port)
    else:
        peers = LANBeaconClient.discover_peers(timeout=timeout, udp_port=udp_port)
        if not peers:
            peers = LANDirectScanner.scan_subnet(udp_port=udp_port)

    if not peers:
        click.secho("\n[AVISO] Nenhum repositório compartilhado foi encontrado na LAN.", fg="yellow")
        click.echo("Dica: Verifique se o outro computador está com 'doxoade lan-git share' ativo.")
        return

    click.secho(f"\n✔ {len(peers)} repositório(s) encontrado(s) na rede:", fg="green", bold=True)
    click.secho("-" * 75, fg="cyan")
    for idx, p in enumerate(peers, 1):
        dirty_flag = click.style(f" [{p.dirty_count} ALTERAÇÕES EM MEMÓRIA]", fg="yellow") if p.is_dirty else ""
        live_flag = click.style(" [LIVE-MIRROR]", fg="magenta", bold=True) if p.is_live else ""
        click.echo(f" [{idx}] {click.style(p.repo_name, bold=True)} ({p.branch} @ {p.short_commit}){dirty_flag}{live_flag}")
        click.echo(f"     Host       : {p.hostname} ({p.ip}:{p.port})")
        click.echo(f"     Mensagem   : {p.commit_message}")
        click.echo(f"     Transporte : {p.transport}")
        click.secho("-" * 75, fg="cyan")


# =====================================================================
# COMANDO: PULL (CLIENT AUTO-MATCHING)
# =====================================================================
@lan_git_cli.command(name="pull")
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--apply", "-a", is_flag=True, help="Efetiva a sincronização no workspace (sai do modo DRY-RUN).")
@click.option("--force", "-f", is_flag=True, help="Sobrescreve alterações locais divergentes.")
@click.option("--autostash", is_flag=True, help="Guarda alterações locais automaticamente no stash.")
@click.option("--live", is_flag=True, help="Puxa o branch de espelhamento ao vivo (dox-live).")
@click.option("--udp-port", default=54545, help="Porta UDP de descoberta.")
def cmd_pull(repo_path: str, apply: bool, force: bool, autostash: bool, live: bool, udp_port: int):
    """Puxa e atualiza o repositório local.
    PADRÃO: DRY-RUN seguro com relatório W5. Use '--apply' (-a) para efetivar.
    """
    abs_path = os.path.abspath(repo_path)
    local_name = os.path.basename(abs_path)
    norm_local = _fuzzy_clean_name(local_name)

    manifests = LANBeaconClient.discover_peers(timeout=2.0, udp_port=udp_port)
    if not manifests:
        click.secho("[AVISO] Nenhum Host transmitindo repositórios via UDP na rede local.", fg="yellow")
        return

    # 🔍 AUTO-MATCHING SEGURO (Silo Shield)
    selected_manifest = None
    for m in manifests:
        if _fuzzy_clean_name(m.repo_name) == norm_local:
            selected_manifest = m
            break

    if not selected_manifest:
        click.secho(f"\n🛑 [SILO SHIELD] Nenhum compartilhamento para '{local_name}' localizado na rede.", fg="red", bold=True)
        click.echo("Projetos disponíveis no Host:")
        for m in manifests:
            click.echo(f"  • {m.repo_name} (no host {m.hostname} @ {m.ip})")
        click.secho(f"\n💡 Você está na pasta '{local_name}'. O download foi bloqueado para evitar contaminação.", fg="yellow")
        return

    is_dry_run = not (apply or force)
    target_branch = "dox-live" if (live or selected_manifest.is_live or selected_manifest.branch == "dox-live") else selected_manifest.branch

    # Executa o fetch dos objetos
    encoded_repo_name = quote(selected_manifest.repo_name)
    http_url = f"http://{selected_manifest.ip}:8080/{encoded_repo_name}"

    click.secho("\n════════════════════════════════════════════════════════════", fg="cyan")
    label_mode = "🔍 MODO AUDITORIA (DRY-RUN)" if is_dry_run else "⚡ MODO APLICAÇÃO REAL (--apply)"
    color_mode = "yellow" if is_dry_run else "green"
    click.secho(f"          LAN-GIT PULL — {label_mode}", fg=color_mode, bold=True)
    click.secho("════════════════════════════════════════════════════════════", fg="cyan")
    click.echo(f"  • Quem (Host)    : {selected_manifest.hostname} ({selected_manifest.ip})")
    click.echo(f"  • Onde (Destino) : {abs_path}")
    click.echo(f"  • Alvo (Branch)  : {target_branch} [{selected_manifest.short_commit}]")
    click.echo(f"  • Por Quê (Log)  : {selected_manifest.commit_message}")

    # Faz o fetch para calcular as diferenças sem tocar no working tree
    refspec = f"+refs/heads/{target_branch}:refs/remotes/{GitSyncEngine.REMOTE_NAME}/{target_branch}"
    GitSyncEngine._configure_remote(abs_path, http_url)
    ok_fetch, fetch_out, code, err_f = GitSyncEngine._run_git_forensic(abs_path, ["fetch", GitSyncEngine.REMOTE_NAME, refspec])
    if not ok_fetch:
        ok_fetch, fetch_out, code, err_f = GitSyncEngine._run_git_forensic(abs_path, ["fetch", GitSyncEngine.REMOTE_NAME, target_branch])
        if not ok_fetch:
            click.secho(f"  ✖ Falha ao buscar objetos do Host: {err_f}", fg="red")
            return

    # Compara o que mudaria
    ok_diff, diff_out, _, _ = GitSyncEngine._run_git_forensic(abs_path, ["diff", "--name-status", f"HEAD..FETCH_HEAD"])
    files_mod, files_new, files_del = [], [], []

    if ok_diff and diff_out:
        for line in diff_out.splitlines():
            parts = line.split('\t', 1)
            if len(parts) == 2:
                st, fp = parts
                if st.startswith('M'): files_mod.append(fp)
                elif st.startswith('A'): files_new.append(fp)
                elif st.startswith('D'): files_del.append(fp)

    total_changes = len(files_mod) + len(files_new) + len(files_del)

    # 📊 DOSSIÊ W5 DE MODIFICAÇÕES
    click.secho("\n  📋 [RELATÓRIO FORENSE DE ARQUIVOS (W5)]", fg="cyan", bold=True)
    if total_changes == 0:
        click.secho("  ✔ Nenhuma diferença detectada. Seu repositório já está idêntico ao Host.", fg="green")
    else:
        click.echo(f"  Total de Alterações: {total_changes} arquivo(s)")
        if files_mod:
            click.secho(f"    📝 Modificados ({len(files_mod)}):", fg="yellow")
            for f in files_mod[:10]: click.echo(f"       ↳ {f}")
            if len(files_mod) > 10: click.echo(f"       ... e mais {len(files_mod)-10} arquivo(s)")
        if files_new:
            click.secho(f"    ✨ Novos ({len(files_new)}):", fg="green")
            for f in files_new[:10]: click.echo(f"       ↳ {f}")
            if len(files_new) > 10: click.echo(f"       ... e mais {len(files_new)-10} arquivo(s)")
        if files_del:
            click.secho(f"    🗑️  Deletados ({len(files_del)}):", fg="red")
            for f in files_del[:5]: click.echo(f"       ↳ {f}")

    click.secho("════════════════════════════════════════════════════════════\n", fg="cyan")

    # Se estiver em Dry-Run, encerra aqui com instrução de aplicação
    if is_dry_run:
        if total_changes > 0:
            click.secho("💡 Para aplicar as alterações acima com segurança no seu projeto, execute:", fg="yellow", bold=True)
            click.secho(f"   doxoade lan-git pull --live --apply\n", fg="cyan", bold=True)
        return

    # ⚡ SE FOR --APPLY OU --FORCE: Efetiva com snapshot de segurança prévio
    click.secho("💾 [BACKUP AUTOMÁTICO] Criando âncora 'dox-safety-backup' antes da aplicação...", fg="yellow")
    GitSyncEngine._run_git_forensic(abs_path, ["branch", "-f", "dox-safety-backup", "HEAD"])

    ok_reset, _, code_r, err_r = GitSyncEngine._run_git_forensic(abs_path, ["reset", "--hard", "FETCH_HEAD"])
    if ok_reset:
        click.secho(f"✔ [100% SINCRONIZADO] {total_changes} arquivo(s) aplicados com sucesso!", fg="green", bold=True)
        click.secho("  (Reversibilidade garantida: 'git reset --hard dox-safety-backup' para desfazer).\n", fg="white")
    else:
        click.secho(f"✖ Falha ao aplicar sincronização: {err_r}", fg="red")

    # ═══════════════════════════════════════════════════════════
    # CORREÇÃO: TRANSMISSÃO P2P COM RETORNO AO BRANCH ORIGINAL
    # ═══════════════════════════════════════════════════════════
    
    # 1. Identificar o branch de trabalho original antes de qualquer operação
    ok_b, curr_branch, _, _ = GitSyncEngine._run_git_forensic(abs_path, ["branch", "--show-current"])
    original_branch = curr_branch.strip() if ok_b and curr_branch.strip() else "main"

    click.echo(f"Sincronizando com '{target_manifest.hostname}' ({target_manifest.ip})...")
    click.echo(f"  [RAMIFICAÇÃO] Branch de trabalho ativo: '{original_branch}'")

    # 2. Executa a transmissão real via rede LAN (Fetch dos objetos e refs)
    ok_fetch, fetch_msg = GitSyncEngine.pull_from_peer(
        abs_path, target_manifest, force=force, autostash=autostash, live=live
    )

    if not ok_fetch:
        click.secho(f"\n✖ [FALHA FORENSE NA TRANSMISSÃO]\n{fetch_msg}", fg="red", bold=True)
        # Garante retorno caso o fetch tenha mudado o contexto
        GitSyncEngine._run_git_forensic(abs_path, ["checkout", original_branch])
        return

    # Sincronização padrão (não-live)
    if not live:
        # Garante que continua no branch de origem
        GitSyncEngine._run_git_forensic(abs_path, ["checkout", original_branch])
        click.secho(f"\n✔ [SUCESSO] {fetch_msg}", fg="green", bold=True)
        click.secho(f"  ✔ [BRANCH] Você está no branch original: '{original_branch}'.", fg="green")
        return

    # ═══════════════════════════════════════════════════════════
    # 3. MODO LIVE: FUSÃO OU ESPELHAMENTO FORÇADO
    # ═══════════════════════════════════════════════════════════
    sync_branch = "dox-live-sync"
    remote_ref = f"{GitSyncEngine.REMOTE_NAME}/dox-live"

    click.secho("\n  [LIVE] Recebendo rascunho em memória...", fg="yellow")

    # 1. Atualiza a branch auxiliar local 'dox-live-sync' apontando para o que veio do Host
    ok_br, _, _, err_br = GitSyncEngine._run_git_forensic(abs_path, ["branch", "-f", sync_branch, remote_ref])
    if not ok_br:
        click.secho(f"  ✖ [FALHA] Não foi possível atualizar '{sync_branch}': {err_br}", fg="red")
        return

    # Garante que o workspace está no branch original
    GitSyncEngine._run_git_forensic(abs_path, ["checkout", original_branch])

    # 2. SE --FORCE ESTIVER ATIVO: Espelhamento direto e absoluto (sem travar por merge ou arquivos dirty)
    if force:
        click.secho(f"  ⚡ [--FORCE ATIVO] Espelhando estado exato do Host em '{original_branch}'...", fg="yellow", bold=True)
        ok_reset, reset_out, _, reset_err = GitSyncEngine._run_git_forensic(abs_path, ["reset", "--hard", sync_branch])
        if ok_reset:
            click.secho(f"  ✔ [SUCESSO] Workspace espelhado com o Host com sucesso ({original_branch} @ {sync_branch}).", fg="green", bold=True)
        else:
            click.secho(f"  ✖ [FALHA NO RESET] {reset_err}", fg="red")
        return

    # 3. SE NÃO FOR FORCE: Tenta merge limpo com proteção contra conflitos
    click.secho(f"  [INFO] Incorporando alterações recebidas em '{original_branch}'...", fg="cyan")
    ok_merge, out_merge, _, err_merge = GitSyncEngine._run_git_forensic(
        abs_path, ["merge", sync_branch, "--no-edit", "--no-ff"]
    )

    if ok_merge:
        click.secho(f"  ✔ [SUCESSO] Alterações do Host incorporadas com sucesso em '{original_branch}'.", fg="green")
    else:
        # Auto-Abort para proteger o workspace em caso de colisão
        click.secho("\n  ⚠ [DIVERGÊNCIA OU ARQUIVOS LOCAIS PENDENTES]", fg="yellow", bold=True)
        click.secho(f"  Não foi possível mesclar automaticamente em '{original_branch}'.", fg="white")
        # Só tenta abortar se MERGE_HEAD existir
        git_dir = os.path.join(abs_path, ".git")
        if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
            GitSyncEngine._run_git_forensic(abs_path, ["merge", "--abort"])
        click.secho(f"  ✔ Branch '{original_branch}' mantido seguro.", fg="green")
        click.secho("\n  💡 Para sobrepor alterações locais e forçar o estado do Host:", fg="yellow")
        click.secho(f"     doxoade lan-git pull --live --force\n", fg="cyan", bold=True)

    return

# =====================================================================
# COMANDO: REPAIR (AUTO-RECUPERAÇÃO DE RAMIFICAÇÃO E LIMPEZA)
# =====================================================================
@lan_git_cli.command(name="repair")
@click.argument("repo_path", default=".", type=click.Path(exists=True))
def cmd_repair(repo_path: str):
    """Diagnostica e recupera automaticamente o repositório de merges travados e conflitos."""
    abs_path = os.path.abspath(repo_path)
    click.secho("============================================================", fg="cyan")
    click.secho("          DOXOADE LAN GIT - AUTO-REPARO DE REPOSITÓRIO", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")

    # 1. Aborta merges pendentes (MERGE_HEAD)
    git_dir = os.path.join(abs_path, ".git")
    if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
        click.secho("  ⚠ Merge pendente detectado. Abortando com segurança...", fg="yellow")
        GitSyncEngine._run_git_forensic(abs_path, ["merge", "--abort"])
        click.secho("  ✔ Merge pendente cancelado.", fg="green")

    # 2. Limpa arquivos com marcadores literais de conflito no stage
    GitSyncEngine._run_git_forensic(abs_path, ["reset", "HEAD", "*pty_status.json*", "*--userdir~*"])
    
    # 3. Retorna ao main caso esteja preso em dox-live ou dox-live-sync
    ok_b, curr_b, _, _ = GitSyncEngine._run_git_forensic(abs_path, ["branch", "--show-current"])
    current_branch = curr_b.strip() if ok_b else ""
    if current_branch in ("dox-live", "dox-live-sync"):
        click.secho(f"  ⚠ Repositório está na branch temporária '{current_branch}'. Retornando ao 'main'...", fg="yellow")
        GitSyncEngine._run_git_forensic(abs_path, ["checkout", "main"])

    # 4. Status final
    ok_st, status_out, _, _ = GitSyncEngine._run_git_forensic(abs_path, ["status", "--short"])
    if not status_out.strip():
        click.secho("\n✔ [100% RECUPERADO] Árvore de trabalho limpa e sincronizável.", fg="green", bold=True)
    else:
        click.secho(f"\nℹ Arquivos modificados remanescentes:\n{status_out}", fg="cyan")
    click.secho("============================================================", fg="cyan")


# =====================================================================
# COMANDO: DOCTOR (DIAGNÓSTICO COM AUTO-REPARO UAC)
# =====================================================================
@lan_git_cli.command(name="doctor")
@click.option("--fix", is_flag=True, help="Aplica regras de Firewall automaticamente via elevação UAC honesta.")
def cmd_doctor(fix: bool):
    """Executa auditoria completa de conectividade, firewall, adaptadores e Git."""
    click.secho("============================================================", fg="cyan")
    click.secho("          DIAGNÓSTICO DE REDE E FIREWALL LAN GIT", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")

    git_bin = shutil.which("git")
    if git_bin:
        try:
            res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
            click.secho(f"[OK] Git detectado no PATH: {res.stdout.strip()}", fg="green")
        except Exception:
            click.secho(f"[OK] Git detectado em: {git_bin}", fg="green")
    else:
        click.secho("[ERRO CRÍTICO] 'git.exe' NÃO FOI ENCONTRADO NO PATH DO WINDOWS.", fg="red", bold=True)

    interfaces = LANInterfaceDetector.get_active_interfaces()
    if interfaces:
        click.secho(f"[OK] {len(interfaces)} interface(s) física(s) detectada(s):", fg="green")
        for iface in interfaces:
            click.echo(f"     - {iface['interface']}: IP {iface['ip']} (Broadcast: {iface['broadcast']})")
    else:
        click.secho("[FALHA] Nenhuma interface de rede física detectada.", fg="red")

    ports_to_test = [
        (54545, "udp", "Discovery Beacon"),
        (9418, "tcp", "Git Daemon Nativo"),
        (8080, "tcp", "Git Smart HTTP"),
        (54546, "tcp", "Git Bundle Stream")
    ]

    has_blocked_ports = False
    click.echo("\nTestando disponibilidade de portas do sistema:")
    for port, proto, desc in ports_to_test:
        ok, err = GitFirewallGuard.test_port_availability(port, proto=proto)
        if ok:
            click.secho(f"  [OK] Porta {port}/{proto.upper()} ({desc}): Disponível", fg="green")
        else:
            has_blocked_ports = True
            click.secho(f"  [BLOQUEIO] Porta {port}/{proto.upper()} ({desc}): {err}", fg="yellow")

    if has_blocked_ports or fix:
        click.secho("\n--- [ELEVAÇÃO HONESTA DE FIREWALL] ---", fg="cyan", bold=True)
        if fix or click.confirm("Deseja aplicar as regras de firewall automaticamente via Windows UAC?", default=True):
            click.echo("Solicitando permissão ao Windows (aceite o pop-up na tela)...")
            if GitFirewallGuard.request_honest_elevation():
                click.secho("✔ Regras de firewall enviadas para aplicação com sucesso!", fg="green")
            else:
                click.secho("✖ Solicitação cancelada pelo usuário ou falha na elevação.", fg="yellow")

    click.secho("============================================================", fg="cyan")

# =====================================================================
# COMANDO: CLONE (BOOTSTRAP DINÂMICO VIA LAN)
# =====================================================================
@lan_git_cli.command(name="clone")
@click.argument("arg1", required=False, default=None)
@click.argument("arg2", required=False, default=None)
@click.option("--dest", "-d", default=None, help="Diretório de destino.")
@click.option("--host", default=None, help="IP direto do Host (ex: 192.168.18.52).")
@click.option("--udp-port", default=54545, help="Porta UDP de descoberta.")
@click.option("--http-port", default=8080, help="Porta HTTP quando usando --web.")
@click.option("--web", is_flag=True, help="Clona via Smart HTTP / Web Portal em vez do Git Daemon.")
def cmd_clone(arg1: Optional[str], arg2: Optional[str], dest: Optional[str], host: Optional[str], udp_port: int, http_port: int, web: bool):
    """Clona um projeto compartilhado na rede LAN para a máquina atual.
    
    Exemplos Dinâmicos:
        doxoade lan-git clone .                  (Clona na pasta atual casando o nome da pasta)
        doxoade lan-git clone . --web            (Clona na pasta atual via Smart HTTP)
        doxoade lan-git clone ORN .              (Clona o projeto ORN dentro da pasta atual)
        doxoade lan-git clone ORN                (Clona criando a pasta ./ORN)
    """
    # Resolução inteligente de argumentos flexíveis:
    project_query = None
    target_dest = dest

    if arg1 == ".":
        target_dest = "."
        # Tenta pegar o nome da pasta atual como pista do projeto
        curr_dir_name = os.path.basename(os.path.abspath("."))
        project_query = curr_dir_name
    elif arg1 and arg2 == ".":
        project_query = arg1
        target_dest = "."
    elif arg1:
        project_query = arg1
        if arg2:
            target_dest = arg2

    click.secho("============================================================", fg="cyan")
    click.secho("          DOXOADE LAN GIT - CLONE DINÂMICO", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")

    target_manifest = None
    peers = []

    if host:
        click.echo(f"🔍 Conectando diretamente ao Host {host}...")
        target_manifest = LANDirectScanner.probe_single(host, udp_port=udp_port)
    else:
        click.echo("🔍 Procurando projetos anunciados na rede local...")
        peers = LANBeaconClient.discover_peers(timeout=2.5, udp_port=udp_port)
        if not peers:
            peers = LANDirectScanner.scan_subnet(udp_port=udp_port)

        if peers:
            if project_query:
                clean_target = _fuzzy_clean_name(project_query)
                for p in peers:
                    clean_remote = _fuzzy_clean_name(p.repo_name)
                    if clean_target == clean_remote or clean_target in clean_remote or clean_remote in clean_target:
                        target_manifest = p
                        break
            
            # Se não casou por nome ou não passou nome, mas só há 1 compartilhado na rede
            if not target_manifest and len(peers) == 1:
                target_manifest = peers[0]
                click.echo(f"  ℹ️ Repositório único detectado na rede: '{target_manifest.repo_name}'")

    # Se foi passado --host com --web direto sem broadcast
    if not target_manifest and host and web:
        target_ip = host
        repo_name = project_query if project_query else "repo"
    elif not target_manifest:
        click.secho("\n[FALHA] Nenhum repositório correspondente encontrado na LAN.", fg="red")
        if peers:
            click.echo("Repositórios disponíveis na rede:")
            for p in peers:
                click.echo(f"  • {p.repo_name} em {p.hostname} ({p.ip})")
        else:
            click.echo("Dica: No PC com o projeto original, certifique-se de rodar:")
            click.secho("  doxoade lan-git share .   (ou 'doxoade lan-git web --clone .')", fg="yellow")
        return
    else:
        target_ip = target_manifest.ip
        repo_name = target_manifest.repo_name

    # Definir diretório final
    final_dest = target_dest if target_dest else repo_name
    abs_dest = os.path.abspath(final_dest)

    # Montar URL de Clone (Git Daemon ou HTTP)
    if web or (target_manifest and target_manifest.transport == "http"):
        port = target_manifest.port if (target_manifest and target_manifest.transport == "http") else http_port
        clone_url = f"http://{target_ip}:{port}/"
    else:
        port = target_manifest.port if target_manifest else 9418
        clone_url = f"git://{target_ip}:{port}/"

    click.echo(f"\n📦 Clonando '{repo_name}'...")
    click.echo(f"  URL     : {clone_url}")
    click.echo(f"  Destino : {abs_dest}")

    # Validação de diretório destino existente
    if os.path.exists(abs_dest) and os.listdir(abs_dest):
        if os.path.exists(os.path.join(abs_dest, ".git")):
            click.secho(f"\n[AVISO] A pasta '{abs_dest}' já é um repositório Git.", fg="yellow")
            click.echo("Use 'doxoade lan-git pull' para atualizar as alterações.")
            return

    # Executar git clone
    clone_cmd = ["git", "clone", clone_url, abs_dest]
    try:
        proc = subprocess.run(clone_cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            click.secho(f"\n✖ [FALHA NO CLONE]\n{proc.stderr.strip()}", fg="red", bold=True)
            return
    except Exception as e:
        click.secho(f"\n✖ [ERRO DE EXECUÇÃO]: {e}", fg="red")
        return

    # Configurar remote 'dox-lan-peer'
    GitSyncEngine._run_git_forensic(abs_dest, ["remote", "remove", GitSyncEngine.REMOTE_NAME])
    GitSyncEngine._run_git_forensic(abs_dest, ["remote", "add", GitSyncEngine.REMOTE_NAME, clone_url])

    click.secho(f"\n✔ [SUCESSO] Projeto '{repo_name}' baixado com sucesso!", fg="green", bold=True)
    click.secho(f"  📁 Localização : {abs_dest}", fg="white")
    click.secho(f"  🔗 Remote ativo: '{GitSyncEngine.REMOTE_NAME}' -> {clone_url}", fg="cyan")
    click.echo("\nPróximos passos:")
    if final_dest != ".":
        click.echo(f"  cd \"{final_dest}\"")
    click.echo("  doxoade lan-git pull")

# ═════════════════════════════════════════════════════════════════════
# COMANDO: NOTE (DOXNOTE MESH - CONTROLE, DIAGNÓSTICO E SERVIÇO)
# ═════════════════════════════════════════════════════════════════════
@lan_git_cli.group(name="note")
def note_group():
    """Sistema de Sincronização P2P para o Bloco de Notas Global da IDE."""
    pass


@note_group.command(name="service")
@click.option("--password", "-p", default=None, help="Chave de pareamento da malha.")
def cmd_note_service(password: Optional[str]):
    """Inicia o daemon P2P do DoxNote Mesh em background/terminal."""
    from doxoade.commands.lan_git.note_mesh.mesh_engine import NoteMeshEngine, UDP_PORT, TCP_PORT
    
    engine = NoteMeshEngine(password=password)
    engine.start()

    click.secho("============================================================", fg="cyan")
    click.secho("          DOXNOTE MESH — SERVIÇO P2P DE NOTAS ATIVO", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")
    click.echo(f"  Arquivo Global : {engine.notes_file}")
    click.echo(f"  Porta Beacon   : {UDP_PORT}/UDP (Descoberta P2P)")
    click.echo(f"  Porta Sync     : {TCP_PORT}/TCP (Túnel Criptografado)")
    click.echo(f"  Dispositivo    : {engine.hostname} ({engine.local_ip})")
    click.secho("============================================================", fg="cyan")
    click.secho("📡 Malha P2P Ativa. Sincronizando com a IDE em tempo real... (Ctrl+C para sair)\n", fg="yellow")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        click.echo("\n[INFO] Encerrando DoxNote Mesh...")
    finally:
        engine.stop()
        click.secho("[OK] Serviço P2P finalizado.", fg="green")


@note_group.command(name="status")
def cmd_note_status():
    """Exibe o diagnóstico e estado vivo da malha DoxNote Mesh."""
    from pathlib import Path
    state_file = Path.home() / ".doxoade" / "mesh_state.json"
    
    click.secho("============================================================", fg="cyan")
    click.secho("          DIAGNÓSTICO DA MALHA DOXNOTE MESH", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")

    if not state_file.exists():
        click.secho("  Status: DESCONECTADO / SERVIÇO INATIVO", fg="yellow")
        click.echo("  Execute 'doxoade lan-git note service' para iniciar.")
        return

    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        status = data.get("status", "unknown").upper()
        status_color = "green" if status == "CONNECTED" else "yellow"

        click.secho(f"  Status Geral  : {status}", fg=status_color, bold=True)
        click.echo(f"  Dispositivo   : {data.get('hostname')} ({data.get('local_ip')})")
        click.echo(f"  Par Conectado : {data.get('peer_name')} ({data.get('peer_ip')})")
        click.echo(f"  Último Sync   : {data.get('last_sync')}")
        click.echo(f"  Latência RTT  : {data.get('rtt_ms')} ms")
    except Exception as e:
        click.secho(f"  Erro ao ler estado: {e}", fg="red")
    click.secho("============================================================", fg="cyan")


@note_group.command(name="open")
def cmd_note_open():
    """Abre o arquivo global shared_notes.md no editor padrão."""
    from pathlib import Path
    p = Path.home() / ".doxoade" / "shared_notes.md"
    if os.name == "nt":
        os.system(f'start "" "{p}"')
    else:
        os.system(f'xdg-open "{p}"')

if __name__ == "__main__":
    lan_git_cli()
