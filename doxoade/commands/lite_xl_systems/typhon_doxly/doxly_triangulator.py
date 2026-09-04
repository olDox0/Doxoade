# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_triangulator.py
# Motor de triangulação de 3 vias (Sotéria + Horus + Chaos)
""" Motor de Triangulação de Diagnóstico do Lite XL (Censo de 3 Vias - Typhon Doxly).
Cruza:
  Via 1: Sintomas em Logs (Sotéria Envelope & Log Scanning)
  Via 2: Probes Vivos de Estado (Horus Active Invariants)
  Via 3: Sensibilidade de Caos (Typhon Chaos Sensitivity)
Sintetiza a Causa Raiz, calcula Score de Confiança e executa Autorreparo Atômico. """

from __future__ import annotations
import os
import re
import sys
import time
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

from .doxly_tree import DOXLY_TREE, DoxlyFailureMode
from .doxly_probes import run_all_doxly_probes, DoxlyProbeReport, DoxlyProbeFinding
from .doxly_chaos import DOXLY_INJECTORS


@dataclass
class TriangulationEvidence:
    """Evidência coletada em uma das três vias."""
    via: str  # "VIA_1_LOGS", "VIA_2_PROBES", "VIA_3_CHAOS"
    failure_mode_id: str
    description: str
    weight: float = 1.0


@dataclass
class TriangulationVerdict:
    """Veredito consolidado do diagnóstico de 3 vias."""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    user_dir: Path = field(default_factory=Path.cwd)
    is_healthy: bool = True
    confidence_score: float = 0.0  # 0.0 a 1.0 (1.0 = Certeza Absoluta)
    root_cause: Optional[DoxlyFailureMode] = None
    evidences: List[TriangulationEvidence] = field(default_factory=list)
    via1_matched_symptoms: List[str] = field(default_factory=list)
    via2_probe_findings: List[str] = field(default_factory=list)
    via3_chaos_verified: bool = False
    recommended_mitigation: str = ""
    can_auto_repair: bool = False
    auto_repaired: bool = False
    repair_message: str = ""

    def print_verdict(self) -> None:
        """Renderiza o relatório forense formatado no terminal."""
        print(f"\n{'═' * 75}")
        print(f"{Fore.CYAN}{Style.BRIGHT}🌀 TYPHON DOXLY — VEREDITO DE TRIANGULAÇÃO DE 3 VIAS{Style.RESET_ALL}")
        print(f"{'═' * 75}")
        print(f"  {Fore.WHITE}Alvo:{Fore.RESET} {self.user_dir}")
        print(f"  {Fore.WHITE}Timestamp:{Fore.RESET} {self.timestamp}")

        if self.is_healthy:
            print(f"\n  {Fore.GREEN}{Style.BRIGHT}✔ SISTEMA 100% SAUDÁVEL E ÍNTEGRO{Style.RESET_ALL}")
            print(f"     {Fore.LIGHTBLACK_EX}↳ Nenhuma evidência de falha em logs, probes vivos ou testes de caos.{Fore.RESET}\n")
            print(f"{'═' * 75}\n")
            return

        conf_pct = self.confidence_score * 100
        conf_color = Fore.GREEN if conf_pct >= 90 else (Fore.YELLOW if conf_pct >= 70 else Fore.RED)

        print(f"  {Fore.WHITE}Causa Raiz:{Fore.RESET} {Fore.RED}{Style.BRIGHT}{self.root_cause.name if self.root_cause else 'Anomalia Indefinida'}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}ID da Falha:{Fore.RESET} {Fore.CYAN}{self.root_cause.id if self.root_cause else 'N/A'}{Fore.RESET}")
        print(f"  {Fore.WHITE}Grau de Certeza:{Fore.RESET} {conf_color}{Style.BRIGHT}{conf_pct:.1f}% de Confiança{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Severidade:{Fore.RESET} {Fore.LIGHTRED_EX}{self.root_cause.severity.upper() if self.root_cause else 'DESCONHECIDA'}{Fore.RESET}\n")

        # Exibição do Cruzamento de Vias
        print(f"  {Fore.CYAN}{Style.BRIGHT}📊 CRUZAMENTO DAS 3 VIAS:{Style.RESET_ALL}")
        
        # Via 1
        via1_status = f"{Fore.GREEN}Detectado ({len(self.via1_matched_symptoms)} sintomas){Fore.RESET}" if self.via1_matched_symptoms else f"{Fore.LIGHTBLACK_EX}Limpo{Fore.RESET}"
        print(f"    ├─ {Fore.BLUE}Via 1 (Sotéria/Logs):{Fore.RESET} {via1_status}")
        for s in self.via1_matched_symptoms[:2]:
            print(f"    │    {Fore.LIGHTBLACK_EX}↳ '{s[:85]}...'{Fore.RESET}")

        # Via 2
        via2_status = f"{Fore.GREEN}Violado ({len(self.via2_probe_findings)} probes){Fore.RESET}" if self.via2_probe_findings else f"{Fore.LIGHTBLACK_EX}Íntegro{Fore.RESET}"
        print(f"    ├─ {Fore.BLUE}Via 2 (Horus/Probes Vivos):{Fore.RESET} {via2_status}")
        for p in self.via2_probe_findings[:2]:
            print(f"    │    {Fore.LIGHTBLACK_EX}↳ {p[:85]}{Fore.RESET}")

        # Via 3
        via3_status = f"{Fore.GREEN}Provado no Caos (Injetor Ativo){Fore.RESET}" if self.via3_chaos_verified else f"{Fore.YELLOW}Não Verificado no Caos{Fore.RESET}"
        print(f"    └─ {Fore.BLUE}Via 3 (Typhon Chaos):{Fore.RESET} {via3_status}\n")

        # Explicação Técnica e Mitigação
        if self.root_cause:
            print(f"  {Fore.YELLOW}{Style.BRIGHT}💬 DIAGNÓSTICO DO ENGENHEIRO:{Style.RESET_ALL}")
            print(f"     {Fore.WHITE}{self.root_cause.dev_comment}{Fore.RESET}\n")

            print(f"  {Fore.GREEN}{Style.BRIGHT}🛠️  PLANO DE MITIGAÇÃO / AÇÃO:{Style.RESET_ALL}")
            print(f"     {Fore.WHITE}{self.recommended_mitigation}{Fore.RESET}")

            if self.can_auto_repair:
                repair_badge = f"{Fore.GREEN}✔ AUTORREPARO EXECUTADO COM SUCESSO" if self.auto_repaired else f"{Fore.CYAN}💡 AUTORREPARO DISPONÍVEL (--repair)"
                print(f"\n  {repair_badge}{Fore.RESET}")
                if self.repair_message:
                    print(f"     {Fore.LIGHTBLACK_EX}↳ {self.repair_message}{Fore.RESET}")
        print(f"\n{'═' * 75}\n")


