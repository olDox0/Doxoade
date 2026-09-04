# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_stress_pack.py
# -*- coding: utf-8 -*-
"""
Pacote de Testes de Estresse e Erros Propositais Compostos (Typhon Doxly Stress Pack).
Injeta cenários de falha combinada (Multi-Vector Chaos) para provar a capacidade do sistema
de desentrelaçar e mitigar falhas simultâneas em produção.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from .doxly_tree import DOXLY_TREE
from .doxly_probes import run_all_doxly_probes
from .doxly_triangulator import DoxlyTriangulator


@dataclass
class StressScenario:
    """Cenário de estresse composto."""
    id: str
    name: str
    description: str
    vectors: List[str]
    payload_builder: Any


@dataclass
class StressPackReport:
    """Relatório consolidado de sobrevivência e precisão sob estresse composto."""
    total_scenarios: int = 0
    survived: int = 0
    crashed: int = 0
    triangulation_accuracy: float = 0.0
    auto_repair_success: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# DEFINIÇÃO DOS CENÁRIOS DE FALHA COMPOSTA
# =============================================================================

STRESS_SCENARIOS: List[StressScenario] = [
    StressScenario(
        id="STRESS_COMPOUND_01_SYNTAX_CONFIG",
        name="Colapso de Sintaxe + Corrupção de Configuração",
        description="Abre buffer de bytecode binário enquanto user_settings.lua está corrompido sem return.",
        vectors=["doxly.syntax.binary_raw_highlight", "doxly.settings.nil_table_index"],
        payload_builder=lambda sandbox: """
-- Injeta user_settings corrompido
local f = io.open(USERDIR .. "/user_settings.lua", "w")
if f then f:write("-- sem tabela\\nlocal a = 1\\n") f:close() end

-- Injeta e abre arquivo binário
local bin_file = USERDIR .. "/corrupted_chunk.lua"
local bf = io.open(bin_file, "wb")
if bf then bf:write("\\x1bLua\\x54\\x00\\x19\\x93\\r\\n\\x1a\\n\\x00\\x00") bf:close() end

core.add_thread(function()
    coroutine.yield(0.5)
    local doc = core.open_doc(bin_file)
    if doc then core.root_view:open_doc(doc) end
    core.log("💥 [STRESS_01] Buffer binário e config corrompida armados.")
end)
"""
    ),
    StressScenario(
        id="STRESS_COMPOUND_02_RENDER_ORPHAN_BUDGET",
        name="Injeção de View Órfã + Estouro de Corrotina Khonsu",
        description="Injeta view sem métodos de contrato na árvore e dispara thread bloqueante de 50ms simultaneamente.",
        vectors=["doxly.node.orphan_view", "doxly.khonsu.coroutine_budget_spike"],
        payload_builder=lambda sandbox: """
core.add_thread(function()
    coroutine.yield(0.5)
    -- Injeta view órfã
    local node = core.root_view and core.root_view:get_active_node()
    if node and node.views then
        table.insert(node.views, { doc = nil, position = {x=0, y=0}, size = {x=100, y=100} })
        core.redraw = true
    end
    -- Estouro de corrotina Khonsu
    local t0 = os.clock()
    while (os.clock() - t0) < 0.050 do
        local _ = math.sqrt(os.clock())
    end
    core.log("💥 [STRESS_02] View órfã e thread pesada armadas simultaneamente.")
end)
"""
    ),
    StressScenario(
        id="STRESS_COMPOUND_03_TOKENIZER_API_GHOST",
        name="Tokenizer Nil + Monkey-Patch em Símbolo Inexistente",
        description="Força passagem de nil para o tokenizer e aplica patch em método fantasma.",
        vectors=["doxly.tokenizer.nil_compare", "doxly.api.patch_nil_target"],
        payload_builder=lambda sandbox: """
