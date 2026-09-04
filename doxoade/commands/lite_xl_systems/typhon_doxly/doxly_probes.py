# -*- coding: utf-8 -*-
# doxoade/commands/lite_xl_systems/typhon_doxly/doxly_probes.py
# Probes vivos de estado, telemetria e integridade
""" Detectores e Probes Ativos em Runtime para o Lite XL (Typhon Doxly Edition).
Inspeciona artefatos vivos: user_settings.lua, runtime_probe.json, profiler_telemetry.json e logs.
Representa a Via 2 (Horus/Anúbis) na Triangulação de 3 Vias do Typhon. """

from __future__ import annotations
import json
import os
import re
import time
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

from .doxly_tree import DOXLY_TREE, DoxlyFailureMode


@dataclass
class DoxlyProbeFinding:
    """Achado individual de um probe ativo."""
    category: str  # CONFIG, API_GUARD, TELEMETRY, LOGS, WORKSPACE
    severity: str  # pass, low, medium, high, critical
    title: str
    message: str
    source_file: Optional[Path] = None
    failure_mode_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    mitigation_hint: str = ""
    auto_fixable: bool = False

    @property
    def is_failure(self) -> bool:
        return self.severity in ("high", "critical")


@dataclass
class DoxlyProbeReport:
    """Relatório consolidado da execução de todos os probes."""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    user_dir: Path = field(default_factory=Path.cwd)
    total_probes: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    findings: List[DoxlyProbeFinding] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.failed == 0

    def add(self, finding: DoxlyProbeFinding) -> None:
        self.findings.append(finding)
        self.total_probes += 1
        if finding.severity == "pass":
            self.passed += 1
        elif finding.is_failure:
            self.failed += 1
        else:
            self.warnings += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "user_dir": str(self.user_dir),
            "is_healthy": self.is_healthy,
            "summary": {
                "total": self.total_probes,
                "passed": self.passed,
                "failed": self.failed,
                "warnings": self.warnings,
            },
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "message": f.message,
                    "source_file": str(f.source_file) if f.source_file else None,
                    "failure_mode_id": f.failure_mode_id,
                    "mitigation_hint": f.mitigation_hint,
                    "auto_fixable": f.auto_fixable,
                }
                for f in self.findings
            ],
        }

    def print_report(self, verbose: bool = True) -> None:
        """Renderiza o relatório formatado com cores no terminal."""
        status_color = Fore.GREEN if self.is_healthy else Fore.RED
        status_text = "SAUDÁVEL" if self.is_healthy else "ANOMALIAS DETECTADAS"

        print(f"\n{Fore.CYAN}{Style.BRIGHT}🔬 RELATÓRIO DE PROBES VIVOS TYPHON DOXLY{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Diretório:{Fore.RESET} {self.user_dir}")
        print(f"  {Fore.WHITE}Status Geral:{Fore.RESET} {status_color}{Style.BRIGHT}{status_text}{Style.RESET_ALL} "
              f"({self.passed} OK, {self.warnings} Avisos, {self.failed} Falhas)\n")

        for f in self.findings:
            if f.severity == "pass":
                icon = f"{Fore.GREEN}✔{Fore.RESET}"
                tag = f"{Fore.GREEN}[PASS]{Fore.RESET}"
            elif f.severity == "critical":
                icon = f"{Fore.RED}☠{Fore.RESET}"
                tag = f"{Fore.RED}[CRIT]{Fore.RESET}"
            elif f.severity == "high":
                icon = f"{Fore.LIGHTRED_EX}✖{Fore.RESET}"
                tag = f"{Fore.LIGHTRED_EX}[FAIL]{Fore.RESET}"
            else:
                icon = f"{Fore.YELLOW}⚠{Fore.RESET}"
                tag = f"{Fore.YELLOW}[WARN]{Fore.RESET}"

            print(f"  {icon} {tag} {Style.BRIGHT}{f.title}{Style.RESET_ALL}")
            print(f"     {Fore.LIGHTBLACK_EX}↳ {f.message}{Fore.RESET}")
            if f.failure_mode_id and verbose:
                print(f"       {Fore.CYAN}Modo de Falha:{Fore.RESET} {f.failure_mode_id}")
            if f.mitigation_hint and f.severity != "pass" and verbose:
                print(f"       {Fore.YELLOW}Mitigação:{Fore.RESET} {f.mitigation_hint}")
        print()


# =============================================================================
# 4. IMPLEMENTAÇÃO DOS PROBES ATÔMICOS
# =============================================================================

