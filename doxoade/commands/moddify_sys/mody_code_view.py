# -*- coding: utf-8 -*-
# doxoade/commands/moddify_sys/mody_code_view.py
"""Visão comparativa de hunks (--code) e relatório estruturado para pesquisa
em rule tables + back/forward chaining (--report)."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

try:
    from doxoade.tools.doxcolors import Fore, Style
except Exception:
    class Fore:
        GREEN = '\x1b[92m'; RED = '\x1b[91m'; YELLOW = '\x1b[93m'
        CYAN = '\x1b[96m'; MAGENTA = '\x1b[95m'; DIM = '\x1b[2m'
        WHITE = '\x1b[97m'; BLUE = '\x1b[94m'; RESET = '\x1b[0m'
    class Style:
        BRIGHT = '\x1b[1m'; RESET_ALL = '\x1b[0m'


@dataclass
class RuleTrace:
    rule_id: str
    phase: str                # 'idempotence' | 'match' | 'validate' | 'decision'
    inputs: Dict[str, Any] = field(default_factory=dict)
    output: str = ""          # 'PASS' | 'FAIL' | 'SKIP' | 'WARN'
    detail: str = ""
    candidates: List = field(default_factory=list)


@dataclass
class HunkView:
    file: str
    hunk_idx: int
    old_start: int
    status: str                       # APPLICABLE | IDEMPOTENT | REJECTED | AMBIGUOUS
    match_type: str = ""
    loc: Optional[int] = None
    offset: int = 0
    patch_before: List[str] = field(default_factory=list)
    patch_removals: List[str] = field(default_factory=list)
    patch_additions: List[str] = field(default_factory=list)
    patch_after: List[str] = field(default_factory=list)
    file_snippet: List[Tuple[int, str]] = field(default_factory=list)
    file_snippet_range: Tuple[int, int] = (0, 0)
    rule_trace: List[RuleTrace] = field(default_factory=list)
    rejection_reason: str = ""
    suggestions: List[str] = field(default_factory=list)
    semantic_verdict: str = "UNKNOWN"
    semantic_confidence: float = 0.0
    semantic_hint: str = ""


class CodeView:

    @staticmethod
    def infer_rule_trace(match_type: str, status: str, detail: Dict,
                          hunk, file_lines: List[str]) -> List[RuleTrace]:
        """Reconstrói cadeia forward/backward a partir do que já foi decidido."""
        traces: List[RuleTrace] = []
        status_up = status.upper()
        mt = (match_type or "").upper()

        # R01 — checagem de idempotência (sempre primeiro)
        idem = ('IDEMPOTENT' in status_up or 'JÁ APLICADO' in status_up
                or 'IDEMPOTENT' in mt)
        traces.append(RuleTrace(
            rule_id="R01_IDEMPOTENCE_CHECK",
            phase="idempotence",
            inputs={
                "removals_count": sum(1 for pl in hunk.lines if pl.kind == '-'),
                "additions_count": sum(1 for pl in hunk.lines if pl.kind == '+'),
                "has_context": any(pl.kind == ' ' for pl in hunk.lines),
            },
            output="PASS" if idem else "FAIL",
            detail=detail.get("reason", "")[:120] if idem else "not idempotent",
        ))
        if idem:
            return traces

        # R02..R10 — estratégias de ancoragem
        if mt == "EXACT":
            traces.append(RuleTrace(
                "R02_EXACT_REMOVAL", "match", {}, "PASS",
                f"unique block at loc={detail.get('loc')}"))
        elif mt == "EXACT_MULTI":
            cands = detail.get("candidates", [])
            traces.append(RuleTrace(
                "R03_EXACT_REMOVAL_MULTI", "match",
                {"n_candidates": len(cands)}, "PASS",
                f"chose nearest of old_start",
                candidates=cands))
        elif mt == "PARTIAL":
            traces.append(RuleTrace(
                "R04_PARTIAL_STREAK", "match",
                {"contig_len": detail.get("contig_len")}, "PASS",
                f"{detail.get('contig_len')} contiguous"))
        elif mt.startswith("ADD_ONLY"):
            sub = mt.replace("ADD_ONLY_", "") or "FALLBACK"
            rid = {
                "PRE_HEADER":       "R05_ADD_PRE_HEADER",
                "POST_HEADER":      "R06_ADD_POST_HEADER",
                "BOTH_ANCHORS":     "R07_ADD_BOTH_ANCHORS",
                "CTX_DESCONC":      "R08_ADD_CTX_DESCONC",
                "FALLBACK":         "R09_ADD_FALLBACK",
                "CORRECTED":        "R07_ADD_BOTH_ANCHORS",
            }.get(sub, "R09_ADD_FALLBACK")
            traces.append(RuleTrace(rid, "match", {}, "PASS", mt))
        elif mt == "NONE":
            traces.append(RuleTrace(
                "R02_EXACT_REMOVAL", "match", {}, "FAIL", "no contiguous block"))
            traces.append(RuleTrace(
                "R03_EXACT_REMOVAL_MULTI", "match", {}, "SKIP", "n/a"))
            traces.append(RuleTrace(
                "R04_PARTIAL_STREAK", "match", {}, "FAIL",
                f"streak {detail.get('contig_len', 0)} below threshold"))
            traces.append(RuleTrace(
                "R11_REJECT", "decision", {}, "FAIL",
                "no strategy succeeded"))

        # R99 — heurísticas de suspeição (para pesquisa)
        loc = detail.get("loc")
        if isinstance(loc, int) and mt.startswith("ADD_ONLY") and loc < len(file_lines):
            target = file_lines[loc] if loc < len(file_lines) else ""
            if target[:1] == ' ':
                traces.append(RuleTrace(
                    "R99_SUSPICIOUS_INDENTED_ADD", "validate",
                    {"loc": loc + 1}, "WARN",
                    f"insertion into indented line: {target.strip()[:50]!r}"))
        if abs(detail.get("offset", 0)) > 5:
            traces.append(RuleTrace(
                "R99_LARGE_OFFSET", "validate",
                {"offset": detail.get("offset")}, "WARN",
                "large offset — verify anchor"))

        # R12 — classificação semântica (se presente)
        _sv = detail.get("semantic_verdict")
        if _sv and _sv != "UNKNOWN":
            _vconf = detail.get("semantic_confidence", 0.0)
            _vhint = detail.get("semantic_hint", "")
            _vout = "WARN" if _sv in (
                "REFACTORED", "SUPERSEDED", "RELOCATED"
            ) else "FAIL"
            traces.append(RuleTrace(
                "R12_SEMANTIC_CLASSIFY", "validate",
                {"verdict": _sv, "confidence": _vconf},
                _vout, _vhint,
            ))
        return traces

    @staticmethod
    def build_hunk_view(file_path: Path, file_lines: List[str], hunk,
                        detail: Dict, status: str) -> HunkView:
        before, removals, additions, after = [], [], [], []
        seen_change = False
        for pl in hunk.lines:
            if pl.kind == '+':
                additions.append(pl.text); seen_change = True
            elif pl.kind == '-':
                removals.append(pl.text); seen_change = True
            elif not seen_change:
                before.append(pl.text)
            else:
                after.append(pl.text)

        target_idx = max(0, hunk.old_start - 1)
        lo = max(0, target_idx - 5)
        hi = min(len(file_lines), target_idx + 15)
        snippet = [(i + 1, file_lines[i].rstrip()) for i in range(lo, hi)]

        trace = CodeView.infer_rule_trace(
            detail.get("match_type", ""), status, detail, hunk, file_lines)

        return HunkView(
            file=str(file_path), hunk_idx=detail.get("hunk", 0),
            old_start=hunk.old_start, status=status,
            match_type=detail.get("match_type", ""),
            loc=detail.get("loc"), offset=detail.get("offset", 0),
            patch_before=before, patch_removals=removals,
            patch_additions=additions, patch_after=after,
            file_snippet=snippet, file_snippet_range=(lo + 1, hi),
            rule_trace=trace,
            rejection_reason=detail.get("reason", ""),
            suggestions=detail.get("suggestions", []),
            semantic_verdict=detail.get("semantic_verdict", "UNKNOWN"),
            semantic_confidence=detail.get("semantic_confidence", 0.0),
            semantic_hint=detail.get("semantic_hint", ""),
        )

    @staticmethod
    def render_console(v: HunkView) -> str:
        out = []
        sc = {"APPLICABLE": Fore.GREEN, "IDEMPOTENT": Fore.GREEN,
              "AMBIGUOUS": Fore.YELLOW, "REJECTED": Fore.RED}.get(v.status, Fore.WHITE)
        out.append(f"   {Fore.CYAN}┌─ code view · Hunk #{v.hunk_idx} "
                   f"(old_start={v.old_start}, match={v.match_type or '—'}, "
                   f"status={sc}{v.status}{Fore.CYAN}){Style.RESET_ALL}")
        out.append(f"   {Fore.CYAN}│{Fore.MAGENTA} PATCH:{Style.RESET_ALL}")
        for ln in v.patch_before:
            out.append(f"   {Fore.CYAN}│{Fore.RESET}   {ln}")
        for ln in v.patch_removals:
            out.append(f"   {Fore.CYAN}│{Fore.RED} - {ln}{Style.RESET_ALL}")
        for ln in v.patch_additions:
            out.append(f"   {Fore.CYAN}│{Fore.GREEN} + {ln}{Style.RESET_ALL}")
        for ln in v.patch_after:
            out.append(f"   {Fore.CYAN}│{Fore.RESET}   {ln}")
        lo, hi = v.file_snippet_range
        out.append(f"   {Fore.CYAN}│{Fore.BLUE} ARQUIVO (L{lo}-{hi}):{Style.RESET_ALL}")
        for num, text in v.file_snippet:
            out.append(f"   {Fore.CYAN}│{Fore.BLUE}{num:5d}{Fore.RESET} │ {text}")
        if v.rule_trace:
            out.append(f"   {Fore.CYAN}│{Fore.YELLOW} RULE TRACE:{Style.RESET_ALL}")
            for rt in v.rule_trace:
                color = {"PASS": Fore.GREEN, "FAIL": Fore.RED,
                         "WARN": Fore.YELLOW, "SKIP": Fore.DIM}.get(rt.output, Fore.WHITE)
                out.append(f"   {Fore.CYAN}│{Fore.RESET}   "
                           f"{color}[{rt.output}]{Fore.RESET} "
                           f"{Fore.CYAN}{rt.rule_id}{Fore.RESET} "
                           f"{Fore.DIM}· {rt.detail}{Style.RESET_ALL}")
        out.append(f"   {Fore.CYAN}└─{Style.RESET_ALL}")
        return "\n".join(out)

    @staticmethod
    def serialize_report(views: List[HunkView], output_path: Path,
                         patch_file: str, parser_name: str,
                         parser_confidence: float) -> None:
        by_file: Dict[str, List[HunkView]] = {}
        for v in views:
            by_file.setdefault(v.file, []).append(v)
        report = {
            "schema_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "patch_file": patch_file,
            "parser": {"name": parser_name, "confidence": parser_confidence},
            "run_summary": {
                "total_files": len(by_file),
                "total_hunks": len(views),
                "applicable": sum(1 for v in views if v.status == "APPLICABLE"),
                "idempotent": sum(1 for v in views if v.status == "IDEMPOTENT"),
                "rejected": sum(1 for v in views if v.status == "REJECTED"),
                "ambiguous": sum(1 for v in views if v.status == "AMBIGUOUS"),
            },
            "files": [{
                "path": fp,
                "hunks": [{
                    "hunk_idx": v.hunk_idx, "old_start": v.old_start,
                    "status": v.status, "match_type": v.match_type,
                    "loc": v.loc, "offset": v.offset,
                    "patch": {"before": v.patch_before,
                              "removals": v.patch_removals,
                              "additions": v.patch_additions,
                              "after": v.patch_after},
                    "file_snippet": {
                        "range": list(v.file_snippet_range),
                        "lines": [{"num": n, "text": t} for n, t in v.file_snippet]},
                    "rule_trace": [asdict(rt) for rt in v.rule_trace],
                    "rejection_reason": v.rejection_reason,
                    "suggestions": v.suggestions,
                    "semantic_verdict": v.semantic_verdict,
                    "semantic_confidence": v.semantic_confidence,
                    "semantic_hint": v.semantic_hint,
                } for v in hv]
            } for fp, hv in by_file.items()],
        }
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                               encoding='utf-8')
