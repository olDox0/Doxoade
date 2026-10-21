# -*- coding: utf-8 -*-
# doxoade\tools\terminal_pty\pty_file_daemon.py
""" PTY File Daemon — Daemon de terminal PTY com file-based IPC.
Detecta automaticamente se ConPTY está disponível; se não, escreve
status detalhado e sugere fallback. """
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from doxoade.tools.terminal_pty import PlatformKind, detect_platform
from doxoade.tools.terminal_pty.shell_resolver import resolve_shell

# ─── Diagnóstico de Ambiente ───────────────────────────────────────────
def _check_conpty_capability() -> dict:
    """Verifica se ConPTY/pywinpty está utilizável neste processo."""
    result = {"available": False, "reason": "", "python": sys.executable}

    if sys.platform != "win32":
        result["available"] = True
        result["reason"] = "POSIX nativo (pty module)"
        return result

    # Windows: precisa de pywinpty + ConPTY + privilégio
    try:
        import winpty  # noqa: F401
    except ImportError as e:
        result["reason"] = f"pywinpty não instalado: {e}"
        return result

    # Detecta se está rodando elevado (Admin)
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if not is_admin:
            result["reason"] = (
                "Processo NÃO elevado (rodando como usuário padrão). "
                "ConPTY/winpty requer Admin ou Developer Mode habilitado."
            )
            return result
    except Exception:
        pass  # Não conseguiu detectar, tenta de qualquer forma

    # Tenta instanciar winpty (é o teste real)
    try:
        import winpty
        test_pty = winpty.PTY(80, 24)
        result["available"] = True
        result["reason"] = "ConPTY OK"
        return result
    except Exception as e:
        result["reason"] = f"winpty.PTY() falhou: {type(e).__name__}: {e}"
        return result


def _write_status(ipc_dir: Path, alive: bool, **extra):
    """Escreve pty_status.json atômico com o estado atual."""
    status_file = ipc_dir / "pty_status.json"
    payload = {"alive": alive, "pid": os.getpid(), "timestamp": time.time()}
    payload.update(extra)
    tmp = status_file.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, status_file)
    except Exception as e:
        print(f"[PTY] Falha ao escrever status: {e}", file=sys.stderr)


# ─── Main ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Doxoade PTY File Daemon")
    parser.add_argument("--ipc-dir", required=True, help="Diretório de IPC")
    parser.add_argument("--shell", default="cmd", help="Shell alvo")
    parser.add_argument("--cols", type=int, default=80)
    parser.add_argument("--rows", type=int, default=24)
    parser.add_argument("--cwd", default=None)
    args = parser.parse_args()

    ipc_dir = Path(args.ipc_dir)
    ipc_dir.mkdir(parents=True, exist_ok=True)

    # 1. Diagnóstico ANTES de tentar spawnar
    cap = _check_conpty_capability()
    if not cap["available"]:
        _write_status(
            ipc_dir,
            alive=False,
            shell=args.shell,
            cols=args.cols,
            rows=args.rows,
            error=cap["reason"],
            python=cap["python"],
            fallback_suggested="terminal_external" if "Admin" in cap["reason"] else "install_pywinpty",
        )
        print(f"[PTY] ConPTY indisponível: {cap['reason']}", file=sys.stderr)
        sys.exit(2)

    # 2. Spawn do PTY
    try:
        import winpty
        shell_cmd = args.shell
        if sys.platform == "win32" and not shell_cmd.lower().endswith(".exe"):
            shell_cmd = f"{shell_cmd}.exe"

        pty_proc = winpty.PTY(args.cols, args.rows)
        pty_proc.spawn(shell_cmd, cwd=args.cwd)

        _write_status(
            ipc_dir,
            alive=True,
            shell=args.shell,
            cols=args.cols,
            rows=args.rows,
            python=cap["python"],
        )
        print(f"[PTY] Daemon OK (pid={os.getpid()})", file=sys.stderr)

        # Loop principal de I/O
        while True:
            try:
                data = pty_proc.read()
                if data:
                    out_file = ipc_dir / "pty_output.txt"
                    with open(out_file, "a", encoding="utf-8", errors="replace") as f:
                        f.write(data)
            except Exception:
                # Se pty.read falhar, o shell morreu
                break
            time.sleep(0.01)

    except Exception as e:
        _write_status(
            ipc_dir,
            alive=False,
            shell=args.shell,
            cols=args.cols,
            rows=args.rows,
            error=f"{type(e).__name__}: {e}",
            traceback=traceback.format_exc(),
            python=cap["python"],
        )
        print(f"[PTY] Spawn falhou: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
