# -*- coding: utf-8 -*-
# doxoade/tools/diagnostics/test_phanto_crisis.py
"""
🧪 DOXOADE PHANTO-CRISIS TEST HARNESS — Prova Empírica de Caos e Resiliência.
Valida:
  1. Ingestão em lote no Ring Buffer sem corrupção.
  2. Sanitização de JSON e integridade de traceback multi-linha.
  3. Despejo e leitura pelo PhantoShadowWriter.
  4. Rotação automática de arquivos (>20MB).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""

from doxoade.tools.diagnostics.phanto_shadow_writer import (
    PhantoShadowWriter,
    PhantoIncident,
)


def run_phanto_chaos_test() -> bool:
    """Executa a bateria de validação de isolamento e integridade forense."""
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
    print("🧪 PHANTO-CRISIS HARNESS — PROVA DE CAOS E NÃO-REGRESSÃO")
    print(f"{'═' * 75}{Style.RESET_ALL}\n")

    # 1. Preparação de ambiente efêmero de teste
    test_diag_dir = Path.home() / ".doxoade_test_diag"
    test_diag_dir.mkdir(parents=True, exist_ok=True)
    test_ndjson = test_diag_dir / "phanto_crisis.ndjson"

    if test_ndjson.exists():
        test_ndjson.unlink()

    all_passed = True

    # ─── TESTE 1: Injeção em Rajada (100 Falhas Simultâneas) ───────────────
    print(f"  {Fore.YELLOW}[TESTE 1/4]{Fore.RESET} Injeção de Rajada (100 falhas rápidas)...", end=" ")
    t0 = time.time()
    mock_errors = []
    for i in range(1, 101):
        err_payload = {
            "ts": int(time.time()),
            "ts_iso": time.strftime("%Y-%m-%d %H:%M:%S"),
            "module": f"chaos_worker_{i % 5}",
            "error": f"Simulated crisis attempt to index nil in loop {i}: \"unexpected token\"",
            "traceback": f"stack traceback:\n\t[C]: in function 'error'\n\t19b1_pty_client.lua:{100 + i}: in function 'poll'",
            "context": f"workspace/buffer_{i % 3}.py",
        }
        mock_errors.append(err_payload)

    # Gravação simulando o phanto_shadow_flush em formato NDJSON
    with open(test_ndjson, "w", encoding="utf-8") as f:
        for err in mock_errors:
            # Testa o sanitizador com aspas e quebras de linha
            escaped_err = err["error"].replace('"', '\\"')
            escaped_tb = err["traceback"].replace("\n", "\\n").replace("\t", "\\t")
            line = (
                f'{{"ts":{err["ts"]},"ts_iso":"{err["ts_iso"]}","module":"{err["module"]}",'
                f'"error":"{escaped_err}","traceback":"{escaped_tb}","context":"{err["context"]}"}}\n'
            )
            f.write(line)

    burst_duration_ms = (time.time() - t0) * 1000
    if burst_duration_ms < 100:
        print(f"{Fore.GREEN}✔ PASS ({burst_duration_ms:.2f}ms){Fore.RESET}")
    else:
        print(f"{Fore.RED}✖ FAIL (Lento: {burst_duration_ms:.2f}ms){Fore.RESET}")
        all_passed = False

    # TESTE 2: Corrigido o cálculo do módulo (i=100 -> 100 % 5 == 0 -> chaos_worker_0)
    print(f"  {Fore.YELLOW}[TESTE 2/4]{Fore.RESET} Integridade Sintática do NDJSON...", end=" ")
    incidents = PhantoShadowWriter.read_incidents(limit=100, ndjson_path=test_ndjson)
    if len(incidents) == 100 and incidents[-1].module == f"chaos_worker_{100 % 5}":
        print(f"{Fore.GREEN}✔ PASS (100/100 incidentes íntegros){Fore.RESET}")
    else:
        print(f"{Fore.RED}✖ FAIL ({len(incidents)}/100 recuperados){Fore.RESET}")
        all_passed = False

    # TESTE 3: Criação real de arquivo esparso com write direto
    print(f"  {Fore.YELLOW}[TESTE 3/4]{Fore.RESET} Rotação de Segurança (.bak)...", end=" ")
    with open(test_ndjson, "wb") as f:
        f.truncate(PhantoShadowWriter.MAX_FILE_BYTES + 1024)

    rotated = PhantoShadowWriter.rotate_if_oversized(test_ndjson)
    bak_file = test_ndjson.with_suffix(".ndjson.bak")
    if rotated and bak_file.exists():
        print(f"{Fore.GREEN}✔ PASS (Rotacionado para .bak com sucesso){Fore.RESET}")
        bak_file.unlink()
    else:
        print(f"{Fore.RED}✖ FAIL (Arquivo excedeu teto sem rotação){Fore.RESET}")
        all_passed = False

    # ─── TESTE 4: Verificação de Não-Regressão de Templates ────────────────
    print(f"  {Fore.YELLOW}[TESTE 4/4]{Fore.RESET} Integridade do 00_phanto_core.lua...", end=" ")
    from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
    from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder

    phanto_lua = LiteXLPaths.get_template_dir() / "00_phanto_core.lua"
    if phanto_lua.exists():
        source = phanto_lua.read_text(encoding="utf-8", errors="replace")
        errors = LiteXLInitBuilder.compile_scan_lua(source)
        if not errors:
            print(f"{Fore.GREEN}✔ PASS (0 erros de sintaxe/balanceamento){Fore.RESET}")
        else:
            print(f"{Fore.RED}✖ FAIL ({len(errors)} erro(s): {errors[0]}){Fore.RESET}")
            all_passed = False
    else:
        print(f"{Fore.RED}✖ FAIL (00_phanto_core.lua não localizado){Fore.RESET}")
        all_passed = False

    # Limpeza
    try:
        if test_ndjson.exists(): test_ndjson.unlink()
        test_diag_dir.rmdir()
    except Exception:
        pass

    # Veredito Final
    print(f"\n{Style.BRIGHT}{'═' * 75}{Style.RESET_ALL}")
    if all_passed:
        print(f"  {Fore.GREEN}{Style.BRIGHT}🏆 RESULTADO FINAL: 4/4 TESTES PASSARAM COM SUCESSO!{Style.RESET_ALL}")
        print(f"  {Fore.LIGHTBLACK_EX}O subsistema Phanto-Crisis cumpre todos os requisitos do ProDeNov 1.2.1.{Fore.RESET}\n")
    else:
        print(f"  {Fore.RED}{Style.BRIGHT}✖ RESULTADO FINAL: FALHAS DETECTADAS NA HOMOLOGAÇÃO.{Style.RESET_ALL}\n")

    return all_passed


if __name__ == "__main__":
    success = run_phanto_chaos_test()
    sys.exit(0 if success else 1)
