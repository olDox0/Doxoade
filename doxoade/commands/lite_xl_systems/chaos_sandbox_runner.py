# doxoade/commands/lite_xl_systems/chaos_sandbox_runner.py
"""
Motor de Orquestração de Testes de Estresse (Sandbox Chaos Runner).
Isola o ambiente, integra os módulos de defesa do Doxoade, injeta payloads de caos,
executa o Lite XL em modo sandbox e extrai relatórios forenses (Hades/Apolo).
"""
import os
import time
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine


class ChaosSandboxRunner:
    """Orquestrador do ciclo de vida de um teste de caos no Sandbox."""

    def __init__(self, payload_filename: str, payload_content: str):
        self.payload_filename = payload_filename
        self.payload_content = payload_content
        self.sandbox_dir = LiteXLEngine.get_sandbox_dir()
        self.forensic_data: Dict[str, Any] = {}

    def prepare_environment(self) -> bool:
        """Prepara o diretório do sandbox e injeta o payload na raiz do USERDIR."""
        try:
            self.sandbox_dir.mkdir(parents=True, exist_ok=True)
            # Salva o payload na raiz do USERDIR do sandbox para garantir caminho absoluto
            payload_path = self.sandbox_dir / self.payload_filename
            payload_path.write_text(self.payload_content, encoding="utf-8")
            return True
        except Exception as e:
            print(f"{Fore.RED}✖ Falha ao preparar sandbox: {e}{Fore.RESET}")
            return False

    def compile_and_execute(self, timeout_seconds: int = 15) -> bool:
        """Copia o init.lua soberano real para o sandbox e anexa o caos."""
        try:
            self.sandbox_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. LOCALIZAR O INIT.LUA SOBERANO (gerado pelo `setup`)
            sovereign_init = LiteXLEngine.get_init_lua_path()
            if not sovereign_init.exists():
                print(f"{Fore.RED}✖ init.lua soberano não encontrado em: {sovereign_init}{Fore.RESET}")
                print(f"{Fore.YELLOW}💡 Execute 'doxoade lite-xl setup -f' primeiro.{Fore.RESET}")
                return False
            
            # 2. COPIAR PARA O SANDBOX (isolamento total)
            sandbox_init = self.sandbox_dir / "init.lua"
            shutil.copy2(str(sovereign_init), str(sandbox_init))
            print(f"{Fore.CYAN}📋 Init.lua soberano copiado para o sandbox.{Fore.RESET}")
            
            # 3. ANEXAR O PAYLOAD DE CAOS
            payload_abs_path = (self.sandbox_dir / self.payload_filename).as_posix()
            chaos_injection = f"""

-- =============================================================================
-- 🍷 INJEÇÃO DE CAOS PELO RUNNER (Executado após o boot soberano completo)
-- =============================================================================
pcall(function()
    dofile("{payload_abs_path}")
end)
"""
            with open(sandbox_init, "a", encoding="utf-8") as f:
                f.write(chaos_injection)
                
            print(f"{Fore.MAGENTA}🛡️ Sistema Doxoade integrado. Payload de caos armado.{Fore.RESET}")
            
            # 4. LIMPAR SESSION_LOG ANTIGO DO SANDBOX (evita leitura de logs stale)
            sandbox_session_log = self.sandbox_dir / "session_log.txt"
            if sandbox_session_log.exists():
                sandbox_session_log.unlink()
            
            # 5. Execução Isolada via Subprocesso
            exe_path = LiteXLEngine.find_executable()
            if not exe_path:
                raise FileNotFoundError("Executável do Lite XL não encontrado.")
            
            cmd = [str(exe_path), "--userdir", str(self.sandbox_dir)]
            
            print(f"{Fore.CYAN}⚡ Executando Sandbox (Timeout: {timeout_seconds}s)...{Fore.RESET}")
            start_time = time.time()
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                self.forensic_data["stdout"] = stdout
                self.forensic_data["stderr"] = stderr
                self.forensic_data["exit_code"] = process.returncode
                self.forensic_data["duration"] = time.time() - start_time
                self.forensic_data["crashed"] = process.returncode != 0
            except subprocess.TimeoutExpired:
                process.kill()
                self.forensic_data["crashed"] = False
                self.forensic_data["duration"] = timeout_seconds
                self.forensic_data["exit_code"] = "TIMEOUT"
                
            return True
        except Exception as e:
            print(f"{Fore.RED}✖ Falha na execução do sandbox: {e}{Fore.RESET}")
            return False

    def extract_forensics(self) -> Dict[str, Any]:
        """Extrai logs de erro, sessão e telemetria do diretório do sandbox."""
        diag_dir = self.sandbox_dir / ".doxoade" / "diagnostics"
        error_txt = self.sandbox_dir / "error.txt"
        session_log = self.sandbox_dir / "session_log.txt"
        
        forensics = {
            "error_txt": "",
            "session_log_tail": "",
            "telemetry": {}
        }
        
        try:
            if error_txt.exists():
                forensics["error_txt"] = error_txt.read_text(encoding="utf-8", errors="replace")
            else:
                forensics["error_txt"] = "[NÃO GERADO] O Lite XL não crashou ou o error.txt não foi criado."
                
            if session_log.exists():
                lines = session_log.read_text(encoding="utf-8", errors="replace").splitlines()
                # 📜 RELAXA O FILTRO: Mostra as últimas 25 linhas reais do boot
                forensics["session_log_tail"] = "\n".join(lines[-25:])
            else:
                forensics["session_log_tail"] = "[NÃO GERADO] O session_log.txt não foi encontrado."
                
            telemetry_file = diag_dir / "profiler_telemetry.json"
            if telemetry_file.exists():
                forensics["telemetry"] = json.loads(telemetry_file.read_text(encoding="utf-8"))
            else:
                forensics["telemetry"] = {"warning": "Telemetria não gerada. O 10_forensic_engine.lua pode não ter rodado."}
        except Exception as e:
            forensics["extraction_error"] = str(e)
            
        self.forensic_data.update(forensics)
        return forensics

    def generate_report(self):
        """Renderiza o relatório de sobrevivência no terminal (Apolo)."""
        print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 RELATÓRIO DE SOBREVIVÊNCIA DO SANDBOX{Style.RESET_ALL}")
        crashed = self.forensic_data.get("crashed", False)
        status_str = f"{Fore.RED}💥 CRASH DETECTADO" if crashed else f"{Fore.GREEN}✔ SOBREVIVEU (Timeout ou Exit 0)"
        
        print(f"  {Fore.WHITE}Status:{Fore.RESET} {status_str}{Fore.RESET}")
        print(f"  {Fore.WHITE}Tempo:{Fore.RESET} {self.forensic_data.get('duration', 0):.2f}s")
        
        session_tail = self.forensic_data.get("session_log_tail", "")
        if session_tail and not session_tail.startswith("[NENHUM") and not session_tail.startswith("[NÃO"):
            print(f"\n{Fore.CYAN}{Style.BRIGHT}📜 REAÇÕES DE DEFESA (Session Log):{Style.RESET_ALL}")
            for line in session_tail.splitlines():
                print(f"  {Fore.LIGHTBLACK_EX}{line}{Fore.RESET}")
        else:
            print(f"\n{Fore.YELLOW}⚠ {session_tail}{Fore.RESET}")
            
        if self.forensic_data.get("error_txt") and not self.forensic_data["error_txt"].startswith("[NÃO"):
            print(f"\n{Fore.RED}{Style.BRIGHT}🩺 CRASH REPORT (error.txt):{Style.RESET_ALL}")
            error_lines = self.forensic_data["error_txt"].splitlines()[:15]
            for line in error_lines:
                print(f"  {Fore.LIGHTRED_EX}{line}{Fore.RESET}")
                
        telemetry = self.forensic_data.get("telemetry", {})
        if isinstance(telemetry, dict) and "warning" not in telemetry:
            spikes = telemetry.get("frame_spikes", [])
            bottlenecks = telemetry.get("thread_bottlenecks", [])
            print(f"\n{Fore.YELLOW}{Style.BRIGHT}🦅 TELEMETRIA (Chronos):{Fore.RESET_ALL}")
            print(f"  {Fore.WHITE}Frame Spikes:{Fore.RESET} {len(spikes)}")
            print(f"  {Fore.WHITE}Thread Bottlenecks:{Fore.RESET} {len(bottlenecks)}")
        else:
            warn_msg = telemetry.get("warning", "Telemetria indisponível.")
            print(f"\n{Fore.YELLOW}⚠ {warn_msg}{Fore.RESET}")

    def cleanup(self):
        """Remove o payload de caos para não poluir futuros testes."""
        try:
            payload_path = self.sandbox_dir / self.payload_filename
            if payload_path.exists():
                payload_path.unlink()
        except Exception:
            pass

    def run(self, timeout: int = 15):
        """Fluxo principal de execução do teste de estresse."""
        print(f"{Fore.MAGENTA}{Style.BRIGHT}🍷 INICIANDO PROTOCOLO DE CAOS CONTROLADO...{Style.RESET_ALL}")
        
        if not self.prepare_environment():
            return
            
        if not self.compile_and_execute(timeout):
            self.cleanup()
            return
            
        self.extract_forensics()
        self.generate_report()
        self.cleanup()