class DoxlyTriangulator:
    """Orquestrador Central da Triangulação de 3 Vias do Lite XL."""

    @classmethod
    def triangulate(
        cls,
        user_dir: Optional[Path] = None,
        log_text: Optional[str] = None,
        run_probes: bool = True,
        check_chaos: bool = False,
        auto_fix: bool = False,
    ) -> TriangulationVerdict:
        """
        Executa o censo de 3 vias completo.
        Retorna o TriangulationVerdict com a causa raiz e plano de ação.
        """
        if user_dir is None:
            from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
            user_dir = LiteXLPaths.get_user_dir()

        verdict = TriangulationVerdict(user_dir=user_dir)
        scores_by_fmid: Dict[str, float] = {}

        # =====================================================================
        # VIA 1: Varredura de Sintomas em Logs (Sotéria Scanning) - Peso: 0.40
        # =====================================================================
        text_to_scan = log_text or ""
        if not text_to_scan:
            session_file = user_dir / "session_log.txt"
            error_file = user_dir / "error.txt"
            t1 = session_file.read_text(encoding="utf-8", errors="replace") if session_file.exists() else ""
            t2 = error_file.read_text(encoding="utf-8", errors="replace") if error_file.exists() else ""
            text_to_scan = f"{t2}\n{t1}"

        if text_to_scan.strip():
            matches = DOXLY_TREE.scan_text(text_to_scan)
            for fm, evidence in matches:
                scores_by_fmid[fm.id] = scores_by_fmid.get(fm.id, 0.0) + 0.40
                verdict.via1_matched_symptoms.append(evidence)
                verdict.evidences.append(TriangulationEvidence("VIA_1_LOGS", fm.id, evidence, weight=0.40))

        # =====================================================================
        # VIA 2: Probes Ativos em Disco (Horus Invariants) - Peso: 0.45
        # =====================================================================
        if run_probes:
            probe_report = run_all_doxly_probes(user_dir, verbose=False)
            for finding in probe_report.findings:
                if finding.is_failure and finding.failure_mode_id:
                    fmid = finding.failure_mode_id
                    scores_by_fmid[fmid] = scores_by_fmid.get(fmid, 0.0) + 0.45
                    verdict.via2_probe_findings.append(finding.message)
                    verdict.evidences.append(TriangulationEvidence("VIA_2_PROBES", fmid, finding.message, weight=0.45))

        # =====================================================================
        # VIA 3: Prova de Sensibilidade contra o Caos - Peso: 0.15
        # =====================================================================
        if scores_by_fmid:
            # Pega o candidato a causa raiz com maior pontuação combinada
            leading_fmid = max(scores_by_fmid, key=scores_by_fmid.get)
            if leading_fmid in DOXLY_INJECTORS:
                scores_by_fmid[leading_fmid] = min(1.0, scores_by_fmid[leading_fmid] + 0.15)
                verdict.via3_chaos_verified = True
                verdict.evidences.append(TriangulationEvidence("VIA_3_CHAOS", leading_fmid, "Injetor ativo comprovado", weight=0.15))

            best_fmid = leading_fmid
            best_score = min(1.0, scores_by_fmid[best_fmid])
            root_fm = DOXLY_TREE.get_by_id(best_fmid)

            verdict.is_healthy = False
            verdict.confidence_score = round(best_score, 2)
            verdict.root_cause = root_fm
            verdict.recommended_mitigation = root_fm.mitigation if root_fm else "Investigar arquivos e traces de log."
            verdict.can_auto_repair = root_fm.auto_fixable if root_fm else False

            # Executa autorreparo automático se solicitado
            if auto_fix and verdict.can_auto_repair:
                ok, msg = cls.auto_repair(verdict, user_dir)
                verdict.auto_repaired = ok
                verdict.repair_message = msg

        return verdict

    @classmethod
    def auto_repair(cls, verdict: TriangulationVerdict, user_dir: Path) -> Tuple[bool, str]:
        """Aplica correções atômicas baseadas na Causa Raiz diagnosticada."""
        if not verdict.root_cause or not verdict.can_auto_repair:
            return False, "Esta falha não suporta autorreparo automatizado."

        fmid = verdict.root_cause.id

        # 1. Reparo de user_settings.lua ausente ou corrompido
        if fmid in ("doxly.config.missing_user_settings", "doxly.settings.nil_table_index"):
            settings_path = user_dir / "user_settings.lua"
            try:
                settings_path.write_text(
                    'return {\n  ["config"] = {\n    ["fps"] = 60,\n    ["transitions"] = false\n  }\n}\n',
                    encoding="utf-8"
                )
                return True, f"Arquivo {settings_path.name} regenerado com tabela de configuração válida."
            except Exception as e:
                return False, f"Falha ao reescrever user_settings.lua: {e}"

        # 2. Reparo de processos zumbis
        if fmid == "doxly.process.ghost_zombie":
            try:
                from doxoade.commands.lite_xl_systems.typhon_deploy import TyphonDeployEngine
                TyphonDeployEngine.exorcise_instances()
                return True, "Processos zumbis do Lite XL encerrados com sucesso."
            except Exception as e:
                return False, f"Falha ao executar exorcismo: {e}"

        # 3. Reparo de Sintaxe Corrompida ou Highlighter Inválido
        if fmid in ("doxly.syntax.corrupted_pattern", "doxly.docview.nil_highlighter", "doxly.tokenizer.nil_compare"):
            try:
                from doxoade.commands.lite_xl_systems.lite_xl_init_builder import LiteXLInitBuilder
                LiteXLInitBuilder.install_sovereign_config(force=True, backup=True)
                return True, "Configuração soberana e Syntax Vaccine reinstaladas e promovidas."
            except Exception as e:
                return False, f"Falha ao reinstalar configuração: {e}"

        return False, f"Nenhum executor de autorreparo configurado para {fmid}."
