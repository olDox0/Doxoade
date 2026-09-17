# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_unix.py
"""
🐧 PTY Backend Unix — Linux / Alpine / macOS (stdlib only).

Utiliza os módulos nativos do Python:
  - pty.openpty() para criar o pseudo-terminal
  - os.fork() + os.execvpe() para spawnar o shell
  - fcntl para I/O não-bloqueante
  - termios para controle de atributos do terminal
  - signal para SIGINT forwarding

Zero dependências externas. Funciona em musl (Alpine) e glibc.

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import errno
import os
import signal
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from doxoade.tools.terminal_pty.shell_resolver import ShellResolution

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTS CONDICIONAIS — Unix apenas
# ──────────────────────────────────────────────────────────────────────────────

UNIX_MODULES_AVAILABLE = False

try:
    import fcntl
    import pty
    import select
    import termios
    UNIX_MODULES_AVAILABLE = True
except ImportError:
    # Windows ou plataforma sem suporte a PTY Unix
    fcntl = None
    pty = None
    select = None
    termios = None
    
@dataclass
class PTYState:
    """Estado interno do PTY Unix."""
    master_fd: int = -1
    slave_fd: int = -1
    child_pid: int = -1
    is_alive: bool = False
    exit_code: Optional[int] = None
    cols: int = 80
    rows: int = 24


class UnixPTYBackend:
    """
    Backend PTY para sistemas Unix usando stdlib.
    
    Uso:
        backend = UnixPTYBackend()
        backend.spawn(shell_resolution, cols=120, rows=30)
        
        while backend.is_alive():
            output = backend.read(timeout_ms=50)
            if output:
                process_output(output)
            
            # Enviar input do usuário
            backend.write(user_input_bytes)
        
        exit_code = backend.get_exit_code()
        backend.close()
    """

    def __init__(self):
        self._state = PTYState()
        self._on_exit_callback: Optional[Callable[[int], None]] = None
        self._read_buffer: bytes = b""

    @property
    def is_alive(self) -> bool:
        """Verifica se o processo filho ainda está rodando."""
        return self._state.is_alive

    @property
    def child_pid(self) -> int:
        """Retorna o PID do processo filho."""
        return self._state.child_pid

    def spawn(
        self,
        shell: ShellResolution,
        cols: int = 80,
        rows: int = 24,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> int:
        """
        Spawnar o shell dentro do PTY.
        
        Args:
            shell: ShellResolution com executável e args.
            cols: Largura inicial do terminal.
            rows: Altura inicial do terminal.
            cwd: Diretório de trabalho (default: cwd atual).
            env: Variáveis de ambiente adicionais.
            
        Returns:
            PID do processo filho.
            
        Raises:
            RuntimeError: Se o fork/spawn falhar.
        """
        if self._state.is_alive:
            raise RuntimeError("PTY já está ativo. Feche antes de respawnar.")

        self._state.cols = max(1, cols)
        self._state.rows = max(1, rows)

        try:
            # Criar o par master/slave do PTY
            master_fd, slave_fd = pty.openpty()
        except OSError as e:
            raise RuntimeError(f"Falha ao abrir PTY: {e}")

        self._state.master_fd = master_fd
        self._state.slave_fd = slave_fd

        # Configurar tamanho inicial do terminal
        self._set_winsize(master_fd, self._state.cols, self._state.rows)

        # Configurar master como não-bloqueante
        self._set_nonblocking(master_fd)

        # Preparar o ambiente
        child_env = os.environ.copy()
        child_env["TERM"] = "xterm-256color"
        child_env["COLORTERM"] = "truecolor"
        if env:
            child_env.update(env)

        # Fork
        try:
            pid = os.fork()
        except OSError as e:
            os.close(master_fd)
            os.close(slave_fd)
            raise RuntimeError(f"Falha no fork: {e}")

        if pid == 0:
            # ─── PROCESSO FILHO ───────────────────────────────────────
            # Criar nova sessão
            os.setsid()

            # O slave se torna o controlling terminal
            try:
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            except (OSError, AttributeError):
                pass  # Alguns sistemas não suportam TIOCSCTTY

            # Redirecionar stdin/stdout/stderr para o slave
            os.dup2(slave_fd, 0)  # stdin
            os.dup2(slave_fd, 1)  # stdout
            os.dup2(slave_fd, 2)  # stderr

            # Fechar os FDs originais
            if slave_fd > 2:
                os.close(slave_fd)
            os.close(master_fd)

            # Mudar diretório se especificado
            if cwd and Path(cwd).is_dir():
                os.chdir(cwd)

            # Executar o shell
            cmd = [shell.executable] + shell.args
            try:
                os.execvpe(cmd[0], cmd, child_env)
            except OSError:
                # Fallback: tentar sem args
                os.execvpe(shell.executable, [shell.executable], child_env)

            # Se chegou aqui, exec falhou
            os._exit(127)

        else:
            # ─── PROCESSO PAI ─────────────────────────────────────────
            # Fechar o slave no pai (só o filho usa)
            os.close(slave_fd)
            self._state.slave_fd = -1
            self._state.child_pid = pid
            self._state.is_alive = True

            # Instalar handler para detectar saída do filho
            self._install_sigchld_handler()

            return pid

    def read(self, timeout_ms: int = 50, max_bytes: int = 8192) -> bytes:
        """
        Lê dados do PTY (output do shell) de forma não-bloqueante.
        
        Args:
            timeout_ms: Timeout em milissegundos (0 = imediato).
            max_bytes: Máximo de bytes para ler.
            
        Returns:
            Bytes lidos (pode conter sequências ANSI).
            Bytes vazios se não houver dados disponíveis.
        """
        if not self._state.is_alive or self._state.master_fd < 0:
            return b""

        # Usar select para verificar se há dados disponíveis
        timeout_sec = timeout_ms / 1000.0
        try:
            readable, _, _ = select.select(
                [self._state.master_fd], [], [], timeout_sec
            )
        except (select.error, ValueError, OSError):
            return b""

        if not readable:
            return b""

        try:
            data = os.read(self._state.master_fd, max_bytes)
            if not data:
                # EOF — o processo filho provavelmente terminou
                self._check_child_status()
                return b""
            return data
        except OSError as e:
            if e.errno == errno.EIO:
                # EIO é normal quando o slave fecha (filho terminou)
                self._check_child_status()
                return b""
            elif e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return b""
            else:
                raise

    def write(self, data: bytes) -> int:
        """
        Envia dados para o PTY (input do teclado).
        
        Args:
            data: Bytes a enviar (teclas digitadas).
            
        Returns:
            Número de bytes escritos.
        """
        if not self._state.is_alive or self._state.master_fd < 0:
            return 0

        if isinstance(data, str):
            data = data.encode("utf-8", errors="replace")

        try:
            return os.write(self._state.master_fd, data)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EIO):
                return 0
            raise

    def resize(self, cols: int, rows: int) -> bool:
        """
        Redimensiona o terminal.
        
        Args:
            cols: Nova largura (colunas).
            rows: Nova altura (linhas).
            
        Returns:
            True se sucesso.
        """
        if self._state.master_fd < 0:
            return False

        cols = max(1, cols)
        rows = max(1, rows)
        self._state.cols = cols
        self._state.rows = rows

        return self._set_winsize(self._state.master_fd, cols, rows)

    def send_interrupt(self) -> bool:
        """
        Envia SIGINT (Ctrl+C) para o grupo de processos do PTY.
        
        Returns:
            True se o sinal foi enviado.
        """
        if not self._state.is_alive or self._state.child_pid <= 0:
            return False

        try:
            # Enviar para o grupo de processos (foreground process group)
            os.killpg(self._state.child_pid, signal.SIGINT)
            return True
        except OSError:
            # Tentar enviar apenas para o PID
            try:
                os.kill(self._state.child_pid, signal.SIGINT)
                return True
            except OSError:
                return False

    def send_eof(self) -> bool:
        """
        Envia EOF (Ctrl+D) para o PTY.
        Equivalente a fechar o stdin do shell.
        
        Returns:
            True se sucesso.
        """
        # Ctrl+D é o byte 0x04 (EOT)
        return self.write(b"\x04") > 0

    def get_exit_code(self) -> Optional[int]:
        """
        Retorna o código de saída do processo filho.
        None se o processo ainda está rodando.
        """
        if self._state.is_alive:
            self._check_child_status()
        return self._state.exit_code

    def close(self) -> None:
        """
        Encerra o PTY e limpa recursos.
        Envia SIGHUP para o filho se ainda estiver vivo.
        """
        if self._state.child_pid > 0 and self._state.is_alive:
            # Tentar encerrar graciosamente
            try:
                os.killpg(self._state.child_pid, signal.SIGHUP)
            except OSError:
                pass

            # Aguardar um pouco para o filho terminar
            deadline = time.time() + 0.5
            while time.time() < deadline:
                self._check_child_status()
                if not self._state.is_alive:
                    break
                time.sleep(0.05)

            # Forçar se ainda estiver vivo
            if self._state.is_alive:
                try:
                    os.killpg(self._state.child_pid, signal.SIGKILL)
                    os.waitpid(self._state.child_pid, 0)
                except OSError:
                    pass

        # Fechar os FDs
        if self._state.master_fd >= 0:
            try:
                os.close(self._state.master_fd)
            except OSError:
                pass
            self._state.master_fd = -1

        if self._state.slave_fd >= 0:
            try:
                os.close(self._state.slave_fd)
            except OSError:
                pass
            self._state.slave_fd = -1

        self._state.is_alive = False
        self._state.child_pid = -1

    def set_on_exit_callback(self, callback: Callable[[int], None]) -> None:
        """Registra callback para quando o processo filho terminar."""
        self._on_exit_callback = callback

    # ─── MÉTODOS INTERNOS ──────────────────────────────────────────────

    @staticmethod
    def _set_nonblocking(fd: int) -> None:
        """Configura um FD como não-bloqueante."""
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    @staticmethod
    def _set_winsize(fd: int, cols: int, rows: int) -> bool:
        """Configura o tamanho da janela do terminal (TIOCSWINSZ)."""
        try:
            # struct winsize { unsigned short ws_row, ws_col, ws_xpixel, ws_ypixel }
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
            return True
        except (OSError, AttributeError):
            return False

    def _check_child_status(self) -> None:
        """Verifica se o processo filho terminou (waitpid não-bloqueante)."""
        if not self._state.is_alive or self._state.child_pid <= 0:
            return

        try:
            pid, status = os.waitpid(
                self._state.child_pid, os.WNOHANG
            )
            if pid == self._state.child_pid:
                self._state.is_alive = False
                if os.WIFEXITED(status):
                    self._state.exit_code = os.WEXITSTATUS(status)
                elif os.WIFSIGNALED(status):
                    self._state.exit_code = -os.WTERMSIG(status)
                else:
                    self._state.exit_code = -1

                if self._on_exit_callback:
                    try:
                        self._on_exit_callback(self._state.exit_code)
                    except Exception:
                        pass
        except ChildProcessError:
            # Filho já foi coletado
            self._state.is_alive = False
        except OSError:
            pass

    def _install_sigchld_handler(self) -> None:
        """
        Instala handler para SIGCHLD para detectar saída do filho.
        Usa um handler leve que apenas marca para verificação posterior.
        """
        original_handler = signal.getsignal(signal.SIGCHLD)

        def _sigchld_handler(signum, frame):
            self._check_child_status()
            # Chamar o handler original se existir
            if callable(original_handler):
                original_handler(signum, frame)

        try:
            signal.signal(signal.SIGCHLD, _sigchld_handler)
        except (OSError, ValueError):
            # Pode falhar se não estamos na main thread
            pass

def is_platform_supported() -> bool:
    """Verifica se o backend Unix PTY é suportado na plataforma atual."""
    if sys.platform == "win32":
        return False
    return UNIX_MODULES_AVAILABLE
    
# def is_platform_supported() -> bool:
#     """Verifica se o backend Unix PTY é suportado na plataforma atual."""
#     if sys.platform == "win32":
#         return False
#     # Verificar se os módulos necessários estão disponíveis
#     try:
#         import pty  # noqa: F401
#         import fcntl  # noqa: F401
#         import termios  # noqa: F401
#         return True
#     except ImportError:
#         return False


__all__ = [
    "UnixPTYBackend",
    "PTYState",
    "is_platform_supported",
]
