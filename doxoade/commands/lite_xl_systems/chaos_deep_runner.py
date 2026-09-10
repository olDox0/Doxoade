# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/chaos_deep_runner.py
"""
🏜️ SET DEEP RUNNER — Executa payloads de caos no sandbox com verificação forense precisa.
"""
from __future__ import annotations
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.commands.lite_xl_systems.chaos_deep_payloads import DEEP_CHAOS_VECTORS


class DeepChaosRunner:
    """Executa cada vetor de caos no sandbox isolado com verificação de fase."""

    @classmethod
    def _phase_log(cls, phase: str, icon: str, message: str, color: str = Fore.CYAN):
        """Log de fase com timestamp e ícone."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"  {color}[{timestamp}] {icon} [{phase}] {message}{Fore.RESET}")

    @classmethod
    def _prepare_sandbox(cls, vector: Dict[str, Any]) -> Optional[Path]:
        """Prepara o sandbox com init de caos + hooks síncronos + payload."""
        cls._phase_log("PREPARATION", "🔧", "Iniciando preparação do sandbox", Fore.BLUE)
        sandbox_dir = LiteXLEngine.get_sandbox_dir()
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        cls._phase_log("PREPARATION", "📂", f"Sandbox: {sandbox_dir}", Fore.LIGHTBLACK_EX)

        # 1. Limpeza rigorosa de artefatos anteriores
        for artifact in ["session_log.txt", "error.txt", "BOOT_CANARY.txt",
                         ".doxoade/api_guard/runtime_probe.json",
                         ".doxoade/diagnostics/forensic_report.txt"]:
            p = sandbox_dir / artifact
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
        cls._phase_log("PREPARATION", "✔", "Artefatos antigos removidos", Fore.GREEN)

        # 2. Injeção de Hooks com I/O síncrono
        hooks_file = Path(__file__).parent / "template" / "chaos_hooks.lua"
        hooks_code = ""
        if hooks_file.exists():
            hooks_code = hooks_file.read_text(encoding="utf-8")
            cls._phase_log("PREPARATION", "✔", "Hooks síncronos carregados", Fore.GREEN)
        else:
            cls._phase_log("PREPARATION", "⚠", "chaos_hooks.lua ausente, usando fallback", Fore.YELLOW)

        # 3. Construção do init.lua específico para o vetor
        sandbox_init = sandbox_dir / "init.lua"
        payload_code = vector["payload"]

        if vector["category"] == "crash":
            # Crashes de boot rodam diretamente no chunk principal (sem pcall/threads)
            init_content = f"""
-- 🛡️ HOOKS DE DETECÇÃO
{hooks_code}

-- 💥 PAYLOAD DE CRASH FATAL DE BOOT [{vector['id']}]
{payload_code}
"""
            cls._phase_log("INJECTION", "💥", "Payload de CRASH injetado (top-level chunk)", Fore.RED)
        else:
            # Falhas de runtime e erros ocultos rodam protegidos pelo loop
            init_content = f"""
-- 🛡️ HOOKS DE DETECÇÃO
{hooks_code}

local core = rawget(_G, "core") or (pcall(require, "core") and require("core") or nil)

