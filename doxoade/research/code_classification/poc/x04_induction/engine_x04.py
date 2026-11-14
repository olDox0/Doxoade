# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/x04_induction/engine_x04.py
"""
X04 v2 - Inducao com hold-out validation.

Mudancas de v1:
    1. Assinatura = seed_facts only + filtro de valores triviais
       (no/none/unknown/other). Remove derived_facts (category=unknown,
       has_any_smell=*, complexity=*, pattern=*, smell_*). Esses fatos
       inflam Jaccard e produzem clusters tautologicos (cluster_001
       de v1 = "qualquer funcao nao-dirty").

    2. Clustering = clique (all-pairs Jaccard >= threshold). v1 usava
       connected components, que e transitivo (A~B + B~C nao implica
       A~C) e absorvia via cadeia.

    3. Hold-out split 70/30 (seed=42). Induz apenas em train, mede
       cobertura em train (memorizacao) e test (generalizacao).

O que v2 prova:
    - clusters emergem de sinal real (facts estruturais, nao derivados)
    - regras generalizam (test coverage > 0 em unidades nao vistas)
    - delta honesto (train e test medidos separados)

Deferido para v3:
    - Naming dictionary (cluster_NNN -> nome semantico)
    - Quarantine (candidate vs stable)
    - Dice coefficient

Rodar: doxoade retro-forward run x04
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
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
# Config v2
# ============================================================
CONFIG = {
    "scope": ["silent_quiescence", "rule_miss"],
    "min_cluster_size": 3,
    "jaccard_threshold": 0.7,
    "default_priority": 12,
    "holdout_ratio": 0.3,
    "holdout_seed": 42,
    "trivial_facts": [["kind", "function"]],
    "trivial_predicates": ["name", "name_prefix", "body_len", "branch_count"],
    "trivial_values": ["no", "none", "unknown", "other"],
}


# ============================================================
# Load
# ============================================================
def load_misses(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def filter_scope(units, scope) -> list[dict]:
    return [u for u in units if u.get("kind") in scope]


# ============================================================
# Hold-out split (v2)
# ============================================================
def split_holdout(units, ratio, seed) -> tuple[list[dict], list[dict]]:
    """70/30 split deterministico via seed. Preserva IDs."""
    rng = random.Random(seed)
    ids = [u["id"] for u in units]
    rng.shuffle(ids)
    n_test = max(1, int(len(ids) * ratio))
    test_ids = set(ids[:n_test])
    train = [u for u in units if u["id"] not in test_ids]
    test = [u for u in units if u["id"] in test_ids]
    return train, test


# ============================================================
# Fact signatures (v2: seed-only + filtro de valores triviais)
# ============================================================
def _is_trivial(p, o) -> bool:
    if [p, o] in CONFIG["trivial_facts"]:
        return True
    if p in CONFIG["trivial_predicates"]:
        return True
    return False


def _is_trivial_value(o) -> bool:
    return str(o) in CONFIG["trivial_values"]


def extract_signature(unit) -> frozenset:
    """Assinatura = seed_facts only, sem fatos triviais.

    Remove:
      - kind=function (universal)
      - name, name_prefix, body_len, branch_count (triviais metricos)
      - qualquer fact com valor em {no, none, unknown, other}
      - derived_facts inteiros (category, complexity, pattern, smell_*,
        has_any_smell) — esses sao produzidos pelo motor, nao pela
        extracao, e inflam Jaccard com "contexto vazio".
    """
    sig: set = set()
    for fact in unit.get("seed_facts", []):
        s, p, o = fact
        if _is_trivial(p, o):
            continue
        if _is_trivial_value(o):
            continue
        sig.add((p, o))
    return frozenset(sig)


# ============================================================
# Similarity
# ============================================================
def jaccard(a, b) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ============================================================
# Clustering v2: clique (all-pairs Jaccard >= threshold)
# ============================================================
def clique_cluster_units(signatures, threshold, min_size) -> list[list[int]]:
    """Greedy clique extraction.

    Diferente de connected components: todos os pares dentro do cluster
    DEVEM ter Jaccard >= threshold. Isso elimina transitividade.

    Determinismo: iteracao por `range(n)` e `sorted(candidates)` — sem
    iteracao em set, sem hash de ID.
    """
    n = len(signatures)
    if n == 0:
        return []

    remaining = set(range(n))
    clusters = []

    while len(remaining) >= min_size:
        adj: dict[int, set[int]] = {i: set() for i in remaining}
        for i in remaining:
            for j in remaining:
                if i < j and jaccard(signatures[i], signatures[j]) >= threshold:
                    adj[i].add(j)
                    adj[j].add(i)

        best_clique: list[int] = []
        for start in sorted(remaining):
            clique = {start}
            for c in sorted(adj[start]):
                if c in remaining and c not in clique:
                    if all(jaccard(signatures[c], signatures[k]) >= threshold
                           for k in clique):
                        clique.add(c)
            if len(clique) > len(best_clique):
                best_clique = sorted(clique)

        if len(best_clique) < min_size:
            break

        clusters.append(best_clique)
        remaining -= set(best_clique)

    for i in sorted(remaining):
        clusters.append([i])

    return clusters


# ============================================================
# Intersection / naming
# ============================================================
def intersect_facts(signatures, cluster_indices) -> frozenset:
    if not cluster_indices:
        return frozenset()
    result = set(signatures[cluster_indices[0]])
    for idx in cluster_indices[1:]:
        result &= signatures[idx]
    return frozenset(result)


def derive_rule_name(intersection) -> tuple[str | None, str]:
    """v2: prioriza return_expr_kind. Sem isso, auto.

    v1 tentava body_0_kind tambem, mas body_starts_return e generico
    demais para nome util. Melhor auto + humano renomeia via review.md.
    """
    for p, o in intersection:
        if p == "return_expr_kind":
            return f"returns_{o.lower()}", "derived"
    return None, "auto"


def _pick_conclusion(intersection, name_hint, name_source):
    if name_source == "derived" and name_hint:
        return "category", name_hint
    p, o = sorted(intersection)[0]
    return "category", f"induced_{p}_{o.lower()}"


def _is_useful_intersection(intersection) -> bool:
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
# Write / hash
# ============================================================
def write_induced_rules(rules, misses_ref, path) -> None:
    data = {
        "schema_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "misses_ref": misses_ref,
        "config": {
            "scope": CONFIG["scope"],
            "min_cluster_size": CONFIG["min_cluster_size"],
            "jaccard_threshold": CONFIG["jaccard_threshold"],
            "holdout_ratio": CONFIG["holdout_ratio"],
            "holdout_seed": CONFIG["holdout_seed"],
            "trivial_facts": CONFIG["trivial_facts"],
            "trivial_predicates": CONFIG["trivial_predicates"],
            "trivial_values": CONFIG["trivial_values"],
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
        return {"ok": False, "error": f"timeout: {str(e.stderr)[:200]}",
                "stdout": e.stdout or "", "stderr": e.stderr or ""}

    summary = load_summary()
    if result.returncode != 0:
        return {
            "ok": False,
            "error": f"exit {result.returncode}",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "summary": summary,
        }

    return {"ok": True, "stdout": result.stdout,
            "stderr": result.stderr, "summary": summary}


def load_summary() -> dict | None:
    if not X03_SUMMARY_PATH.exists():
        return None
    try:
        return json.loads(X03_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


# ============================================================
# Coverage (v2: train vs test)
# ============================================================
def split_coverage(train, test, summary_after) -> dict:
    """Le summary_after['units'], particiona cobertura por train/test."""
    if summary_after is None or "units" not in summary_after:
        return {
            "train_total": len(train), "train_covered": 0,
            "test_total": len(test), "test_covered": 0,
            "train_covered_ids": [], "test_covered_ids": [],
        }

    after = {u["id"]: u for u in summary_after["units"]}
    train_covered = [
        u["id"] for u in train
        if after.get(u["id"], {}).get("current_category") not in
           (None, "unknown")
    ]
    test_covered = [
        u["id"] for u in test
        if after.get(u["id"], {}).get("current_category") not in
           (None, "unknown")
    ]
    return {
        "train_total": len(train),
        "train_covered": len(train_covered),
        "train_covered_ids": train_covered,
        "test_total": len(test),
        "test_covered": len(test_covered),
        "test_covered_ids": test_covered,
    }


# ============================================================
# Render
# ============================================================
def _format_intersection(intersection) -> str:
    if not intersection:
        return "{}"
    parts = [f"{p}={o}" for p, o in intersection]
    return "{" + ", ".join(parts) + "}"


def render_output(before_counts, train, test, diagnostics, rules,
                  coverage, x03_run, checks) -> list[str]:
    lines = []
    lines.append("=== X04 v2: induction with hold-out validation ===")
    lines.append("")

    lines.append("=== Config ===")
    lines.append(f"  scope:              {CONFIG['scope']}")
    lines.append(f"  units_in_scope:     {before_counts.get('silent_quiescence', 0) + before_counts.get('rule_miss', 0)}")
    lines.append(f"  holdout_ratio:      {CONFIG['holdout_ratio']}")
    lines.append(f"  holdout_seed:       {CONFIG['holdout_seed']}")
    lines.append(f"  train_units:        {len(train)}")
    lines.append(f"  test_units:         {len(test)}")
    lines.append(f"  signature:          seed-only, filter trivial values")
    lines.append(f"  clustering:         clique")
    lines.append(f"  jaccard_threshold:  {CONFIG['jaccard_threshold']}")
    lines.append(f"  min_cluster_size:   {CONFIG['min_cluster_size']}")
    lines.append("")

    lines.append(f"=== Clusters (train only, {len(train)} units) ===")
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
    lines.append("")

    lines.append("=== Coverage (X03 re-run com induced rules) ===")
    train_pct = (coverage["train_covered"] / coverage["train_total"] * 100
                 if coverage["train_total"] else 0)
    test_pct = (coverage["test_covered"] / coverage["test_total"] * 100
                if coverage["test_total"] else 0)
    lines.append(
        f"  TRAIN:   {coverage['train_covered']:>3} / "
        f"{coverage['train_total']:>3} covered ({train_pct:.0f}%)  "
        f"[memorizacao]"
    )
    lines.append(
        f"  TEST:    {coverage['test_covered']:>3} / "
        f"{coverage['test_total']:>3} covered ({test_pct:.0f}%)  "
        f"[generalizacao]"
    )
    if coverage["test_covered_ids"]:
        lines.append(f"  test_covered: {', '.join(coverage['test_covered_ids'])}")
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
        lines.append("X04 v2 PASS")
    else:
        lines.append(f"FAIL: {len(checks) - pass_count} falha(s)")

    return lines


# ============================================================
# Self-check (v2: C7 holdout_generalizes)
# ============================================================
def _self_check(rules, coverage, x03_run, det_hashes, summary_after):
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

    c4_ok = coverage["train_covered"] > 0
    checks.append({
        "name": "C4 train_covered",
        "pass": c4_ok,
        "detail": f"{coverage['train_covered']}/{coverage['train_total']}",
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

    c7_ok = coverage["test_covered"] >= 1
    test_pct = (coverage["test_covered"] / coverage["test_total"] * 100
                if coverage["test_total"] else 0)
    checks.append({
        "name": "C7 holdout_generalizes",
        "pass": c7_ok,
        "detail": (f"{coverage['test_covered']}/{coverage['test_total']}"
                   f" ({test_pct:.0f}%)"
                   if c7_ok else
                   f"0/{coverage['test_total']} — memorizacao confirmada"),
    })

    return checks


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_x04.py v2 ===")
        _dbg(f"misses path: {MISSES_PATH}")
        _dbg("")

    t0 = time.perf_counter()

    if not MISSES_PATH.exists():
        print(f"FATAL: {MISSES_PATH} not found.", file=sys.stderr)
        return 2
    if not X03_ENGINE.exists():
        print(f"FATAL: {X03_ENGINE} not found.", file=sys.stderr)
        return 2

    misses = load_misses(MISSES_PATH)
    before_counts = misses["units_by_kind"]

    scoped = filter_scope(misses["units"], CONFIG["scope"])
    train, test = split_holdout(scoped, CONFIG["holdout_ratio"],
                                 CONFIG["holdout_seed"])
    if DEBUG:
        _dbg(f"  scoped: {len(scoped)}, train: {len(train)}, "
             f"test: {len(test)}")

    train_signatures = [extract_signature(u) for u in train]
    if DEBUG:
        for u, sig in zip(train, train_signatures):
            _dbg(f"  TRAIN {u['id']} {u['unit_name']:<22} sig={sorted(sig)}")
        for u in test:
            _dbg(f"  TEST  {u['id']} {u['unit_name']:<22}")

    clusters = clique_cluster_units(
        train_signatures,
        CONFIG["jaccard_threshold"],
        CONFIG["min_cluster_size"],
    )
    if DEBUG:
        _dbg(f"  clusters: {len(clusters)}")
        for i, c in enumerate(clusters):
            _dbg(f"    cluster_{i:03d}: {len(c)} units")

    rules, diagnostics = propose_rules(clusters, train, train_signatures)

    misses_ref = {
        "path": "doxoade/research/code_classification/poc/x03_real_corpus/misses.json",
        "corpus_hash": misses.get("corpus_hash"),
    }
    write_induced_rules(rules, misses_ref, INDUCED_RULES_PATH)

    det_hashes = [hash_induced_rules(rules)]
    for _ in range(2):
        sigs2 = [extract_signature(u) for u in train]
        c2 = clique_cluster_units(sigs2, CONFIG["jaccard_threshold"],
                                   CONFIG["min_cluster_size"])
        r2, _ = propose_rules(c2, train, sigs2)
        det_hashes.append(hash_induced_rules(r2))

    if rules:
        x03_run = run_x03_with_rules(INDUCED_RULES_PATH)
    else:
        x03_run = {"ok": False, "error": "nenhuma regra induzida",
                    "summary": None}

    summary_after = x03_run.get("summary")
    coverage = split_coverage(train, test, summary_after)

    checks = _self_check(rules, coverage, x03_run, det_hashes, summary_after)
    lines = render_output(before_counts, train, test, diagnostics, rules,
                          coverage, x03_run, checks)

    for ln in lines:
        print(ln)

    output_path = HERE / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
    )

    all_pass = all(c["pass"] for c in checks)
    if all_pass:
        t_ms = (time.perf_counter() - t0) * 1000
        LOG.info("X04 v2 PASS: %d rules, train=%d/%d test=%d/%d, %.1fms",
                 len(rules),
                 coverage["train_covered"], coverage["train_total"],
                 coverage["test_covered"], coverage["test_total"],
                 t_ms)
        return 0
    else:
        LOG.error("X04 v2 FAIL: %d check(s)",
                  sum(1 for c in checks if not c["pass"]))
        return 1


if __name__ == "__main__":
    sys.exit(main())
