# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_reporter.py
"""
🎨 Renderizador Visual Forense Apolo para o Doxoade Regret.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any
from doxoade.tools.doxcolors import Fore, Style

try:
    from doxoade.commands.regret_systems.regret_lua_inspector import RegretFinding
except ImportError:
    from .regret_lua_inspector import RegretFinding


class RegretReporter:
    """Formata e renderiza os laudos de regressão no terminal."""

    @staticmethod
    def render_file_report(
        file_path: Path,
        revision: str,
        findings: List[RegretFinding],
        verbose: bool = True
    ) -> None:
        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"📉 DOXOADE REGRET AUDIT — [{file_path.name}] contra [{revision}]")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Arquivo:{Fore.RESET} {file_path}")
        print(f"  {Fore.WHITE}Status:{Fore.RESET} ", end="")

        real_regressions = [f for f in findings if f.severity in ("critical", "high")]
        volatiles = [f for f in findings if f.severity == "medium" and f.category == "VOLATILE_MUTATION"]
        ux_findings = [f for f in findings if f.category in ("UX_BUTTON_LOST", "UX_DEFAULT_CHANGED", "MODIFIED_MODERATE")]
        relocations = [f for f in findings if f.severity in ("info", "low") and f not in ux_findings]

        if not real_regressions and not volatiles and not relocations and not ux_findings:
            print(f"{Fore.GREEN}{Style.BRIGHT}✔ NENHUMA REGRESSÃO DETECTADA (Contratos íntegros){Style.RESET_ALL}\n")
            return

        if not real_regressions:
            status_parts = []
            if relocations:
                status_parts.append(f"{len(relocations)} relocações saudáveis")
            if volatiles:
                status_parts.append(f"{Fore.YELLOW}{len(volatiles)} funções instáveis/mutadas{Fore.RESET}")
            if ux_findings:
                status_parts.append(f"{Fore.CYAN}{len(ux_findings)} ajustes de UX{Fore.RESET}")
            print(f"{Fore.GREEN}{Style.BRIGHT}✔ REFATORAÇÃO LIMPA{Style.RESET_ALL} ({', '.join(status_parts)})\n")
        else:
            crit_count = sum(1 for f in real_regressions if f.severity == "critical")
            high_count = sum(1 for f in real_regressions if f.severity == "high")
            print(f"{Fore.RED}{Style.BRIGHT}⚠ {len(real_regressions)} REGRESSÃO(ÕES) REAL(IS){Style.RESET_ALL} "
                  f"({Fore.RED}{crit_count} Críticas{Fore.RESET}, {Fore.YELLOW}{high_count} Altas{Fore.RESET})\n")

        for idx, finding in enumerate(findings, start=1):
            if finding.severity == "critical":
                sev_badge = f"{Fore.RED}[CRÍTICA]{Fore.RESET}"
                cat_color = Fore.RED
            elif finding.severity == "high":
                sev_badge = f"{Fore.YELLOW}[ALTA]{Fore.RESET}"
                cat_color = Fore.YELLOW
            elif finding.category == "VOLATILE_MUTATION":
                sev_badge = f"{Fore.YELLOW}[INSTÁVEL/VOLÁTIL]{Fore.RESET}"
                cat_color = Fore.YELLOW
            elif finding.category.startswith("UX_"):
                sev_badge = f"{Fore.MAGENTA}[UX/LAYOUT]{Fore.RESET}"
                cat_color = Fore.MAGENTA
            elif finding.category == "MODIFIED_MODERATE":
                sev_badge = f"{Fore.WHITE}[MODERADA]{Fore.RESET}"
                cat_color = Fore.WHITE
            else:
                sev_badge = f"{Fore.CYAN}[RELOCADO/INFO]{Fore.RESET}"
                cat_color = Fore.CYAN

            print(f"  {cat_color}▶ #{idx} {sev_badge} {Style.BRIGHT}{finding.category}:{Style.RESET_ALL} {finding.identifier}")
            print(f"     {Fore.LIGHTBLACK_EX}├─ [O QUÊ?]    :{Fore.RESET} {finding.impact_description}")
            print(f"     {Fore.LIGHTBLACK_EX}├─ [QUEM/ONDE?] :{Fore.RESET} {file_path.name} (Símbolo: {finding.identifier})")
            print(f"     {Fore.LIGHTBLACK_EX}├─ [MITIGAÇÃO] :{Fore.RESET} {Fore.GREEN}{finding.mitigation_hint}{Fore.RESET}")

            if verbose and finding.snippet_lost and finding.severity in ("critical", "high"):
                print(f"     {Fore.CYAN}┌─ [CÓDIGO EXTIRPADO NA REFATORAÇÃO]{Fore.RESET}")
                for line in finding.snippet_lost.splitlines()[:5]:
                    print(f"     {Fore.RED} - {line}{Fore.RESET}")
                print(f"     {Fore.CYAN}└{'─' * 60}{Fore.RESET}")
            print()

    @staticmethod
    def render_summary(total_files: int, total_real_regressions: int, total_relocations: int = 0, total_volatiles: int = 0, total_ux: int = 0) -> None:
        print(f"{'═' * 75}")
        if total_real_regressions == 0:
            notes = []
            if total_relocations > 0:
                notes.append(f"{total_relocations} relocações saudáveis")
            if total_volatiles > 0:
                notes.append(f"{total_volatiles} funções instáveis")
            if total_ux > 0:
                notes.append(f"{total_ux} ajustes de UX auditados")
            note_str = f" ({', '.join(notes)})" if notes else ""
            print(f"{Fore.GREEN}{Style.BRIGHT}🏆 NENHUMA PERDA DE CAPACIDADES EM {total_files} ARQUIVO(S){note_str}.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}{Style.BRIGHT}💥 TOTAL DE REGRESSÕES REAIS: {total_real_regressions} EM {total_files} ARQUIVO(S).{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Dica: Verifique os laudos antes de commitar ou use '--dump' para salvar os trechos.{Fore.RESET}")
        print(f"{'═' * 75}\n")
