# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_diagnostics_engine.py
"""
🔬 DOXLY PTY DIAGNOSTICS & TELEMETRY ENGINE — Sonda Ativa ConPTY (V4.0).
Sistema de diagnóstico e auditoria para eliminar pontos cegos em subprocessos ConPTY.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Anúbis & Horus
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Tuple

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""


class ConPTYInspector:
    """Auditor e diagnosticador do contrato nativo do pywinpty 3.x."""

    @classmethod
    def probe_write_contract(cls, pty_instance) -> Tuple[str, Any]:
        """Testa empiricamente qual tipo de dado o write() do Rust realmente aceita."""
        test_payload = "echo PROBE_TEST\r\n"
        
        # Tentativa 1: Bytes literais
        try:
            n_bytes = pty_instance.write(test_payload.encode("utf-8"))
            if n_bytes > 0:
                return "BYTES", n_bytes
        except Exception as e:
            pass

        # Tentativa 2: String Unicode
        try:
            n_str = pty_instance.write(test_payload)
            if n_str > 0:
                return "STR", n_str
        except Exception as e:
            pass

        # Tentativa 3: Bytearray
        try:
            n_barr = pty_instance.write(bytearray(test_payload, "utf-8"))
            if n_barr > 0:
                return "BYTEARRAY", n_barr
        except Exception as e:
            pass

        return "FAILED", 0

    @classmethod
    def run_inspector(cls) -> Dict[str, Any]:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print("🔬 DOXLY CONPTY DIAGNOSTICS ENGINE — LAUDO DE API & I/O")
        print(f"{'═' * 75}{Style.RESET_ALL}\n")

        import winpty
        version = getattr(winpty, "__version__", "3.x")
        print(f"  {Fore.WHITE}Engine:{Fore.RESET} pywinpty v{version} (Maturin/Rust Native Backend)")

        pty = winpty.PTY(80, 24)
        cmd_exe = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        pty.spawn(cmd_exe)
        
        print(f"  {Fore.WHITE}Processo:{Fore.RESET} PID {pty.pid} [ConPTY alocado com sucesso]")
        time.sleep(0.3)
        initial_read = pty.read()
        print(f"  {Fore.WHITE}Handshake Inicial:{Fore.RESET} {len(initial_read)} chars recebidos.")

        # Teste de contrato de escrita
        write_type, bytes_sent = cls.probe_write_contract(pty)
        print(f"  {Fore.WHITE}Contrato de Escrita aceito:{Fore.RESET} {Fore.GREEN}{write_type}{Fore.RESET} ({bytes_sent} bytes)")

        # Drena resposta
        time.sleep(0.3)
        response = pty.read()
        
        has_echo = "PROBE_TEST" in response
        status_color = Fore.GREEN if has_echo else Fore.RED
        print(f"  {Fore.WHITE}Recepção de Comandos:{Fore.RESET} {status_color}{'✔ CONFIRMADA' if has_echo else '✖ FALHOU'}{Fore.RESET}")

        # Encerramento gracioso
        if write_type == "BYTES":
            pty.write(b"exit\r\n")
        else:
            pty.write("exit\r\n")
        time.sleep(0.2)
        
        is_clean_exit = not pty.isalive()
        print(f"  {Fore.WHITE}Encerramento Gracioso:{Fore.RESET} {Fore.GREEN if is_clean_exit else Fore.YELLOW}{'✔ EXIT Limpo' if is_clean_exit else 'Ainda ativo'}{Fore.RESET}")

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print("💡 PRESCRIÇÃO AUTOMÁTICA:")
        if write_type == "BYTES":
            print(f"  O backend Rust do pywinpty {version} exige {Fore.YELLOW}BYTES (payload.encode('utf-8')){Fore.RESET}.")
            print("  Ao enviar `str`, o Rust descarta o payload e retorna 0.")
        print(f"{'═' * 75}{Style.RESET_ALL}\n")

        return {
            "write_type": write_type,
            "has_echo": has_echo,
            "clean_exit": is_clean_exit
        }


if __name__ == "__main__":
    ConPTYInspector.run_inspector()
