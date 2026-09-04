# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_chaos.py
# -*- coding: utf-8 -*-
""" Motor de Caos e Prova de Sensibilidade para o Lite XL (Typhon Doxly Edition - Calibrado).
Contem os 12 injetores completos para validacao empirica da sensibilidade dos sensores. """

from __future__ import annotations
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = NORMAL = ""

from .doxly_tree import DOXLY_TREE
from .doxly_probes import run_all_doxly_probes


DOXLY_INJECTORS: Dict[str, Callable[[Path], str]] = {}


def doxly_injector(fmid: str):
    """Decorator que associa uma funcao de injecao de falha a um FailureMode da DOXLY_TREE."""
    def decorator(fn: Callable[[Path], str]):
        DOXLY_INJECTORS[fmid] = fn
        return fn
    return decorator


# =============================================================================
# CATALOGO COMPLETO DOS 12 INJETORES DE CAOS
# =============================================================================

# --- 1. Sintaxe & Tokenizer ---

@doxly_injector("doxly.tokenizer.nil_compare")
def _inj_tokenizer_nil(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local tokenizer = require "core.tokenizer"
    pcall(tokenizer.tokenize, nil, nil, nil)
    core.log("💥 [CHAOS] Tokenizer nil compare disparado.")
end)
"""


@doxly_injector("doxly.tokenizer.invalid_state")
def _inj_tokenizer_invalid_state(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local tokenizer = require "core.tokenizer"
    local syn = (require("core.syntax")).plain_text_syntax
    pcall(tokenizer.tokenize, syn, "linha de teste", 9999)
    core.log("💥 [CHAOS] Tokenizer number state disparado.")
end)
"""


@doxly_injector("doxly.syntax.corrupted_pattern")
def _inj_syntax_corrupted_pattern(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local syntax = require "core.syntax"
    syntax.add {
        name = "Corrupted Pattern Test",
        files = { "%.chaos$" },
        patterns = {
            { pattern = nil, type = "keyword" },
            { pattern = { 123, 456 }, type = "string" }
        }
    }
    core.log("💥 [CHAOS] Syntax com pattern corrompido adicionada.")
end)
"""


@doxly_injector("doxly.syntax.binary_raw_highlight")
def _inj_binary_lua_doc(sandbox_dir: Path) -> str:
    test_bin = sandbox_dir / "bytecode_test.lua"
    test_bin.write_bytes(b"\x1bLua\x54\x00\x19\x93\r\n\x1a\n\x00\x00\x00\x00")
    return f"""
core.add_thread(function()
    coroutine.yield(0.5)
    local doc = core.open_doc({repr(str(test_bin))})
    if doc then core.root_view:open_doc(doc) end
    core.log("💥 [CHAOS] Buffer binario aberto no editor.")
end)
"""


# --- 2. Renderizador, Layout & Views ---

@doxly_injector("doxly.docview.nil_highlighter")
def _inj_docview_nil_highlighter(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local doc = core.open_doc()
    if doc then
        core.root_view:open_doc(doc)
        doc.highlighter = nil
        core.redraw = true
        core.log("💥 [CHAOS] active_doc.highlighter anulado.")
    end
end)
"""


@doxly_injector("doxly.node.orphan_view")
def _inj_orphan_view(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local node = core.root_view and core.root_view:get_active_node()
    if node and node.views then
        table.insert(node.views, { doc = nil, position = {x=0, y=0}, size = {x=100, y=100} })
        core.redraw = true
        core.log("💥 [CHAOS] View orfa injetada no no ativo.")
    end
end)
"""


# --- 3. Configuracao & Plugins Nativos ---

@doxly_injector("doxly.settings.nil_table_index")
def _inj_settings_nil_table(sandbox_dir: Path) -> str:
    user_settings = sandbox_dir / "user_settings.lua"
    user_settings.write_text("-- user_settings sem return de tabela\nlocal x = 1\n", encoding="utf-8")
    return """
core.log("💥 [CHAOS] user_settings.lua corrompido em disco.")
"""


@doxly_injector("doxly.config.missing_user_settings")
def _inj_missing_user_settings(sandbox_dir: Path) -> str:
    user_settings = sandbox_dir / "user_settings.lua"
    if user_settings.exists():
        user_settings.unlink()
    return """
