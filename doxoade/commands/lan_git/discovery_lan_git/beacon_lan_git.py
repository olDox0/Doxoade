# doxoade/commands/lan_git/discovery_lan_git/beacon_lan_git.py
# Host: Transmissor UDP | Client: Receptor UDP (Plano A)
""" Módulo de Descoberta UDP (Beacon Ping/Pong) com Telemetria em Tempo Real.
Plano A: Broadcast em sub-rede local com rate limiting e logs visuais no Host. """

import socket
import select
import time
from typing import List, Optional, Callable
import click

from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import (
    GitManifest, DOX_MAGIC_HEADER
)
from doxoade.commands.lan_git.network_lan_git.interfaces_lan_git import LANInterfaceDetector
from doxoade.commands.lan_git.network_lan_git.git_firewall_guard import GitFirewallGuard


PING_PAYLOAD = f"PING_{DOX_MAGIC_HEADER}".encode("utf-8")


class LANBeaconHost:
    """Modo Servidor: Escuta solicitações de ping UDP e responde com telemetria."""

    def __init__(self, manifest: GitManifest, udp_port: int = 54545):
        self.manifest = manifest
        self.udp_port = udp_port
        self.guard = GitFirewallGuard()
        self.running = False
        self._sock: Optional[socket.socket] = None
        self._seen_pings: dict = {}  # Limita poluição de logs repetidos

    def start(self, stop_callback: Optional[Callable[[], bool]] = None):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.udp_port))
        self._sock.setblocking(False)
        self.running = True

        while self.running:
            if stop_callback and stop_callback():
                break

            ready = select.select([self._sock], [], [], 0.5)
            if ready[0]:
                try:
                    data, addr = self._sock.recvfrom(2048)
                    client_ip, client_port = addr

                    if not self.guard.check_rate_limit(client_ip):
                        continue

                    if data == PING_PAYLOAD:
                        response_bytes = self.manifest.to_bytes()
                        self._sock.sendto(response_bytes, addr)

                        now = time.time()
                        if client_ip not in self._seen_pings or now - self._seen_pings[client_ip] > 4.0:
                            self._seen_pings[client_ip] = now
                            timestamp_str = time.strftime("%H:%M:%S")

                            # Identifica o dispositivo pelo IP
                            from doxoade.commands.lan_git.transport_lan_git.git_http_server import identify_peer_device
                            device_label = identify_peer_device(client_ip)
                            click.secho(f"  [{timestamp_str}] [DISCOVERY] {device_label} localizou este repositório via UDP.", fg="cyan")

                except Exception:
                    continue

        self.stop()

    def update_manifest(self, new_manifest: GitManifest):
        """Permite atualizar o manifesto transmitido em modo Live Mirror."""
        self.manifest = new_manifest

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


class LANBeaconClient:
    """Modo Cliente: Envia pings broadcast e coleta respostas dos Hosts na rede."""

    @classmethod
    def discover_peers(cls, timeout: float = 2.0, udp_port: int = 54545) -> List[GitManifest]:
        interfaces = LANInterfaceDetector.get_active_interfaces()
        if not interfaces:
            return []

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.2)

        for iface in interfaces:
            bcast_ip = iface.get("broadcast", "255.255.255.255")
            try:
                sock.sendto(PING_PAYLOAD, (bcast_ip, udp_port))
            except Exception:
                pass

        try:
            sock.sendto(PING_PAYLOAD, ("255.255.255.255", udp_port))
        except Exception:
            pass

        start_time = time.time()
        discovered: List[GitManifest] = []
        seen_hosts = set()

        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                manifest = GitManifest.from_bytes(data)
                if manifest:
                    key = (manifest.ip, manifest.port, manifest.repo_name)
                    if key not in seen_hosts:
                        seen_hosts.add(key)
                        discovered.append(manifest)
            except socket.timeout:
                continue
            except Exception:
                break

        sock.close()
        return discovered