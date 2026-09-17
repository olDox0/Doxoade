# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_stdio_server.py
"""
🔌 DOXOADE PTY STDIO SERVER — Transporte STDIO para o Terminal Real.

Este módulo é um shim de transporte para integração imediata com o Lite XL.

Ele:
  • Spawna o backend PTY real (ConPTY/Unix PTY)
  • Usa stdin/stdout do processo como transporte
  • Mantém handshake de segurança com token
  • Usa o mesmo protocolo binário do pty_server original

Diferença em relação ao pty_server.py:
  • Não abre socket TCP local.
  • A comunicação ocorre via pipes do processo aberto pelo Lite XL.

Uso:
  python -m doxoade.tools.terminal_pty.pty_stdio_server --shell cmd

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from typing import Optional

from doxoade.tools.terminal_pty import (
    PlatformKind,
    detect_platform,
    is_conpty_available,
)
from doxoade.tools.terminal_pty.security import (
    PTYSecurityManager,
    format_ready_line,
)
from doxoade.tools.terminal_pty.shell_resolver import (
    resolve_shell,
    get_shell_description,
)
from doxoade.tools.terminal_pty.pty_protocol import (
    MsgType,
    ProtocolStreamReader,
    parse_auth_request,
    parse_input_data,
    parse_resize,
    make_output_data,
    make_pty_exited,
    make_pong,
    make_auth_ok,
    make_auth_fail,
)
from doxoade.tools.terminal_pty.pty_unix import (
    UnixPTYBackend,
    is_platform_supported as is_unix_supported,
)
from doxoade.tools.terminal_pty.pty_windows import (
    WindowsPTYBackend,
    check_windows_pty_readiness,
)


READ_TIMEOUT_MS = 20
WindowsPTYBackend = None
check_windows_pty_readiness = None

# Backend Unix (só importa em plataformas Unix)
UnixPTYBackend = None
is_unix_supported = None

_platform = detect_platform()

if _platform == PlatformKind.WINDOWS:
    from doxoade.tools.terminal_pty.pty_windows import (
        WindowsPTYBackend,
        check_windows_pty_readiness,
    )
else:
    from doxoade.tools.terminal_pty.pty_unix import (
        UnixPTYBackend,
        is_platform_supported as is_unix_supported,
    )

def log_debug(message: str, debug: bool) -> None:
    if debug:
        print(f"[PTY-STDIO] {message}", file=sys.stderr, flush=True)


def create_backend(debug: bool):
    """Cria o backend PTY correto para a plataforma atual."""
    platform_kind = detect_platform()

    if platform_kind == PlatformKind.WINDOWS:
        if WindowsPTYBackend is None:
            print("[PTY-STDIO] Backend Windows não carregado.", file=sys.stderr, flush=True)
            return None
        ready, message = check_windows_pty_readiness()
        if not ready:
            print(f"[PTY-STDIO] {message}", file=sys.stderr, flush=True)
            return None
        log_debug("Backend: Windows ConPTY (pywinpty)", debug)
        return WindowsPTYBackend()

    elif platform_kind in (PlatformKind.LINUX, PlatformKind.MACOS):
        if UnixPTYBackend is None:
            print("[PTY-STDIO] Backend Unix não carregado.", file=sys.stderr, flush=True)
            return None
        if not is_unix_supported():
            print("[PTY-STDIO] Unix PTY não suportado.", file=sys.stderr, flush=True)
            return None
        log_debug("Backend: Unix PTY (stdlib)", debug)
        return UnixPTYBackend()

    print(f"[PTY-STDIO] Plataforma não suportada: {platform_kind}", file=sys.stderr, flush=True)
    return None

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doxoade-pty-stdio-server",
        description="Doxoade Terminal Real — STDIO transport for Lite XL",
    )
    parser.add_argument("--shell", "-s", default="auto")
    parser.add_argument("--cols", "-c", type=int, default=120)
    parser.add_argument("--rows", "-r", type=int, default=30)
    parser.add_argument("--cwd", "-w", default=None)
    parser.add_argument("--debug", "-d", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    debug = args.debug

    # 1. Resolver shell
    shell = resolve_shell(args.shell)
    log_debug(f"Shell resolvido: {get_shell_description(shell)}", debug)

    # 2. Criar backend
    backend = create_backend(debug)
    if backend is None:
        return 1

    # 3. Segurança / handshake
    security = PTYSecurityManager()
    token = security.generate_token()

    ready_line = format_ready_line(
        port=0,
        token=token,
        shell=shell.shell_id,
        pid=os.getpid(),
        conpty_available=is_conpty_available(),
    )

    # O Lite XL lê esta linha no stdout do processo.
    print(ready_line, flush=True)
    log_debug(f"Handshake emitido: {ready_line[:60]}...", debug)

    # 4. Aguardar AUTH via stdin
    auth_line = sys.stdin.buffer.readline()
    received_token = parse_auth_request(auth_line)

    if received_token is None or not security.validate_token(received_token):
        sys.stdout.buffer.write(make_auth_fail().to_bytes())
        sys.stdout.buffer.flush()
        log_debug("AUTH falhou.", debug)
        return 1

    sys.stdout.buffer.write(make_auth_ok().to_bytes())
    sys.stdout.buffer.flush()
    log_debug("AUTH_OK enviado.", debug)

    # 5. Spawn do PTY
    try:
        pid = backend.spawn(
            shell=shell,
            cols=max(1, args.cols),
            rows=max(1, args.rows),
            cwd=args.cwd or os.getcwd(),
        )
        log_debug(f"PTY spawnado PID={pid}", debug)
    except Exception as e:
        print(f"[PTY-STDIO] Falha ao spawnar PTY: {e}", file=sys.stderr, flush=True)
        return 1

    state = {"running": True}
    write_lock = threading.Lock()

    def send_message(msg) -> None:
        try:
            with write_lock:
                sys.stdout.buffer.write(msg.to_bytes())
                sys.stdout.buffer.flush()
        except Exception as e:
            log_debug(f"Erro ao enviar mensagem: {e}", debug)
            state["running"] = False

    def on_pty_exit(exit_code: int) -> None:
        log_debug(f"PTY exit callback: {exit_code}", debug)
        state["running"] = False

    backend.set_on_exit_callback(on_pty_exit)

    # 6. Thread: PTY -> stdout
    def pty_reader_loop():
        while state["running"] and backend.is_alive:
            try:
                data = backend.read(timeout_ms=READ_TIMEOUT_MS)
                if data:
                    send_message(make_output_data(data))
                elif data == b"":
                    time.sleep(0.01)
            except Exception as e:
                log_debug(f"PTY reader erro: {e}", debug)
                break

        exit_code = backend.get_exit_code()
        if exit_code is None:
            exit_code = 0
        send_message(make_pty_exited(exit_code))
        state["running"] = False

    # 7. Thread: stdin -> PTY
    def stdin_reader_loop():
        reader = ProtocolStreamReader()

        while state["running"]:
            try:
                chunk = sys.stdin.buffer.read(65536)
                if not chunk:
                    log_debug("stdin EOF.", debug)
                    state["running"] = False
                    break

                reader.feed(chunk)
                messages = reader.read_all_messages()

                for msg in messages:
                    if msg.msg_type == MsgType.INPUT_DATA:
                        backend.write(parse_input_data(msg))

                    elif msg.msg_type == MsgType.RESIZE:
                        cols, rows = parse_resize(msg)
                        backend.resize(cols, rows)
                        log_debug(f"Resize: {cols}x{rows}", debug)

                    elif msg.msg_type == MsgType.INTERRUPT:
                        backend.send_interrupt()
                        log_debug("Interrupt enviado.", debug)

                    elif msg.msg_type == MsgType.PING:
                        send_message(make_pong())

                    elif msg.msg_type == MsgType.SHUTDOWN:
                        log_debug("Shutdown recebido.", debug)
                        state["running"] = False
                        backend.close()
                        return

            except Exception as e:
                log_debug(f"stdin reader erro: {e}", debug)
                state["running"] = False
                break

    pty_thread = threading.Thread(
        target=pty_reader_loop,
        daemon=True,
        name="PTYStdioReader",
    )
    stdin_thread = threading.Thread(
        target=stdin_reader_loop,
        daemon=True,
        name="PTYStdioInput",
    )

    pty_thread.start()
    stdin_thread.start()

    # 8. Loop principal
    try:
        while state["running"] and backend.is_alive:
            time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        state["running"] = False
        backend.close()
        pty_thread.join(timeout=1.0)
        stdin_thread.join(timeout=1.0)

    log_debug("Encerrado.", debug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
