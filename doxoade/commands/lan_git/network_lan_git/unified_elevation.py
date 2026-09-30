# doxoade/commands/lan_git/network_lan_git/unified_elevation.py
"""
🛡️ DOXOADE UNIFIED NETWORK ELEVATION & FIREWALL SHIELD
Gerenciador soberano de integridade de portas e elevação transparente (UAC) no Windows.
Unifica as portas de DoxNote Mesh (Notas P2P), Git Daemon, Web Portal e Discovery UDP.

Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations

import os
import sys
import time
import ctypes
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        GREEN = YELLOW = RED = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""


class UnifiedFirewallShield:
    """Orquestrador de privilégios e regras de firewall para a malha Doxoade."""

    RULE_NAME_TCP = "Doxoade-Unified-LAN-TCP"
    RULE_NAME_UDP = "Doxoade-Unified-LAN-UDP"

    # Matriz canônica de portas da malha Doxoade
    TCP_PORTS: List[int] = [8080, 9418, 54546, 54548]
    UDP_PORTS: List[int] = [54545, 54547]

    @staticmethod
    def is_admin() -> bool:
        """Verifica se o processo atual possui privilégios administrativos no SO."""
        if os.name != "nt":
            return os.geteuid() == 0 if hasattr(os, "geteuid") else True
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @classmethod
    def get_ports_summary(cls) -> Dict[str, str]:
        """Retorna sumário formatado das portas gerenciadas."""
        return {
            "tcp": ",".join(map(str, cls.TCP_PORTS)),
            "udp": ",".join(map(str, cls.UDP_PORTS))
        }

    @classmethod
    def generate_powershell_script(cls, action: str = "apply") -> str:
        """
        Gera script PowerShell idempotente.
        Remove regras legadas/antigas e aplica as regras definitivas restritas à LocalSubnet.
        """
        tcp_ports = ",".join(map(str, cls.TCP_PORTS))
        udp_ports = ",".join(map(str, cls.UDP_PORTS))

        # Lista de regras antigas que devem ser limpas para evitar duplicação
        legacy_rules = [
            "Doxoade-LAN-Git-TCP", "Doxoade-LAN-Git-UDP", "Doxoade-LAN-Git-HTTP",
            "DoxNote-Mesh-TCP-In", "DoxNote-Mesh-UDP-In",
            cls.RULE_NAME_TCP, cls.RULE_NAME_UDP
        ]

        cleanup_cmd = "; ".join([
            f"Remove-NetFirewallRule -DisplayName '{rule}' -ErrorAction SilentlyContinue"
            for rule in legacy_rules
        ])

        if action == "remove":
            return f"$ErrorActionPreference = 'SilentlyContinue'; {cleanup_cmd}; Write-Output 'RULES_REMOVED_OK'"

        ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
{cleanup_cmd}

New-NetFirewallRule -DisplayName '{cls.RULE_NAME_TCP}' `
  -Description 'Doxoade Unified Mesh: Git Daemon, Web Portal e DoxNote HTTP' `
  -Direction Inbound -LocalPort {tcp_ports} -Protocol TCP -Action Allow `
  -RemoteAddress LocalSubnet -Profile Any | Out-Null

New-NetFirewallRule -DisplayName '{cls.RULE_NAME_UDP}' `
  -Description 'Doxoade Unified Mesh: Discovery Broadcast e Beacon P2P' `
  -Direction Inbound -LocalPort {udp_ports} -Protocol UDP -Action Allow `
  -RemoteAddress LocalSubnet -Profile Any | Out-Null

Write-Output 'RULES_APPLIED_OK'
"""
        return ps_script.strip()

    @classmethod
    def generate_netsh_commands(cls, action: str = "apply") -> List[str]:
        """Gera comandos clássicos netsh (Plano B: Fallback)."""
        tcp_ports = ",".join(map(str, cls.TCP_PORTS))
        udp_ports = ",".join(map(str, cls.UDP_PORTS))

        if action == "remove":
            return [
                f'netsh advfirewall firewall delete rule name="{cls.RULE_NAME_TCP}"',
                f'netsh advfirewall firewall delete rule name="{cls.RULE_NAME_UDP}"'
            ]

        return [
            f'netsh advfirewall firewall delete rule name="{cls.RULE_NAME_TCP}"',
            f'netsh advfirewall firewall delete rule name="{cls.RULE_NAME_UDP}"',
            f'netsh advfirewall firewall add rule name="{cls.RULE_NAME_TCP}" dir=in action=allow protocol=TCP localport={tcp_ports} remoteip=localsubnet',
            f'netsh advfirewall firewall add rule name="{cls.RULE_NAME_UDP}" dir=in action=allow protocol=UDP localport={udp_ports} remoteip=localsubnet'
        ]

    @classmethod
    def check_rules_status(cls) -> Dict[str, Any]:
        """Audita se as regras ativas estão presentes no Firewall do Windows."""
        status = {
            "is_windows": os.name == "nt",
            "is_admin": cls.is_admin(),
            "tcp_rule_active": False,
            "udp_rule_active": False,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        if os.name != "nt":
            status["tcp_rule_active"] = True
            status["udp_rule_active"] = True
            return status

        try:
            cmd = f"Get-NetFirewallRule -DisplayName '{cls.RULE_NAME_TCP}','{cls.RULE_NAME_UDP}' | Select-Object -ExpandProperty DisplayName"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=5
            )
            out = res.stdout.strip()
            if cls.RULE_NAME_TCP in out:
                status["tcp_rule_active"] = True
            if cls.RULE_NAME_UDP in out:
                status["udp_rule_active"] = True
        except Exception:
            pass

        return status

    @classmethod
    def apply_firewall_rules(
        cls,
        dry_run: bool = False,
        fallback_netsh: bool = False
    ) -> Tuple[bool, str]:
        """
        Aplica regras unificadas de firewall.
        Suporta dry-run (Item 5.3 ProDeNov) e fallback automático (Plano B).
        """
        if os.name != "nt":
            return True, "Sistemas não-Windows não exigem configuração de NetFirewallRule."

        if dry_run:
            if fallback_netsh:
                cmds = "\n".join(cls.generate_netsh_commands(action="apply"))
                return True, f"[DRY-RUN] Comandos Netsh que seriam executados:\n{cmds}"
            else:
                script = cls.generate_powershell_script(action="apply")
                return True, f"[DRY-RUN] Script PowerShell que seria executado:\n{script}"

        # Execução Direta se já for Administrador
        if cls.is_admin():
            if fallback_netsh:
                for cmd in cls.generate_netsh_commands(action="apply"):
                    subprocess.run(cmd, shell=True, capture_output=True)
                return True, "Regras de firewall aplicadas com sucesso via Netsh (Admin direto)."
            else:
                ps_script = cls.generate_powershell_script(action="apply")
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if "RULES_APPLIED_OK" in res.stdout:
                    return True, "Regras de firewall unificadas aplicadas com sucesso (Admin direto)."
                return False, f"Falha na execução do script PowerShell: {res.stderr[:200]}"

        # Execução com Elevação Honesta UAC (Plano A)
        temp_dir = Path(os.environ.get("TEMP", ".")) / ".doxoade_elevation"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if fallback_netsh:
            batch_file = temp_dir / "apply_netsh.bat"
            batch_content = "@echo off\r\n" + "\r\n".join(cls.generate_netsh_commands(action="apply")) + "\r\nexit\r\n"
            batch_file.write_text(batch_content, encoding="utf-8")
            params = f'/c "{batch_file.resolve()}"'
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 0)
        else:
            ps_file = temp_dir / "apply_firewall.ps1"
            ps_file.write_text(cls.generate_powershell_script(action="apply"), encoding="utf-8")
            params = f'-NoProfile -ExecutionPolicy Bypass -File "{ps_file.resolve()}"'
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, 0)

        if ret > 32:
            time.sleep(1.2)  # Pausa breve para conclusão do subprocesso elevado
            return True, "Regras solicitadas via UAC com sucesso. Verifique o status com '--status'."
        return False, "A elevação de privilégios foi recusada pelo usuário no pop-up do UAC."

    @classmethod
    def remove_firewall_rules(cls, dry_run: bool = False) -> Tuple[bool, str]:
        """Remove as regras criadas garantindo reversibilidade (Regra 1.2 ProDeNov)."""
        if os.name != "nt":
            return True, "Ambiente não-Windows."

        if dry_run:
            script = cls.generate_powershell_script(action="remove")
            return True, f"[DRY-RUN] Script PowerShell de purga:\n{script}"

        if cls.is_admin():
            ps_script = cls.generate_powershell_script(action="remove")
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                timeout=10
            )
            return True, "Regras de firewall Doxoade removidas com sucesso."

        temp_dir = Path(os.environ.get("TEMP", ".")) / ".doxoade_elevation"
        temp_dir.mkdir(parents=True, exist_ok=True)
        ps_file = temp_dir / "remove_firewall.ps1"
        ps_file.write_text(cls.generate_powershell_script(action="remove"), encoding="utf-8")
        params = f'-NoProfile -ExecutionPolicy Bypass -File "{ps_file.resolve()}"'
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, 0)

        if ret > 32:
            time.sleep(1.0)
            return True, "Remoção solicitada via prompt UAC."
        return False, "Elevação UAC recusada."


if __name__ == "__main__":
    # Autoteste standalone
    shield = UnifiedFirewallShield
    print("Is Admin:", shield.is_admin())
    print("Ports:", shield.get_ports_summary())
    print("Status:", shield.check_rules_status())
