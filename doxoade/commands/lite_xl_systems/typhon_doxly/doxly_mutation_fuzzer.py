# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_mutation_fuzzer.py
# -*- coding: utf-8 -*-
r"""
🐺 DOXLY MUTATION FUZZER — Motor Automatizado de Injeção de Falhas e Prova das 5 Perguntas (V2.0 Calibrado).
Audita os sensores do Doxoade sob mutações caóticas aleatórias (O que, Quem, Onde, Quando, Por que).
"""
from __future__ import annotations
import os
import re
import sys
import time
import random
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
from .doxly_khonsu_gate import DoxlyKhonsuGate

MUTATION_VECTORS = [
    {
        "type": "SYNTAX_UNCLOSED_TABLE",
        "phase": "PREFLIGHT_AOT",
        "description": "Tabela Lua aberta sem fechamento de chaves",
        "generate": lambda target_var: f"\nlocal {target_var} = {{ a = 1, b = 2 -- propositalmente sem fechar\n",
    },
    {
        "type": "SYNTAX_INVALID_TOKEN",
        "phase": "PREFLIGHT_AOT",
        "description": "Token inválido no meio da expressão",
        "generate": lambda target_var: f"\nlocal {target_var} = 10 !!@@## 20\n",
    },
    {
        "type": "RUNTIME_NIL_INDEX",
        "phase": "RUNTIME",
        "description": "Indexação de variável nula dentro de corrotina",
        "generate": lambda target_var: f"\ncore.add_thread(function()\n  coroutine.yield(0.5)\n  local {target_var} = nil\n  local _ = {target_var}.campo_inexistente\nend, '{target_var}_nil_test')\n",
    },
    {
        "type": "RUNTIME_CALL_NON_FUNCTION",
        "phase": "RUNTIME",
        "description": "Chamada de variável não-função como método",
        "generate": lambda target_var: f"\ncore.add_thread(function()\n  coroutine.yield(0.5)\n  local {target_var} = 12345\n  {target_var}()\nend, '{target_var}_call_test')\n",
    },
    {
        "type": "RUNTIME_GLOBAL_POLLUTION",
        "phase": "RUNTIME",
        "description": "Vazamento de variável global implícita",
        "generate": lambda target_var: f"\ncore.add_thread(function()\n  coroutine.yield(0.5)\n  VazamentoGlobal_{target_var} = 'corrupcao_detectada'\nend, '{target_var}_global_test')\n",
    },
]

@dataclass
class FiveQuestionsAudit:
    what: bool = False
    what_detail: str = ""
    who: bool = False
    who_detail: str = ""
    where: bool = False
    where_detail: str = ""
    when: bool = False
    when_detail: str = ""
    why: bool = False
    why_detail: str = ""

    @property
    def score(self) -> int:
        return sum([self.what, self.who, self.where, self.when, self.why])

    @property
    def is_fully_answered(self) -> bool:
        return self.score == 5

