# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_windows.py
"""
🪟 PTY Backend Windows — ConPTY via pywinpty (PtyProcess Non-Blocking Engine).
Mapeamento de alta fidelidade para o PtyProcess do pywinpty 3.x.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations

import os
import select
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from doxoade.tools.terminal_pty import get_windows_build, is_conpty_available
from doxoade.tools.terminal_pty.shell_resolver import ShellResolution

WINPTY_AVAILABLE = False
WINPTY_IMPORT_ERROR: Optional[str] = None

try:
    from winpty import PtyProcess
    WINPTY_AVAILABLE = True
except ImportError as e:
    WINPTY_IMPORT_ERROR = str(e)
except Exception as e:
    WINPTY_IMPORT_ERROR = f"Erro inesperado ao importar pywinpty: {e}"


def check_windows_pty_readiness() -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Backend Windows só pode ser usado em Windows."
    if not WINPTY_AVAILABLE:
        return False, (
            f"⚠ pywinpty não está instalado ou falhou ao importar.\n"
            f"  Erro: {WINPTY_IMPORT_ERROR}\n"
            f"  Instale com: pip install pywinpty"
        )
    if not is_conpty_available():
        build = get_windows_build()
        return False, (
            f"⚠ ConPTY requer Windows 10 build >= 17763 (1809).\n"
            f"  Build atual: {build or 'desconhecido'}\n"
            f"  Atualize o Windows ou use um terminal externo."
        )
    return True, "✓ ConPTY disponível e pywinpty instalado."


class WindowsPTYBackend:
    """
    Backend PTY para Windows baseado em PtyProcess com I/O não-bloqueante.
    """

    def __init__(self):
        self._proc: Optional[PtyProcess] = None
        self._on_exit_callback: Optional[Callable[[int], None]] = None
        self._cols = 120
        self._rows = 30
        self._closed = False

    @property
    def is_alive(self) -> bool:
        if self._closed or self._proc is None:
            return False
        try:
            return self._proc.isalive()
        except Exception:
            return False

    @property
    def child_pid(self) -> int:
        if self._proc is not None:
            return getattr(self._proc, "pid", -1)
        return -1

    def spawn(
        self,
        shell: ShellResolution,
        cols: int = 120,
        rows: int = 30,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> int:
        ready, message = check_windows_pty_readiness()
        if not ready:
            raise RuntimeError(message)

        if self.is_alive:
            raise RuntimeError("PTY Windows já está ativo. Feche antes de respawnar.")

        self._cols = max(1, cols)
        self._rows = max(1, rows)
        self._closed = False

        work_dir = cwd or os.getcwd()
        if not Path(work_dir).is_dir():
            work_dir = os.getcwd()

        child_env = os.environ.copy()
        child_env["TERM"] = "xterm-256color"
        child_env["COLORTERM"] = "truecolor"
        child_env["PYTHONIOENCODING"] = "utf-8"
        if env:
            child_env.update(env)

        argv = [shell.executable] + shell.args

        try:
            self._proc = PtyProcess.spawn(
                argv=argv,
                cwd=work_dir,
                env=child_env,
                dimensions=(self._rows, self._cols),
            )
            # Configura o socket do ConPTY como não-bloqueante
            if hasattr(self._proc, "fileobj") and self._proc.fileobj:
                try:
                    self._proc.fileobj.setblocking(False)
                except Exception:
                    pass
            return self._proc.pid
        except Exception as e:
            self.close()
            raise RuntimeError(f"Falha ao criar ConPTY via PtyProcess: {e}")

    def read(self, timeout_ms: int = 20, max_bytes: int = 8192) -> bytes:
        if not self.is_alive or self._proc is None:
            return b""
        try:
            fileobj = getattr(self._proc, "fileobj", None)
            if fileobj is not None:
                timeout_sec = max(0.0, timeout_ms / 1000.0)
                r, _, _ = select.select([fileobj], [], [], timeout_sec)
                if not r:
                    return b""
                data = fileobj.recv(max_bytes)
                if not data:
                    return b""
                # Filtra o marcador de keepalive interno do pywinpty
                if data == b"0011Ignore":
                    return b""
                data = data.replace(b"0011Ignore", b"")
                return data
            else:
                text = self._proc.read()
                if text:
                    return text.encode("utf-8", errors="replace")
                return b""
        except (BlockingIOError, OSError):
            return b""
        except EOFError:
            if self._on_exit_callback:
                pcall_exit = getattr(self._proc, "exitstatus", 0) or 0
                self._on_exit_callback(pcall_exit)
            return b""
        except Exception:
            return b""

    def write(self, data: bytes | str) -> int:
        if not self.is_alive or self._proc is None:
            return 0
        try:
            if isinstance(data, bytes):
                text = data.decode("utf-8", errors="replace")
            else:
                text = str(data)
            self._proc.write(text)
            return len(data)
        except Exception:
            return 0

    def resize(self, cols: int, rows: int) -> bool:
        if not self.is_alive or self._proc is None:
            return False
        try:
            self._cols = max(1, cols)
            self._rows = max(1, rows)
            self._proc.setwinsize(self._rows, self._cols)
            return True
        except Exception:
            return False

    def send_interrupt(self) -> bool:
        if not self.is_alive or self._proc is None:
            return False
        try:
            self._proc.write("\x03")
            return True
        except Exception:
            return False

    def get_exit_code(self) -> Optional[int]:
        if self._proc is not None:
            return getattr(self._proc, "exitstatus", None)
        return None

    def set_on_exit_callback(self, callback: Callable[[int], None]) -> None:
        self._on_exit_callback = callback

    def close(self) -> None:
        self._closed = True
        if self._proc is not None:
            try:
                self._proc.close(force=True)
            except Exception:
                pass
            self._proc = None
