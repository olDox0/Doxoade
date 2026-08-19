# doxoade/commands/lan_git/cli_lan_git.py
# Entrypoint dos comandos CLI (share, discover, pull, doctor)
""" Interface de Linha de Comando (CLI) para o Sistema LAN Git Doxoade.
Fornece os comandos: share, discover, pull, web e doctor (com auto-reparo UAC). """

import os
import sys
import time
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
from doxoade.commands.lan_git.transport_lan_git.git_bundle_stream import GitBundleHost
from doxoade.commands.lan_git.client_lan_git.git_sync_engine import GitSyncEngine
from doxoade.commands.lan_git.client_lan_git.lan_git_comparator import LANComparator, SyncStatus
from doxoade.commands.lan_git.web_lan_git.portal_server_lan_git import LANWebPortal


@click.group(name="lan-git")
def lan_git_cli():
    """Sistema de Sincronização P2P e Compartilhamento Local de Repositórios Git."""
    pass


# =====================================================================
# COMANDO: SHARE (HOST)
# =====================================================================
@lan_git_cli.command(name="share")
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--port", default=9418, help="Porta TCP do servidor Git.")
@click.option("--udp-port", default=54545, help="Porta UDP para anúncio Discovery.")
@click.option("--http", is_flag=True, help="Usa Plano B (Smart HTTP) em vez do Git Daemon.")
@click.option("--bundle", is_flag=True, help="Usa Plano C (Streaming de Git Bundle).")
def cmd_share(repo_path: str, port: int, udp_port: int, http: bool, bundle: bool):
    """Compartilha o repositório atual na rede local (Somente Leitura)."""
    abs_path = os.path.abspath(repo_path)
    primary_iface = LANInterfaceDetector.get_primary_interface()

    if not primary_iface:
        click.secho("[ERRO CRÍTICO] Nenhuma interface de rede física ativa foi detectada.", fg="red")
        return

    host_ip = primary_iface["ip"]
    transport_type = "git_daemon"
    if http:
        transport_type = "http"
        port = 8080 if port == 9418 else port
    elif bundle:
        transport_type = "bundle"
        port = 54546 if port == 9418 else port

    manifest = GitManifestExtractor.extract(abs_path, host_ip=host_ip, port=port, transport=transport_type)
    if not manifest:
        click.secho(f"[ERRO] O caminho '{abs_path}' não é um repositório Git válido.", fg="red")
        return

    server_instance = None
    if transport_type == "git_daemon":
        server_instance = GitDaemonServer(abs_path, port=port)
        ok, err = server_instance.start()
        if not ok:
            click.secho(f"[ERRO] Falha ao iniciar Git Daemon: {err}", fg="red")
            return
    elif transport_type == "http":
        server_instance = GitHTTPServer(abs_path, port=port)
        ok, err = server_instance.start()
        if not ok:
            click.secho(f"[ERRO] Falha ao iniciar Git HTTP Server: {err}", fg="red")
            return

    beacon = LANBeaconHost(manifest, udp_port=udp_port)
    beacon_thread = threading.Thread(target=beacon.start, daemon=True)
    beacon_thread.start()

    click.secho("============================================================", fg="cyan")
    click.secho("             DOXOADE LAN GIT - MODO SERVIDOR (HOST)", fg="green", bold=True)
    click.secho("============================================================", fg="cyan")
    click.echo(f"  Repositório : {click.style(manifest.repo_name, bold=True)}")
    click.echo(f"  Branch      : {manifest.branch} [{manifest.short_commit}]")
    click.echo(f"  Mensagem    : {manifest.commit_message}")
    click.echo(f"  Interface   : {primary_iface['interface']} ({host_ip})")
    click.echo(f"  Transporte  : {transport_type.upper()} (Porta TCP {port})")
    click.echo(f"  Discovery   : UDP Broadcast (Porta {udp_port})")
    click.echo(f"  Permissão   : SOMENTE LEITURA (Anti-Push Ativo)")
    click.secho("============================================================", fg="cyan")
    click.secho("📡 Aguardando conexões de computadores na rede... (Ctrl+C para encerrar)", fg="yellow")

    try:
        if transport_type == "bundle":
            while True:
                GitBundleHost.serve_bundle(abs_path, port=port)
                time.sleep(1)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\n[INFO] Encerrando servidor e liberando portas...")
    finally:
        beacon.stop()
        if server_instance:
            server_instance.stop()
        click.secho("[OK] Servidor finalizado com segurança.", fg="green")


