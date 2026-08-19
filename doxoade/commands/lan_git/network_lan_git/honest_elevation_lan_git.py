# doxoade/commands/lan_git/network_lan_git/honest_elevation_lan_git.py
""" Módulo Honest Elevation (Elevação Transparente de Privilégios no Windows).
Solicita autorização ao usuário e invoca a API nativa ShellExecuteW (runas) para UAC. """

import os
import sys
import ctypes
import subprocess
from typing import List, Tuple, Optional
import click


class HonestElevation:
    """Gerencia elevação transparente e oficial de privilégios no Windows."""

    @staticmethod
    def is_admin() -> bool:
        """Verifica se o processo atual já possui privilégios de Administrador."""
        if os.name != "nt":
            return os.geteuid() == 0 if hasattr(os, "geteuid") else True
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @classmethod
    def execute_powershell_elevated(cls, ps_command: str) -> bool:
        """
        Dispara o prompt oficial do UAC do Windows para executar comandos administrativos.
        """
        if os.name != "nt":
            return False

        # Codifica o comando para execução limpa no PowerShell
        params = f"-NoProfile -ExecutionPolicy Bypass -Command \"{ps_command}\""
        
        try:
            # ShellExecuteW com verbo 'runas' invoca o UAC oficial do Windows
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                "powershell.exe",
                params,
                None,
                1  # SW_SHOWNORMAL
            )
            # Retorno > 32 indica sucesso na invocação do UAC
            return ret > 32
        except Exception as e:
            click.secho(f"  [ELEVATION-ERR] Falha ao solicitar elevação UAC: {e}", fg="red")
            return False

    @classmethod
    def apply_firewall_rules_with_consent(cls, git_port: int = 9418, udp_port: int = 54545, http_port: int = 8080) -> bool:
        """
        Pede autorização ao usuário e aplica as regras do Firewall do Windows.
        """
        click.secho("\n🛡️ [HONEST ELEVATION] Configuração de Firewall Necessária", fg="cyan", bold=True)
        click.echo("O Windows requer permissão para liberar o tráfego da rede local (LocalSubnet).")
        
        if not click.confirm(click.style("Deseja abrir o prompt UAC do Windows para aplicar as regras com segurança?", fg="yellow"), default=True):
            click.echo("Operação cancelada pelo usuário.")
            return False

        ps_script = (
            f"New-NetFirewallRule -DisplayName 'Doxoade-LAN-Git-TCP' -Direction Inbound -LocalPort {git_port} -Protocol TCP -Action Allow -RemoteAddress LocalSubnet -ErrorAction SilentlyContinue; "
            f"New-NetFirewallRule -DisplayName 'Doxoade-LAN-Git-HTTP' -Direction Inbound -LocalPort {http_port} -Protocol TCP -Action Allow -RemoteAddress LocalSubnet -ErrorAction SilentlyContinue; "
            f"New-NetFirewallRule -DisplayName 'Doxoade-LAN-Git-UDP' -Direction Inbound -LocalPort {udp_port} -Protocol UDP -Action Allow -RemoteAddress LocalSubnet -ErrorAction SilentlyContinue"
        )

        click.echo("Aguardando confirmação no pop-up do Windows UAC...")
        if cls.execute_powershell_elevated(ps_script):
            click.secho("✔ Regras de Firewall solicitadas com sucesso.", fg="green")
            return True
        else:
            click.secho("✖ A elevação de privilégios foi recusada no UAC.", fg="red")
            return False