# doxoade/commands/lan_git/network_lan_git/unified_elevation.py
"""
🛡️ DOXOADE UNIFIED NETWORK ELEVATION & FIREWALL SHIELD (V2.1 - Anti-Freeze)
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
        Gera script PowerShell idempotente e estritamente não-interativo.
        $ConfirmPreference = 'None' e -Confirm:$false neutralizam prompts de [Y/N].
        """
        tcp_ports = ",".join(map(str, cls.TCP_PORTS))
        udp_ports = ",".join(map(str, cls.UDP_PORTS))

        legacy_rules = [
            "Doxoade-LAN-Git-TCP", "Doxoade-LAN-Git-UDP", "Doxoade-LAN-Git-HTTP",
            "DoxNote-Mesh-TCP-In", "DoxNote-Mesh-UDP-In",
            cls.RULE_NAME_TCP, cls.RULE_NAME_UDP
        ]
        quoted_rules = "'" + "','".join(legacy_rules) + "'"

        if action == "remove":
            return f"""
$ErrorActionPreference = 'SilentlyContinue'
$ConfirmPreference = 'None'
$rules = @({quoted_rules})
foreach ($r in $rules) {{
    Remove-NetFirewallRule -DisplayName $r -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
}}
Write-Output 'RULES_REMOVED_OK'
""".strip()

        ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$ConfirmPreference = 'None'

$rules = @({quoted_rules})
foreach ($r in $rules) {{
    Remove-NetFirewallRule -DisplayName $r -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
}}

New-NetFirewallRule -DisplayName '{cls.RULE_NAME_TCP}' -Description 'Doxoade Unified Mesh: Git Daemon, Web Portal e DoxNote HTTP' -Direction Inbound -LocalPort {tcp_ports} -Protocol TCP -Action Allow -RemoteAddress LocalSubnet -Profile Any -Confirm:$false | Out-Null

New-NetFirewallRule -DisplayName '{cls.RULE_NAME_UDP}' -Description 'Doxoade Unified Mesh: Discovery Broadcast e Beacon P2P' -Direction Inbound -LocalPort {udp_ports} -Protocol UDP -Action Allow -RemoteAddress LocalSubnet -Profile Any -Confirm:$false | Out-Null

