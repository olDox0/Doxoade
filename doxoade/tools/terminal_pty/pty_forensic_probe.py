# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_forensic_probe.py
"""
🔬 DOXLY PTY FORENSIC PROBE V2 — Sonda de Captura de Crash e I/O Ativo.
Testa permutações de escrita (VK_RETURN), drena ConPTY em regime contínuo
e impede o fechamento abrupto que dispara a janela 0xc0000142.
Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

NTSTATUS_CODES = {
    0x00000000: ("STATUS_SUCCESS", "Processo finalizado normalmente."),
    0xC0000005: ("STATUS_ACCESS_VIOLATION", "Violação de acesso à memória."),
    0xC0000142: ("STATUS_DLL_INIT_FAILED", "ConPTY fechado abruptamente enquanto o cliente ainda executava."),
    0xC000013A: ("STATUS_CONTROL_C_EXIT", "Aplicação finalizada por sinal Ctrl+C."),
}


def get_process_exit_code(pid: int) -> Optional[int]:
    if sys.platform != "win32" or pid <= 0:
        return None
    try:
        handle = ctypes.windll.kernel32.OpenProcess(0x1000 | 0x00100000, False, pid)
        if not handle:
            return None
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return None if exit_code.value == 259 else exit_code.value
    except Exception:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="NomeDaFuncaoOndeEstaOErro", debug=True)
        return None


def drain_pty_output(p, duration_sec: float = 0.5) -> str:
    """Drena todos os bytes disponíveis no ConPTY sem travar."""
    accumulated = ""
    start = time.time()
    while time.time() - start < duration_sec:
        try:
            chunk = p.read()
            if chunk:
                accumulated += chunk
            else:
                time.sleep(0.02)
        except Exception:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context="NomeDaFuncaoOndeEstaOErro", debug=True)
            break
    return accumulated


def run_probe():
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
    print("🔬 DOXLY PTY CRASH TRAP — CAPTURA DE I/O E POST-MORTEM")
    print(f"{'═' * 75}{Style.RESET_ALL}\n")
    
    try:
        import winpty
        print(f"  {Fore.YELLOW}[1] Inicializando PTY 80x24 (pywinpty {getattr(winpty, '__version__', '3.x')})...{Fore.RESET}")
        p = winpty.PTY(80, 24)

        cmd_exe = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        # Passa o appname e cmdline explícito para o ConPTY associar os streams
        p.spawn(cmd_exe, cmdline=f'"{cmd_exe}"')
        pid = getattr(p, "pid", -1)
        print(f"      PID do processo filho: {Fore.GREEN}{pid}{Fore.RESET}")

        # 1. Drena banner do Windows
        time.sleep(0.4)
        initial_banner = drain_pty_output(p, 0.4)
        clean_banner = initial_banner.replace("\x1b", "^[").strip()
        print(f"      Banner recebido: {Fore.LIGHTBLACK_EX}{clean_banner[:70]}...{Fore.RESET}")
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="parte 1 falhou - run_probe", debug=True)
    try:
        # 2. Teste de escrita com \r\n
        print(f"\n  {Fore.YELLOW}[2] Injetando comando de teste ('echo TEST_DOX')...{Fore.RESET}")
        # No Windows ConPTY nativo, o enter é enviado como \r
        bytes_written = p.write("echo TEST_DOX\r")
        print(f"      Bytes escritos: {bytes_written}")
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="parte 2 Teste de escrita Falhou - run_probe", debug=True)

    try:
        # 3. Drena resposta do comando
        time.sleep(0.3)
        cmd_response = drain_pty_output(p, 0.5)
        clean_response = cmd_response.replace("\x1b", "^[").strip()

        if "TEST_DOX" in cmd_response:
            print(f"      {Fore.GREEN}✔ SUCESSO DE I/O: Resposta recebida!{Fore.RESET}")
            print(f"      Conteúdo: {Fore.WHITE}{clean_response}{Fore.RESET}")
        else:
            print(f"      {Fore.YELLOW}⚠ Sem echo no buffer. Tentando com \\r\\n...{Fore.RESET}")
            p.write("echo TEST_DOX_CRLF\r\n")
            crlf_resp = drain_pty_output(p, 0.4)
            if "TEST_DOX_CRLF" in crlf_resp:
                print(f"      {Fore.GREEN}✔ SUCESSO DE I/O com \\r\\n!{Fore.RESET}")
            else:
                print(f"      {Fore.RED}✖ Falha de recepção no pipe stdin.{Fore.RESET}")
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="parte 3 drenagem falhou - run_probe", debug=True)

    try:
        # 4. Encerramento blindado (anti-0xc0000142)
        print(f"\n  {Fore.YELLOW}[3] Executando encerramento controlado...{Fore.RESET}")
        # Envia exit com \r para fechar o cmd.exe antes de destruir o ConPTY
        p.write("exit\r")
        
        # Aguarda o processo terminar no kernel
        deadline = time.time() + 1.5
        killed_gracefully = False
        while time.time() < deadline:
            if get_process_exit_code(pid) is not None:
                killed_gracefully = True
                break
            time.sleep(0.05)

        exit_code = get_process_exit_code(pid)

        if killed_gracefully and exit_code == 0:
            print(f"      {Fore.GREEN}✔ Processo encerrou com EXIT_0 (Sem colapso de DLLs){Fore.RESET}")
        elif exit_code == 0xC0000142:
            print(f"      {Fore.RED}💥 CRASH CAPTURADO: 0xC0000142 (O processo foi abortado antes de concluir exit){Fore.RESET}")
        else:
            print(f"      {Fore.YELLOW}⚠ Código de saída: {exit_code} (Terminando manualmente){Fore.RESET}")
            try:
                # Mata o processo filho no kernel antes de destruir o PTY para evitar o popup do Windows
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            except Exception as e:
                from doxoade.tools.error_info import handle_error
                handle_error(e, context="subprocess - run_probe", debug=True)
                pass
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="parte 4 encerramento falhou - run_probe", debug=True)

    # Drena qualquer resto do buffer antes do GC
    drain_pty_output(p, 0.1)
    del p
    print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Perícia concluída sem travamentos.{Style.RESET_ALL}\n")


if __name__ == "__main__":
    run_probe()