def probe_user_settings_integrity(user_dir: Path) -> DoxlyProbeFinding:
    """Valida se user_settings.lua existe e retorna explicitamente uma tabela (evita settings.lua:843)."""
    settings_file = user_dir / "user_settings.lua"
    if not settings_file.exists():
        fm = DOXLY_TREE.get_by_id("doxly.config.missing_user_settings")
        return DoxlyProbeFinding(
            category="CONFIG",
            severity="medium",
            title="Arquivo user_settings.lua Ausente",
            message="O arquivo user_settings.lua não foi encontrado no USERDIR.",
            source_file=settings_file,
            failure_mode_id=fm.id if fm else None,
            mitigation_hint=fm.mitigation if fm else "Criar user_settings.lua padrão.",
            auto_fixable=True,
        )

    content = settings_file.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"return\s*\{", content):
        fm = DOXLY_TREE.get_by_id("doxly.settings.nil_table_index")
        return DoxlyProbeFinding(
            category="CONFIG",
            severity="high",
            title="user_settings.lua Inválido (Sem Retorno de Tabela)",
            message="O arquivo existe mas não retorna uma tabela Lua explícita, arriscando quebra no settings.lua:843.",
            source_file=settings_file,
            failure_mode_id=fm.id if fm else None,
            mitigation_hint=fm.mitigation if fm else "Adicionar 'return { [\"config\"] = { ... } }'.",
            auto_fixable=True,
        )

    return DoxlyProbeFinding(
        category="CONFIG",
        severity="pass",
        title="user_settings.lua Íntegro",
        message="Arquivo de configurações presente e retorna tabela válida.",
        source_file=settings_file,
    )


def probe_api_guard_contracts(user_dir: Path) -> List[DoxlyProbeFinding]:
    """Inspeciona o runtime_probe.json gerado pelo API Guard no boot."""
    probe_json = user_dir / ".doxoade" / "api_guard" / "runtime_probe.json"
    if not probe_json.exists():
        return [
            DoxlyProbeFinding(
                category="API_GUARD",
                severity="low",
                title="API Guard Probe Pendente",
                message="runtime_probe.json não localizado. O Lite XL precisa ser iniciado ao menos uma vez.",
                source_file=probe_json,
                mitigation_hint="Inicie o Lite XL para gerar o relatório de introspecção.",
            )
        ]

    try:
        data = json.loads(probe_json.read_text(encoding="utf-8", errors="replace"))
        summary = data.get("summary", {})
        missing_cnt = summary.get("missing", 0)
        mismatch_cnt = summary.get("type_mismatch", 0)
        total = summary.get("total", 0)

        if missing_cnt == 0 and mismatch_cnt == 0:
            return [
                DoxlyProbeFinding(
                    category="API_GUARD",
                    severity="pass",
                    title="Contratos de API 100% Válidos",
                    message=f"Todos os {total} símbolos essenciais do Lite XL estão presentes e compatíveis.",
                    source_file=probe_json,
                )
            ]

        findings = []
        fm = DOXLY_TREE.get_by_id("doxly.api.missing_critical_symbol")
        apis = data.get("apis", {})
        for api_name, spec in apis.items():
            if spec.get("status") == "missing":
                findings.append(
                    DoxlyProbeFinding(
                        category="API_GUARD",
                        severity="critical" if spec.get("severity") == "critical" else "medium",
                        title=f"API Ausente: {api_name}",
                        message=f"O símbolo '{api_name}' (esperado: {spec.get('expected_type')}) não existe no runtime.",
                        source_file=probe_json,
                        failure_mode_id=fm.id if fm else None,
                        mitigation_hint=fm.mitigation if fm else "Injetar polyfill de compatibilidade.",
                    )
                )
        return findings
    except Exception as e:
        return [
            DoxlyProbeFinding(
                category="API_GUARD",
                severity="medium",
                title="Falha ao Parsear runtime_probe.json",
                message=f"Arquivo corrompido ou ilegível: {e}",
                source_file=probe_json,
            )
        ]


def probe_chronos_telemetry(user_dir: Path) -> DoxlyProbeFinding:
    """Inspeciona profiler_telemetry.json procurando frame spikes (>16.6ms) e gargalos."""
    telem_file = user_dir / ".doxoade" / "diagnostics" / "profiler_telemetry.json"
    if not telem_file.exists():
        return DoxlyProbeFinding(
            category="TELEMETRY",
            severity="low",
            title="Telemetria Chronos Inativa",
            message="profiler_telemetry.json não encontrado. O módulo 10_forensic_engine.lua gerará no próximo ciclo.",
            source_file=telem_file,
        )

    try:
        data = json.loads(telem_file.read_text(encoding="utf-8", errors="replace"))
        active_fps = data.get("active_fps", 60.0)
        spikes = data.get("frame_spikes", [])
        gc_kb = data.get("gc_memory_kb", 0)

        if active_fps < 45.0 or len(spikes) >= 10:
            fm = DOXLY_TREE.get_by_id("doxly.khonsu.coroutine_budget_spike")
            return DoxlyProbeFinding(
                category="TELEMETRY",
                severity="medium",
                title=f"Degradação de FPS Detectada ({active_fps:.1f} FPS)",
                message=f"{len(spikes)} frame spikes (>16.6ms) registrados. GC Memory: {gc_kb:.1f} KB.",
                source_file=telem_file,
                failure_mode_id=fm.id if fm else None,
                mitigation_hint=fm.mitigation if fm else "Reduzir budget das corrotinas Khonsu.",
            )

        return DoxlyProbeFinding(
            category="TELEMETRY",
            severity="pass",
            title="Pipeline Gráfico Estável (60 FPS)",
            message=f"FPS Médio: {active_fps:.1f} | Spikes recentes: {len(spikes)} | Memória GC: {gc_kb:.1f} KB.",
            source_file=telem_file,
        )
    except Exception as e:
        return DoxlyProbeFinding(
            category="TELEMETRY",
            severity="low",
            title="Telemetria Ilegível",
            message=f"Erro ao ler JSON de telemetria: {e}",
            source_file=telem_file,
        )