# =====================================================================
# COMANDO: WEB (PORTAL)
# =====================================================================
@lan_git_cli.command(name="web")
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--password", "-p", prompt=True, hide_input=True, confirmation_prompt=True, help="Senha para proteger o portal web.")
@click.option("--port", default=8080, help="Porta HTTP do portal web.")
def cmd_web(repo_path: str, password: str, port: int):
    """Inicia o Portal Web Local protegido por senha para download e bootstrap."""
    abs_path = os.path.abspath(repo_path)
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
    click.echo(f"  Repositório : {click.style(os.path.basename(abs_path), bold=True)}")
    click.echo(f"  Link Direto : {click.style(f'http://{host_ip}:{port}', fg='bright_yellow', bold=True)}")
    click.echo(f"  Segurança   : Autenticação Criptográfica Ativa (Timing-Safe)")
    click.echo(f"  Proteções   : Anti-BruteForce, Anti-DNS Rebinding, FastPack Stream")
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
@click.option("--scan", is_flag=True, help="Ativa varredura direta de sub-rede (Plano B).")
def cmd_discover(udp_port: int, timeout: float, scan: bool):
    """Procura por repositórios compartilhados na rede local."""
    click.echo(f"🔍 Procurando peers na rede local (Janela: {timeout}s)...")

    peers = []
    if scan:
        click.echo("ℹ️ Modo Scan direto de sub-rede ativado (Plano B)...")
        peers = LANDirectScanner.scan_subnet(udp_port=udp_port)
    else:
        peers = LANBeaconClient.discover_peers(timeout=timeout, udp_port=udp_port)
        if not peers:
            # Auto-Fallback transparente para varredura rápida se o broadcast não responder
            click.echo("ℹ️ Broadcast sem resposta imediata. Tentando varredura rápida de sub-rede...")
            peers = LANDirectScanner.scan_subnet(udp_port=udp_port)

    if not peers:
        click.secho("\n[AVISO] Nenhum repositório compartilhado foi encontrado na LAN.", fg="yellow")
        click.echo("Dica: Verifique se o outro computador está com 'doxoade lan-git share' ativo.")
        return

    click.secho(f"\n✔ {len(peers)} repositório(s) encontrado(s) na rede:", fg="green", bold=True)
    click.secho("-" * 75, fg="cyan")
    for idx, p in enumerate(peers, 1):
        dirty_flag = click.style(" [ALTERAÇÕES PENDENTES NO HOST]", fg="yellow") if p.is_dirty else ""
        click.echo(f" [{idx}] {click.style(p.repo_name, bold=True)} ({p.branch} @ {p.short_commit}){dirty_flag}")
        click.echo(f"     Host       : {p.hostname} ({p.ip}:{p.port})")
        click.echo(f"     Mensagem   : {p.commit_message}")
        click.echo(f"     Transporte : {p.transport}")
        click.secho("-" * 75, fg="cyan")


# =====================================================================
# COMANDO: PULL (CLIENT)
# =====================================================================
@lan_git_cli.command(name="pull")
@click.argument("repo_path", default=".", type=click.Path(exists=True))
@click.option("--host", default=None, help="IP direto do Host (ex: 192.168.18.52).")
@click.option("--udp-port", default=54545, help="Porta UDP de descoberta.")
def cmd_pull(repo_path: str, host: Optional[str], udp_port: int):
    """Puxa e atualiza o repositório local a partir do peer da rede."""
    abs_path = os.path.abspath(repo_path)
    target_manifest = None

    if host:
        click.echo(f"Conectando diretamente ao Host {host}...")
        target_manifest = LANDirectScanner.probe_single(host, udp_port=udp_port)
    else:
        click.echo("Procurando o repositório na rede local...")
        peers = LANBeaconClient.discover_peers(timeout=2.0, udp_port=udp_port)
        if not peers:
            # Auto-fallback para varredura de sub-rede
            peers = LANDirectScanner.scan_subnet(udp_port=udp_port)

        if peers:
            current_repo_name = os.path.basename(abs_path)
            for p in peers:
                if p.repo_name.lower() == current_repo_name.lower():
                    target_manifest = p
                    break
            if not target_manifest:
                target_manifest = peers[0]

    if not target_manifest:
        click.secho("[FALHA] Nenhum peer com repositório ativo foi localizado na rede.", fg="red")
        click.echo("Dica: Certifique-se de que 'doxoade lan-git share' está rodando no Host.")
        return

    click.echo(f"Sincronizando com '{target_manifest.hostname}' ({target_manifest.ip})...")
    ok, message = GitSyncEngine.pull_from_peer(abs_path, target_manifest)

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

    # 1. Auditoria do Git
    git_bin = shutil.which("git")
    if git_bin:
        try:
            res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
            click.secho(f"[OK] Git detectado no PATH: {res.stdout.strip()}", fg="green")
        except Exception:
            click.secho(f"[OK] Git detectado em: {git_bin}", fg="green")
    else:
        click.secho("[ERRO CRÍTICO] 'git.exe' NÃO FOI ENCONTRADO NO PATH DO WINDOWS.", fg="red", bold=True)

    # 2. Interfaces Físicas
    interfaces = LANInterfaceDetector.get_active_interfaces()
    if interfaces:
        click.secho(f"[OK] {len(interfaces)} interface(s) física(s) detectada(s):", fg="green")
        for iface in interfaces:
            click.echo(f"     - {iface['interface']}: IP {iface['ip']} (Broadcast: {iface['broadcast']})")
    else:
        click.secho("[FALHA] Nenhuma interface de rede física detectada.", fg="red")

    # 3. Teste de Portas
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

    # 4. Auto-Reparo Honesto via UAC
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