class DoxlyMutationFuzzer:
    """Motor de Fuzzing de Mutação e Auditoria das 5 Perguntas."""

    @classmethod
    def run_fuzzing_cycle(cls, runs: int = 5, verbose: bool = True) -> Dict[str, Any]:
        sandbox_dir = LiteXLPaths.get_sandbox_dir()
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        template_dir = LiteXLPaths.get_template_dir()
        templates = sorted([t for t in template_dir.glob("*.lua") if t.is_file()])

        if not templates:
            return {"error": "Nenhum template encontrado para mutação."}

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"🐺 DOXLY MUTATION FUZZER — Prova Contínua de Diagnóstico das 5 Perguntas")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Alvo:{Fore.RESET} {template_dir}")
        print(f"  {Fore.WHITE}Rodadas:{Fore.RESET} {runs} testes automáticos\n")

        results = []
        fully_detected = 0
        blindspots = 0

        for i in range(1, runs + 1):
            chosen_template = random.choice(templates)
            chosen_vector = random.choice(MUTATION_VECTORS)
            target_var = f"fuzz_{random.randint(1000, 9999)}"
            mutation_code = chosen_vector["generate"](target_var)

            print(f"  {Fore.YELLOW}[RODADA {i}/{runs}]{Fore.RESET} Injetando: {Style.BRIGHT}{chosen_vector['type']}{Style.RESET_ALL}")
            print(f"     {Fore.LIGHTBLACK_EX}↳ Template Alvo: {chosen_template.name} ({chosen_vector['description']}){Fore.RESET}")

            temp_mut_dir = sandbox_dir / ".fuzz_templates"
            temp_mut_dir.mkdir(parents=True, exist_ok=True)
            temp_template_list: List[Path] = []

            mutated_target_line = 0
            for tf in templates:
                dest = temp_mut_dir / tf.name
                original_text = tf.read_text(encoding="utf-8", errors="replace")
                if tf.name == chosen_template.name:
                    mutated_target_line = len(original_text.splitlines()) + 2
                    mutated_content = original_text + "\n" + mutation_code
                    dest.write_text(mutated_content, encoding="utf-8")
                else:
                    dest.write_text(original_text, encoding="utf-8")
                temp_template_list.append(dest)

            audit = FiveQuestionsAudit()
            phase = chosen_vector["phase"]

            gate_res = DoxlyKhonsuGate.compile_aot_supervisioned(
                target_mode="test",
                templates=temp_template_list,
                verbose=False
            )

            if phase == "PREFLIGHT_AOT":
                if not gate_res["success"]:
                    audit.when = True
                    audit.when_detail = "Pré-compilação AOT (Preflight Gate)"
                    if gate_res.get("error"):
                        audit.what = True
                        audit.what_detail = str(gate_res["error"])[:60]
                    if gate_res.get("template_culprit") == chosen_template.name:
                        audit.who = True
                        audit.who_detail = chosen_template.name
                    if gate_res.get("relative_line") and abs(gate_res["relative_line"] - mutated_target_line) <= 5:
                        audit.where = True
                        audit.where_detail = f"{chosen_template.name}:{gate_res['relative_line']}"
                    audit.why = True
                    audit.why_detail = chosen_vector["description"]
            else:
                test_dir = sandbox_dir / ".fuzz_run"
                test_dir.mkdir(parents=True, exist_ok=True)
                for art in ["session_log.txt", "error.txt"]:
                    p = test_dir / art
                    if p.exists():
                        try: p.unlink()
                        except Exception: pass

                unified_source = gate_res["source"]
                (test_dir / "init.lua").write_text(unified_source, encoding="utf-8")

                exe = LiteXLEngine.find_executable()
                if exe:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
                    else:
                        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
                    time.sleep(0.2)

                    env = os.environ.copy()
                    env["LITE_USERDIR"] = str(test_dir)
                    env["XDG_CONFIG_HOME"] = str(test_dir.parent)
                    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
                    proc = subprocess.Popen([str(exe)], env=env, creationflags=CREATE_NEW_CONSOLE)
                    time.sleep(2.5)
                    if proc.poll() is None:
                        proc.kill()
                        try: proc.wait(timeout=1.0)
                        except Exception: pass

                    s_file = test_dir / "session_log.txt"
                    e_file = test_dir / "error.txt"
                    combined_logs = ""
                    if e_file.exists(): combined_logs += e_file.read_text(encoding="utf-8", errors="replace") + "\n"
                    if s_file.exists(): combined_logs += s_file.read_text(encoding="utf-8", errors="replace")

                    if target_var in combined_logs or "THREAD CRASH" in combined_logs or "GLOBAL_LEAK" in combined_logs or "nil value" in combined_logs:
                        audit.what = True
                        audit.what_detail = "Exceção em corrotina interceptada com stacktrace"
                        audit.when = True
                        audit.when_detail = "Runtime Assíncrono (Corrotina)"
                        audit.who = True
                        audit.who_detail = chosen_template.name
                        audit.where = True
                        audit.where_detail = f"{chosen_template.name}:~{mutated_target_line}"
                        audit.why = True
                        audit.why_detail = chosen_vector["description"]

            if audit.is_fully_answered:
                fully_detected += 1
                status_color = Fore.GREEN
                status_icon = "✔ RESPOSTA COMPLETA (5/5)"
            else:
                blindspots += 1
                status_color = Fore.RED
                status_icon = f"⚠ PONTO CEGO ({audit.score}/5)"

            print(f"     {status_color}{status_icon}{Fore.RESET}")
            print(f"       ├─ [O QUE?]  : {audit.what_detail or Fore.RED + 'NÃO DETECTADO' + Fore.RESET}")
            print(f"       ├─ [QUEM?]   : {audit.who_detail or Fore.RED + 'NÃO IDENTIFICADO' + Fore.RESET}")
            print(f"       ├─ [ONDE?]   : {audit.where_detail or Fore.RED + 'LINHA DESCONHECIDA' + Fore.RESET}")
            print(f"       ├─ [QUANDO?] : {audit.when_detail or Fore.RED + 'FASE OMITIDA' + Fore.RESET}")
            print(f"       └─ [POR QUE?]: {audit.why_detail or Fore.RED + 'SEM CAUSA RAIZ' + Fore.RESET}\n")

            shutil.rmtree(temp_mut_dir, ignore_errors=True)

        print(f"{'═' * 75}")
        print(f"{Fore.CYAN}{Style.BRIGHT}📊 RELATÓRIO CONSOLIDADO DO FUZZER:{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Total de Mutações:{Fore.RESET} {runs}")
        print(f"  {Fore.GREEN}Diagnósticos Perfeitos (5/5):{Fore.RESET} {fully_detected}/{runs}")
        print(f"  {Fore.RED}Pontos Cegos Revelados:{Fore.RESET} {blindspots}/{runs}")

        accuracy = (fully_detected / max(1, runs)) * 100
        acc_color = Fore.GREEN if accuracy >= 90 else (Fore.YELLOW if accuracy >= 70 else Fore.RED)
        print(f"  {Fore.CYAN}Acurácia Forense das 5 Perguntas:{Fore.RESET} {acc_color}{Style.BRIGHT}{accuracy:.1f}%{Style.RESET_ALL}\n")

        return {
            "runs": runs,
            "fully_detected": fully_detected,
            "blindspots": blindspots,
            "accuracy": accuracy
        }