core.add_thread(function()
    coroutine.yield(0.5)
    -- Tokenizer nil
    pcall((require("core.tokenizer")).tokenize, nil, nil, nil)
    -- Monkey-patch em nil
    local API = rawget(_G, "DOXOADE_API")
    if API and API.patch then
        API.patch({
            id = "stress:ghost_patch",
            target = require("core"),
            method = "this_method_does_not_exist_at_all",
            wrapper = function(orig, self, ...) return orig(self, ...) end
        })
    end
    core.log("💥 [STRESS_03] Tokenizer nil e API patch fantasma disparados.")
end)
"""
    ),
]


# =============================================================================
# EXECUTOR DO PACOTE DE ESTRESSE
# =============================================================================

def run_stress_pack(sandbox_dir: Optional[Path] = None, verbose: bool = True) -> StressPackReport:
    """Executa a bateria de cenários de estresse composto e triangula a sobrevivência."""
    if sandbox_dir is None:
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        sandbox_dir = LiteXLPaths.get_sandbox_dir()

    from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
    from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

    if verbose:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"🔥 TYPHON DOXLY STRESS PACK — Pacote de Erros Propositais Compostos")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Sandbox:{Fore.RESET} {sandbox_dir}")
        print(f"  {Fore.WHITE}Cenários Planejados:{Fore.RESET} {len(STRESS_SCENARIOS)}\n")

    report = StressPackReport(total_scenarios=len(STRESS_SCENARIOS))
    detected_count = 0

    for scenario in STRESS_SCENARIOS:
        if verbose:
            print(f"  {Fore.YELLOW}▶ Executando [{scenario.id}]:{Fore.RESET} {Style.BRIGHT}{scenario.name}{Style.RESET_ALL}")
            print(f"     {Fore.LIGHTBLACK_EX}↳ {scenario.description}{Fore.RESET}")

        # 1. Prepara Sandbox com o Payload Composto
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        for art in ["session_log.txt", "error.txt"]:
            p = sandbox_dir / art
            if p.exists():
                try: p.unlink()
                except Exception: pass

        base_init = LiteXLInitBuilder.generate_sovereign_init()
        compound_payload = scenario.payload_builder(sandbox_dir)
        sandbox_init = sandbox_dir / "init.lua"
        sandbox_init.write_text(f"{base_init}\n\n-- 🔥 STRESS PACK [{scenario.id}]\n{compound_payload}\n", encoding="utf-8")

        # 2. Executa Lite XL
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
        time.sleep(0.3)

        exe = LiteXLEngine.find_executable()
        env = os.environ.copy()
        env["LITE_USERDIR"] = str(sandbox_dir)
        env["XDG_CONFIG_HOME"] = str(sandbox_dir.parent)

        CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
        proc = subprocess.Popen([str(exe)], env=env, creationflags=CREATE_NEW_CONSOLE)
        time.sleep(3.0)

        crashed = proc.poll() is not None
        if not crashed:
            proc.kill()
            try: proc.wait(timeout=1.0)
            except Exception: pass

        # 3. Triangulação de 3 Vias do Cenário
        verdict = DoxlyTriangulator.triangulate(user_dir=sandbox_dir, run_probes=True)
        triangulated = not verdict.is_healthy

        if not crashed:
            report.survived += 1
            status_badge = f"{Fore.GREEN}✔ SOBREVIVEU{Fore.RESET}"
        else:
            report.crashed += 1
            status_badge = f"{Fore.RED}💥 CRASHOU{Fore.RESET}"

        if triangulated:
            detected_count += 1
            diag_badge = f"{Fore.GREEN}[Triangulado: {verdict.confidence_score*100:.0f}%]{Fore.RESET}"
        else:
            diag_badge = f"{Fore.YELLOW}[Não Triangulado]{Fore.RESET}"

        if verbose:
            print(f"     Status: {status_badge} | Diagnóstico: {diag_badge}")
            if verdict.root_cause:
                print(f"     {Fore.CYAN}↳ Causa Raiz Identificada:{Fore.RESET} {verdict.root_cause.name}")
            print()

        report.results.append({
            "scenario_id": scenario.id,
            "name": scenario.name,
            "survived": not crashed,
            "triangulated": triangulated,
            "verdict": verdict,
        })

    report.triangulation_accuracy = (detected_count / report.total_scenarios) * 100

    if verbose:
        print(f"{'═' * 75}")
        print(f"{Fore.CYAN}{Style.BRIGHT}📊 RELATÓRIO DO PACOTE DE ESTRESSE:{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Cenários Avaliados:{Fore.RESET} {report.total_scenarios}")
        print(f"  {Fore.GREEN}Sobrevivências:{Fore.RESET} {report.survived}/{report.total_scenarios} "
              f"| {Fore.RED}Crashes:{Fore.RESET} {report.crashed}")
        print(f"  {Fore.CYAN}Acurácia da Triangulação:{Fore.RESET} {Style.BRIGHT}{report.triangulation_accuracy:.1f}%{Style.RESET_ALL}\n")

    return report
