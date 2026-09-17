# -*- coding: utf-8 -*-
# doxoade/tools/terminal_systems/terminal_stream_daemon.py
"""
🖥️ DOXOADE TERMINAL STREAM DAEMON — Motor de Sessão Persistente de Shell Interativo.
Compliance: ProDeNov 1.2.1, PASC-6.1, Limite < 50KB.
"""
from __future__ import annotations

import os
import sys
import time
import json
import signal
import shutil
import ctypes
import threading
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List


@dataclass
class TerminalSessionConfig:
    project_dir: Path
    shell_type: str = "powershell" if sys.platform == "win32" else "bash"
    ipc_dir: Optional[Path] = None
    buffer_flush_interval: float = 0.015
    auto_activate_venv: bool = True
    max_output_history_bytes: int = 10 * 1024 * 1024


class TerminalStreamDaemon:
    def __init__(self, config: TerminalSessionConfig):
        self.config = config
        self.project_dir = Path(config.project_dir).resolve()
        self.ipc_dir = config.ipc_dir or (self.project_dir / ".doxoade" / "terminal_ipc")
        self.ipc_dir.mkdir(parents=True, exist_ok=True)

        self.stdin_queue_file = self.ipc_dir / "stdin.queue"
        self.stdout_stream_file = self.ipc_dir / "stdout.stream"
        self.control_signal_file = self.ipc_dir / "signal.ctrl"
        self.status_file = self.ipc_dir / "session_status.json"

        self.proc: Optional[subprocess.Popen] = None
        self._is_running = False
        self._stop_event = threading.Event()
        self._stdin_read_offset = 0
        self._total_bytes_written = 0

    def _detect_project_venv(self) -> Tuple[Optional[Path], Optional[Path]]:
        candidates = [
            self.project_dir / "venv",
            self.project_dir / ".venv",
            self.project_dir / "doxoade" / "venv",
            self.project_dir / "doxoade" / ".venv",
            self.project_dir / "env",
        ]
        for vpath in candidates:
            if vpath.exists() and vpath.is_dir():
                scripts = vpath / ("Scripts" if sys.platform == "win32" else "bin")
                if scripts.exists():
                    return scripts, vpath
        return None, None

    def _build_shell_command(self) -> List[str]:
        scripts_dir, _ = self._detect_project_venv()
        shell = self.config.shell_type.lower()

        if sys.platform == "win32":
            if shell in ("powershell", "pwsh"):
                ps_exe = shutil.which("pwsh") or shutil.which("powershell.exe") or "powershell.exe"
                activate_snippet = ""
                if self.config.auto_activate_venv and scripts_dir:
                    act_ps1 = scripts_dir / "Activate.ps1"
                    if act_ps1.exists():
                        activate_snippet = f"if (Test-Path '{act_ps1}') {{ & '{act_ps1}' }}; "

                return [
                    ps_exe,
                    "-NoLogo",
                    "-NoExit",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    f"Set-Location '{self.project_dir}'; {activate_snippet}"
                ]
            else:
                cmd_exe = shutil.which("cmd.exe") or "cmd.exe"
                init_bat = ""
                if self.config.auto_activate_venv and scripts_dir:
                    act_bat = scripts_dir / "activate.bat"
                    if act_bat.exists():
                        init_bat = f'call "{act_bat}" & '
                return [cmd_exe, "/k", f'cd /d "{self.project_dir}" & {init_bat} cls']
        else:
            bash_exe = shutil.which("bash") or shutil.which("sh") or "/bin/bash"
            return [bash_exe, "-i"]

    def start_session(self) -> bool:
        if self._is_running and self.proc and self.proc.poll() is None:
            return True

        self._reset_ipc_files()
        cmd_args = self._build_shell_command()
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        scripts_dir, _ = self._detect_project_venv()
        if scripts_dir:
            env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")

        try:
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            self.proc = subprocess.Popen(
                cmd_args,
                cwd=str(self.project_dir),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                creationflags=creation_flags,
                close_fds=(sys.platform != "win32")
            )

            self._is_running = True
            self._stop_event.clear()

            threading.Thread(target=self._stream_reader_worker, daemon=True).start()
            threading.Thread(target=self._stdin_queue_worker, daemon=True).start()
            threading.Thread(target=self._signal_listener_worker, daemon=True).start()

            self._write_status(is_alive=True, message="Sessão interativa inicializada.")
            return True
        except Exception as e:
            self._is_running = False
            self._write_status(is_alive=False, error=str(e))
            return False

    def _reset_ipc_files(self) -> None:
        try:
            self.stdin_queue_file.write_text("", encoding="utf-8")
            self.stdout_stream_file.write_bytes(b"")
            self.control_signal_file.write_text("", encoding="utf-8")
            self._stdin_read_offset = 0
            self._total_bytes_written = 0
        except Exception:
            pass

    def _stream_reader_worker(self) -> None:
        while self._is_running and not self._stop_event.is_set():
            if not self.proc or not self.proc.stdout:
                break
            try:
                raw_chunk = self.proc.stdout.read(2048)
                if not raw_chunk:
                    if self.proc.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue

                with open(self.stdout_stream_file, "ab") as f_out:
                    f_out.write(raw_chunk)
                    f_out.flush()

                self._total_bytes_written += len(raw_chunk)
            except Exception:
                break

    def _stdin_queue_worker(self) -> None:
        while self._is_running and not self._stop_event.is_set():
            try:
                if self.stdin_queue_file.exists():
                    f_size = self.stdin_queue_file.stat().st_size
                    if f_size > self._stdin_read_offset:
                        with open(self.stdin_queue_file, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(self._stdin_read_offset)
                            new_text = f.read()
                            self._stdin_read_offset = f.tell()

                        if new_text and self.proc and self.proc.stdin:
                            self.proc.stdin.write(new_text.encode("utf-8", errors="replace"))
                            self.proc.stdin.flush()
                time.sleep(self.config.buffer_flush_interval)
            except Exception:
                time.sleep(0.05)

    def _signal_listener_worker(self) -> None:
        while self._is_running and not self._stop_event.is_set():
            try:
                if self.control_signal_file.exists():
                    sig = self.control_signal_file.read_text(encoding="utf-8").strip()
                    if sig:
                        self.control_signal_file.write_text("", encoding="utf-8")
                        if sig in ("SIGINT", "CTRL_C") and self.proc:
                            if sys.platform == "win32":
                                ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, self.proc.pid)
                            else:
                                os.kill(self.proc.pid, signal.SIGINT)
                            with open(self.stdout_stream_file, "ab") as f:
                                f.write(b"\n^C\n")
                                f.flush()
                time.sleep(0.02)
            except Exception:
                time.sleep(0.05)

    def _write_status(self, is_alive: bool, message: str = "", error: Optional[str] = None) -> None:
        try:
            payload = {
                "is_alive": is_alive,
                "pid": self.proc.pid if self.proc else None,
                "project_dir": str(self.project_dir),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": message,
                "error": error,
            }
            self.status_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", "-p", default=".")
    parser.add_argument("--shell", "-s", default="powershell" if sys.platform == "win32" else "bash")
    args = parser.parse_args()

    daemon = TerminalStreamDaemon(TerminalSessionConfig(project_dir=Path(args.project_dir), shell_type=args.shell))
    if daemon.start_session():
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            daemon._stop_event.set()