def probe_session_logs_and_errors(user_dir: Path) -> List[DoxlyProbeFinding]:
    """Varre error.txt e session_log.txt procurando casamentos com a DOXLY_TREE."""
    findings = []
    error_txt = user_dir / "error.txt"

    # 1. Checagem de Crash Fatal em error.txt
    if error_txt.exists() and error_txt.stat().st_size > 0:
        err_content = error_txt.read_text(encoding="utf-8", errors="replace")
        matches = DOXLY_TREE.scan_text(err_content)
        if matches:
            for fm, evidence in matches:
                # Se for apenas o Binary Guard neutralizando o buffer com sucesso, emite aviso leve
                if fm.id == "doxly.syntax.binary_raw_highlight" and "[BINARY GUARD]" in evidence:
                    findings.append(
                        DoxlyProbeFinding(
                            category="LOGS",
                            severity="low",  # ✅ Não quebra o status geral como FAIL
                            title=f"Defesa Ativa: {fm.name}",
                            message=f"Buffer binário neutralizado com segurança pelo escudo: '{evidence[:85]}...'",
                            source_file=session_log,
                            failure_mode_id=fm.id,
                            mitigation_hint="Fechar a aba do arquivo compilado se não for necessária.",
                            auto_fixable=False,
                        )
                    )
        else:
            findings.append(
                DoxlyProbeFinding(
                    category="LOGS",
                    severity="high",
                    title="Crash Não Catalogado em error.txt",
                    message=err_content.splitlines()[0][:120] if err_content else "Crash anônimo.",
                    source_file=error_txt,
                    mitigation_hint="Adicionar novo modo de falha à DOXLY_TREE.",
                )
            )

    # 2. Checagem de Incidentes Recentes no session_log.txt
    session_log = user_dir / "session_log.txt"
    if session_log.exists():
        log_lines = session_log.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(log_lines[-100:])  # Últimas 100 linhas
        matches = DOXLY_TREE.scan_text(tail)
        for fm, evidence in matches:
            findings.append(
                DoxlyProbeFinding(
                    category="LOGS",
                    severity="high" if fm.severity in ("high", "critical") else "medium",
                    title=f"Incidente em Log: {fm.name}",
                    message=f"Detectado em session_log.txt: '{evidence[:100]}'",
                    source_file=session_log,
                    failure_mode_id=fm.id,
                    mitigation_hint=fm.mitigation,
                    auto_fixable=fm.auto_fixable,
                )
            )

    if not findings:
        findings.append(
            DoxlyProbeFinding(
                category="LOGS",
                severity="pass",
                title="Logs de Sessão Limpos",
                message="Nenhum crash em error.txt e zero incidentes conhecidos nas últimas 100 linhas de log.",
                source_file=session_log if session_log.exists() else None,
            )
        )

    return findings


# =============================================================================
# 5. ORQUESTRADOR GLOBAL DE PROBES VIVOS
# =============================================================================

def run_all_doxly_probes(user_dir: Optional[Path] = None, verbose: bool = True) -> DoxlyProbeReport:
    """Executa todos os detectores vivos e retorna o relatório consolidado."""
    if user_dir is None:
        from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
        user_dir = LiteXLPaths.get_user_dir()

    report = DoxlyProbeReport(user_dir=user_dir)

    # Probe 1: Integridade de Configurações
    report.add(probe_user_settings_integrity(user_dir))

    # Probe 2: Contratos de API do Lite XL
    for f in probe_api_guard_contracts(user_dir):
        report.add(f)

    # Probe 3: Telemetria e FPS
    report.add(probe_chronos_telemetry(user_dir))

    # Probe 4: Logs e Crash Reports
    for f in probe_session_logs_and_errors(user_dir):
        report.add(f)

    if verbose:
        report.print_report(verbose=True)

    return report
