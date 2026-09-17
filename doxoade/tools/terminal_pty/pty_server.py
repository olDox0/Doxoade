# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_server.py
"""
🖥️ PTY Server — Orquestrador Principal do Terminal Real Doxoade.

Une todos os módulos da Fase 1 em um servidor coeso:
  • Recebe argumentos CLI (--shell, --cols, --rows, --cwd, --debug)
  • Detecta plataforma e seleciona backend (UnixPTY ou WindowsPTY)
  • Gera token de segurança e abre socket TCP local
  • Imprime DOX_PTY_READY no stdout para o Lite XL parsear
  • Autentica o cliente Lua
  • Inicia o PTY com o shell resolvido
  • Entra no loop de I/O bidirecional (socket ↔ PTY)

Uso standalone (debug):
  python -m doxoade.tools.terminal_pty.pty_server --shell cmd --debug

Uso via Lite XL (process.start):
  python -m doxoade.tools.terminal_pty.pty_server --shell cmd --cols 120 --rows 30

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import argparse
import os
import queue
import signal
import socket
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTS INTERNOS
# ──────────────────────────────────────────────────────────────────────────────

from doxoade.tools.terminal_pty import (
    PlatformKind,
    detect_platform,
    is_conpty_available,
)
from doxoade.tools.terminal_pty.security import (
    BIND_HOST,
    PTYSecurityManager,
    create_secure_socket,
    find_available_port,
    format_ready_line,
)
from doxoade.tools.terminal_pty.shell_resolver import (
    ShellResolution,
    resolve_shell,
    get_shell_description,
)
from doxoade.tools.terminal_pty.pty_protocol import (
    MsgType,
    PTYMessage,
    ProtocolError,
    ProtocolStreamReader,
    HEADER_SIZE,
    build_auth_request,
    parse_auth_request,
    make_output_data,
    make_pty_exited,
    make_pong,
    make_error,
    make_auth_ok,
    make_auth_fail,
    parse_input_data,
    parse_resize,
)
from doxoade.tools.terminal_pty.pty_unix import (
    UnixPTYBackend,
    is_platform_supported as is_unix_supported,
)
from doxoade.tools.terminal_pty.pty_windows import (
    WindowsPTYBackend,
    check_windows_pty_readiness,
    is_platform_supported as is_windows_supported,
)


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────────────────────

SERVER_NAME = "DOXOADE-PTY-SERVER"
READ_TIMEOUT_MS = 20  # Timeout de leitura do PTY (ms)
SOCKET_RECV_SIZE = 65536
KEEPALIVE_INTERVAL_SEC = 5.0
SHUTDOWN_GRACE_SEC = 2.0


# ──────────────────────────────────────────────────────────────────────────────
# CLASSE PRINCIPAL DO SERVIDOR
# ──────────────────────────────────────────────────────────────────────────────

class PTYServer:
    """
    Orquestrador do Terminal Real PTY.
    
    Fluxo de vida:
      1. __init__() → configura argumentos
      2. start() → resolve shell, cria backend, abre socket, autentica
      3. run() → loop de I/O bidirecional até shutdown
      4. stop() → encerra PTY, fecha socket, limpa threads
    """

    def __init__(self, args: argparse.Namespace):
        self._args = args
        self._shell_id = args.shell or "auto"
        self._cols = max(1, args.cols)
        self._rows = max(1, args.rows)
        self._cwd = args.cwd or os.getcwd()
        self._debug = args.debug

        # Componentes
        self._security = PTYSecurityManager()
        self._backend = None  # UnixPTYBackend ou WindowsPTYBackend
        self._shell_resolution: Optional[ShellResolution] = None

        # Socket
        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None
        self._port: int = 0

        # Estado
        self._running = False
        self._authenticated = False
        self._shutdown_requested = False

        # Threads
        self._pty_reader_thread: Optional[threading.Thread] = None
        self._socket_reader_thread: Optional[threading.Thread] = None

        # Buffer de leitura do socket
        self._socket_reader = ProtocolStreamReader()

        # Fila de mensagens para enviar ao cliente
        self._send_queue: queue.Queue = queue.Queue()

        # Lock para escrita no socket
        self._socket_write_lock = threading.Lock()

    # ─── SETUP E INICIALIZAÇÃO ─────────────────────────────────────────

    def start(self) -> bool:
        """
        Inicializa o servidor PTY.
        Retorna True se tudo foi configurado com sucesso.
        """
        self._log(f"[{SERVER_NAME}] Iniciando...")
        self._log(f"  Shell solicitado: {self._shell_id}")
        self._log(f"  Dimensões: {self._cols}x{self._rows}")
        self._log(f"  CWD: {self._cwd}")

        # 1. Resolver shell
        try:
            self._shell_resolution = resolve_shell(self._shell_id)
            self._log(f"  Shell resolvido: {get_shell_description(self._shell_resolution)}")
            if self._shell_resolution.warning:
                self._log(f"  ⚠ {self._shell_resolution.warning}")
        except Exception as e:
            self._error(f"Falha ao resolver shell: {e}")
            return False

        # 2. Selecionar e criar backend PTY
        try:
            self._backend = self._create_backend()
            if self._backend is None:
                return False
        except Exception as e:
            self._error(f"Falha ao criar backend PTY: {e}")
            return False

        # 3. Abrir socket TCP local
        try:
            self._port = find_available_port()
            self._server_socket = create_secure_socket(self._port)
            self._log(f"  Socket aberto em {BIND_HOST}:{self._port}")
        except Exception as e:
            self._error(f"Falha ao abrir socket: {e}")
            return False

        # 4. Gerar token de segurança
        token = self._security.generate_token()
        self._log(f"  Token gerado: {token[:16]}...")

        # 5. Imprimir linha de handshake no stdout (para o Lite XL parsear)
        ready_line = format_ready_line(
            port=self._port,
            token=token,
            shell=self._shell_resolution.shell_id,
            pid=os.getpid(),
            conpty_available=is_conpty_available(),
        )
        # Flush imediato é crítico — o Lite XL está lendo stdout
        print(ready_line, flush=True)
        self._log(f"  Handshake emitido: {ready_line[:60]}...")

        return True

    def _create_backend(self):
        """Cria o backend PTY apropriado para a plataforma."""
        platform_kind = detect_platform()

        if platform_kind == PlatformKind.WINDOWS:
            ready, message = check_windows_pty_readiness()
            if not ready:
                self._error(message)
                return None
            self._log("  Backend: Windows ConPTY (pywinpty)")
            return WindowsPTYBackend()

        elif platform_kind in (PlatformKind.LINUX, PlatformKind.MACOS):
            if not is_unix_supported():
                self._error("Backend Unix PTY não suportado nesta plataforma.")
                return None
            self._log("  Backend: Unix PTY (stdlib)")
            return UnixPTYBackend()

        else:
            self._error(f"Plataforma não suportada: {platform_kind}")
            return None

    # ─── AUTENTICAÇÃO ──────────────────────────────────────────────────

    def wait_for_client(self, timeout_sec: float = 30.0) -> bool:
        """
        Aguarda conexão do cliente Lua e realiza handshake de autenticação.
        Retorna True se autenticado com sucesso.
        """
        self._log(f"  Aguardando conexão do cliente (timeout: {timeout_sec}s)...")
        self._server_socket.settimeout(timeout_sec)

        try:
            client_sock, addr = self._server_socket.accept()
            self._client_socket = client_sock
            self._log(f"  Conexão recebida de {addr}")
        except socket.timeout:
            self._error("Timeout: nenhum cliente conectou.")
            return False
        except OSError as e:
            self._error(f"Erro ao aceitar conexão: {e}")
            return False

        # Fase de autenticação (protocolo texto simples antes do binário)
        client_sock.settimeout(10.0)
        try:
            auth_data = client_sock.recv(4096)
            if not auth_data:
                self._error("Cliente desconectou antes de autenticar.")
                return False

            received_token = parse_auth_request(auth_data)
            if received_token is None:
                self._error("Mensagem de autenticação malformada.")
                client_sock.sendall(b"AUTH_FAIL\n")
                return False

            if self._security.validate_token(received_token):
                self._authenticated = True
                client_sock.sendall(b"AUTH_OK\n")
                self._log("  ✓ Autenticação bem-sucedida.")
                client_sock.settimeout(None)  # Modo não-bloqueante via threads
                return True
            else:
                self._error("Token inválido ou expirado.")
                client_sock.sendall(b"AUTH_FAIL\n")
                return False

        except socket.timeout:
            self._error("Timeout na autenticação.")
            return False
        except Exception as e:
            self._error(f"Erro na autenticação: {e}")
            return False

    # ─── SPAWN DO PTY ──────────────────────────────────────────────────

    def spawn_pty(self) -> bool:
        """Spawnar o shell dentro do PTY."""
        try:
            pid = self._backend.spawn(
                shell=self._shell_resolution,
                cols=self._cols,
                rows=self._rows,
                cwd=self._cwd,
            )
            self._log(f"  PTY spawnado com PID: {pid}")

            # Registrar callback de exit
            self._backend.set_on_exit_callback(self._on_pty_exit)

            return True
        except Exception as e:
            self._error(f"Falha ao spawnar PTY: {e}")
            traceback.print_exc()
            return False

    # ─── LOOP PRINCIPAL DE I/O ────────────────────────────────────────

    def run(self) -> None:
        """
        Loop principal de I/O bidirecional.
        Roda até shutdown ser solicitado ou o PTY terminar.
        """
        self._running = True
        self._log(f"[{SERVER_NAME}] Loop de I/O iniciado.")

        # Iniciar thread de leitura do PTY → socket
        self._pty_reader_thread = threading.Thread(
            target=self._pty_reader_loop,
            daemon=True,
            name="PTYReaderLoop",
        )
        self._pty_reader_thread.start()

        # Iniciar thread de leitura do socket → PTY
        self._socket_reader_thread = threading.Thread(
            target=self._socket_reader_loop,
            daemon=True,
            name="SocketReaderLoop",
        )
        self._socket_reader_thread.start()

        # Loop principal: monitora estado e envia mensagens da fila
        try:
            while self._running and not self._shutdown_requested:
                # Verificar se o PTY ainda está vivo
                if not self._backend.is_alive:
                    exit_code = self._backend.get_exit_code()
                    self._log(f"  PTY terminou com código: {exit_code}")
                    self._send_message(make_pty_exited(exit_code or 0))
                    # Dar um tempo para o cliente receber a mensagem
                    time.sleep(0.2)
                    break

                # Processar fila de envio
                self._flush_send_queue()

                # Sleep curto para não consumir CPU
                time.sleep(0.01)

        except KeyboardInterrupt:
            self._log("  KeyboardInterrupt recebido.")
        except Exception as e:
            self._error(f"Erro no loop principal: {e}")
            traceback.print_exc()
        finally:
            self._running = False

    def _pty_reader_loop(self) -> None:
        """Thread: lê output do PTY e enfileira para envio ao socket."""
        while self._running and not self._shutdown_requested:
            try:
                if not self._backend.is_alive:
                    break

                data = self._backend.read(timeout_ms=READ_TIMEOUT_MS)
                if data:
                    self._send_queue.put(make_output_data(data))
                elif data == b"":
                    # Possível EOF
                    time.sleep(0.05)

            except Exception as e:
                if self._running:
                    self._error(f"Erro no PTY reader: {e}")
                break

        self._log("  PTY reader loop finalizado.")

    def _socket_reader_loop(self) -> None:
        """Thread: lê mensagens do socket cliente e despacha para o PTY."""
        while self._running and not self._shutdown_requested:
            try:
                if self._client_socket is None:
                    break

                # Ler dados do socket
                data = self._client_socket.recv(SOCKET_RECV_SIZE)
                if not data:
                    # Cliente desconectou
                    self._log("  Cliente desconectou.")
                    self._shutdown_requested = True
                    break

                # Alimentar o parser de protocolo
                self._socket_reader.feed(data)

                # Processar todas as mensagens completas
                messages = self._socket_reader.read_all_messages()
                for msg in messages:
                    self._handle_client_message(msg)

            except socket.timeout:
                continue
            except ConnectionResetError:
                self._log("  Conexão resetada pelo cliente.")
                self._shutdown_requested = True
                break
            except OSError as e:
                if self._running:
                    self._error(f"Erro no socket reader: {e}")
                break
            except Exception as e:
                if self._running:
                    self._error(f"Erro inesperado no socket reader: {e}")
                break

        self._log("  Socket reader loop finalizado.")

    def _handle_client_message(self, msg: PTYMessage) -> None:
        """Despacha uma mensagem recebida do cliente Lua."""
        try:
            if msg.msg_type == MsgType.INPUT_DATA:
                # Teclas digitadas → enviar para o PTY
                input_bytes = parse_input_data(msg)
                if input_bytes and self._backend.is_alive:
                    self._backend.write(input_bytes)

            elif msg.msg_type == MsgType.RESIZE:
                # Redimensionar o terminal
                cols, rows = parse_resize(msg)
                self._backend.resize(cols, rows)
                self._log(f"  Resize: {cols}x{rows}")

            elif msg.msg_type == MsgType.INTERRUPT:
                # Ctrl+C / SIGINT
                self._backend.send_interrupt()
                self._log("  Interrupt enviado (Ctrl+C)")

            elif msg.msg_type == MsgType.PING:
                # Keepalive → responder com PONG
                self._send_queue.put(make_pong())

            elif msg.msg_type == MsgType.SHUTDOWN:
                # Cliente solicitou encerramento
                self._log("  Shutdown solicitado pelo cliente.")
                self._shutdown_requested = True

            else:
                self._log(f"  Mensagem desconhecida: 0x{msg.msg_type:02X}")

        except ProtocolError as e:
            self._error(f"Erro de protocolo: {e}")
            self._send_queue.put(make_error(str(e)))
        except Exception as e:
            self._error(f"Erro ao processar mensagem: {e}")

    def _flush_send_queue(self) -> None:
        """Envia todas as mensagens pendentes na fila para o socket."""
        while not self._send_queue.empty():
            try:
                msg = self._send_queue.get_nowait()
                self._send_message(msg)
            except queue.Empty:
                break
            except Exception as e:
                self._error(f"Erro ao enviar mensagem: {e}")
                break

    def _send_message(self, msg: PTYMessage) -> None:
        """Envia uma mensagem serializada para o socket cliente."""
        if self._client_socket is None:
            return

        try:
            with self._socket_write_lock:
                self._client_socket.sendall(msg.to_bytes())
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._shutdown_requested = True

    # ─── CALLBACKS E EVENTOS ───────────────────────────────────────────

    def _on_pty_exit(self, exit_code: int) -> None:
        """Callback invocado quando o processo do PTY termina."""
        self._log(f"  Callback: PTY exit com código {exit_code}")
        self._shutdown_requested = True

    # ─── SHUTDOWN E LIMPEZA ────────────────────────────────────────────

    def stop(self) -> None:
        """Encerra o servidor graciosamente."""
        self._log(f"[{SERVER_NAME}] Encerrando...")
        self._running = False
        self._shutdown_requested = True

        # Fechar PTY
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:
                pass
            self._backend = None

        # Fechar socket cliente
        if self._client_socket is not None:
            try:
                self._client_socket.close()
            except Exception:
                pass
            self._client_socket = None

        # Fechar socket servidor
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        # Aguardar threads finalizarem
        if self._pty_reader_thread is not None:
            self._pty_reader_thread.join(timeout=1.0)
        if self._socket_reader_thread is not None:
            self._socket_reader_thread.join(timeout=1.0)

        # Invalidar token
        self._security.invalidate_token()

        self._log(f"[{SERVER_NAME}] Encerrado.")

    # ─── LOGGING ───────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        """Log para stderr (stdout é reservado para handshake com Lite XL)."""
        if self._debug:
            print(f"[PTY-DEBUG] {message}", file=sys.stderr, flush=True)

    def _error(self, message: str) -> None:
        """Log de erro para stderr."""
        print(f"[PTY-ERROR] {message}", file=sys.stderr, flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# ARGUMENT PARSER
# ──────────────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos CLI."""
    parser = argparse.ArgumentParser(
        prog="doxoade-pty-server",
        description="🖥️ Doxoade Terminal Real — Servidor PTY (ConPTY/PTY)",
    )
    parser.add_argument(
        "--shell", "-s",
        default="auto",
        help=(
            "Shell a usar. "
            "Windows: 'cmd', 'powershell', 'pwsh', 'auto' (default: cmd). "
            "Linux: 'auto', '/bin/bash', '/bin/sh', etc."
        ),
    )
    parser.add_argument(
        "--cols", "-c",
        type=int,
        default=120,
        help="Largura inicial do terminal em colunas (default: 120).",
    )
    parser.add_argument(
        "--rows", "-r",
        type=int,
        default=30,
        help="Altura inicial do terminal em linhas (default: 30).",
    )
    parser.add_argument(
        "--cwd", "-w",
        default=None,
        help="Diretório de trabalho inicial (default: cwd atual).",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Ativa logging de debug no stderr.",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Exibe versão e informações de diagnóstico.",
    )
    return parser


