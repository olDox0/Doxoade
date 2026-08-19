# doxoade/commands/lan_git/network_lan_git/git_firewall_guard.py
# Diagnóstico de portas e gerador de comandos PowerShell
""" Módulo Guardião de Firewall, Diagnóstico de Portas e Elevação Honesta.
Testa integridade de rede e solicita elevação UAC nativa com transparência para o usuário. """

import os
import sys
import socket
import time
import ctypes
from typing import Tuple, Optional, Dict


class GitFirewallGuard:
    """Gerenciador de integridade de portas, políticas de firewall e UAC Honesto."""

    DEFAULT_DISCOVERY_PORT_UDP = 54545
    DEFAULT_GIT_DAEMON_PORT_TCP = 9418
    DEFAULT_HTTP_PORT_TCP = 8080
    DEFAULT_BUNDLE_PORT_TCP = 54546

    def __init__(self):
        self._rate_limits: Dict[str, list] = {}
        self.MAX_ATTEMPTS = 5
        self.WINDOW_SECONDS = 60

    @staticmethod
    def is_admin() -> bool:
        """Verifica se o processo atual possui privilégios de Administrador no Windows."""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def test_port_availability(port: int, proto: str = "tcp") -> Tuple[bool, Optional[str]]:
        sock_type = socket.SOCK_STREAM if proto.lower() == "tcp" else socket.SOCK_DGRAM
        s = socket.socket(socket.AF_INET, sock_type)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            s.close()
            return True, None
        except PermissionError:
            return False, f"Permissão negada para bind na porta {port} ({proto.upper()}). Requer elevação de firewall."
        except OSError as e:
            return False, f"Porta {port} ({proto.upper()}) ocupada ou bloqueada: {e}"

    @classmethod
    def generate_firewall_rules(cls) -> Dict[str, str]:
        """Gera os comandos de liberação estritamente restritos à LocalSubnet."""
        ports_tcp = f"{cls.DEFAULT_GIT_DAEMON_PORT_TCP},{cls.DEFAULT_HTTP_PORT_TCP},{cls.DEFAULT_BUNDLE_PORT_TCP}"
        port_udp = f"{cls.DEFAULT_DISCOVERY_PORT_UDP}"

        ps_script = (
            f"New-NetFirewallRule -DisplayName 'Doxoade-LAN-Git-TCP' -Direction Inbound "
            f"-LocalPort {ports_tcp} -Protocol TCP -Action Allow -RemoteAddress LocalSubnet -ErrorAction SilentlyContinue; "
            f"New-NetFirewallRule -DisplayName 'Doxoade-LAN-Git-UDP' -Direction Inbound "
            f"-LocalPort {port_udp} -Protocol UDP -Action Allow -RemoteAddress LocalSubnet -ErrorAction SilentlyContinue"
        )
        return {"powershell": ps_script}

    @classmethod
    def request_honest_elevation(cls) -> bool:
        """
        Invoca o popup oficial do Windows UAC (Sim/Não) para aplicar as regras de firewall.
        Trabalha em harmonia com o SO (sem bypasses opacos).
        """
        if os.name != "nt":
            return False

        ps_commands = cls.generate_firewall_rules()["powershell"]
        args = f'-NoProfile -ExecutionPolicy Bypass -Command "{ps_commands}"'

        try:
            # Executa com verbo 'runas' para disparar o UAC nativo do Windows
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "powershell.exe",
                args,
                None,
                1  # SW_SHOWNORMAL
            )
            # Retorno > 32 indica que o usuário clicou em 'SIM' no UAC
            return ret > 32
        except Exception:
            return False

    def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        if client_ip not in self._rate_limits:
            self._rate_limits[client_ip] = [now]
            return True

        self._rate_limits[client_ip] = [
            t for t in self._rate_limits[client_ip] if now - t < self.WINDOW_SECONDS
        ]

        if len(self._rate_limits[client_ip]) >= self.MAX_ATTEMPTS:
            return False

        self._rate_limits[client_ip].append(now)
        return True

    def reset_ip_block(self, client_ip: str):
        if client_ip in self._rate_limits:
            del self._rate_limits[client_ip]