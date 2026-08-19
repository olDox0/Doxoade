""" Interface de Linha de Comando (CLI) para o Sistema LAN Git Doxoade Multi-Silos.
Implementa Auto-Matching de Projetos (Zero Erro Humano), Live Mirroring e UAC. """

import os
import sys
import time
import re
import threading
import shutil
import subprocess
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

    http_server = GitHTTPServer(abs_path, port=http_port)
    http_server.start()

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
        http_server.stop()
        click.secho("[OK] Servidores finalizados com segurança.", fg="green")


# =====================================================================
# COMANDO: WEB (PORTAL MULTI-PROJETOS)
# =====================================================================
@lan_git_cli.command(name="web")
@click.argument("repo_path", default=".", type=click.Path(exists=False))
@click.option("--project", "-p", default=None, help="Nome simplificado do projeto alvo (ex: sysutils).")
@click.option("--password", "-p_pass", prompt=True, hide_input=True, confirmation_prompt=True, help="Senha do portal web.")
@click.option("--port", default=8080, help="Porta HTTP do portal web.")
def cmd_web(repo_path: str, project: Optional[str], password: str, port: int):
    """Inicia o Portal Web para download e bootstrap de qualquer Silo/Projeto."""
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
    portal = LANWebPortal(abs_path, password=password, host_ip=host_ip, port=port)

    ok, err = portal.start()
    if not ok:
        click.secho(f"[ERRO] {err}", fg="red")
        return

    click.secho("============================================================", fg="cyan")
    click.secho("          DOXOADE LAN WEB PORTAL & HUB DE BOOTSTRAP", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")
    click.echo(f"  Silo/Projeto: {click.style(os.path.basename(abs_path), bold=True)}")
    click.echo(f"  Link Direto : {click.style(f'http://{host_ip}:{port}', fg='bright_yellow', bold=True)}")
    click.echo(f"  Segurança   : Autenticação Criptográfica Ativa (Timing-Safe)")
    click.echo(f"  Proteções   : Anti-BruteForce, Anti-DNS Rebinding, ZIP Sanitizado")
    click.secho("============================================================", fg="cyan")
    click.secho(f"🌐 Abra o navegador no outro computador e acesse: http://{host_ip}:{port}", fg="yellow")
    click.secho("Pressione Ctrl+C para encerrar o portal.", fg="white")

    try:
        while True:
            time.sleep(1)
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
@click.option("--repo", "-r", default=None, help="Nome específico do repositório a sincronizar.")
@click.option("--host", default=None, help="IP direto do Host (ex: 192.168.18.52).")
@click.option("--udp-port", default=54545, help="Porta UDP de descoberta.")
@click.option("--force", "-f", is_flag=True, help="Força a sincronização sobrescrevendo alterações locais (Reset Hard).")
@click.option("--autostash", is_flag=True, help="Guarda alterações locais no stash e restaura após o pull.")
@click.option("--live", is_flag=True, help="Espelha o estado de rascunho em memória do Host (Live Mirror).")
def cmd_pull(repo_path: str, repo: Optional[str], host: Optional[str], udp_port: int, force: bool, autostash: bool, live: bool):
    """Puxa e atualiza o repositório local com Auto-Matching Inteligente."""
    abs_path = os.path.abspath(repo_path)
    target_manifest = None

    if host:
        click.echo(f"Conectando diretamente ao Host {host}...")
        target_manifest = LANDirectScanner.probe_single(host, udp_port=udp_port)
    else:
        click.echo("Procurando o repositório na rede local...")
        peers = LANBeaconClient.discover_peers(timeout=2.0, udp_port=udp_port)
        if not peers:
            peers = LANDirectScanner.scan_subnet(udp_port=udp_port)

        if peers:
            # 🎯 AUTO-MATCHING INTELIGENTE:
            # 1. Se o usuário passou --repo, procura pelo nome
            # 2. Se não passou, compara o nome da pasta atual (ex: 'Sysutils_proj') de forma difusa com os repos do Host ('Projeto SysUtils')
            current_folder_name = os.path.basename(abs_path)
            clean_local = _fuzzy_clean_name(repo if repo else current_folder_name)

            for p in peers:
                clean_remote = _fuzzy_clean_name(p.repo_name)
                if clean_local == clean_remote or clean_local in clean_remote or clean_remote in clean_local:
                    target_manifest = p
                    break

            # Se ainda não casou mas só há 1 repositório sendo anunciado na LAN, usa ele como padrão
            if not target_manifest and len(peers) == 1:
                target_manifest = peers[0]

    if not target_manifest:
        click.secho("[FALHA] Nenhum repositório correspondente foi localizado na rede.", fg="red")
        return

    click.echo(f"Sincronizando com '{target_manifest.hostname}' ({target_manifest.ip})...")
    ok, message = GitSyncEngine.pull_from_peer(abs_path, target_manifest, force=force, autostash=autostash, live=live)

    if ok:
        click.secho(f"\n✔ [SUCESSO] {message}", fg="green", bold=True)
    else:
        click.secho(f"\n✖ [FALHA FORENSE]\n{message}", fg="red", bold=True)


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


if __name__ == "__main__":
    lan_git_cli()