Write-Output 'RULES_APPLIED_OK'
"""
        return ps_script.strip()

    @classmethod
    def generate_netsh_commands(cls, action: str = "apply") -> List[str]:
        """Gera comandos clássicos netsh (Plano B: Fallback ultrarrápido)."""
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
            f'netsh advfirewall firewall add rule name="{cls.RULE_NAME_TCP}" dir=in action=allow protocol=TCP localport={tcp_ports} remoteip=localsubnet profile=any',
            f'netsh advfirewall firewall add rule name="{cls.RULE_NAME_UDP}" dir=in action=allow protocol=UDP localport={udp_ports} remoteip=localsubnet profile=any'
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

        # 1. Tentativa via Netsh (executa em ~20ms, imune a problemas de CIM)
        try:
            res_tcp = subprocess.run(
                f'netsh advfirewall firewall show rule name="{cls.RULE_NAME_TCP}"',
                shell=True, capture_output=True, text=True, timeout=3
            )
            if "Doxoade-Unified-LAN-TCP" in res_tcp.stdout:
                status["tcp_rule_active"] = True

            res_udp = subprocess.run(
                f'netsh advfirewall firewall show rule name="{cls.RULE_NAME_UDP}"',
                shell=True, capture_output=True, text=True, timeout=3
            )
            if "Doxoade-Unified-LAN-UDP" in res_udp.stdout:
                status["udp_rule_active"] = True

            if status["tcp_rule_active"] and status["udp_rule_active"]:
                return status
        except Exception:
            pass

        # 2. Tentativa complementar via PowerShell
        try:
            cmd = f"Get-NetFirewallRule -DisplayName '{cls.RULE_NAME_TCP}','{cls.RULE_NAME_UDP}' | Select-Object -ExpandProperty DisplayName"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True, text=True, timeout=4, stdin=subprocess.DEVNULL
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
        """Aplica regras unificadas com salvaguardas anti-freeze e fallback automático."""
        if os.name != "nt":
            return True, "Sistemas não-Windows não exigem configuração de NetFirewallRule."

        if dry_run:
            if fallback_netsh:
                cmds = "\n".join(cls.generate_netsh_commands(action="apply"))
                return True, f"[DRY-RUN] Comandos Netsh que seriam executados:\n{cmds}"
            else:
                script = cls.generate_powershell_script(action="apply")
                return True, f"[DRY-RUN] Script PowerShell que seria executado:\n{script}"

        temp_dir = Path(os.environ.get("TEMP", ".")) / ".doxoade_elevation"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # ROTA ADMIN DIRETA: Quando o terminal já é Administrador
        if cls.is_admin():
            if fallback_netsh:
                for cmd in cls.generate_netsh_commands(action="apply"):
                    subprocess.run(cmd, shell=True, capture_output=True)
                return True, "Regras de firewall aplicadas com sucesso via Netsh (Admin direto)."

            # Grava em arquivo .ps1 para evitar quebras de CLI multilinha
            ps_file = temp_dir / "apply_firewall.ps1"
            ps_file.write_text(cls.generate_powershell_script(action="apply"), encoding="utf-8")

            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ps_file.resolve())],
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    timeout=8
                )
                if "RULES_APPLIED_OK" in res.stdout:
                    return True, "Regras de firewall unificadas aplicadas com sucesso (PowerShell)."
            except subprocess.TimeoutExpired:
                # Plano B: Se o PowerShell demorar, o Netsh assume e resolve em milissegundos
                pass

            # Fallback automático para Netsh
            for cmd in cls.generate_netsh_commands(action="apply"):
                subprocess.run(cmd, shell=True, capture_output=True)
            return True, "Regras de firewall aplicadas via Netsh Fallback (Plano B)."

        # ROTA UAC ELEVADA: Quando invocado por usuário comum
        if fallback_netsh:
            batch_file = temp_dir / "apply_netsh.bat"
            batch_content = "@echo off\r\n" + "\r\n".join(cls.generate_netsh_commands(action="apply")) + "\r\nexit\r\n"
            batch_file.write_text(batch_content, encoding="utf-8")
            params = f'/c "{batch_file.resolve()}"'
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 0)
        else:
            ps_file = temp_dir / "apply_firewall.ps1"
            ps_file.write_text(cls.generate_powershell_script(action="apply"), encoding="utf-8")
            params = f'-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{ps_file.resolve()}"'
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", params, None, 0)

        if ret > 32:
            time.sleep(1.2)
            return True, "Regras solicitadas via UAC com sucesso. Verifique o status com 'network status'."
        return False, "A elevação de privilégios foi recusada pelo usuário no pop-up do UAC."

    @classmethod
    def remove_firewall_rules(cls, dry_run: bool = False) -> Tuple[bool, str]:
        """Remove as regras criadas garantindo reversibilidade total (Regra 1.2 ProDeNov)."""
        if os.name != "nt":
            return True, "Ambiente não-Windows."

        if dry_run:
            script = cls.generate_powershell_script(action="remove")
            return True, f"[DRY-RUN] Script de purga:\n{script}"

        temp_dir = Path(os.environ.get("TEMP", ".")) / ".doxoade_elevation"
        temp_dir.mkdir(parents=True, exist_ok=True)

        if cls.is_admin():
            for cmd in cls.generate_netsh_commands(action="remove"):
                subprocess.run(cmd, shell=True, capture_output=True)
            return True, "Regras de firewall Doxoade removidas com sucesso."

        batch_file = temp_dir / "remove_netsh.bat"
        batch_content = "@echo off\r\n" + "\r\n".join(cls.generate_netsh_commands(action="remove")) + "\r\nexit\r\n"
        batch_file.write_text(batch_content, encoding="utf-8")
        params = f'/c "{batch_file.resolve()}"'
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", params, None, 0)

        if ret > 32:
            time.sleep(1.0)
            return True, "Remoção solicitada via prompt UAC."
        return False, "Elevação UAC recusada."
