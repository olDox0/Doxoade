# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/pty_file_daemon.py
"""
🖥️ PTY File-Stream Daemon — Transporte Resiliente via Buffer de Arquivo (IPC).
Mantém o ConPTY vivo e sincroniza I/O bidirecional com o Lite XL sem dependência de sockets.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

from doxoade.tools.terminal_pty import PlatformKind, detect_platform
from doxoade.tools.terminal_pty.shell_resolver import resolve_shell

def main():
    parser = argparse.ArgumentParser(description="Doxoade PTY File-Stream Daemon")
    parser.add_argument("--ipc-dir", required=True, help="Diretório compartilhado para buffers IPC")
    parser.add_argument("--shell", default="auto", help="Identificador do shell (cmd, powershell, auto)")
    parser.add_argument("--cols", type=int, default=120)
    parser.add_argument("--rows", type=int, default=30)
    parser.add_argument("--cwd", default=None)
    args = parser.parse_args()

    ipc_dir = Path(args.ipc_dir).resolve()
    ipc_dir.mkdir(parents=True, exist_ok=True)
    
    # 🔪 Exorcismo de daemon anterior na mesma pasta
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

    # Se estiver no Windows com cmd.exe, injeta o alias do doxoade --pure automaticamente
    if platform_kind == PlatformKind.WINDOWS and shell_res.shell_id == "cmd":
        venv_act = Path(work_dir) / "venv" / "Scripts" / "activate.bat"
        init_cmd = ""
        if venv_act.exists():
            init_cmd += f'"{venv_act}" && '
        # Cria o macro doskey: digitar 'doxoade' roda 'doxoade --pure'
        init_cmd += "doskey doxoade=doxoade --pure $*"
        shell_res.args = ["/k", init_cmd]

    # Limpa buffers da sessão anterior
    for f in [file_in, file_out, file_cmd]:
        if f.exists():
            try: f.unlink()
            except Exception: pass

    # Inicializa backend PTY
    platform_kind = detect_platform()
    if platform_kind == PlatformKind.WINDOWS:
        from doxoade.tools.terminal_pty.pty_windows import WindowsPTYBackend
        backend = WindowsPTYBackend()
    else:
        from doxoade.tools.terminal_pty.pty_unix import UnixPTYBackend
        backend = UnixPTYBackend()

    shell_res = resolve_shell(args.shell)
    work_dir = args.cwd or os.getcwd()

    # Se estiver no Windows e houver venv no diretório de trabalho, injeta ativação
    if platform_kind == PlatformKind.WINDOWS and shell_res.shell_id == "cmd":
        venv_act = Path(work_dir) / "venv" / "Scripts" / "activate.bat"
        if venv_act.exists():
            shell_res.args = ["/k", str(venv_act)]

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

    file_status.write_text(json.dumps({
        "alive": True,
        "pid": pid,
        "shell": shell_res.shell_id,
        "cols": args.cols,
        "rows": args.rows
    }), encoding="utf-8")

    last_in_offset = 0

    try:
        while backend.is_alive:
            # 1. Leitura da saída do ConPTY ➔ Append em pty_out.bin
            try:
                out_data = backend.read(timeout_ms=15)
                if out_data:
                    with open(file_out, "ab") as fo:
                        fo.write(out_data)
                        fo.flush()
            except Exception:
                pass

            # 2. Leitura de novas teclas do pty_in.bin ➔ Injeta no ConPTY
            if file_in.exists() and file_in.stat().st_size > 0:
                try:
                    with open(file_in, "rb") as fi:
                        new_input = fi.read()
                    # Trunca o arquivo para 0 bytes após consumir o comando
                    with open(file_in, "wb") as fi:
                        fi.truncate(0)
                    if new_input:
                        backend.write(new_input)
                except Exception:
                    pass

            # 3. Comandos de controle (Resize / Interrupt / Shutdown)
            if file_cmd.exists():
                try:
                    cmd_data = json.loads(file_cmd.read_text(encoding="utf-8"))
                    file_cmd.unlink(missing_ok=True)
                    action = cmd_data.get("action")
                    if action == "resize":
                        backend.resize(cmd_data.get("cols", 120), cmd_data.get("rows", 30))
                    elif action == "interrupt":
                        backend.send_interrupt()
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
