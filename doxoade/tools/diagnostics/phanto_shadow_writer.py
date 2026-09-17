# -*- coding: utf-8 -*-
# doxoade/tools/diagnostics/phanto_shadow_writer.py
"""
👻 PHANTO SHADOW WRITER & ANALYZER V2.1 — Multi-Mode (Production/Test/Sandbox).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ""


@dataclass
class PhantoIncident:
    ts: int
    ts_iso: str
    module: str
    error: str
    traceback: str
    context: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PhantoIncident:
        return cls(
            ts=int(data.get("ts", 0)),
            ts_iso=str(data.get("ts_iso", "")),
            module=str(data.get("module", "unknown")),
            error=str(data.get("error", "")),
            traceback=str(data.get("traceback", "")),
            context=str(data.get("context", "")),
        )


class PhantoShadowWriter:
    MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB

    @classmethod
    def get_ndjson_path(cls, user_dir: Optional[Path] = None, mode: str = "production") -> Path:
        """Resolve o caminho do arquivo NDJSON considerando o modo (production, test, sandbox)."""
        if user_dir is None:
            from doxoade.commands.lite_xl_systems.typhon_deploy import TyphonDeployEngine
            deploy_dir = TyphonDeployEngine._get_deploy_dir(mode)
        else:
            deploy_dir = user_dir

        diag_dir = deploy_dir / ".doxoade" / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        return diag_dir / "phanto_crisis.ndjson"

    @classmethod
    def rotate_if_oversized(cls, ndjson_path: Path) -> bool:
        if not ndjson_path.exists():
            return False
        try:
            if ndjson_path.stat().st_size > cls.MAX_FILE_BYTES:
                bak_path = ndjson_path.with_suffix(".ndjson.bak")
                if bak_path.exists():
                    bak_path.unlink()
                ndjson_path.rename(bak_path)
                return True
        except Exception:
            pass
        return False

    @classmethod
    def read_incidents(cls, limit: int = 50, ndjson_path: Optional[Path] = None) -> List[PhantoIncident]:
        path = ndjson_path or cls.get_ndjson_path()
        if not path.exists():
            return []

        incidents: List[PhantoIncident] = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    line = line.strip()
                    if line:
                        try:
                            payload = json.loads(line)
                            incidents.append(PhantoIncident.from_dict(payload))
                        except Exception:
                            continue
        except Exception:
            pass
        return incidents

    @classmethod
    def render_cli_report(cls, mode: str = "production", limit: int = 20, verbose: bool = False) -> None:
        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass

        ndjson_path = cls.get_ndjson_path(mode=mode)
        cls.rotate_if_oversized(ndjson_path)
        incidents = cls.read_incidents(limit=limit, ndjson_path=ndjson_path)

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"👻 PHANTO-CRISIS — LAUDO FORENSE DE ERROS [{mode.upper()}]")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Arquivo Alvo:{Fore.RESET} {ndjson_path}")
        print(f"  {Fore.WHITE}Total Inspecionado:{Fore.RESET} {len(incidents)} eventos recentes\n")

        if not incidents:
            print(f"  {Fore.GREEN}✔ Nenhum incidente registrado no ambiente [{mode}].{Fore.RESET}")
            print(f"  {Fore.LIGHTBLACK_EX}↳ O buffer está limpo ou o editor não capturou falhas.{Fore.RESET}\n")
            return

        module_counts: Dict[str, int] = {}
        for inc in incidents:
            module_counts[inc.module] = module_counts.get(inc.module, 0) + 1

        print(f"  {Fore.MAGENTA}📊 DISTRIBUIÇÃO POR MÓDULO:{Fore.RESET}")
        for mod, cnt in sorted(module_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"     ├─ {Style.BRIGHT}{mod:<30}{Style.RESET_ALL} : {Fore.YELLOW}{cnt} falha(s){Fore.RESET}")
        print()

        print(f"  {Fore.RED}📋 ÚLTIMOS INCIDENTES:{Fore.RESET}")
        for idx, inc in enumerate(incidents, 1):
            print(f"  {Fore.WHITE}[{idx:02d}] [{inc.ts_iso}] {Fore.CYAN}{Style.BRIGHT}{inc.module}{Style.RESET_ALL}")
            print(f"       {Fore.LIGHTRED_EX}Erro:{Fore.RESET} {inc.error}")
            if inc.context and inc.context != "nil":
                print(f"       {Fore.LIGHTBLACK_EX}Contexto:{Fore.RESET} {inc.context}")
            if verbose and inc.traceback:
                print(f"       {Fore.LIGHTBLACK_EX}Stacktrace:{Fore.RESET}")
                for tb_line in inc.traceback.strip().splitlines()[:5]:
                    print(f"         {Fore.LIGHTBLACK_EX}↳ {tb_line}{Fore.RESET}")
            print()

if __name__ == "__main__":
    mode_arg = "production"
    should_clear = False

    for i, a in enumerate(sys.argv):
        if a in ("--mode", "-m") and i + 1 < len(sys.argv):
            mode_arg = sys.argv[i + 1].lower()
        elif a in ("--test", "-t"):
            mode_arg = "test"
        elif a in ("--sandbox", "-s"):
            mode_arg = "sandbox"
        elif a in ("--clear", "-c"):
            should_clear = True

    target_ndjson = PhantoShadowWriter.get_ndjson_path(mode=mode_arg)

    if should_clear:
        if target_ndjson.exists():
            target_ndjson.unlink()
            bak = target_ndjson.with_suffix(".ndjson.bak")
            if bak.exists():
                bak.unlink()
            print(f"{Fore.GREEN}✔ Histórico de incidentes Phanto-Crisis [{mode_arg.upper()}] foi limpo com sucesso.{Fore.RESET}\n")
        else:
            print(f"{Fore.YELLOW}ℹ Nenhum arquivo de incidentes para limpar em [{mode_arg.upper()}].{Fore.RESET}\n")
        sys.exit(0)

    is_verbose = "--verbose" in sys.argv or "-v" in sys.argv
    PhantoShadowWriter.render_cli_report(mode=mode_arg, limit=30, verbose=is_verbose)
