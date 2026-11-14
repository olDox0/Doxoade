# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/x04_induction/engine_x04.py
"""
X04 - Inducao por clustering sobre misses.json (v1: memorizacao controlada).

Contrato provado (se PASS):
    - clusters emergem com jaccard >= threshold sobre facts (nao source)
    - regras induzidas tem evidence rastreavel
    - delta mensuravel na mesma corpus (memorizacao)
    - X03 re-run com --rules ainda passa seus 7 checks

Escopo (Q1): silent_quiescence + rule_miss
    extraction_miss fica fora — e dominio de Q06 (extractor nao ve),
    nao de X04 (rule falta).

NAO prova (v2):
    - generalizacao (precisa hold-out)
    - FP rate (precisa baseline humano)
    - que as regras induzidas sao "boas" (so que cobrem exemplos)

Decisoes Q2 (naming hibrido):
    - interseccao com 1 fact descritivo -> nome derivado
      (return_expr_kind=Call -> returns_call)
    - interseccao composta ou sem descritivo -> cluster_NNN (humano renomeia)

Decisoes Q3 (jaccard):
    - threshold = 0.7 (equilibrado)
    - min_cluster_size = 3 (Q4 B: agressivo)
    - cluster via connected components (nao k-means, nao hierarquico)

Decisoes Q5 (v1 e memorizacao):
    - hold-out fica para v2
    - "delta > 0" prova que a regra dispara nos exemplos, nao que generaliza

Rodar: doxoade retro-forward run x04
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = Path(__file__).parent / "logging.txt"
DEBUG = "--debug" in sys.argv
HERE = Path(__file__).resolve().parent
X03_DIR = HERE.parent / "x03_real_corpus"
X03_ENGINE = X03_DIR / "engine_x03.py"
MISSES_PATH = X03_DIR / "misses.json"
X03_SUMMARY_PATH = X03_DIR / "x03_with_rules_summary.json"

INDUCED_RULES_PATH = HERE / "induced_rules.json"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc_x04")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


def _dbg(*parts) -> None:
    if DEBUG:
        print("[DEBUG]", *parts, file=sys.stderr)


# ============================================================
# Config (Q1/Q2/Q3 fixas no prototipo)
# ============================================================
CONFIG = {
    "scope": ["silent_quiescence", "rule_miss"],
    "min_cluster_size": 3,
    "jaccard_threshold": 0.7,
    "default_priority": 12,
    "trivial_facts": [
        ["kind", "function"],
    ],
    "trivial_predicates": ["name", "name_prefix", "body_len", "branch_count"],
    "descriptive_predicates": [
        "return_expr_kind", "body_0_kind",
    ],
}


# ============================================================
# Load
# ============================================================
def load_misses(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def filter_scope(units, scope) -> list[dict]:
    return [u for u in units if u.get("kind") in scope]


# ============================================================
# Fact signatures
# ============================================================
def _is_trivial(p, o) -> bool:
    if [p, o] in CONFIG["trivial_facts"]:
        return True
    if p in CONFIG["trivial_predicates"]:
        return True
    return False


def extract_signature(unit) -> frozenset:
    sig: set = set()
    for fact in unit.get("seed_facts", []):
        s, p, o = fact
        if not _is_trivial(p, o):
            sig.add((p, o))
    for fact in unit.get("derived_facts", []):
        s, p, o = fact
        if not _is_trivial(p, o):
            sig.add((p, o))
    return frozenset(sig)


# ============================================================
# Similarity + clustering
# ============================================================
def jaccard(a, b) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def cluster_units(signatures, threshold) -> list[list[int]]:
    """Connected components via Jaccard >= threshold. Deterministico."""
    n = len(signatures)
    if n == 0:
        return []

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(signatures[i], signatures[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    return [sorted(g) for g in groups.values()]


# ============================================================
# Intersection
# ============================================================
def intersect_facts(signatures, cluster_indices) -> frozenset:
    if not cluster_indices:
        return frozenset()
    result = set(signatures[cluster_indices[0]])
    for idx in cluster_indices[1:]:
        result &= signatures[idx]
    return frozenset(result)


# ============================================================
# Naming (Q2 hibrido)
# ============================================================
def derive_rule_name(intersection) -> tuple[str | None, str]:
    descriptive = [(p, o) for p, o in intersection
                   if p in CONFIG["descriptive_predicates"]]

    if len(descriptive) != 1:
        return None, "auto"

    pred, obj = descriptive[0]
    if pred == "return_expr_kind":
        return f"returns_{obj.lower()}", "derived"
    if pred == "body_0_kind":
        return f"body_starts_{obj.lower()}", "derived"
    if pred == "complexity":
        obj_clean = obj.replace("+", "plus")
        return f"complexity_{obj_clean}", "derived"
    return None, "auto"


# ============================================================
# Propose rules
# ============================================================
def _pick_conclusion(intersection, name_hint, name_source):
    if name_source == "derived" and name_hint:
        return "category", name_hint
    p, o = sorted(intersection)[0]
    return "category", f"induced_{p}_{o.lower()}"


def _is_useful_intersection(intersection) -> bool:
    """Rejeita interseccao so com body_len (nao categorizavel)."""
    if not intersection:
        return False
    if all(p == "body_len" for p, _ in intersection):
        return False
    return True


def propose_rules(clusters, units, signatures) -> tuple[list[dict], list[dict]]:
    rules: list[dict] = []
    diagnostics: list[dict] = []

    for idx, cluster_idx in enumerate(clusters):
        diag = {
            "cluster_index": idx,
            "size": len(cluster_idx),
            "unit_ids": [units[i]["id"] for i in cluster_idx],
        }

        if len(cluster_idx) < CONFIG["min_cluster_size"]:
            diag["skipped_reason"] = (
                f"size {len(cluster_idx)} < min {CONFIG['min_cluster_size']}"
            )
            diagnostics.append(diag)
            continue

        intersection = intersect_facts(signatures, cluster_idx)
        diag["intersection"] = sorted([list(p) for p in intersection])

        if not _is_useful_intersection(intersection):
            diag["skipped_reason"] = "intersection trivial ou vazia"
            diagnostics.append(diag)
            continue

        name, name_source = derive_rule_name(intersection)
        if name is None:
            name = f"cluster_{idx:03d}"

        concl_pred, concl_obj = _pick_conclusion(
            intersection, name, name_source
        )

        rule_id = f"R_ind_{len(rules)+1:03d}"
        rule = {
            "id": rule_id,
            "intersection": sorted([list(p) for p in intersection]),
            "conclusion": [concl_pred, concl_obj],
            "evidence": [units[i]["id"] for i in cluster_idx],
            "cluster_size": len(cluster_idx),
            "name_source": name_source,
            "name_hint": name,
            "priority": CONFIG["default_priority"],
        }
        rules.append(rule)

        diag["rule_id"] = rule_id
        diag["name"] = name
        diagnostics.append(diag)

    return rules, diagnostics


# ============================================================
# Write induced_rules.json
# ============================================================
def write_induced_rules(rules, misses_ref, path) -> None:
    data = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "misses_ref": misses_ref,
        "config": {
            "scope": CONFIG["scope"],
            "min_cluster_size": CONFIG["min_cluster_size"],
            "jaccard_threshold": CONFIG["jaccard_threshold"],
            "trivial_facts": CONFIG["trivial_facts"],
            "trivial_predicates": CONFIG["trivial_predicates"],
        },
        "rules": rules,
    }
    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def hash_induced_rules(rules) -> str:
    canonical = json.dumps(rules, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ============================================================
# Run X03 with rules
# ============================================================
def run_x03_with_rules(rules_path) -> dict:
    cmd = [sys.executable, str(X03_ENGINE), "--rules", str(rules_path)]
    try:
        result = subprocess.run(
            cmd, cwd=str(X03_DIR), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=120, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = e.stderr or ""
        return {"ok": False, "error": f"timeout: {err[:200]}",
                "stdout": out, "stderr": err}

    if result.returncode != 0:
        return {
            "ok": False,
            "error": f"exit {result.returncode}",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    return {"ok": True, "stdout": result.stdout, "stderr": result.stderr}


def load_summary() -> dict | None:
    if not X03_SUMMARY_PATH.exists():
        return None
    return json.loads(X03_SUMMARY_PATH.read_text(encoding="utf-8"))


# ============================================================
# Delta
# ============================================================
def compute_delta(before: dict, after: dict | None) -> dict:
    if after is None:
        return {"error": "no summary from X03 re-run"}
    delta = {}
    for kind in ("covered", "extraction_miss", "rule_miss",
                 "silent_quiescence", "process_error"):
        b = before.get(kind, 0)
        a = after.get(kind, 0)
        delta[kind] = {"before": b, "after": a, "delta": a - b}
    return delta


# ============================================================
# Render
# ============================================================
def _format_intersection(intersection) -> str:
    if not intersection:
        return "{}"
    parts = [f"{p}={o}" for p, o in intersection]
    return "{" + ", ".join(parts) + "}"


def render_output(before_counts, diagnostics, rules, delta,
                  x03_run, checks) -> list[str]:
    lines = []
    lines.append("=== X04: induction over misses.json ===")
    lines.append("")

    lines.append("=== Config ===")
    lines.append(f"  scope:              {CONFIG['scope']}")
    lines.append(f"  min_cluster_size:   {CONFIG['min_cluster_size']}")
    lines.append(f"  jaccard_threshold:  {CONFIG['jaccard_threshold']}")
    units_in_scope = sum(before_counts.get(k, 0) for k in CONFIG["scope"])
    lines.append(f"  units_in_scope:     {units_in_scope}")
    lines.append("")

    lines.append("=== Clusters ===")
    if not diagnostics:
        lines.append("  (nenhum cluster)")
    for d in diagnostics:
        status = "SKIP" if d.get("skipped_reason") else "OK"
        inter = _format_intersection(
            [tuple(p) for p in d.get("intersection", [])]
        )
        lines.append(
            f"  cluster_{d['cluster_index']:03d} [{status}] "
            f"size={d['size']:>2}  intersection={inter}"
        )
        if d.get("skipped_reason"):
            lines.append(f"    skip: {d['skipped_reason']}")
        elif d.get("rule_id"):
            rule = next(r for r in rules if r["id"] == d["rule_id"])
            lines.append(
                f"    -> {rule['id']}: category={rule['name_hint']}  "
                f"(name_source={rule['name_source']})"
            )
            lines.append(f"    evidence: {', '.join(rule['evidence'])}")

    lines.append("")

    lines.append("=== Induced rules ===")
    if not rules:
        lines.append("  (nenhuma regra induzida)")
    for r in rules:
        inter = _format_intersection([tuple(p) for p in r["intersection"]])
        lines.append(
            f"  {r['id']}: category={r['name_hint']:<22} "
            f"({r['cluster_size']} units, source={r['name_source']})"
        )
        lines.append(f"    intersection: {inter}")
        lines.append(f"    evidence: {', '.join(r['evidence'])}")
    lines.append("")

    lines.append("=== Delta (X03 re-run com induced rules) ===")
    if "error" in delta:
        lines.append(f"  ERROR: {delta['error']}")
    else:
        for kind in ("covered", "extraction_miss", "rule_miss",
                     "silent_quiescence"):
            d = delta[kind]
            sign = "+" if d["delta"] > 0 else ""
            lines.append(
                f"  {kind:<20} {d['before']:>3} -> {d['after']:>3}  "
                f"({sign}{d['delta']})"
            )
    lines.append("")

    if not x03_run["ok"]:
        lines.append("=== X03 re-run: FAIL ===")
        lines.append(f"  error: {x03_run['error']}")
        err_tail = (x03_run.get("stderr") or "").strip().splitlines()[-3:]
        for ln in err_tail:
            lines.append(f"  {ln}")
        lines.append("")

    lines.append("=== Self-check ===")
    pass_count = 0
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        if c["pass"]:
            pass_count += 1
        lines.append(f"  {c['name']:<28} {status:<6} ({c['detail']})")
    lines.append("")

    if pass_count == len(checks):
        lines.append("X04 PASS")
    else:
        lines.append(f"FAIL: {len(checks) - pass_count} falha(s)")

    return lines


# ============================================================
# Self-check
# ============================================================
def _self_check(rules, diagnostics, delta, x03_run, det_hashes, summary_after):
    checks = []

    c1_ok = len(rules) >= 1
    checks.append({
        "name": "C1 induced_rules_written",
        "pass": c1_ok,
        "detail": f"{len(rules)} regras",
    })

    c2_ok = all(len(r["evidence"]) >= CONFIG["min_cluster_size"]
                for r in rules) if rules else False
    checks.append({
        "name": "C2 evidence_complete",
        "pass": c2_ok,
        "detail": ("OK" if c2_ok else "regra sem evidence suficiente"),
    })

    sizes = {r["cluster_size"] for r in rules}
    c3_ok = len(sizes) >= 2 or len(rules) >= 3
    checks.append({
        "name": "C3 clusters_varied",
        "pass": c3_ok,
        "detail": f"sizes={sorted(sizes)}" if sizes else "sem regras",
    })

    delta_covered = delta.get("covered", {}).get("delta", 0) if "error" not in delta else 0
    c4_ok = delta_covered > 0
    checks.append({
        "name": "C4 delta_positive",
        "pass": c4_ok,
        "detail": f"covered delta={delta_covered:+d}",
    })

    c5_ok = x03_run["ok"] and bool(summary_after) and summary_after.get(
        "self_check_pass", False
    )
    checks.append({
        "name": "C5 x03_still_passes",
        "pass": c5_ok,
        "detail": ("OK" if c5_ok else "X03 re-run falhou"),
    })

    uniq = len(set(det_hashes))
    c6_ok = uniq == 1
    checks.append({
        "name": "C6 determinism",
        "pass": c6_ok,
        "detail": f"{uniq} hash(es) em 3 runs",
    })

    return checks


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_x04.py ===")
        _dbg(f"misses path: {MISSES_PATH}")
        _dbg(f"x03 engine:  {X03_ENGINE}")
        _dbg("")

    t0 = time.perf_counter()

    if not MISSES_PATH.exists():
        print(f"FATAL: {MISSES_PATH} not found. Rode X03 primeiro.",
              file=sys.stderr)
        return 2
    if not X03_ENGINE.exists():
        print(f"FATAL: {X03_ENGINE} not found.", file=sys.stderr)
        return 2

    misses = load_misses(MISSES_PATH)
    before_counts = misses["units_by_kind"]

    scoped = filter_scope(misses["units"], CONFIG["scope"])
    if DEBUG:
        _dbg(f"  units in scope: {len(scoped)}")

    signatures = [extract_signature(u) for u in scoped]
    if DEBUG:
        for u, sig in zip(scoped, signatures):
            _dbg(f"  {u['id']} {u['unit_name']:<25} sig={sorted(sig)}")

    clusters = cluster_units(signatures, CONFIG["jaccard_threshold"])
    if DEBUG:
        _dbg(f"  clusters found: {len(clusters)}")
        for i, c in enumerate(clusters):
            _dbg(f"    cluster_{i:03d}: {len(c)} units")

    rules, diagnostics = propose_rules(clusters, scoped, signatures)
    if DEBUG:
        _dbg(f"  rules proposed: {len(rules)}")

    misses_ref = {
        "path": MISSES_PATH.relative_to(X03_DIR.parent.parent.parent.parent.parent.parent).as_posix()
            if MISSES_PATH.is_absolute() else str(MISSES_PATH),
        "corpus_hash": misses.get("corpus_hash"),
    }
    write_induced_rules(rules, misses_ref, INDUCED_RULES_PATH)

    det_hashes = [hash_induced_rules(rules)]
    for _ in range(2):
        scoped2 = filter_scope(misses["units"], CONFIG["scope"])
        sigs2 = [extract_signature(u) for u in scoped2]
        clusters2 = cluster_units(sigs2, CONFIG["jaccard_threshold"])
        rules2, _ = propose_rules(clusters2, scoped2, sigs2)
        det_hashes.append(hash_induced_rules(rules2))

    if rules:
        x03_run = run_x03_with_rules(INDUCED_RULES_PATH)
    else:
        x03_run = {"ok": False, "error": "nenhuma regra induzida"}

    summary_after = load_summary() if x03_run["ok"] else None
    after_counts = summary_after["units_by_kind"] if summary_after else None
    delta = compute_delta(before_counts, after_counts) if summary_after \
        else {"error": "X03 nao gerou summary"}

    checks = _self_check(rules, diagnostics, delta, x03_run,
                         det_hashes, summary_after)

    lines = render_output(before_counts, diagnostics, rules, delta,
                          x03_run, checks)

    for ln in lines:
        print(ln)

    output_path = HERE / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
    )

    all_pass = all(c["pass"] for c in checks)
    if all_pass:
        t_ms = (time.perf_counter() - t0) * 1000
        LOG.info("X04 PASS: %d rules, delta covered=%+d, %.1fms",
                 len(rules),
                 delta.get("covered", {}).get("delta", 0) if "error" not in delta else 0,
                 t_ms)
        return 0
    else:
        LOG.error("X04 FAIL: %d check(s)",
                  sum(1 for c in checks if not c["pass"]))
        return 1


if __name__ == "__main__":
    sys.exit(main())
