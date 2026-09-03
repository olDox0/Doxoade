# doxoade/commands/lite_xl_systems/lite_xl_process.py
"""
⚔️ Ares — Ciclo de vida do processo Lite XL (find/launch/kill).
Parte do split de engine_lite_xl.py (God Class original V17.0) em módulos por responsabilidade.
"""
import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

from .lite_xl_paths import LiteXLPaths
from .lite_xl_init_builder import LiteXLInitBuilder
from .lite_xl_snapshots import LiteXLSnapshots

class LiteXLProcess:
    """⚔️ Ares — Ciclo de vida do processo Lite XL (find/launch/kill)."""

    @classmethod
    def find_executable(cls) -> Optional[Path]:
        if sys.platform == "win32":
            known_locations = [
                Path("C:/Program Files/Lite XL/lite-xl.exe"),
                Path("C:/Program Files (x86)/Lite XL/lite-xl.exe"),
                Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Lite XL\lite-xl.exe")),
                Path(os.path.expandvars(r"%APPDATA%\Lite XL\lite-xl.exe")),
                Path(os.path.expandvars(r"%USERPROFILE%\scoop\apps\lite-xl\current\lite-xl.exe")),
            ]
            for loc in known_locations:
                if loc.exists() and loc.is_file():
                    return loc

        scripts_dir = str(Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")).lower()
        path_entries = os.environ.get("PATH", "").split(os.pathsep)

        for entry in path_entries:
            if not entry or entry.lower().rstrip("\\/") == scripts_dir.rstrip("\\/"):
                continue
            p = Path(entry)
            if sys.platform == "win32":
                candidate = p / "lite-xl.exe"
                if candidate.exists() and candidate.is_file():
                    return candidate
            else:
                candidate = p / "lite-xl"
                if candidate.exists() and os.access(candidate, os.X_OK):
                    return candidate

        return None

    @classmethod
    def is_process_alive(cls) -> bool:
        """Verifica apenas se o processo do Lite XL está vivo no sistema operacional."""
        if sys.platform == "win32":
            try:
                out = subprocess.check_output(
                    [
                        "tasklist",
                        "/FI",
                        "IMAGENAME eq lite-xl.exe",
                        "/FO",
                        "CSV",
                        "/NH",
                    ],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return any(
                    line.strip().lower().startswith('"lite-xl.exe"')
                    or line.strip().lower().startswith("lite-xl.exe")
                    for line in out.splitlines()
                )
            except Exception:
                return False
        else:
            try:
                out = subprocess.check_output(
                    ["pgrep", "-f", "lite-xl"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                return bool(out.strip())
            except Exception:
                return False

    @classmethod
    def is_running(cls, focus_window: bool = True) -> bool:
        """
        Compatibilidade com o comportamento antigo.

        Por padrão:
        - verifica se o processo está vivo;
        - tenta focar a janela;
        - retorna o resultado do foco.

        Para apenas checar processo sem focar:
            LiteXLEngine.is_running(focus_window=False)
        """
        if not cls.is_process_alive():
            return False

        if focus_window:
            return cls.focus_running_window()

        return True

    @classmethod
    def focus_running_window(cls) -> bool:
        """Tenta trazer a janela do Lite XL para o primeiro plano (Best Effort)."""
        if sys.platform == "win32":
            try:
                cmd = (
                    "$ws = New-Object -ComObject WScript.Shell; if"
                    " ($ws.AppActivate('Lite XL')) { exit 0 } else { exit 1 }"
                )
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True,
                    timeout=2,
                )
                return res.returncode == 0
            except Exception:
                return False
        return True

    @classmethod
    def resolve_target_path(cls, raw_path: str) -> Tuple[Optional[str], bool, bool]:
        """Resolve caminhos e cria arquivos/pastas automaticamente se não existirem."""
        if not raw_path or raw_path.strip() == ".":
            cwd = Path.cwd().resolve()
            return str(cwd), True, True

        clean = raw_path.strip().strip("'\"")
        if clean.startswith("~"):
            clean = os.path.expanduser(clean)

        p = Path(clean)
        try:
            abs_p = p.resolve()
        except Exception:
            abs_p = p.absolute()

        if not abs_p.exists():
            if clean.endswith(("\\", "/")) or not abs_p.suffix:
                abs_p.mkdir(parents=True, exist_ok=True)
                return str(abs_p), True, True
            else:
                abs_p.parent.mkdir(parents=True, exist_ok=True)
                abs_p.touch(exist_ok=True)
                return str(abs_p), True, False

        return str(abs_p), True, abs_p.is_dir()

    @classmethod
    def probe_boot(cls, timeout: float = 8.0, start_time: Optional[float] = None) -> bool:
        """Prova de boot: valida se o 00_header criou/atualizou o session_log.txt nesta sessão."""
        log_path = LiteXLPaths.get_session_log_path()
        mark_time = start_time or time.time()
        deadline = time.time() + timeout

        while time.time() < deadline:
            if log_path.exists():
                try:
                    mtime = log_path.stat().st_mtime
                    if mtime >= (mark_time - 1.0):
                        return True
                except OSError:
                    pass
            time.sleep(0.3)
        return False

    @classmethod
    def send_to_running_instance(cls, target_path: str) -> Tuple[bool, str]:
        resolved, exists, is_dir = cls.resolve_target_path(target_path)
        if not resolved:
            return False, "Caminho inválido."

        if not exists:
            return False, f"O caminho não existe no disco: {resolved}"

        try:
            ipc_queue = LiteXLPaths.get_ipc_queue_path()
            with open(ipc_queue, "a", encoding="utf-8") as f:
                f.write(resolved + "\n")
            cls.focus_running_window()
            return True, resolved
        except Exception as e:
            return False, str(e)

    @classmethod
    def cleanup_old_shims(cls):
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        if not scripts_dir.exists():
            return
        for name in ["lite-xl.cmd", "litexl.cmd", "lite-lx.cmd", "lxl.cmd", "lite-xl", "litexl", "lite-lx", "lxl"]:
            target = scripts_dir / name
            if target.exists():
                try:
                    target.unlink()
                except Exception:
                    pass

    @classmethod
    def install_terminal_shims(cls) -> List[str]:
        cls.cleanup_old_shims()
        scripts_dir = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
        if not scripts_dir.exists():
            return []

        py_exe = str(Path(sys.executable).resolve())
        installed = []
        aliases = ["lite-xl", "litexl", "lite-lx", "lxl"]

        for alias in aliases:
            if sys.platform == "win32":
                shim_path = scripts_dir / f"{alias}.cmd"
                content = f'@echo off\n"{py_exe}" -m doxoade lite-xl open %*\n'
                shim_path.write_text(content, encoding="utf-8")
                installed.append(str(shim_path))
            else:
                shim_path = scripts_dir / alias
                content = f'#!/bin/sh\nexec "{py_exe}" -m doxoade lite-xl open "$@"\n'
                shim_path.write_text(content, encoding="utf-8")
                shim_path.chmod(0o755)
                installed.append(str(shim_path))

        return installed

    @classmethod
    def graceful_shutdown(cls, timeout: float = 1.5) -> bool:
        """Envia sinal de fechamento gracioso via IPC para salvar sessão e workspace."""
        if not cls.is_process_alive():
            return True

        # Dispara o comando que executa workspace.save() e core.quit()
        cls.send_to_running_instance("__DOXOADE_GRACEFUL_QUIT__")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not cls.is_process_alive():
                time.sleep(0.2)  # Janela de flush do I/O no Windows
                return True
            time.sleep(0.1)

        # Fallback se a janela estiver travada/bloqueada
        cls.kill_ghost_processes()
        time.sleep(0.2)
        return True

    @classmethod
    def launch_with_safety_guard(
        cls, target_path: Optional[str] = None, restore_session: bool = True, *args, **kwargs
    ) -> Tuple[bool, str]:
        """Inicia o Lite XL com monitoramento de session_log e error.txt."""
        if restore_session:
            LiteXLSnapshots.restore_workspace_state()
        else:
            LiteXLSnapshots.backup_workspace_state()

        init_path = LiteXLPaths.get_init_lua_path()
        exe = cls.find_executable()
        if not exe:
            return False, "Binário do Lite XL não encontrado."

        cmd_args = [str(exe)]
        if target_path:
            cmd_args.append(str(target_path))

        # Pre-flight check estático do init.lua
        if init_path.exists():
            raw_init = init_path.read_text(encoding="utf-8", errors="replace")
            scan_errs = LiteXLInitBuilder.compile_scan_lua(raw_init)
            compile_err = LiteXLInitBuilder.true_compile_check(init_path)

            if scan_errs or (compile_err and compile_err != "NO_RUNTIME"):
                err_detail = "; ".join(scan_errs) if scan_errs else str(compile_err)
                LiteXLSnapshots.restore_stable_snapshot()
                LiteXLSnapshots.restore_workspace_state()
                subprocess.Popen(cmd_args)
                return False, (
                    f"PRE-FLIGHT GATE: ERRO DETECTADO NO INIT.LUA.\n"
                    f"  MODO SEGURO ATIVADO (Snapshot Estável Restaurado).\n"
                    f"  Laudo: {err_detail}"
                )

        # Limpa session_log e error.txt anteriores para isolar a sessão atual
        log_path = LiteXLPaths.get_session_log_path()
        error_path = LiteXLPaths.get_error_txt_path()
        for p in [log_path, error_path]:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        start_time = time.time()
        proc = subprocess.Popen(cmd_args)

        # Handshake Watchdog (monitora logs e error.txt por até 3s)
        boot_confirmed = False
        has_errors = False
        error_excerpt = ""
        deadline = time.time() + 3.0

        while time.time() < deadline:
            if proc.poll() is not None:
                # Processo encerrou abruptamente
                break

            # 🛡️ 1. Checagem prioritária de crash fatal (error.txt)
            if error_path.exists():
                try:
                    mtime = error_path.stat().st_mtime
                    if mtime >= (start_time - 1.0):
                        err_content = error_path.read_text(encoding="utf-8", errors="replace")
                        has_errors = True
                        error_excerpt = "\n".join(err_content.splitlines()[:6])
                        break
                except Exception:
                    pass

            # 🛡️ 2. Checagem de session_log.txt
            if log_path.exists():
                try:
                    log_content = log_path.read_text(encoding="utf-8", errors="replace")
                    if "[ERROR]" in log_content:
                        has_errors = True
                        err_lines = [l for l in log_content.splitlines() if "[ERROR]" in l or "[TRACE]" in l]
                        error_excerpt = "\n".join(err_lines[-5:])
                        break
                    if "=== SOVEREIGN BOOT OK ===" in log_content:
                        boot_confirmed = True
                        break
                except Exception:
                    pass

            time.sleep(0.15)

        # Confirmação de Sucesso
        if (boot_confirmed or (log_path.exists() and not has_errors)) and not has_errors and proc.poll() is None:
            LiteXLSnapshots.promote_to_stable_snapshot()
            LiteXLSnapshots.backup_workspace_state()
            return True, "Lite XL inicializado com sucesso em Modo Soberano (Sessão Preservada)."

        # 🚨 Fallback Imediato (mata qualquer popup modal travado e restaura o snapshot)
        try:
            proc.kill()
        except Exception:
            pass

        LiteXLSnapshots.restore_stable_snapshot()
        LiteXLSnapshots.restore_workspace_state()
        subprocess.Popen(cmd_args)

        return False, (
            f"FALHA CAPTURADA NO BOOT / RENDERIZAÇÃO.\n"
            f"  MODO SEGURO ATIVADO (Sessão e Snapshot Estável Restaurados).\n"
            f"  Evidência capturada:\n{error_excerpt or 'Timeout aguardando handshake.'}"
        )

    @classmethod
    def kill_ghost_processes(cls):
        """Mata processos fantasmas e purga a fila IPC residual."""
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill", "-9", "-f", "lite-xl"], capture_output=True, timeout=5)

        cls._clear_ipc_queue()

    @classmethod
    def _clear_ipc_queue(cls) -> None:
        """Remove a fila IPC residual com segurança."""
        try:
            ipc_file = LiteXLPaths.get_ipc_queue_path()
            if ipc_file.exists():
                ipc_file.unlink()
        except Exception:
            pass

    @classmethod
    def launch_sandbox(cls, target_path: Optional[str] = None) -> Optional[subprocess.Popen]:
        """Lança o Lite XL no sandbox isolado usando a variável oficial LITE_USERDIR."""
        exe = cls.find_executable()
        if not exe:
            return None
        sandbox_dir = LiteXLPaths.get_sandbox_dir()
        
        env = os.environ.copy()
        env["LITE_USERDIR"] = str(sandbox_dir)
        env["XDG_CONFIG_HOME"] = str(sandbox_dir.parent)
        
        cmd = [str(exe)]
        if target_path:
            cmd.append(target_path)
            
        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        return subprocess.Popen(
            cmd,
            env=env,
            creationflags=CREATE_NEW_CONSOLE,
            close_fds=(sys.platform != "win32")
        )
