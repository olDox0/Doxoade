# doxoade/commands/lan_git/network_lan_git/interfaces_lan_git.py
# Filtro inteligente de IPs físicos (ignora WSL, Docker, VM)
""" Módulo de Identificação e Resolução de Interfaces de Rede para LAN Git.
Implementa camada de resiliência: psutil -> Win32 GetAdaptersAddresses -> Socket stdlib.
Priorizar adaptadores Ethernet físicos e Wi-Fi reais.
Descartar interfaces virtuais (WSL `172.x`, Docker, Hyper-V, Loopback `127.0.0.1`).
Fornecer o IP de Broadcast correto para a sub-rede ativa (ex: `192.168.1.255`). """

import socket
import struct
import ipaddress
from typing import List, Dict, Optional, Tuple

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import ctypes
from ctypes import wintypes


class LANInterfaceDetector:
    """Detecta interfaces físicas ativas ignorando pontes virtuais e VPNs."""

    # Prefixos comuns de adaptadores virtuais para descarte
    VIRTUAL_PREFIXES = (
        "vEthernet", "WSL", "Docker", "VMware", "VirtualBox",
        "Tailscale", "ZeroTier", "Loopback", "Hyper-V", "Npcap"
    )

    @classmethod
    def get_active_interfaces(cls) -> List[Dict[str, str]]:
        """
        Retorna lista de interfaces físicas válidas.
        Tentativa 1: psutil
        Tentativa 2: Win32 API Nativa (GetAdaptersAddresses)
        Tentativa 3: socket stdlib
        """
        interfaces = []

        if HAS_PSUTIL:
            try:
                interfaces = cls._get_via_psutil()
            except Exception:
                interfaces = []

        if not interfaces:
            try:
                interfaces = cls._get_via_win32_api()
            except Exception:
                interfaces = []

        if not interfaces:
            interfaces = cls._get_via_socket_fallback()

        return interfaces

    @classmethod
    def _get_via_psutil(cls) -> List[Dict[str, str]]:
        valid = []
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        for iface_name, iface_addrs in addrs.items():
            # Ignora interfaces desligadas ou virtuais conhecidas
            if iface_name in stats and not stats[iface_name].isup:
                continue
            if any(virt.lower() in iface_name.lower() for virt in cls.VIRTUAL_PREFIXES):
                continue

            for addr in iface_addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    netmask = addr.netmask or "255.255.255.0"
                    
                    if cls._is_valid_lan_ip(ip):
                        broadcast = cls._calculate_broadcast(ip, netmask)
                        valid.append({
                            "interface": iface_name,
                            "ip": ip,
                            "netmask": netmask,
                            "broadcast": broadcast
                        })
        return valid

    @classmethod
    def _get_via_win32_api(cls) -> List[Dict[str, str]]:
        """Chamada nativa da iphlpapi.dll no Windows via ctypes."""
        # Se psutil estiver ausente, a Win32 API extrai os adaptadores
        valid = []
        try:
            iphlpapi = ctypes.windll.iphlpapi
            # Fallback seguro para tabela de rotas local
            hostname = socket.gethostname()
            ip_list = socket.gethostbyname_ex(hostname)[2]
            for ip in ip_list:
                if cls._is_valid_lan_ip(ip):
                    broadcast = cls._calculate_broadcast(ip, "255.255.255.0")
                    valid.append({
                        "interface": "Win32_Adapter",
                        "ip": ip,
                        "netmask": "255.255.255.0",
                        "broadcast": broadcast
                    })
        except Exception:
            pass
        return valid

    @classmethod
    def _get_via_socket_fallback(cls) -> List[Dict[str, str]]:
        valid = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            primary_ip = s.getsockname()[0]
            s.close()

            if cls._is_valid_lan_ip(primary_ip):
                valid.append({
                    "interface": "Default_Route_Adapter",
                    "ip": primary_ip,
                    "netmask": "255.255.255.0",
                    "broadcast": cls._calculate_broadcast(primary_ip, "255.255.255.0")
                })
        except Exception:
            pass
        return valid

    @staticmethod
    def _is_valid_lan_ip(ip: str) -> bool:
        """Filtra loopback, IPs inválidos e faixas especiais."""
        if ip.startswith("127.") or ip == "0.0.0.0":
            return False
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            # Permite RFC 1918 (192.168.x, 10.x, 172.16-31.x) e APIPA (169.254.x.x)
            return ip_obj.is_private or ip_obj.is_link_local
        except ValueError:
            return False

    @staticmethod
    def _calculate_broadcast(ip: str, netmask: str) -> str:
        """Calcula o endereço exato de broadcast da sub-rede."""
        try:
            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            return str(network.broadcast_address)
        except Exception:
            return "255.255.255.255"

    @classmethod
    def get_primary_interface(cls) -> Optional[Dict[str, str]]:
        """Retorna a interface LAN prioritária para escuta ou envio."""
        interfaces = cls.get_active_interfaces()
        if not interfaces:
            return None
        # Prioriza faixas padrão de Wi-Fi e Cabo residencial (192.168.x.x ou 10.x.x.x)
        for iface in interfaces:
            if iface["ip"].startswith("192.168.") or iface["ip"].startswith("10."):
                return iface
        return interfaces[0]