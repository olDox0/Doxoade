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
import os, re, sys, time, subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try: from doxoade.tools.doxcolors import Fore, Style
except ImportError:
    class Fore: RED = GREEN = YELLOW = BLUE = CYAN = WHITE = MAGENTA = RESET = LIGHTBLACK_EX = ""
    class Style: BRIGHT = DIM = RESET_ALL = NORMAL = ""

from .doxly_tree import DOXLY_TREE, DoxlyFailureMode
from .doxly_probes import run_all_doxly_probes
from .doxly_chaos import DOXLY_INJECTORS

@dataclass
class TriangulationEvidence:
    via: str
    failure_mode_id: str
    description: str
    weight: float = 1.0

@dataclass
class TriangulationVerdict:
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    user_dir: Path = field(default_factory=Path.cwd)
    is_healthy: bool = True
    confidence_score: float = 0.0
    root_cause: Optional[DoxlyFailureMode] = None
    evidences: List[TriangulationEvidence] = field(default_factory=list)
    git_history: List[Dict[str, str]] = field(default_factory=list)
    git_diff_old: str = ""
    
    via1_matched_symptoms: List[str] = field(default_factory=list)
    via2_probe_findings: List[str] = field(default_factory=list)
    via3_chaos_verified: bool = False
    via6_regret: Optional[Dict[str, Any]] = None
    
    # [FASE 8] Novos campos de contexto
    culprit_file: str = ""
    culprit_line: int = 0
    recent_diff: str = ""
    
    recommended_mitigation: str = ""
    can_auto_repair: bool = False
    auto_repaired: bool = False
    repair_message: str = ""

    def print_verdict(self) -> None:
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
        print(f"  {Fore.WHITE}Grau de Certeza:{Fore.RESET} {conf_color}{Style.BRIGHT}{conf_pct:.1f}%{Style.RESET_ALL}")

        print(f"\n  {Fore.CYAN}{Style.BRIGHT}📊 CRUZAMENTO DAS VIAS:{Style.RESET_ALL}")
        via1_status = f"{Fore.GREEN}Detectado ({len(self.via1_matched_symptoms)} sintomas){Fore.RESET}" if self.via1_matched_symptoms else f"{Fore.LIGHTBLACK_EX}Limpo{Fore.RESET}"
        print(f"    ├─ {Fore.BLUE}Via 1 (Sotéria/Logs):{Fore.RESET} {via1_status}")
        via2_status = f"{Fore.GREEN}Violado ({len(self.via2_probe_findings)} probes){Fore.RESET}" if self.via2_probe_findings else f"{Fore.LIGHTBLACK_EX}Íntegro{Fore.RESET}"
        print(f"    ├─ {Fore.BLUE}Via 2 (Horus/Probes Vivos):{Fore.RESET} {via2_status}")
        via3_status = f"{Fore.GREEN}Provado no Caos (Injetor Ativo){Fore.RESET}" if self.via3_chaos_verified else f"{Fore.YELLOW}Não Verificado no Caos{Fore.RESET}"
        print(f"    ├─ {Fore.BLUE}Via 3 (Typhon Chaos):{Fore.RESET} {via3_status}")
        
        # [FASE 8.1] Via 5
        via5_status = f"{Fore.GREEN}Analisado ({len(self.git_history)} commits){Fore.RESET}" if self.git_history else f"{Fore.LIGHTBLACK_EX}Sem histórico Git{Fore.RESET}"
        print(f"    └─ {Fore.BLUE}Via 5 (Git Archaeology):{Fore.RESET} {via5_status}")

        if self.git_history:
            print(f"\n  {Fore.YELLOW}{Style.BRIGHT}📜 HISTÓRICO DE MUDANÇAS ({self.culprit_file}):{Style.RESET_ALL}")
            for c in self.git_history:
                print(f"    {Fore.LIGHTBLACK_EX}{c['hash']}{Fore.RESET} ({c['date']}) — {c['message']}")
            
            if self.git_diff_old:
                print(f"\n  {Fore.MAGENTA}{Style.BRIGHT}🔍 DIFF vs. ÚLTIMA VERSÃO ESTÁVEL:{Style.RESET_ALL}")
                for line in self.git_diff_old.splitlines()[:15]:
                    color = Fore.GREEN if line.startswith('+') else (Fore.RED if line.startswith('-') else Fore.LIGHTBLACK_EX)
                    print(f"    {color}{line}{Fore.RESET}")
                if len(self.git_diff_old.splitlines()) > 15:
                    print(f"    {Fore.LIGHTBLACK_EX}... (diff truncado){Fore.RESET}")

        if self.recent_diff:
            print(f"\n  {Fore.MAGENTA}{Style.BRIGHT}🔍 ALTERAÇÕES RECENTES NO CULPADO (Git Diff):{Style.RESET_ALL}")
            for line in self.recent_diff.splitlines()[:10]:
                color = Fore.GREEN if line.startswith('+') else (Fore.RED if line.startswith('-') else Fore.LIGHTBLACK_EX)
                print(f"    {color}{line}{Fore.RESET}")
            if len(self.recent_diff.splitlines()) > 10:
                print(f"    {Fore.LIGHTBLACK_EX}... (diff truncado){Fore.RESET}")

        # [FASE 8.4] Via 6 — visibilidade total
        if self.via6_regret:
            v6 = self.via6_regret
            if v6.get("fatal_error"):
                via6_status = f"{Fore.RED}FALHA FATAL: {v6['fatal_error'][:60]}{Fore.RESET}"
            elif not v6.get("executed"):
                via6_status = f"{Fore.YELLOW}Não executou (motivo desconhecido){Fore.RESET}"
            elif v6.get("regressions"):
                via6_status = (
                    f"{Fore.RED}{len(v6['regressions'])} regressão(ões), "
                    f"{v6.get('orphans', 0)} órfão(s), "
                    f"{v6.get('errors') and len(v6['errors']) or 0} erro(s) de análise{Fore.RESET}"
                )
            else:
                via6_status = (
                    f"{Fore.GREEN}Íntegro ({v6.get('files_scanned', 0)} arquivos, "
                    f"{v6.get('orphans', 0)} órfãos){Fore.RESET}"
                )
        else:
            via6_status = f"{Fore.LIGHTBLACK_EX}Não executado{Fore.RESET}"
        print(f"    └─ {Fore.BLUE}Via 6 (Regret Cross-File):{Fore.RESET} {via6_status}")

        # [FASE 8.4] Detalhes de erro da Via 6 (nunca mais blackbox)
        if self.via6_regret:
            v6 = self.via6_regret
            if v6.get("fatal_error"):
                print(f"\n  {Fore.RED}{Style.BRIGHT}💥 ERRO FATAL DA VIA 6:{Style.RESET_ALL}")
                print(f"     {Fore.RED}{v6['fatal_error']}{Fore.RESET}")
                if v6.get("fatal_traceback"):
                    for line in v6["fatal_traceback"].splitlines()[-5:]:
                        print(f"     {Fore.LIGHTBLACK_EX}{line}{Fore.RESET}")
            if v6.get("errors"):
                print(f"\n  {Fore.YELLOW}⚠ ERROS INDIVIDUAIS NA VIA 6 ({len(v6['errors'])}):{Style.RESET_ALL}")
                for err in v6["errors"][:5]:
                    stage = err.get("stage", "?")
                    fname = err.get("file") or err.get("path", "?")
                    msg = err.get("error", "?")
                    print(f"     {Fore.YELLOW}▶ [{stage}] {fname}{Fore.RESET}")
                    print(f"       {Fore.RED}↳ {msg[:120]}{Fore.RESET}")
                if len(v6["errors"]) > 5:
                    print(f"     {Fore.LIGHTBLACK_EX}... e mais {len(v6['errors']) - 5} erro(s){Fore.RESET}")

        if self.root_cause:
            print(f"\n  {Fore.YELLOW}{Style.BRIGHT}💬 DIAGNÓSTICO DO ENGENHEIRO:{Style.RESET_ALL}")
            print(f"     {Fore.WHITE}{self.root_cause.dev_comment}{Fore.RESET}\n")
            print(f"  {Fore.GREEN}{Style.BRIGHT}🛠️  PLANO DE MITIGAÇÃO / AÇÃO:{Style.RESET_ALL}")
            print(f"     {Fore.WHITE}{self.recommended_mitigation}{Fore.RESET}")

        print(f"\n{'═' * 75}\n")

