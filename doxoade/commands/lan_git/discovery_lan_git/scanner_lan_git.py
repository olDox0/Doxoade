# doxoade/commands/lan_git/discovery_lan_git/scanner_lan_git.py
# Varredura direta de sub-rede / Ping sweep (Plano B)
""" Módulo de Varredura Direta (Scanner Fallback - Plano B).
Caso o roteador bloqueie broadcast UDP, faz probes unicast concorrentes na sub-rede /24. """

import socket
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from doxoade.commands.lan_git.discovery_lan_git.manifest_lan_git import (
    GitManifest, DOX_MAGIC_HEADER
)
from doxoade.commands.lan_git.discovery_lan_git.beacon_lan_git import PING_PAYLOAD
from doxoade.commands.lan_git.network_lan_git.interfaces_lan_git import LANInterfaceDetector


class LANDirectScanner:
    """Varredor de contingência para redes com AP Isolation (Isolamento de Wi-Fi)."""

    @staticmethod
    def _probe_ip(ip: str, port: int, timeout: float = 0.3) -> Optional[GitManifest]:
        """Tenta enviar um probe UDP unicast direto para um IP específico."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout)
            s.sendto(PING_PAYLOAD, (ip, port))
            data, _ = s.recvfrom(2048)
            s.close()
            return GitManifest.from_bytes(data)
        except Exception:
            return None

    @classmethod
    def scan_subnet(cls, udp_port: int = 54545, max_workers: int = 50) -> List[GitManifest]:
        """Escaneia a sub-rede ativa disparando threads paralelas."""
        primary = LANInterfaceDetector.get_primary_interface()
        if not primary:
            return []

        ip = primary["ip"]
        netmask = primary["netmask"]

        try:
            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        except Exception:
            return []

        manifests: List[GitManifest] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(cls._probe_ip, str(target_ip), udp_port): str(target_ip)
                for target_ip in network.hosts()
            }

            for future in as_completed(futures):
                res = future.result()
                if res:
                    manifests.append(res)

        return manifests

    @classmethod
    def probe_single(cls, target_ip: str, udp_port: int = 54545) -> Optional[GitManifest]:
        """Probe direto para conexão manual (--host <ip>)."""
        return cls._probe_ip(target_ip, udp_port, timeout=1.5)