-- 🕳️ PAYLOAD DE CAOS EM RUNTIME [{vector['id']}]
{payload_code}
"""
            cls._phase_log("INJECTION", "🕳️", f"Payload de {vector['category'].upper()} injetado", Fore.YELLOW)

        sandbox_init.write_text(init_content, encoding="utf-8")
        cls._phase_log("PREPARATION", "✔", "init.lua montado e sincronizado", Fore.GREEN)
        return sandbox_dir
    @classmethod
    def _execute_sandbox(cls, sandbox_dir: Path, category: str, max_timeout: int = 6) -> Dict[str, Any]:
        """Lança o Lite XL apontando o USERDIR real via variável de ambiente oficial."""
        cls._phase_log("EXECUTION", "⚡", "Lançando Lite XL no sandbox", Fore.CYAN)

        # 1. Exorcismo de instâncias antigas para evitar redirecionamento por IPC
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
        time.sleep(0.5)

        exe = LiteXLEngine.find_executable()
        if not exe:
            cls._phase_log("EXECUTION", "✖", "Executável não encontrado", Fore.RED)
            return {"crashed": True, "exit_code": -1, "duration": 0, "error": "exe not found"}

        # 2. Configuração correta de ambiente para o Lite XL (LITE_USERDIR oficial)
        env = os.environ.copy()
        env["LITE_USERDIR"] = str(sandbox_dir)
        env["XDG_CONFIG_HOME"] = str(sandbox_dir.parent)

        cls._phase_log("EXECUTION", "📂", f"LITE_USERDIR: {sandbox_dir}", Fore.LIGHTBLACK_EX)

        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        start_time = time.time()

        # Dispara o Lite XL APENAS com o binário, sem passar flags inexistentes
        proc = subprocess.Popen(
            [str(exe)],
            env=env,
            creationflags=CREATE_NEW_CONSOLE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        cls._phase_log("EXECUTION", "🆔", f"PID: {proc.pid}", Fore.CYAN)

        crashed = False
        exit_code = None

        # 3. Polling ativo
        poll_limit = 2.0 if category == "crash" else max_timeout
        while (time.time() - start_time) < poll_limit:
            poll = proc.poll()
            if poll is not None:
                crashed = (poll != 0)
                exit_code = poll
                break
            time.sleep(0.3)

        duration = time.time() - start_time

        # 4. Encerramento forçado se ainda estiver vivo
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=1.0)
            except Exception:
                pass

        return {
            "crashed": crashed,
            "exit_code": exit_code,
            "duration": round(duration, 2)
        }

    @classmethod
    def _extract_forensics(cls, sandbox_dir: Path) -> Dict[str, Any]:
        """Lê os arquivos forenses gravados no disco."""
        cls._phase_log("EXTRACTION", "🔍", "Extraindo forensics", Fore.CYAN)
        error_file = sandbox_dir / "error.txt"
        session_file = sandbox_dir / "session_log.txt"

        error_txt = error_file.read_text(encoding="utf-8", errors="replace") if error_file.exists() else ""
        session_log = session_file.read_text(encoding="utf-8", errors="replace") if session_file.exists() else ""

        if error_txt:
            cls._phase_log("EXTRACTION", "💥", f"error.txt detectado ({len(error_txt)} chars)", Fore.GREEN)
        else:
            cls._phase_log("EXTRACTION", "ℹ", "error.txt ausente", Fore.LIGHTBLACK_EX)

        if session_log:
            cls._phase_log("EXTRACTION", "📜", f"session_log.txt detectado ({len(session_log.splitlines())} linhas)", Fore.GREEN)
        else:
            cls._phase_log("EXTRACTION", "✖", "session_log.txt ausente", Fore.YELLOW)

        return {
            "error_txt": error_txt,
            "session_log": session_log
        }

    @classmethod
    def _analyze_result(cls, vector: Dict[str, Any], exec_info: Dict[str, Any], forensics: Dict[str, Any]) -> Dict[str, Any]:
        """Julgamento de Ma'at: valida se o vetor foi devidamente detectado."""
        cls._phase_log("ANALYSIS", "🧠", "Analisando resultados", Fore.MAGENTA)
        category = vector["category"]
        expected_detector = vector.get("expected_detector", "")
        error_txt = forensics["error_txt"]
        session_log = forensics["session_log"]
        crashed = exec_info["crashed"]

        detected = False
        reason = ""

        if category == "crash":
            # Detectado se o processo morreu, se gerou error.txt ou se o erro de boot foi capturado no log
            has_crash_log = any(kw in session_log for kw in [
                "nil value", "stack overflow", "not found", "CORE_ERROR", "GHOST_PCALL"
            ])
            if crashed or bool(error_txt) or has_crash_log:
                detected = True
                reason = "Crash fatal de boot interceptado e neutralizado com registro forense"
            else:
                reason = "Nenhum sinal do crash fatal foi registrado"

        elif category == "fault":
            if "🕳️ [SET]" in session_log or "CORE_ERROR" in session_log or "HOOK" in session_log:
                detected = True
                reason = "Falha em runtime registrada e contida no session_log"
            else:
                reason = "Nenhum evento da falha foi registrado no log"

        elif category == "hidden":
            if expected_detector == "hook_pcall" and ("GHOST_PCALL" in session_log or "nonexistent_field" in session_log):
                detected = True
                reason = "Hook capturou o erro engolido pelo pcall silencioso"
            elif expected_detector == "hook_patch" and ("GHOST_PCALL" in session_log or "API GUARD" in session_log or "Monkey patch" in session_log or "method_that_never_existed" in session_log):
                detected = True
                reason = "Hook/API Guard detectou monkey-patch em símbolo inexistente"
            elif expected_detector == "hook_global" and ("GLOBAL_LEAK" in session_log or "AccidentalGlobalLeakVar" in session_log):
                detected = True
                reason = "Hook do Ma'at detectou a poluição no namespace global"
            else:
                reason = "O erro oculto passou despercebido pelos sensores"

        return {
            "detected": detected,
            "reason": reason
        }

    @classmethod
    def run_deep_suite(cls, categories: Optional[Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Executa a suíte completa de caos profundo ou filtra pelas categorias informadas.
        Suporta strings, listas ou tuplas em `categories`.
        """
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}🏜️ SET DEEP CHAOS SUITE — Testes de Crash, Falha e Erro Oculto{Style.RESET_ALL}")
        print(f"Ambiente: Sandbox isolado | Forensics: Hórus/Anúbis/Ma'at\n")

        # Normalização do filtro de categorias
        selected_cats = set()
        if categories:
            if isinstance(categories, (list, tuple, set)):
                selected_cats = {str(c).lower().strip() for c in categories if c}
            elif isinstance(categories, str):
                selected_cats = {c.lower().strip() for c in categories.split(",") if c.strip()}

        # Filtragem dos vetores
        if selected_cats:
            target_vectors = [
                v for v in DEEP_CHAOS_VECTORS
                if v["category"].lower() in selected_cats or v["id"].lower() in selected_cats
            ]
            print(f"🎯 Filtro aplicado: {', '.join(sorted(selected_cats))} ({len(target_vectors)} vetores selecionados)\n")
        else:
            target_vectors = DEEP_CHAOS_VECTORS

        total = len(target_vectors)
        if total == 0:
            print(f"{Fore.YELLOW}⚠ Nenhum vetor encontrado para o filtro informado.{Fore.RESET}\n")
            return {"total": 0, "passed": 0, "failed": 0}

        passed = 0
        failed = 0

        for idx, vector in enumerate(target_vectors, start=1):
            icon = "💥" if vector["category"] == "crash" else ("🕳️" if vector["category"] == "fault" else "👻")
            print(f"\n[{idx}/{total}] {icon} {vector['name']} ({vector['category'].upper()})")

            sandbox_dir = cls._prepare_sandbox(vector)
            exec_info = cls._execute_sandbox(sandbox_dir, vector["category"])
            forensics = cls._extract_forensics(sandbox_dir)
            analysis = cls._analyze_result(vector, exec_info, forensics)

            if analysis["detected"]:
                passed += 1
                print(f"   {Fore.GREEN}✔ [DETECTADO] {analysis['reason']}{Fore.RESET}")
            else:
                failed += 1
                print(f"   {Fore.RED}✖ [CEGUEIRA] {analysis['reason']}{Fore.RESET}")

        print("\n" + "=" * 70)
        if failed == 0:
            print(f"{Fore.GREEN}{Style.BRIGHT}🎉 VEREDITO FINAL: 100% DOS CENÁRIOS DE CAOS FORAM DETECTADOS! ({passed}/{total}){Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}{Style.BRIGHT}⚠ VEREDITO: {failed} CENÁRIO(S) NÃO DETECTADO(S) DE {total}.{Style.RESET_ALL}")
        print("=" * 70 + "\n")

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "missed": failed,     # Evita o KeyError no Click
            "detected": passed
        }
