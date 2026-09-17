# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_reporter.py
"""
🎨 Renderizador Visual Forense Apolo para o Doxoade Regret.
Fase 3: Suporte a Badges Visuais de Proveniência, Linhagem Histórica, Orfandade e Snippets.
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Optional

from doxoade.tools.doxcolors import Fore, Style

try:
    from doxoade.commands.regret_systems.regret_lua_inspector import RegretFinding
    from doxoade.commands.regret_systems.regret_provenance import FileOriginMeta
except ImportError:
    from .regret_lua_inspector import RegretFinding
    from .regret_provenance import FileOriginMeta


class RegretReporter:
    """Formata e renderiza os laudos de regressão, orfandade e proveniência no terminal."""

    @staticmethod
    def render_file_report(
        file_path: Path,
        revision: str,
        findings: List[RegretFinding],
        origin_meta: Optional[FileOriginMeta] = None,
        verbose: bool = True,
        show_snippets: bool = False,
    ) -> None:
        if not verbose:
            return
        if not verbose and not findings and not origin_meta:
            return

        real_regressions = [
            f for f in findings
            if f.severity in ("critical", "high")
            and f.category not in ("ORPHAN_COMMAND", "ORPHAN_LOCAL_FUNCTION", "ORPHAN_PYTHON_FUNCTION")
        ]
        ancestral_leaks = [
            f for f in findings
            if f.category in ("SPLIT_CAPABILITY_LEAK", "CONTRACT_ORPHANED_ON_SPLIT", "FORK_DRIFT")
        ]
        orphans = [
            f for f in findings
            if f.category in (
                "ORPHAN_COMMAND",
                "DEAD_KEYMAP",
                "ORPHAN_LOCAL_FUNCTION",
                "ORPHAN_PYTHON_FUNCTION",
                "DISCONNECTED_HANDLER",
            )
        ]
        volatiles = [f for f in findings if f.severity == "medium" and f.category == "VOLATILE_MUTATION"]
        ux_findings = [f for f in findings if f.category in ("UX_BUTTON_LOST", "UX_DEFAULT_CHANGED", "MODIFIED_MODERATE")]
        relocations = [
            f for f in findings
            if f.severity in ("info", "low")
            and f not in ux_findings
            and f not in orphans
            and f not in ancestral_leaks
        ]

        # 🧠 ECONOMIA COGNITIVA: Se o arquivo estiver 100% limpo e sem meta especial, linha discreta
        if not real_regressions and not volatiles and not relocations and not ux_findings and not orphans and not ancestral_leaks and not origin_meta:
            if verbose:
                print(f"  {Fore.GREEN}✔{Fore.RESET} [{file_path.name}] {Fore.LIGHTBLACK_EX}Íntegro (Zero regressões){Fore.RESET}")
            return

        print(f"\n{Fore.CYAN}{Style.BRIGHT}{'═' * 75}")
        print(f"📉 DOXOADE REGRET AUDIT — [{file_path.name}] contra [{revision}]")
        print(f"{'═' * 75}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Arquivo:{Fore.RESET} {file_path}")

        # 🏛️ FASE 3: Painel de Linhagem e Certidão de Nascimento (Provenance Panel)
        if origin_meta:
            print(f"  {Fore.CYAN}🏛️  Linhagem Histórica:{Fore.RESET}")
            if origin_meta.created_commit != "unknown":
                print(f"     ├─ {Fore.LIGHTBLACK_EX}Origem:{Fore.RESET} Criado no commit {Fore.YELLOW}{origin_meta.created_commit}{Fore.RESET} em {origin_meta.created_date} por {Fore.WHITE}{origin_meta.created_author}{Fore.RESET}")
                if origin_meta.initial_commit_msg:
                    print(f"     │  ↳ {Fore.LIGHTBLACK_EX}\"{origin_meta.initial_commit_msg[:60]}...\"{Fore.RESET}")
            if origin_meta.is_split_child:
                parent_status = f"{Fore.GREEN}(Presente no disco){Fore.RESET}" if origin_meta.ancestor_path and origin_meta.ancestor_path.exists() else f"{Fore.YELLOW}(Histórico){Fore.RESET}"
                print(f"     ├─ {Fore.MAGENTA}Ancestralidade:{Fore.RESET} Filho de cisão de {Fore.CYAN}{origin_meta.parent_file_name}{Fore.RESET} {parent_status}")
            if origin_meta.rename_history:
                print(f"     └─ {Fore.LIGHTBLACK_EX}Renames ({len(origin_meta.rename_history)}):{Fore.RESET} {' -> '.join(origin_meta.rename_history[:2])}")

        print(f"  {Fore.WHITE}Status:{Fore.RESET} ", end="")

        if not real_regressions:
            status_parts = []
            if relocations:
                status_parts.append(f"{len(relocations)} relocações saudáveis")
            if volatiles:
                status_parts.append(f"{Fore.YELLOW}{len(volatiles)} funções instáveis/mutadas{Fore.RESET}")
            if ux_findings:
                status_parts.append(f"{Fore.CYAN}{len(ux_findings)} ajustes de UX{Fore.RESET}")
            if orphans:
                status_parts.append(f"{Fore.MAGENTA}{len(orphans)} item(ns) órfão(s){Fore.RESET}")

            print(f"{Fore.GREEN}{Style.BRIGHT}✔ REFATORAÇÃO LIMPA{Style.RESET_ALL} ({', '.join(status_parts)})\n")
        else:
            crit_count = sum(1 for f in real_regressions if f.severity == "critical")
            high_count = sum(1 for f in real_regressions if f.severity == "high")
            print(f"{Fore.RED}{Style.BRIGHT}⚠ {len(real_regressions)} REGRESSÃO(ÕES) REAL(IS){Style.RESET_ALL} "
                  f"({Fore.RED}{crit_count} Críticas{Fore.RESET}, {Fore.YELLOW}{high_count} Altas{Fore.RESET})")
            if ancestral_leaks:
                print(f"      {Fore.RED}↳ {len(ancestral_leaks)} perda(s) de capacidade ancestral decorrentes de split{Fore.RESET}")
            if orphans:
                print(f"      {Fore.MAGENTA}↳ {len(orphans)} funcionalidade(s) órfã(s) detectadas{Fore.RESET}")
            print()

        # Iteração correta: cada achado é formatado e renderizado com seu snippet próprio
        for idx, finding in enumerate(findings, start=1):
            if finding.category == "CONTRACT_ORPHANED_ON_SPLIT":
                sev_badge = f"{Fore.RED}{Style.BRIGHT}[CONTRATO ANCESTRAL PERDIDO]{Style.RESET_ALL}"
                cat_color = Fore.RED
            elif finding.category == "SPLIT_CAPABILITY_LEAK":
                sev_badge = f"{Fore.RED}[VAZAMENTO DE SPLIT]{Fore.RESET}"
                cat_color = Fore.RED
            elif finding.category == "FORK_DRIFT":
                sev_badge = f"{Fore.YELLOW}[DESVIO DE LINHAGEM]{Fore.RESET}"
                cat_color = Fore.YELLOW
            elif finding.category == "DEAD_KEYMAP":
                sev_badge = f"{Fore.RED}[ATALHO MORTO]{Fore.RESET}"
                cat_color = Fore.RED
            elif finding.category == "DISCONNECTED_HANDLER":
                sev_badge = f"{Fore.RED}[HANDLER DESCONECTADO]{Fore.RESET}"
                cat_color = Fore.RED
            elif finding.category == "ORPHAN_COMMAND":
                sev_badge = f"{Fore.YELLOW}[COMANDO ÓRFÃO]{Fore.RESET}"
                cat_color = Fore.YELLOW
            elif finding.category in ("ORPHAN_LOCAL_FUNCTION", "ORPHAN_PYTHON_FUNCTION"):
                sev_badge = f"{Fore.MAGENTA}[FUNÇÃO ZUMBI / ÓRFÃ]{Fore.RESET}"
                cat_color = Fore.MAGENTA
            elif finding.severity == "critical":
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

            print(f"  {cat_color}▶ #{idx} {sev_badge} {Style.BRIGHT}{finding.category}: {finding.identifier}{Style.RESET_ALL}")
            print(f"     {Fore.LIGHTBLACK_EX}├─ [O QUÊ?]    :{Fore.RESET} {finding.impact_description}")
            print(f"     {Fore.LIGHTBLACK_EX}├─ [QUEM/ONDE?] :{Fore.RESET} {file_path.name} (Símbolo: {finding.identifier})")
            print(f"     {Fore.LIGHTBLACK_EX}├─ [MITIGAÇÃO] :{Fore.RESET} {Fore.GREEN}{finding.mitigation_hint}{Fore.RESET}")

            # 📜 RENDERIZADOR DE EVIDÊNCIAS DE CÓDIGO (SNIPPETS DETALHADOS)
            has_code = bool(finding.snippet_lost and finding.snippet_lost.strip())
            should_print_snippet = (
                has_code and (
                    show_snippets
                    or finding.severity in ("critical", "high")
                )
            )

            if should_print_snippet:
                code_lines = finding.snippet_lost.splitlines()
                max_lines = 100 if show_snippets else 5
                slice_lines = code_lines[:max_lines]
                header_label = (
                    "EVIDÊNCIA DE CÓDIGO (COMPLETO)"
                    if show_snippets
                    else "CÓDIGO IDENTIFICADO NA AUDITORIA"
                )
                print(f"     {Fore.CYAN}┌─ [{header_label} — Linha ~{finding.old_line_approx}]{Fore.RESET}")
                for l_idx, raw_line in enumerate(slice_lines, start=finding.old_line_approx):
                    # Normaliza tabulações (\t) para evitar descompasso em consoles Windows
                    clean_line = raw_line.expandtabs(4)
                    line_num_str = f"{l_idx:4d} |"
                    print(f"     {Fore.CYAN}{line_num_str}{Fore.RESET} {Fore.YELLOW}{clean_line}{Fore.RESET}")
                if len(code_lines) > max_lines:
                    print(f"     {Fore.CYAN}     | {Fore.LIGHTBLACK_EX}... e mais {len(code_lines) - max_lines} linha(s) ocultas{Fore.RESET}")
                print(f"     {Fore.CYAN}└{'─' * 60}{Fore.RESET}")
            print()

    @staticmethod
    def render_summary(
        total_files: int,
        total_real_regressions: int,
        total_relocations: int = 0,
        total_volatiles: int = 0,
        total_ux: int = 0,
        total_orphans: int = 0,
        total_ancestral_leaks: int = 0,
    ) -> None:
        """Exibe o veredito final formatado com o sumário de regressões, orfandades e proveniência."""
        print(f"{'═' * 75}")
        if total_real_regressions == 0 and total_orphans == 0 and total_ancestral_leaks == 0:
            notes = []
            if total_relocations > 0:
                notes.append(f"{total_relocations} relocações saudáveis")
            if total_volatiles > 0:
                notes.append(f"{total_volatiles} funções instáveis")
            if total_ux > 0:
                notes.append(f"{total_ux} ajustes de UX auditados")

            note_str = f" ({', '.join(notes)})" if notes else ""
            print(f"{Fore.GREEN}{Style.BRIGHT}🏆 NENHUMA PERDA DE CAPACIDADES, ORFANDADE OU VAZAMENTO ANCESTRAL EM {total_files} ARQUIVO(S){note_str}.{Style.RESET_ALL}")
        else:
            status_color = Fore.RED if total_real_regressions > 0 else Fore.YELLOW
            details = []
            if total_real_regressions > 0:
                details.append(f"{total_real_regressions} regressão(ões) real(is)")
            if total_ancestral_leaks > 0:
                details.append(f"{total_ancestral_leaks} vazamento(s) de split ancestral")
            if total_orphans > 0:
                details.append(f"{total_orphans} funcionalidade(s) órfã(s)")

            print(f"{status_color}{Style.BRIGHT}💥 TOTAL: {' | '.join(details)} em {total_files} arquivo(s).{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Dica: Verifique as badges acima para reatar contratos ancestrais perdidos ou reconectar órfãos.{Fore.RESET}")
        print(f"{'═' * 75}\n")
