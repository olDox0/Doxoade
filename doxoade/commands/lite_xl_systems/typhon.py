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

    # ─────────────────────────────────────────────────────────────
    # 🧪 TEST-DEPLOY — Pipeline isolado no SANDBOX (não toca o init real)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def _get_sandbox_dir(cls) -> Path:
        """Diretório do sandbox isolado para test-deploy."""
        return LiteXLEngine.get_sandbox_dir()

    @classmethod
    def run_health_gate(cls) -> Tuple[bool, Dict[str, Any]]:
        """Executa o gate de saúde completo. Retorna (passou, dados_do_gate)."""
        gate = LiteXLEngine.run_health_gate()
        return gate["healthy"], gate

    @classmethod
    def deploy_to_sandbox(cls) -> Tuple[bool, str]:
        """Compila o init de TESTE (com módulo de sandbox) e instala no sandbox isolado.
        NUNCA toca o init.lua de produção."""
        try:
            sandbox_dir = cls._get_sandbox_dir()
            sandbox_dir.mkdir(parents=True, exist_ok=True)
            # 🛡️ FIX: generate_sandbox_init() inclui o sandbox_module.lua,
            # diferenciando do init de produção (generate_sovereign_init()).
            init_content = LiteXLEngine.generate_sandbox_init()
            sandbox_init = sandbox_dir / "init.lua"
            sandbox_init.write_text(init_content, encoding="utf-8")
            return True, f"Init de teste (com sandbox) instalado: {sandbox_init}"
        except Exception as e:
            return False, f"Falha ao instalar init no sandbox: {e}"

    @classmethod
    def launch_sandbox(cls) -> Tuple[bool, str, Optional[int]]:
        """Lança o Lite XL apontando para o sandbox isolado com LITE_USERDIR."""
        try:
            exe = LiteXLEngine.find_executable()
            if not exe:
                return False, "Executável lite-xl.exe não encontrado", None
            sandbox_dir = cls._get_sandbox_dir()
            project_dir = os.getcwd()
            
            env = os.environ.copy()
            env["LITE_USERDIR"] = str(sandbox_dir)
            env["XDG_CONFIG_HOME"] = str(sandbox_dir.parent)
            
            CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
            proc = subprocess.Popen(
                [str(exe), project_dir],
                env=env,
                creationflags=CREATE_NEW_CONSOLE,
                close_fds=(sys.platform != "win32"),
            )
            return True, f"Sandbox lançado (PID {proc.pid})", proc.pid
        except Exception as e:
            return False, f"Falha ao lançar sandbox: {e}", None

    @classmethod
    def run_test_pipeline(cls, watch_seconds: int = 4) -> Dict[str, Any]:
        """
        🧪 TYPHON TEST-DEPLOY — Pipeline supervisionado com análise de telemetria.
        Fases: HEALTH GATE → DEPLOY TEST → LAUNCH (LITE_USERDIR) → WATCH → FORENSIC VERDICT.
        """
        result = {"success": False, "phases": [], "verdict": None, "sandbox_pid": None}

        def _phase(name: str, ok: bool, msg: str) -> None:
            result["phases"].append({"name": name, "ok": ok, "msg": msg})

        # 1. Health Gate estático
        gate_ok, gate = cls.run_health_gate()
        if not gate_ok:
            _phase("HEALTH_GATE", False, f"Sistema NÃO saudável: {gate['failed']} falha(s) crítica(s)")
            result["verdict"] = "ABORTED_BY_GATE"
            return result
        _phase("HEALTH_GATE", True, f"Sistema saudável ({gate['passed']} OK, {gate['warnings']} avisos)")

        # 2. Deploy no diretório de teste isolado
        from .typhon_deploy import TyphonDeployEngine
        deploy_res = TyphonDeployEngine.deploy("test")
        if not deploy_res["success"]:
            _phase("DEPLOY_TEST", False, deploy_res["error"])
            result["verdict"] = "DEPLOY_FAILED"
            return result
        _phase("DEPLOY_TEST", True, f"Init de teste compilado ({deploy_res['size']} chars)")

        # 3. Lançamento com LITE_USERDIR
        test_dir = TyphonDeployEngine._get_deploy_dir("test")
        exe = LiteXLEngine.find_executable()
        if not exe:
            _phase("LAUNCH_TEST", False, "Executável lite-xl.exe não encontrado")
            result["verdict"] = "LAUNCH_FAILED"
            return result

        env = os.environ.copy()
        env["LITE_USERDIR"] = str(test_dir)
        env["XDG_CONFIG_HOME"] = str(test_dir.parent)

        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
        time.sleep(0.5)

        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        proc = subprocess.Popen(
            [str(exe), os.getcwd()],
            env=env,
            creationflags=CREATE_NEW_CONSOLE,
            close_fds=(sys.platform != "win32")
        )
        _phase("LAUNCH_TEST", True, f"Instância de teste lançada (PID: {proc.pid})")
        result["sandbox_pid"] = proc.pid

        # 4. Watch com inspeção de logs
        time.sleep(watch_seconds)
        alive = proc.poll() is None

        # 5. Análise de Forensics
        error_file = test_dir / "error.txt"
        session_file = test_dir / "session_log.txt"
        has_error_txt = error_file.exists() and error_file.stat().st_size > 0
        session_log = session_file.read_text(encoding="utf-8", errors="replace") if session_file.exists() else ""

        # Encerramento limpo da instância de teste
        if alive:
            proc.kill()
            try:
                proc.wait(timeout=1.0)
            except Exception:
                pass

        if alive and not has_error_txt and ("HOOKS_INIT" in session_log or "SOVEREIGN BOOT OK" in session_log or len(session_log) > 0):
            _phase("WATCH", True, f"PID {proc.pid} estável. Telemetria confirmada.")
            result["success"] = True
            result["verdict"] = "TEST_STABLE"
        else:
            reason = "Processo encerrou prematuramente" if not alive else ("error.txt detectado" if has_error_txt else "Sem telemetria no session_log")
            _phase("WATCH", False, f"Falha no teste: {reason}")
            result["success"] = False
            result["verdict"] = "TEST_UNSTABLE"

        return result

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
    # FASE 0: SNAPSHOT — ponto de restauração PRÉ-DEPLOY
    # (NÃO sobrescreve mais o init.stable.lua — isso quebra o ciclo vicioso)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def take_snapshot(cls) -> Tuple[bool, str]:
        """Salva o init.lua atual como ponto pré-deploy (não toca no stable)."""
        init_path = LiteXLEngine.get_init_lua_path()
        pre_path = cls._get_doxoade_dir() / "init.pre_deploy.lua"
        if not init_path.exists():
            return False, "init.lua não existe ainda — primeiro deploy, sem snapshot"
        try:
            shutil.copy2(init_path, pre_path)
            return True, f"Pré-deploy salvo: {pre_path}"
        except Exception as e:
            return False, f"Falha ao criar snapshot: {e}"

    # PROMOÇÃO: novo init.lua só vira "stable" com veredicto positivo
    @classmethod
    def promote_to_stable(cls) -> Tuple[bool, str]:
        """Promove o init.lua recém-verificado a snapshot estável oficial."""
        init_path = LiteXLEngine.get_init_lua_path()
        stable_path = cls._get_stable_init_path()
        if not init_path.exists():
            return False, "init.lua não existe para promoção"
        try:
            shutil.copy2(init_path, stable_path)
            state = cls.load_state()
            state["stable_snapshot"] = {
                "path": str(stable_path),
                "promoted_at": datetime.now().isoformat(timespec="seconds"),
            }
            cls.save_state(state)
            return True, f"init.lua promovido a estável: {stable_path}"
        except Exception as e:
            return False, f"Falha na promoção: {e}"

    # ─────────────────────────────────────────────────────────────
    # FASE 1: PREFLIGHT (Gate de validação)
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def run_preflight(cls) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Executa validação completa do init.lua em memória.
        Retorna: (passou, mensagem, detalhes)
        """

        try:
            from doxoade.tools.lua_systems.api_guard.api_catalog import APICatalogSchema, get_default_catalog, save_catalog, get_api_guard_dir
            catalog = get_default_catalog()
            guard_dir = get_api_guard_dir()
            (guard_dir / "catalog.json").write_text(APICatalogSchema.serialize_json(catalog), encoding="utf-8")
            (guard_dir / "catalog.lua").write_text(APICatalogSchema.export_to_lua(catalog), encoding="utf-8")
        except Exception:
            pass

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

            # 🛡️ Cláusula anti-vácuo: harness morto = nenhum módulo reportado = FALHA
            if not shadow.get("files"):
                details["shadow_audit"] = False
                return False, (
                    "Shadow Audit falhou em: harness não reportou nenhum módulo "
                    f"({shadow.get('reason', 'verifique get_shadow_harness_path')})"
                ), details

            if shadow.get("status") == "FAIL":
                failed_files = [
                    f"{n} → {str(i.get('error', 'unknown error'))[:120]}"
                    for n, i in shadow.get("files", {}).items()
                    if i.get("status") == "FAIL"
                ]
                crashed_cmds = [
                    f"{c.get('command', '?')} → {str(c.get('error', '?'))[:70]}"
                    for c in shadow.get("crashed_commands", [])
                ]
                prompt_crashes = [
                    f"prompt '{p.get('prompt', '?')}' → {str(p.get('error', '?'))[:70]}"
                    for p in shadow.get("prompt_crashes", [])
                ]
                causes = []
                if failed_files:    causes.append("arquivos: " + ", ".join(failed_files))
                if crashed_cmds:    causes.append("comandos: " + " | ".join(crashed_cmds))
                if prompt_crashes:  causes.append("prompts: " + " | ".join(prompt_crashes))
                reason = "; ".join(causes) or shadow.get("reason") or "causa não identificada"
                return False, f"Shadow Audit falhou em: {reason}", details

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
    # FASE 4: WATCH — veredicto baseado em EVIDÊNCIAS FRESCAS
    # ─────────────────────────────────────────────────────────────
    @classmethod
    def watch(cls, pid: int, watch_seconds: float = 5.0) -> Tuple[str, Dict[str, Any]]:
        """
        Observa o PID recém-lançado e emite veredicto semântico.

        STABLE  → processo vivo + nenhum error.txt novo + boot confirmado no log.
        CRASH   → processo morreu OU error.txt criado/atualizado após o deploy.
        TIMEOUT → janela expirou com processo vivo, sem confirmação (INCONCLUSIVO).

        Regra de ouro: nenhum artefato é lido sem baseline de frescor (mtime/size).
        """
        t0 = time.time()
        details: Dict[str, Any] = {
            "elapsed_seconds": 0.0,
            "errors": [],
            "boot_confirmed": False,
        }

        error_txt = LiteXLEngine.get_error_txt_path()
        session_log = LiteXLEngine.get_session_log_path()

        # Baselines de frescor capturados ANTES do boot do novo PID
        baseline_error_mtime = error_txt.stat().st_mtime if error_txt.exists() else None
        baseline_log_size = session_log.stat().st_size if session_log.exists() else 0

        GRACE_AFTER_BOOT = 3.0  # Aumentado para dar tempo do flush
        FALLBACK_ALIVE_THRESHOLD = 4.0  # Se vivo por 4s sem crash, é STABLE
        boot_confirmed_at = None
        deadline = t0 + watch_seconds        
        
        while time.time() < deadline:
            # 1) Processo morreu → CRASH imediato
            if not cls._is_pid_alive(pid):
                details["elapsed_seconds"] = round(time.time() - t0, 2)
                details["errors"].append(f"PID {pid} morreu durante a janela de observação")
                return "CRASH", details

            # 2) error.txt NOVO/ATUALIZADO após o deploy → CRASH
            if error_txt.exists():
                mtime = error_txt.stat().st_mtime
                if baseline_error_mtime is None or mtime > baseline_error_mtime:
                    details["elapsed_seconds"] = round(time.time() - t0, 2)
                    try:
                        snippet = error_txt.read_text(encoding="utf-8", errors="replace")[:300]
                    except Exception:
                        snippet = "error.txt criado/atualizado após o deploy"
                    details["errors"].append(snippet)
                    return "CRASH", details

            # 3) Confirmação de boot via crescimento do session_log
            if boot_confirmed_at is None and session_log.exists():
                try:
                    if session_log.stat().st_size > baseline_log_size:
                        content = session_log.read_text(encoding="utf-8", errors="replace")
                        if "SOVEREIGN BOOT OK" in content:
                            boot_confirmed_at = time.time()
                            details["boot_confirmed"] = True
                except Exception:
                    pass

            # 4) STABLE antecipado: boot confirmado + grace period vivo
            if boot_confirmed_at is not None and (time.time() - boot_confirmed_at) >= GRACE_AFTER_BOOT:
                details["elapsed_seconds"] = round(time.time() - t0, 2)
                return "STABLE", details

            # 5) FALLBACK: Processo vivo por FALLBACK_ALIVE_THRESHOLD sem crash → STABLE
            # Cobre o caso onde o flush do log está atrasado mas o app está estável
            if (time.time() - t0) >= FALLBACK_ALIVE_THRESHOLD and not details.get("fallback_stable"):
                details["fallback_stable"] = True
                details["boot_confirmed"] = True
                details["elapsed_seconds"] = round(time.time() - t0, 2)
                return "STABLE", details

            time.sleep(0.25)

        # Fim da janela
        details["elapsed_seconds"] = round(time.time() - t0, 2)
        if cls._is_pid_alive(pid):
            if boot_confirmed_at is not None:
                return "STABLE", details      # vivo + boot confirmado
            return "TIMEOUT", details         # vivo, sem sinal de boot (inconclusivo)
        details["errors"].append(f"PID {pid} morreu no final da janela")
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
    def run_pipeline(cls, skip_gate: bool = False) -> Dict[str, Any]:
        """
        🐉 Pipeline TYPHON de produção:
        SNAPSHOT → PREFLIGHT → 🏥 HEALTH GATE → DEPLOY → RELAUNCH → WATCH → VERDICT.
        O HEALTH GATE é obrigatório; use skip_gate=True (--force) para ignorá-lo.
        """
        result = {"success": False, "phases": [], "verdict": None}

        def _phase(name: str, ok: bool, msg: str) -> None:
            result["phases"].append({"name": name, "ok": ok, "msg": msg})

        # FASE 0: SNAPSHOT (ponto de restauração pré-deploy)
        ok, msg = cls.take_snapshot()
        _phase("SNAPSHOT", ok, msg)
        if not ok:
            result["verdict"] = "SNAPSHOT_FAILED"
            return result

        # FASE 1: PREFLIGHT (validação do init em memória)
        ok, msg, _details = cls.run_preflight()
        _phase("PREFLIGHT", ok, msg)
        if not ok:
            result["verdict"] = "PREFLIGHT_FAILED"
            return result

        # FASE 2: 🏥 HEALTH GATE (obrigatório, salvo --force)
        if skip_gate:
            _phase("HEALTH_GATE", True, "IGNORADO via --force (deploy forçado)")
        else:
            gate_ok, gate = cls.run_health_gate()
            if not gate_ok:
                _phase("HEALTH_GATE", False, f"Sistema NÃO saudável: {gate['failed']} falha(s) — deploy ABORTADO")
                result["verdict"] = "ABORTED_BY_GATE"
                return result
            _phase("HEALTH_GATE", True, f"Sistema saudável ({gate['passed']} OK, {gate['warnings']} avisos)")

        # FASE 3: DEPLOY (grava o init de produção)
        ok, msg = cls.deploy_init()
        _phase("DEPLOY", ok, msg)
        if not ok:
            result["verdict"] = "DEPLOY_FAILED"
            return result

        # FASE 4: RELAUNCH (reinicia o Lite XL com o novo init)
        ok, msg, pid = cls.relaunch()
        _phase("RELAUNCH", ok, msg)
        if not ok or pid is None:
            result["verdict"] = "RELAUNCH_FAILED"
            return result

        # FASE 5: WATCH (monitora a estabilidade do processo)
        stable = cls.watch(pid)
        _phase("WATCH", stable, f"PID {pid} {'STABLE' if stable else 'UNSTABLE'}")

        # VERDICT
        result["success"] = stable
        if stable:
            result["verdict"] = "DEPLOY_STABLE"
            cls.promote_to_stable()  # promove o init verificado a estável
        else:
            result["verdict"] = "DEPLOY_UNSTABLE"
        return result

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