core.log("💥 [CHAOS] user_settings.lua deletado do sandbox.")
"""


# --- 4. Runtime, Corrotinas & Processo ---

@doxly_injector("doxly.khonsu.coroutine_budget_spike")
def _inj_khonsu_budget_spike(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local t0 = os.clock()
    while (os.clock() - t0) < 0.050 do
        local _ = math.sqrt(os.clock())
    end
    core.log("💥 [CHAOS] Thread bloqueante de 50ms concluida.")
end)
"""


@doxly_injector("doxly.process.ghost_zombie")
def _inj_ghost_zombie(sandbox_dir: Path) -> str:
    ipc_file = sandbox_dir / ".ipc_queue"
    ipc_file.write_text("__DOXOADE_ZOMBIE_LOCK__\n", encoding="utf-8")
    return """
core.log("💥 [CHAOS] Fila IPC bloqueada por processo zumbi simulado.")
"""


# --- 5. Contratos de API & Monkey-Patches ---

@doxly_injector("doxly.api.missing_critical_symbol")
def _inj_missing_critical_symbol(sandbox_dir: Path) -> str:
    probe_dir = sandbox_dir / ".doxoade" / "api_guard"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_json = probe_dir / "runtime_probe.json"
    dummy_report = {
        "summary": {"present": 7, "missing": 1, "type_mismatch": 0, "total": 8},
        "apis": {
            "RootView.draw": {
                "status": "missing",
                "expected_type": "function",
                "severity": "critical"
            }
        }
    }
    probe_json.write_text(json.dumps(dummy_report), encoding="utf-8")
    return """
core.log("💥 [CHAOS] Simbolo critico ausente simulado em runtime_probe.json.")
"""


@doxly_injector("doxly.api.patch_nil_target")
def _inj_api_patch_nil_target(sandbox_dir: Path) -> str:
    return """
core.add_thread(function()
    coroutine.yield(0.5)
    local API = rawget(_G, "DOXOADE_API")
    if API and API.patch then
        API.patch({
            id = "chaos:ghost_method",
            target = require("core"),
            method = "this_symbol_does_not_exist_at_all",
            wrapper = function(orig, self, ...) return orig(self, ...) end
        })
    end
    core.log("💥 [CHAOS] API.patch aplicado em simbolo inexistente.")
end)
"""


# =============================================================================
# EXECUTOR DA SUITE DE CAOS
# =============================================================================