def print_diagnostics() -> None:
    """Imprime informações de diagnóstico do ambiente."""
    from doxoade.tools.terminal_pty import __version__
    from doxoade.tools.terminal_pty.pty_windows import get_backend_info

    print(f"Doxoade PTY Server v{__version__}")
    print(f"  Platform: {detect_platform().value}")
    print(f"  Python: {sys.version}")
    print(f"  ConPTY available: {is_conpty_available()}")

    if detect_platform() == PlatformKind.WINDOWS:
        info = get_backend_info()
        print(f"  Windows build: {info['windows_build']}")
        print(f"  pywinpty installed: {info['pywinpty_installed']}")
        print(f"  pywinpty version: {info['pywinpty_version']}")
    else:
        print(f"  Unix PTY supported: {is_unix_supported()}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    """Ponto de entrada principal do servidor PTY."""
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.version:
        print_diagnostics()
        return 0

    server = PTYServer(args)

    # Handler para SIGTERM/SIGINT (encerramento gracioso)
    def _signal_handler(signum, frame):
        server.stop()
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
    except (OSError, ValueError):
        pass  # Pode falhar em threads não-main

    try:
        # Fase 1: Setup
        if not server.start():
            return 1

        # Fase 2: Aguardar autenticação do cliente
        if not server.wait_for_client(timeout_sec=30.0):
            server.stop()
            return 1

        # Fase 3: Spawnar o PTY
        if not server.spawn_pty():
            server.stop()
            return 1

        # Fase 4: Loop de I/O
        server.run()

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[PTY-FATAL] {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        server.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
