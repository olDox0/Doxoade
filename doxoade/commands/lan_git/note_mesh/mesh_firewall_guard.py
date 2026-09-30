# -*- coding: utf-8 -*-
# doxoade/commands/lan_git/note_mesh/mesh_firewall_guard.py
"""
🛡️ MESH FIREWALL GUARD — Permissão Temporária com Elevação Honesta.
Solicita UAC, cria regra de firewall com TTL de 24h, e loga cada etapa.
Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations
import os
import json
import time
import socket
import ctypes
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

MESH_TCP_PORT = 54548
MESH_UDP_PORT = 54547
RULE_NAME_TCP = "DoxNote-Mesh-TCP-In"
RULE_NAME_UDP = "DoxNote-Mesh-UDP-In"
RULE_TTL_HOURS = 24

class MeshFirewallGuard:
    """Guardião de firewall com elevação UAC e regras temporárias."""

    def __init__(self):
        self.home = Path.home()
        self.doxoade_dir = self.home / ".doxoade"
        self.debug_dir = self.doxoade_dir / "mesh_debug"
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.debug_dir / "firewall_guard.log"

    def _log(self, level: str, msg: str, **extra):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{ts}] [{level}] {msg}"
        if extra:
            line += f" | {json.dumps(extra, ensure_ascii=False)}"
        print(line)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def test_outbound_connect(self, target_ip: str, port: int = MESH_TCP_PORT, timeout: float = 2.0) -> Dict[str, Any]:
        """Testa se conseguimos conectar na porta TCP do peer."""
        result = {"target": f"{target_ip}:{port}", "success": False, "error": None, "latency_ms": None}
        t0 = time.perf_counter()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((target_ip, port))
            elapsed = (time.perf_counter() - t0) * 1000
            s.close()
            result["success"] = True
            result["latency_ms"] = round(elapsed, 2)
        except TimeoutError:
            result["error"] = "TIMEOUT (Porta bloqueada ou host inacessível)"
        except ConnectionRefusedError:
            result["error"] = "CONNECTION_REFUSED (Porta fechada no destino)"
        except OSError as e:
            result["error"] = f"OS_ERROR: {e}"
        return result

    @staticmethod
    def is_admin() -> bool:
        if os.name != "nt": return False
        try: return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception: return False

    def request_firewall_permission(self, ttl_hours: int = RULE_TTL_HOURS) -> Dict[str, Any]:
        """Solicita elevação UAC e cria regras de firewall temporárias."""
        result = {"timestamp": datetime.now().isoformat(), "rules_created": [], "errors": [], "ttl_hours": ttl_hours}
        if os.name != "nt":
            result["errors"].append("Apenas Windows suportado")
            return result

        expire_at = (datetime.now() + timedelta(hours=ttl_hours)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Script PowerShell para criar regras e agendar tarefa para remoção automática
        ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$expireAt = '{expire_at}'
Remove-NetFirewallRule -DisplayName '{RULE_NAME_TCP}' -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName '{RULE_NAME_UDP}' -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName '{RULE_NAME_TCP}' -Description 'DoxNote Mesh TCP (expira ' + $expireAt + ')' -Direction Inbound -LocalPort {MESH_TCP_PORT} -Protocol TCP -Action Allow -RemoteAddress LocalSubnet -Profile Any | Out-Null
New-NetFirewallRule -DisplayName '{RULE_NAME_UDP}' -Description 'DoxNote Mesh UDP (expira ' + $expireAt + ')' -Direction Inbound -LocalPort {MESH_UDP_PORT} -Protocol UDP -Action Allow -RemoteAddress LocalSubnet -Profile Any | Out-Null
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -Command \\"Remove-NetFirewallRule -DisplayName '{RULE_NAME_TCP}' -ErrorAction SilentlyContinue; Remove-NetFirewallRule -DisplayName '{RULE_NAME_UDP}' -ErrorAction SilentlyContinue\\""
$trigger = New-ScheduledTaskTrigger -Once -At $expireAt
Register-ScheduledTask -TaskName 'DoxNoteMeshFirewallCleanup' -Action $action -Trigger $trigger -Force -ErrorAction SilentlyContinue | Out-Null
Write-Output 'RULES_CREATED_OK'
"""
        if self.is_admin():
            try:
                res = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], capture_output=True, text=True, timeout=30)
                if "RULES_CREATED_OK" in res.stdout:
                    result["rules_created"] = [RULE_NAME_TCP, RULE_NAME_UDP]
                    result["expire_at"] = expire_at
                else:
                    result["errors"].append(res.stderr[:200])
            except Exception as e:
                result["errors"].append(str(e))
        else:
            # Salvar script em arquivo temporário para evitar problemas de escape no ShellExecuteW
            temp_ps = self.debug_dir / "elevate_fw.ps1"
            temp_ps.write_text(ps_script, encoding="utf-8")
            args = f'-NoProfile -ExecutionPolicy Bypass -File "{temp_ps.resolve()}"'
            
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 1)
                if ret > 32:
                    result["rules_created"] = [RULE_NAME_TCP, RULE_NAME_UDP]
                    result["expire_at"] = expire_at
                    result["uac_result"] = "user_accepted"
                else:
                    result["uac_result"] = "user_denied"
                    result["errors"].append("UAC recusado pelo usuário")
            except Exception as e:
                result["errors"].append(str(e))
        
        self._log("INFO", "Solicitação de Firewall", **result)
        return result

    def run_full_diagnostic(self, peer_ip: str) -> Dict[str, Any]:
        """Executa bateria completa de diagnóstico."""
        report = {"timestamp": datetime.now().isoformat(), "peer_ip": peer_ip, "checks": {}}
        report["checks"]["outbound"] = self.test_outbound_connect(peer_ip)
        report["checks"]["is_admin"] = self.is_admin()
        
        if report["checks"]["outbound"]["success"]:
            report["verdict"] = "CONNECTIVITY_OK"
        else:
            report["verdict"] = "OUTBOUND_BLOCKED"
        return report
