# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from doxoade.tools.terminal_pty import PlatformKind, detect_platform
from doxoade.tools.terminal_pty.shell_resolver import resolve_shell


def main() -> int:
    parser = argparse.ArgumentParser(description="Doxoade PTY File-Stream Daemon")
    parser.add_argument("--ipc-dir", required=True, help="Diretório compartilhado para buffers IPC")
    parser.add_argument("--shell", default="auto", help="Identificador do shell (cmd, powershell, auto)")
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=30)
    parser.add_argument("--cwd", default=None)
    args = parser.parse_args()

    ipc_dir = Path(args.ipc_dir).resolve()
    ipc_dir.mkdir(parents=True, exist_ok=True)

    # 1. Trava anti-duplicação de PIDs órfãos
    pid_lock_file = ipc_dir / "pty_daemon.pid"
    if pid_lock_file.exists():
        try:
            old_pid = int(pid_lock_file.read_text().strip())
            if old_pid != os.getpid():
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
                else:
                    subprocess.run(["kill", "-9", str(old_pid)], capture_output=True)
        except Exception:
            pass
    pid_lock_file.write_text(str(os.getpid()), encoding="utf-8")

    file_in = ipc_dir / "pty_in.bin"
    file_out = ipc_dir / "pty_out.bin"
    file_cmd = ipc_dir / "pty_cmd.json"
    file_status = ipc_dir / "pty_status.json"

    # 2. Limpeza prévia de buffers residuais
    for f in [file_in, file_out, file_cmd]:
        if f.exists():
            try:
                f.unlink()
            except Exception:
                pass

    # 3. Resolução da plataforma, diretório e shell
    platform_kind = detect_platform()
    work_dir = args.cwd or os.getcwd()
    shell_res = resolve_shell(args.shell)

    # 🎯 Iniciação Limpa do CMD (Gera script bat isolado no ipc_dir sem conflito de aspas)
    if platform_kind == PlatformKind.WINDOWS and shell_res.shell_id == "cmd":
        init_bat = ipc_dir / "init_env.cmd"
        work_path = Path(work_dir).resolve()
        
        # Procura venvs em múltiplos padrões (venv, .venv, env)
        candidates = [
            work_path / "venv" / "Scripts" / "activate.bat",
            work_path / ".venv" / "Scripts" / "activate.bat",
            work_path / "env" / "Scripts" / "activate.bat",
        ]
        venv_act = next((c for c in candidates if c.exists()), None)

        bat_lines = ["@echo off", f'cd /d "{work_path}"']
        if venv_act:
            bat_lines.append(f'call "{venv_act.resolve()}"')
        else:
            # Fallback limpo: se não tiver venv, opera no CMD padrão sem erro
            bat_lines.append('echo [INFO] Projeto sem virtualenv local. Operando em CMD padrão.')

        bat_lines.append("doskey doxoade=doxoade --pure $*")
        init_bat.write_text("\r\n".join(bat_lines) + "\r\n", encoding="utf-8")
        shell_res.args = ["/k", str(init_bat.resolve())]

    # 4. Seleção e criação do Backend PTY
    if platform_kind == PlatformKind.WINDOWS:
        from doxoade.tools.terminal_pty.pty_windows import WindowsPTYBackend
        backend = WindowsPTYBackend()
    else:
        from doxoade.tools.terminal_pty.pty_unix import UnixPTYBackend
        backend = UnixPTYBackend()

    try:
        pid = backend.spawn(
            shell=shell_res,
            cols=max(1, args.cols),
            rows=max(1, args.rows),
            cwd=work_dir,
        )
    except Exception as e:
        file_status.write_text(json.dumps({"alive": False, "error": str(e)}), encoding="utf-8")
        return 1

    # Publica status de prontidão para o Lite XL
    file_status.write_text(json.dumps({
        "alive": True,
        "pid": pid,
        "shell": shell_res.shell_id,
        "cols": args.cols,
        "rows": args.rows
    }), encoding="utf-8")

    # 5. Loop de I/O contínuo não-bloqueante
    try:
        while backend.is_alive:
            # Leitura do stdout do PTY
            try:
                out_data = backend.read(timeout_ms=15)
                if out_data:
                    with open(file_out, "ab") as fo:
                        fo.write(out_data)
                        fo.flush()
            except Exception:
                pass

            # Escrita de comandos enviados pelo Lite XL (stdin)
            if file_in.exists() and file_in.stat().st_size > 0:
                try:
                    with open(file_in, "rb") as fi:
                        new_input = fi.read()
                    with open(file_in, "wb") as fi:
                        fi.truncate(0)
                    if new_input:
                        backend.write(new_input)
                except Exception:
                    pass

            # Sinais de controle (resize, interrupt, shutdown)
            if file_cmd.exists():
                try:
                    cmd_data = json.loads(file_cmd.read_text(encoding="utf-8"))
                    file_cmd.unlink(missing_ok=True)
                    action = cmd_data.get("action")
                    if action == "resize":
                        backend.resize(cmd_data.get("cols", 120), cmd_data.get("rows", 30))
                    elif action == "interrupt":
                        # 1. Envia caractere de controle \x03
                        backend.send_interrupt()
                        # 2. No Windows, se houver processo filho rodando no CMD, força cancelamento
                        if platform_kind == PlatformKind.WINDOWS and backend.child_pid > 0:
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/FI", f"PID ne {backend.child_pid}", "/FI", f"PID ne {os.getpid()}"],
                                capture_output=True
                            )
                    elif action == "shutdown":
                        break
                except Exception:
                    pass

            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        exit_code = backend.get_exit_code() or 0
        backend.close()
        file_status.write_text(json.dumps({"alive": False, "exit_code": exit_code}), encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