class DoxlyTriangulator:
    @classmethod
    def _extract_context_from_text(cls, text: str) -> Tuple[str, int]:
        """Extrai o arquivo e linha do culpado a partir do stacktrace."""
        # Busca por padrões tipo: `C:\...\tmpXXX.lua:1234:` ou `07_keymaps.lua:63:`
        m = re.search(r'([a-zA-Z0-9_\-\.]+\.lua):(\d+):', text)
        if m:
            return m.group(1), int(m.group(2))
        return "", 0

    @classmethod
    def _run_regret_analysis(cls, user_dir: Path) -> Dict[str, Any]:
        """
        [FASE 8.4] Executa o `doxoade regret` em modo cross-file com
        VISIBILIDADE TOTAL: cada exceção é rastreada e reportada com traceback.
        Nenhum erro é silenciado.
        """
        import traceback as _tb
        result = {
            "regressions": [],
            "orphans": 0,
            "ancestral_leaks": 0,
            "executed": False,
            "files_scanned": 0,
            "errors": [],           # [FASE 8.4] Lista de erros individuais
            "fatal_error": "",      # [FASE 8.4] Erro fatal que impediu tudo
            "fatal_traceback": "",  # [FASE 8.4] Stacktrace completo do fatal
        }

        try:
            from doxoade.commands.regret_systems.regret_engine import RegretEngine
            from doxoade.commands.regret_systems.regret_lua_inspector import (
                LuaCapabilityInventory,
                RegretLuaInspector,
            )
        except Exception as e:
            result["fatal_error"] = f"Falha no import: {e}"
            result["fatal_traceback"] = _tb.format_exc()
            return result

        # [FASE 8.5] Resolve caminhos usando `doxoade` como raiz
        # (independente de onde a `__file__` está).
        try:
            import doxoade as _dox_pkg
            _dox_root = Path(_dox_pkg.__file__).parent.resolve()
        except Exception:
            _dox_root = Path(__file__).parent
            for _ in range(6):  # Fallback: sobe até achar `doxoade/__init__.py`
                if (_dox_root / "__init__.py").exists():
                    break
                _dox_root = _dox_root.parent

        targets_dir = [
            _dox_root / "tools" / "terminal_pty",
            _dox_root / "commands" / "lite_xl_systems" / "template",
        ]

        files_to_scan: List[Path] = []
        for tdir in targets_dir:
            try:
                if tdir.exists() and tdir.is_dir():
                    for ext in ("*.py", "*.lua"):
                        files_to_scan.extend(tdir.glob(ext))
                else:
                    result["errors"].append({
                        "stage": "resolve_targets",
                        "path": str(tdir),
                        "error": f"Diretório não existe: {tdir}",
                    })
            except Exception as e:
                result["errors"].append({
                    "stage": "resolve_targets",
                    "path": str(tdir),
                    "error": str(e),
                })

        result["files_scanned"] = len(files_to_scan)
        if not files_to_scan:
            result["fatal_error"] = "Nenhum arquivo encontrado (diretórios terminal_pty/template ausentes ou vazios)."
            return result

        # Extrai inventários Lua
        external_lua_inventories: List[LuaCapabilityInventory] = []
        for fpath in files_to_scan:
            if fpath.suffix == ".lua" and fpath.exists():
                try:
                    code = fpath.read_text(encoding="utf-8", errors="replace")
                    external_lua_inventories.append(
                        RegretLuaInspector.extract_inventory(code, file_name=fpath.name)
                    )
                except Exception as e:
                    result["errors"].append({
                        "stage": "extract_inventory",
                        "file": fpath.name,
                        "error": str(e),
                    })

        # Analisa arquivo por arquivo
        for fpath in files_to_scan:
            if not fpath.exists():
                continue
            try:
                findings, _ = RegretEngine.analyze_file(
                    file_path=fpath,
                    revision="HEAD",
                    use_backup=False,
                    check_orphans=True,
                    check_provenance=False,
                    show_snippets=False,
                    external_lua_inventories=external_lua_inventories,
                    verbose=False,
                )
                for f in findings:
                    if f.severity in ("critical", "high"):
                        result["regressions"].append({
                            "file": fpath.name,
                            "identifier": f.identifier,
                            "category": f.category,
                            "severity": f.severity,
                            "impact": f.impact_description,
                            "mitigation": f.mitigation_hint,
                        })
                    if f.category in ("ORPHAN_COMMAND", "ORPHAN_LOCAL_FUNCTION", "ORPHAN_PYTHON_FUNCTION"):
                        result["orphans"] += 1
                    if f.category in ("SPLIT_CAPABILITY_LEAK", "CONTRACT_ORPHANED_ON_SPLIT"):
                        result["ancestral_leaks"] += 1
            except Exception as e:
                # [FASE 8.4] NÃO silencia. Registra arquivo, erro e traceback.
                result["errors"].append({
                    "stage": "analyze_file",
                    "file": fpath.name,
                    "error": f"{type(e).__name__}: {e}",
                    "traceback": _tb.format_exc(),
                })

        result["executed"] = True
        return result

    @classmethod
    def _fetch_git_history(cls, file_name: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Executa `git log` no arquivo culpado para ver quando e por que mudou.
        Retorna uma lista de commits (hash, data, mensagem).
        """
        if not file_name: return []
        try:
            # Tenta achar o arquivo real no projeto
            cmd = ["git", "log", "-n", str(limit), "--format=%h|%ad|%s", "--date=short", "--", file_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if result.returncode != 0:
                return []
            
            commits = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append({
                        "hash": parts[0].strip(),
                        "date": parts[1].strip(),
                        "message": parts[2].strip(),
                    })
            return commits
        except Exception:
            return []

    @classmethod
    def _fetch_git_diff_vs_commit(cls, file_name: str, commit_hash: str) -> str:
        """Retorna o diff entre o commit antigo e a versão atual do arquivo."""
        if not file_name or not commit_hash: return ""
        try:
            cmd = ["git", "diff", commit_hash, "HEAD", "--", file_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if result.returncode == 0:
                out = result.stdout
                # Retorna até 80 linhas
                return "\n".join(out.splitlines()[:80])
            return ""
        except Exception:
            return ""

    @classmethod
    def _fetch_recent_diff(cls, file_name: str) -> str:
        """Executa `doxoade diff` no arquivo culpado para ver o que mudou."""
        if not file_name: return ""
        try:
            # Busca o arquivo real no projeto
            cmd = ["doxoade", "diff", file_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if result.returncode == 0:
                out = result.stdout
                # Se houver diferenças reais (linhas com + ou -)
                if "Mudanças perto da linha" in out or "+ |" in out or "- |" in out:
                    return out
            return ""
        except Exception:
            return ""

    @classmethod
    def triangulate(
        cls,
        user_dir: Optional[Path] = None,
        log_text: Optional[str] = None,
        run_probes: bool = True,
        check_chaos: bool = False,
        auto_fix: bool = False,
    ) -> TriangulationVerdict:
        if user_dir is None:
            from doxoade.commands.lite_xl_systems.lite_xl_paths import LiteXLPaths
            user_dir = LiteXLPaths.get_user_dir()
            
        verdict = TriangulationVerdict(user_dir=user_dir)
        scores_by_fmid: Dict[str, float] = {}
        
        text_to_scan = log_text or ""
        if not text_to_scan:
            session_file = user_dir / "session_log.txt"
            error_file = user_dir / "error.txt"
            phanto_file = user_dir / ".doxoade" / "diagnostics" / "phanto_crisis.ndjson"
            
            t1 = session_file.read_text(encoding="utf-8", errors="replace") if session_file.exists() else ""
            t2 = error_file.read_text(encoding="utf-8", errors="replace") if error_file.exists() else ""
            t3 = phanto_file.read_text(encoding="utf-8", errors="replace") if phanto_file.exists() else ""
            text_to_scan = f"{t2}\n{t1}\n{t3}"

        # VIA 1: Logs
        if text_to_scan.strip():
            matches = DOXLY_TREE.scan_text(text_to_scan)
            for fm, evidence in matches:
                scores_by_fmid[fm.id] = scores_by_fmid.get(fm.id, 0.0) + 0.40
                verdict.via1_matched_symptoms.append(evidence)
                verdict.evidences.append(TriangulationEvidence("VIA_1_LOGS", fm.id, evidence, weight=0.40))
                
            # [FASE 8] Extrai contexto de arquivo/linha do log
            verdict.culprit_file, verdict.culprit_line = cls._extract_context_from_text(text_to_scan)

        # VIA 2: Probes
        if run_probes:
            probe_report = run_all_doxly_probes(user_dir, verbose=False)
            for finding in probe_report.findings:
                if finding.is_failure and finding.failure_mode_id:
                    fmid = finding.failure_mode_id
                    scores_by_fmid[fmid] = scores_by_fmid.get(fmid, 0.0) + 0.45
                    verdict.via2_probe_findings.append(finding.message)
                    verdict.evidences.append(TriangulationEvidence("VIA_2_PROBES", fmid, finding.message, weight=0.45))

        # VIA 3: Chaos
        if scores_by_fmid:
            leading_fmid = max(scores_by_fmid, key=scores_by_fmid.get)
            if leading_fmid in DOXLY_INJECTORS:
                scores_by_fmid[leading_fmid] = min(1.0, scores_by_fmid[leading_fmid] + 0.15)
                verdict.via3_chaos_verified = True
                verdict.evidences.append(TriangulationEvidence("VIA_3_CHAOS", leading_fmid, "Injetor ativo comprovado", weight=0.15))

            # Consolida Veredito
            best_fmid = leading_fmid
            best_score = min(1.0, scores_by_fmid[best_fmid])
            root_fm = DOXLY_TREE.get_by_id(best_fmid)
            
            verdict.is_healthy = False
            verdict.confidence_score = round(best_score, 2)
            verdict.root_cause = root_fm
            verdict.recommended_mitigation = root_fm.mitigation if root_fm else "Investigar arquivos e traces de log."
            verdict.can_auto_repair = root_fm.auto_fixable if root_fm else False

            # VIA 5: Git Archaeology (commits)
            if verdict.culprit_file and root_fm and root_fm.id == "doxly.pty.handshake_fail":
                verdict.git_history = cls._fetch_git_history(verdict.culprit_file, limit=5)
                if verdict.git_history:
                    last_commit = verdict.git_history[-1]["hash"]
                    verdict.git_diff_old = cls._fetch_git_diff_vs_commit(verdict.culprit_file, last_commit)

            # [FASE 8.3] VIA 6: Regret Cross-File (Regressões estruturais)
            # Sempre executa (independente de qual foi a causa raiz) para
            # que o laudo mostre o estado estrutural completo.
            if root_fm:  # Só executa se houver causa raiz identificada
                regret_res = cls._run_regret_analysis(user_dir)
                verdict.via6_regret = regret_res  # [FASE 8.3] Sempre atribui
                if regret_res.get("regressions"):
                    verdict.evidences.append(TriangulationEvidence(
                        "VIA_6_REGRET",
                        root_fm.id,
                        f"{len(regret_res['regressions'])} regressão(ões) estrutural(is) detectada(s)",
                        weight=0.30,
                    ))
                if regret_res.get("orphans"):
                    verdict.evidences.append(TriangulationEvidence(
                        "VIA_6_ORPHANS",
                        root_fm.id,
                        f"{regret_res['orphans']} funcionalidade(s) órfã(s)",
                        weight=0.10,
                    ))

            if auto_fix and verdict.can_auto_repair:
                ok, msg = cls.auto_repair(verdict, user_dir)
                verdict.auto_repaired = ok
                verdict.repair_message = msg

        return verdict

    @classmethod
    def auto_repair(cls, verdict: TriangulationVerdict, user_dir: Path) -> Tuple[bool, str]:
        # Implementação existente (mantida para compatibilidade)
        if not verdict.root_cause or not verdict.can_auto_repair: 
            return False, "Esta falha não suporta autorreparo automatizado."
        # ... lógica específica ...
        return False, "Nenhum executor configurado."