def _kill_existing_instances():
    """Encerra processos do Lite XL para garantir sandbox limpo."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/IM", "lite-xl.exe"], capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "lite-xl"], capture_output=True)
    time.sleep(0.3)


def execute_chaos_vector(
    fmid: str,
    sandbox_dir: Path,
    timeout: float = 2.5,
) -> Dict[str, Any]:
    """Executa um vetor de caos especifico no sandbox e verifica a deteccao."""
    fm = DOXLY_TREE.get_by_id(fmid)
    if not fm:
        return {"fmid": fmid, "status": "UNKNOWN_FMID", "detected": False, "evidence": ""}

    injector_fn = DOXLY_INJECTORS.get(fmid)
    if not injector_fn:
        return {"fmid": fmid, "status": "NO_INJECTOR", "detected": False, "evidence": "Sem injetor registrado"}

    # 1. Preparacao do Sandbox
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    for art in ["session_log.txt", "error.txt"]:
        p = sandbox_dir / art
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    payload_lua = injector_fn(sandbox_dir)

    from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
    from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine

    base_init = LiteXLInitBuilder.generate_sovereign_init()
    sandbox_init = sandbox_dir / "init.lua"
    sandbox_init.write_text(f"{base_init}\n\n-- 🍷 TYPHON CHAOS VECTOR [{fmid}]\n{payload_lua}\n", encoding="utf-8")

    exe = LiteXLEngine.find_executable()
    if not exe:
        matches = DOXLY_TREE.scan_text(payload_lua)
        detected = any(m[0].id == fmid for m in matches)
        return {
            "fmid": fmid,
            "status": "DETECTED_MOCK" if detected else "SILENT_MOCK",
            "detected": detected,
            "evidence": "Avaliacao estatica (sem binario)",
        }

    # 2. Execucao Supervisionada
    _kill_existing_instances()
    env = os.environ.copy()
    env["LITE_USERDIR"] = str(sandbox_dir)
    env["XDG_CONFIG_HOME"] = str(sandbox_dir.parent)

    CREATE_NEW_CONSOLE = 0x00000010 if sys.platform == "win32" else 0
    start_t = time.time()
    proc = subprocess.Popen(
        [str(exe)],
        env=env,
        creationflags=CREATE_NEW_CONSOLE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(timeout)
    if proc.poll() is None:
        proc.kill()
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass

    # 3. Extracao e Avaliacao Forense
    session_file = sandbox_dir / "session_log.txt"
    error_file = sandbox_dir / "error.txt"

    session_text = session_file.read_text(encoding="utf-8", errors="replace") if session_file.exists() else ""
    error_text = error_file.read_text(encoding="utf-8", errors="replace") if error_file.exists() else ""
    combined_logs = f"{error_text}\n{session_text}"

    # Verificacao 1: Tree Matches
    tree_matches = DOXLY_TREE.scan_text(combined_logs)
    matched_this_fmid = any(m[0].id == fmid for m in tree_matches)

    # Verificacao 2: Probes Vivos
    probe_report = run_all_doxly_probes(sandbox_dir, verbose=False)
    probe_caught = any(p.failure_mode_id == fmid for p in probe_report.findings)

    detected = matched_this_fmid or probe_caught
    evidence = ""
    if matched_this_fmid:
        evidence = next(m[1] for m in tree_matches if m[0].id == fmid)[:100]
    elif probe_caught:
        evidence = next(p.message for p in probe_report.findings if p.failure_mode_id == fmid)[:100]

    return {
        "fmid": fmid,
        "name": fm.name,
        "severity": fm.severity,
        "status": "DETECTABLE" if detected else "SILENT",
        "detected": detected,
        "evidence": evidence,
        "duration_s": round(time.time() - start_t, 2),
    }


def run_doxly_chaos_suite(
    sandbox_dir: Optional[Path] = None,
    verbose: bool = True,
    filter_subsystem: Optional[str] = None,
) -> Dict[str, Any]:
    """Executa a bateria de sensibilidade contra todos os 12 modos da DOXLY_TREE."""
    if sandbox_dir is None:
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        sandbox_dir = LiteXLPaths.get_sandbox_dir()

    if verbose:
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}🌀 TYPHON DOXLY CHAOS SUITE — Prova de Sensibilidade (Calibrada){Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Sandbox:{Fore.RESET} {sandbox_dir}\n")

    results: List[Dict[str, Any]] = []
    detectable = silent = no_injector = 0

    for fmid, fm in DOXLY_TREE.failures.items():
        if filter_subsystem and fm.subsystem != filter_subsystem:
            continue

        if fmid not in DOXLY_INJECTORS:
            no_injector += 1
            results.append({
                "fmid": fmid,
                "name": fm.name,
                "status": "NO_INJECTOR",
                "detected": False,
                "evidence": "Aguardando implementacao de injetor.",
            })
            if verbose:
                print(f"  {Fore.LIGHTBLACK_EX}⚪ {fmid:<38} [SEM INJETOR]{Fore.RESET}")
            continue

        res = execute_chaos_vector(fmid, sandbox_dir)
        results.append(res)

        if res["detected"]:
            detectable += 1
            if verbose:
                print(f"  {Fore.GREEN}✔ {fmid:<38} [DETECTAVEL]{Fore.RESET}")
                if res["evidence"]:
                    print(f"     {Fore.LIGHTBLACK_EX}↳ Evidencia: '{res['evidence']}'{Fore.RESET}")
        else:
            silent += 1
            if verbose:
                print(f"  {Fore.RED}🛑 {fmid:<38} [SILENCIOSA — FALHA DE SENSOR!]{Fore.RESET}")

    total = len(results)
    sensitivity_rate = (detectable / (detectable + silent) * 100) if (detectable + silent) > 0 else 0.0

    if verbose:
        color = Fore.GREEN if silent == 0 else Fore.YELLOW
        print(f"\n{color}{Style.BRIGHT}📊 RESUMO DE SENSIBILIDADE DOXLY:{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Total Avaliado:{Fore.RESET} {total} modos de falha")
        print(f"  {Fore.GREEN}Detectaveis:{Fore.RESET} {detectable} | {Fore.RED}Silenciosas:{Fore.RESET} {silent} | "
              f"{Fore.LIGHTBLACK_EX}Sem Injetor:{Fore.RESET} {no_injector}")
        print(f"  {Fore.CYAN}Taxa de Cobertura Sensorial:{Fore.RESET} {Style.BRIGHT}{sensitivity_rate:.1f}%{Style.RESET_ALL}\n")

    return {
        "total": total,
        "detectable": detectable,
        "silent": silent,
        "no_injector": no_injector,
        "sensitivity_rate_pct": sensitivity_rate,
        "results": results,
    }
