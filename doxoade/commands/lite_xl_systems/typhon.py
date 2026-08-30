# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon.py
"""
🐉 TYPHON — Pipeline de Deploy Supervisionado com Auto-Rollback.
O pai dos monstros. A tempestade que abala tudo... e restaura a ordem.
"""
from __future__ import annotations

import json
import os
import re
import sys
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from .engine_lite_xl import LiteXLEngine

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""


class TyphonEngine:
    """Motor do Pipeline TYPHON: SNAPSHOT → PREFLIGHT → DEPLOY → RELAUNCH → WATCH → VERDICT."""

    STATE_FILE_NAME = "typhon_state.json"
    STABLE_INIT_NAME = "init.stable.lua"
    DEPLOY_LOG_NAME = "typhon_deploy_log.txt"

    @classmethod
    def _get_doxoade_dir(cls) -> Path:
        """Diretório de artefatos do Doxoade dentro do USERDIR do Lite XL."""
        user_dir = LiteXLEngine.get_user_dir()
        d = user_dir / ".doxoade"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def _get_state_path(cls) -> Path:
        return cls._get_doxoade_dir() / cls.STATE_FILE_NAME

    @classmethod
    def _get_stable_init_path(cls) -> Path:
        return cls._get_doxoade_dir() / cls.STABLE_INIT_NAME

    @classmethod
    def _get_deploy_log_path(cls) -> Path:
        return cls._get_doxoade_dir() / cls.DEPLOY_LOG_NAME

    # ─────────────────────────────────────────────────────────────
    # ESTADO PERSISTENTE
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def load_state(cls) -> Dict[str, Any]:
        """Carrega o estado persistente do último deploy."""
        state_path = cls._get_state_path()
        if not state_path.exists():
            return {"history": [], "last_deploy": None, "stable_snapshot": None}
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"history": [], "last_deploy": None, "stable_snapshot": None}

    @classmethod
    def save_state(cls, state: Dict[str, Any]) -> None:
        state_path = cls._get_state_path()
        state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    # ─────────────────────────────────────────────────────────────
    # FASE 0: SNAPSHOT (Backup do init.lua estável)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def take_snapshot(cls) -> Tuple[bool, str]:
        """Captura o init.lua atual como snapshot estável antes do deploy."""
        init_path = LiteXLEngine.get_init_lua_path()
        stable_path = cls._get_stable_init_path()

        if not init_path.exists():
            return False, "init.lua não existe ainda — primeiro deploy, sem snapshot"

        try:
            shutil.copy2(init_path, stable_path)
            return True, f"Snapshot salvo: {stable_path}"
        except Exception as e:
            return False, f"Falha ao criar snapshot: {e}"

    # ─────────────────────────────────────────────────────────────
    # FASE 1: PREFLIGHT (Gate de validação)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def run_preflight(cls) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Executa validação completa do init.lua em memória.
        Retorna: (passou, mensagem, detalhes)
        """
        details: Dict[str, Any] = {
            "compilation": False,
            "shadow_audit": False,
            "undeclared_vars": [],
            "init_size_bytes": 0,
        }

        # 1. Gera init.lua em memória
        try:
            init_content = LiteXLEngine.generate_sovereign_init()
            details["init_size_bytes"] = len(init_content.encode("utf-8"))
        except Exception as e:
            return False, f"Falha ao gerar init.lua: {e}", details

        # 2. Compilação real (Lua 5.4)
        runtime = LiteXLEngine.lua_runtime_info()
        if runtime:
            lua_exe, lua_ver = runtime
            import tempfile
            temp_init = Path(tempfile.gettempdir()) / f"typhon_preflight_{os.getpid()}.lua"
            temp_init.write_text(init_content, encoding="utf-8")
            try:
                lua_safe_path = str(temp_init).replace("\\", "/")
                result = subprocess.run(
                    [str(lua_exe), "-e", f'dofile("{lua_safe_path}")'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    return False, f"Erro de compilação Lua:\n{result.stderr.strip()}", details
                details["compilation"] = True
            except Exception as e:
                return False, f"Falha na compilação: {e}", details
            finally:
                try:
                    temp_init.unlink()
                except Exception:
                    pass
        else:
            details["compilation"] = None  # Sem runtime, pula

        # 3. Shadow Audit
        try:
            shadow = LiteXLEngine.run_shadow_audit()
            if shadow.get("status") == "FAIL":
                failed = [f for f, d in shadow.get("files", {}).items() if d.get("status") == "FAIL"]
                return False, f"Shadow Audit falhou em: {', '.join(failed)}", details
            details["shadow_audit"] = True
        except Exception as e:
            return False, f"Shadow Audit falhou: {e}", details

        # 4. Variáveis não declaradas
        LUA_LITERALS = {"true", "false", "nil"}
        undeclared = []
        for line_no, line in enumerate(init_content.splitlines(), 1):
            match = re.search(r'rawset\(_G,\s*"[^"]+",\s*([a-zA-Z_][a-zA-Z0-9_]*)\)', line)
            if match:
                var_name = match.group(1)
                if var_name in LUA_LITERALS:
                    continue
                preceding = "\n".join(init_content.splitlines()[:line_no - 1])
                has_local = re.search(rf'\blocal\s+{re.escape(var_name)}\b', preceding)
                has_rawset = re.search(rf'rawset\(_G,\s*"{re.escape(var_name)}"', preceding)
                if not has_local and not has_rawset:
                    undeclared.append({"line": line_no, "var": var_name})

        details["undeclared_vars"] = undeclared
        if undeclared:
            names = [f"L{u['line']}:{u['var']}" for u in undeclared]
            return False, f"Variáveis não declaradas: {', '.join(names)}", details

        return True, "Preflight OK", details

    # ─────────────────────────────────────────────────────────────
    # FASE 2: DEPLOY (Grava init.lua no disco)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def deploy_init(cls) -> Tuple[bool, str]:
        """Gera e grava o init.lua em produção."""
        try:
            LiteXLEngine.install_sovereign_config()
            return True, "init.lua gravado com sucesso"
        except Exception as e:
            return False, f"Falha no deploy: {e}"

    # ─────────────────────────────────────────────────────────────
    # FASE 3: RELAUNCH (Kill + Start supervisionado)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def relaunch(cls, target: str = ".") -> Tuple[bool, str, Optional[int]]:
        """
        Encerra o Lite XL existente e relança.
        Retorna: (sucesso, mensagem, PID do novo processo)
        """
        # Kill supervisionado
        if LiteXLEngine.is_running():
            try:
                ipc_queue = LiteXLEngine.get_ipc_queue_path()
                with open(ipc_queue, "a", encoding="utf-8") as f:
                    f.write("__DOXOADE_GRACEFUL_QUIT__\n")
                time.sleep(0.5)
            except Exception:
                pass
            LiteXLEngine.kill_ghost_processes()
            time.sleep(1.0)

        # Launch
        native_exe = LiteXLEngine.find_executable()
        if not native_exe:
            return False, "Executável lite-xl não encontrado", None

        resolved_path, _, _ = LiteXLEngine.resolve_target_path(target)
        working_dir = str(Path(resolved_path).parent if Path(resolved_path).is_file() else resolved_path)

        try:
            proc = subprocess.Popen(
                [str(native_exe), resolved_path],
                cwd=working_dir,
                close_fds=True,
            )
            return True, f"Lite XL relançado (PID: {proc.pid})", proc.pid
        except Exception as e:
            return False, f"Falha ao relançar: {e}", None

    # ─────────────────────────────────────────────────────────────
    # FASE 4: WATCH (Polling de PID + Leitura de log)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def watch(cls, pid: int, watch_seconds: int = 5, poll_interval: float = 0.5) -> Tuple[str, Dict[str, Any]]:
        """
        Monitora o processo do Lite XL até estabilizar ou crashar.
        Retorna: (verdict, details)
        verdict: "STABLE", "CRASH", "TIMEOUT"
        """
        details: Dict[str, Any] = {
            "pid_alive": False,
            "boot_ok_detected": False,
            "errors": [],
            "elapsed_seconds": 0.0,
        }

        log_path = LiteXLEngine.get_session_log_path()
        start_time = time.time()
        deadline = start_time + watch_seconds

        while time.time() < deadline:
            # 1. Verifica se o processo está vivo
            alive = cls._is_pid_alive(pid)
#            alive = LiteXLEngine.is_process_alive(pid)
            details["pid_alive"] = alive
            details["elapsed_seconds"] = round(time.time() - start_time, 2)

            # 2. Lê o session_log.txt
            if log_path.exists():
                try:
                    log_content = log_path.read_text(encoding="utf-8", errors="replace")

                    if "=== SOVEREIGN BOOT OK ===" in log_content:
                        details["boot_ok_detected"] = True
                        return "STABLE", details

                    # Captura erros da sessão atual
                    errors = []
                    for line in log_content.splitlines():
                        if "[ERROR]" in line:
                            errors.append(line.strip())
                    details["errors"] = errors

                    # Processo morreu com erros?
                    if not alive and errors:
                        return "CRASH", details

                except Exception:
                    pass

            # 3. Processo morreu silenciosamente?
            if not alive and not details.get("boot_ok_detected"):
                time.sleep(0.5)  # Dá mais uma chance pro log aparecer
                if log_path.exists():
                    log_content = log_path.read_text(encoding="utf-8", errors="replace")
                    if "[ERROR]" in log_content:
                        details["errors"] = [l.strip() for l in log_content.splitlines() if "[ERROR]" in l]
                        return "CRASH", details

            time.sleep(poll_interval)

        # Timeout: processo vivo mas sem SOVEREIGN BOOT OK
        if details["pid_alive"]:
            return "TIMEOUT", details

        return "CRASH", details

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Verifica se um PID específico está vivo (cross-platform)."""
        if pid is None:
            return False
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True, timeout=3
                )
                return str(pid) in result.stdout
            else:
                import os as _os
                _os.kill(pid, 0)  # Signal 0 = check existence, no kill
                return True
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return False

    # ─────────────────────────────────────────────────────────────
    # FASE 5: ROLLBACK (Restaura snapshot estável)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def rollback(cls) -> Tuple[bool, str]:
        """Restaura o init.lua a partir do snapshot estável."""
        stable_path = cls._get_stable_init_path()
        init_path = LiteXLEngine.get_init_lua_path()

        if not stable_path.exists():
            return False, "Nenhum snapshot estável disponível para rollback"

        try:
            shutil.copy2(stable_path, init_path)
            return True, f"Rollback concluído: {stable_path} → {init_path}"
        except Exception as e:
            return False, f"Falha no rollback: {e}"

    # ─────────────────────────────────────────────────────────────
    # FASE 6: ABRE DEBUG EM CASO DE FALHA
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def open_debug(cls) -> Tuple[bool, str]:
        """Abre o debug do Lite XL para investigação de crash."""
        try:
            debug_cmd = ["doxoade", "lite-xl", "debug"]
            subprocess.Popen(debug_cmd, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            return True, "Debug aberto em nova janela"
        except Exception as e:
            return False, f"Falha ao abrir debug: {e}"

    # ─────────────────────────────────────────────────────────────
    # PIPELINE COMPLETO
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def run_pipeline(
        cls,
        target: str = ".",
        watch_seconds: int = 5,
        dry_run: bool = False,
        no_rollback: bool = False,
        baseline: bool = False,
        echo=None,
    ) -> Dict[str, Any]:
        """
        Executa o pipeline completo TYPHON.
        Retorna um dict com timeline e resultado final.
        """
        if echo is None:
            echo = print

        timeline: List[Dict[str, Any]] = []
        state = cls.load_state()
        pipeline_start = time.time()

        def log_phase(phase: str, status: str, duration_ms: float, detail: str = ""):
            entry = {
                "phase": phase,
                "status": status,
                "duration_ms": round(duration_ms, 2),
                "detail": detail,
                "timestamp": datetime.now().isoformat(),
            }
            timeline.append(entry)
            badge = f"{Fore.GREEN}✔{Fore.RESET}" if status == "OK" else f"{Fore.RED}✖{Fore.RESET}"
            echo(f"  {badge} {Fore.CYAN}[{phase}]{Fore.RESET} {detail} {Fore.LIGHTBLACK_EX}({duration_ms:.0f}ms){Fore.RESET}")

        echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}🐉 TYPHON DEPLOY PIPELINE{Style.RESET_ALL}")
        echo(f"  {Fore.WHITE}Alvo: {target} | Watch: {watch_seconds}s | Rollback: {'OFF' if no_rollback else 'ON'}{Fore.RESET}\n")

        # ── FASE 0: SNAPSHOT ──
        t0 = time.time()
        snap_ok, snap_msg = cls.take_snapshot()
        log_phase("SNAPSHOT", "OK" if snap_ok else "SKIP", (time.time() - t0) * 1000, snap_msg)

        # Baseline: captura boot time do snapshot estável
        baseline_boot_ms = None
        if baseline and state.get("last_deploy", {}).get("boot_time_ms"):
            baseline_boot_ms = state["last_deploy"]["boot_time_ms"]

        # ── FASE 1: PREFLIGHT ──
        t0 = time.time()
        preflight_ok, preflight_msg, preflight_details = cls.run_preflight()
        log_phase("PREFLIGHT", "OK" if preflight_ok else "FAIL", (time.time() - t0) * 1000, preflight_msg)

        if not preflight_ok:
            echo(f"\n  {Fore.RED}{Style.BRIGHT}✖ PIPELINE ABORTADO — Preflight falhou.{Style.RESET_ALL}")
            echo(f"  {Fore.YELLOW}Nenhuma alteração foi feita em produção.{Fore.RESET}\n")

            # Registra no histórico
            state.setdefault("history", []).append({
                "type": "ABORTED",
                "phase": "PREFLIGHT",
                "reason": preflight_msg,
                "timestamp": datetime.now().isoformat(),
                "timeline": timeline,
            })
            cls.save_state(state)
            return {"success": False, "phase": "PREFLIGHT", "timeline": timeline, "detail": preflight_msg}

        if dry_run:
            echo(f"\n  {Fore.YELLOW}{Style.BRIGHT}🔍 DRY-RUN — Pipeline validado, nenhuma alteração gravada.{Style.RESET_ALL}\n")
            return {"success": True, "dry_run": True, "timeline": timeline}

        # ── FASE 2: DEPLOY ──
        t0 = time.time()
        deploy_ok, deploy_msg = cls.deploy_init()
        log_phase("DEPLOY", "OK" if deploy_ok else "FAIL", (time.time() - t0) * 1000, deploy_msg)

        if not deploy_ok:
            echo(f"\n  {Fore.RED}✖ Deploy falhou. Snapshot preservado para rollback manual.{Fore.RESET}\n")
            return {"success": False, "phase": "DEPLOY", "timeline": timeline, "detail": deploy_msg}

        # ── FASE 3: RELAUNCH ──
        t0 = time.time()
        launch_ok, launch_msg, new_pid = cls.relaunch(target)
        log_phase("RELAUNCH", "OK" if launch_ok else "FAIL", (time.time() - t0) * 1000, launch_msg)

        if not launch_ok or new_pid is None:
            echo(f"\n  {Fore.RED}✖ Relaunch falhou.{Fore.RESET}\n")
            if not no_rollback:
                echo(f"  {Fore.YELLOW}Executando rollback...{Fore.RESET}")
                rb_ok, rb_msg = cls.rollback()
                echo(f"  {'✔' if rb_ok else '✖'} {rb_msg}")
            return {"success": False, "phase": "RELAUNCH", "timeline": timeline, "detail": launch_msg}

        # ── FASE 4: WATCH ──
        t0 = time.time()
        echo(f"  {Fore.CYAN}👁️ Monitorando PID {new_pid} por {watch_seconds}s...{Fore.RESET}")
        verdict, watch_details = cls.watch(new_pid, watch_seconds)
        watch_duration = (time.time() - t0) * 1000

        verdict_colors = {"STABLE": Fore.GREEN, "CRASH": Fore.RED, "TIMEOUT": Fore.YELLOW}
        verdict_badges = {"STABLE": "✔ STABLE", "CRASH": "✖ CRASH", "TIMEOUT": "⚠ TIMEOUT"}
        color = verdict_colors.get(verdict, Fore.WHITE)
        echo(f"  {color}{Style.BRIGHT}{verdict_badges[verdict]}{Style.RESET_ALL} ({watch_details['elapsed_seconds']}s)")

        if watch_details["errors"]:
            echo(f"  {Fore.RED}Erros capturados:{Fore.RESET}")
            for err in watch_details["errors"][:5]:
                echo(f"    {Fore.RED}• {err[:120]}{Fore.RESET}")

        log_phase("WATCH", verdict, watch_duration, f"PID {new_pid} → {verdict}")

        # ── FASE 5: VERDICT ──
        pipeline_duration = (time.time() - pipeline_start) * 1000

        if verdict == "STABLE":
            # Promove snapshot como estável
            state["last_deploy"] = {
                "timestamp": datetime.now().isoformat(),
                "boot_time_ms": watch_details["elapsed_seconds"] * 1000,
                "pid": new_pid,
                "init_size_bytes": preflight_details.get("init_size_bytes", 0),
            }
            state.setdefault("history", []).append({
                "type": "DEPLOY_OK",
                "timestamp": datetime.now().isoformat(),
                "timeline": timeline,
                "total_ms": pipeline_duration,
            })
            cls.save_state(state)

            echo(f"\n  {Fore.GREEN}{Style.BRIGHT}✔ DEPLOY BEM-SUCEDIDO{Style.RESET_ALL} ({pipeline_duration:.0f}ms)")

            # Delta de baseline
            if baseline_boot_ms is not None:
                current_boot_ms = watch_details["elapsed_seconds"] * 1000
                delta = current_boot_ms - baseline_boot_ms
                sign = "+" if delta > 0 else ""
                delta_color = Fore.RED if delta > 500 else (Fore.GREEN if delta < -100 else Fore.WHITE)
                echo(f"  {Fore.WHITE}Boot: {current_boot_ms:.0f}ms ({delta_color}{sign}{delta:.0f}ms vs baseline{Fore.RESET})")

            echo()
            return {"success": True, "verdict": "STABLE", "timeline": timeline, "total_ms": pipeline_duration}

        else:
            # CRASH ou TIMEOUT → rollback
            echo(f"\n  {Fore.RED}{Style.BRIGHT}✖ DEPLOY FALHOU — Veredicto: {verdict}{Style.RESET_ALL}")

            if not no_rollback:
                echo(f"  {Fore.YELLOW}🛡️ Executando ROLLBACK automático...{Fore.RESET}")
                rb_ok, rb_msg = cls.rollback()
                echo(f"  {'✔' if rb_ok else '✖'} {rb_msg}")

                if rb_ok:
                    echo(f"  {Fore.CYAN}🔄 Relançando versão estável...{Fore.RESET}")
                    re_ok, re_msg, re_pid = cls.relaunch(target)
                    echo(f"  {'✔' if re_ok else '✖'} {re_msg}")

            # Abre debug automaticamente
            echo(f"  {Fore.MAGENTA}🐛 Abrindo debug para investigação...{Fore.RESET}")
            dbg_ok, dbg_msg = cls.open_debug()
            echo(f"  {'✔' if dbg_ok else '✖'} {dbg_msg}")

            state.setdefault("history", []).append({
                "type": "DEPLOY_FAILED",
                "verdict": verdict,
                "errors": watch_details.get("errors", []),
                "timestamp": datetime.now().isoformat(),
                "timeline": timeline,
                "rollback": not no_rollback,
            })
            cls.save_state(state)

            echo()
            return {
                "success": False,
                "verdict": verdict,
                "timeline": timeline,
                "errors": watch_details.get("errors", []),
                "total_ms": pipeline_duration,
            }

    # ─────────────────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Retorna status completo do TYPHON."""
        state = cls.load_state()
        init_path = LiteXLEngine.get_init_lua_path()
        stable_path = cls._get_stable_init_path()

        return {
            "init_lua_exists": init_path.exists(),
            "init_lua_size": init_path.stat().st_size if init_path.exists() else 0,
            "stable_snapshot_exists": stable_path.exists(),
            "stable_snapshot_size": stable_path.stat().st_size if stable_path.exists() else 0,
            "last_deploy": state.get("last_deploy"),
            "deploy_history_count": len(state.get("history", [])),
            "recent_history": state.get("history", [])[-5:],
            "state_file": str(cls._get_state_path()),
            "lite_xl_running": LiteXLEngine.is_running(),
        }
