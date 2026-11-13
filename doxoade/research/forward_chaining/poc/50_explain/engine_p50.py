# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/50_explain/engine_p50.py
"""
P50 - Explainability (C5): positive + negative.

Contrato: C5 (Explicacao).
    Fatos + Regras + Trace -> Cadeia legivel.

Extensao sobre P20/P21: TraceEntry ganha derived_from (fatos usados
em cada derivacao). Com isso:

- explain(F): "F foi derivado pela regra R no ciclo C, a partir de [...]"
- explain_chain(F): arvore recursiva ate fatos seed
- why_not(F): "F nao foi derivado. Para cada regra que casaria a
  conclusao, dizemos qual condicao falhou e com quais bindings."

P50a - explain(avo(joao, pedro))
P50b - explain_chain(bisavo(joao, ana)) -> arvore 2 niveis
P50c - why_not(avo(joao, ana)) -> R_trans falha em cond[1]
P50d - explain(seed) -> source=seed
P50e - explain(unknown) -> source=unknown
P50f - completeness: derived tem trace; parents sao seed ou derived
P50g - determinism (100 runs)

Cenario:
    Fatos: pai(joao,maria), pai(maria,pedro), pai(pedro,ana)
    R_trans: pai(X,Y) AND pai(Y,Z) -> avo(X,Z)
    R_bisavo: avo(X,Y) AND pai(Y,Z) -> bisavo(X,Z)

    Ciclo 1: avo(joao,pedro), avo(maria,ana)
    Ciclo 2: bisavo(joao,ana)

Rodar: doxoade retro-forward run 50
"""
from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc50")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


class CycleLimitError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class Var:
    name: str
    def __repr__(self) -> str:
        return f"Var({self.name})"


@dataclasses.dataclass(frozen=True)
class Triple:
    s: str
    p: str
    o: str
    source: str = "seed"
    rule_id: str | None = None
    cycle: int = 0

    def to_tuple(self) -> tuple[str, str, str]:
        return (self.s, self.p, self.o)


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    conditions: tuple
    conclusion: tuple

    def conclusion_fact(self, bindings, cycle):
        r = substitute(self.conclusion, bindings)
        if r is None:
            return None
        s, p, o = r
        return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)


@dataclasses.dataclass
class TraceEntry:
    cycle: int
    rule_id: str
    fact: tuple
    derived_from: list


# ---------- rendering ----------
def render_term(t):
    if isinstance(t, Var):
        return t.name
    return str(t)


def render(t) -> str:
    return f"({render_term(t[0])}, {render_term(t[1])}, {render_term(t[2])})"


def render_bindings(bindings) -> str:
    if not bindings:
        return "{}"
    return "{" + ", ".join(
        f"{k}={v}" for k, v in sorted(bindings.items())
    ) + "}"


# ---------- unificacao ----------
def unify_term(pattern, value, bindings):
    if isinstance(pattern, Var):
        if pattern.name in bindings:
            return bindings if bindings[pattern.name] == value else None
        return {**bindings, pattern.name: value}
    return bindings if pattern == value else None


def unify(pattern, fact_tuple, bindings):
    b = bindings
    for p_t, f_v in zip(pattern, fact_tuple):
        b = unify_term(p_t, f_v, b)
        if b is None:
            return None
    return b


def substitute(pattern, bindings):
    out = []
    for t in pattern:
        if isinstance(t, Var):
            if t.name not in bindings:
                return None
            out.append(bindings[t.name])
        else:
            out.append(t)
    return (out[0], out[1], out[2])


def match_conditions(conditions, facts, bindings=None):
    if bindings is None:
        bindings = {}
    if not conditions:
        return [bindings]
    first = conditions[0]
    rest = conditions[1:]
    results = []
    for f in facts:
        b = unify(first, f.to_tuple(), bindings)
        if b is None:
            continue
        results.extend(match_conditions(rest, facts, b))
    return results


def match_with_facts(conditions, facts, bindings=None):
    """Backtracking com witnesses: [(bindings, [facts_usados_em_ordem])]."""
    if bindings is None:
        bindings = {}
    if not conditions:
        return [(bindings, [])]
    first = conditions[0]
    rest = conditions[1:]
    results = []
    for f in facts:
        b = unify(first, f.to_tuple(), bindings)
        if b is None:
            continue
        for sub_b, sub_used in match_with_facts(rest, facts, b):
            results.append((sub_b, [f.to_tuple()] + sub_used))
    return results


# ---------- engine ----------
class Engine:
    def __init__(self, max_cycles=100):
        self.max_cycles = max_cycles
        self.trace: list[TraceEntry] = []

    def run(self, initial_facts, rules):
        self.trace = []
        facts = list(initial_facts)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            existing = frozenset(f.to_tuple() for f in facts)
            new_this_cycle = []
            for rule in rules:
                for bindings, used in match_with_facts(rule.conditions, facts):
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        continue
                    t = cf.to_tuple()
                    if t in existing:
                        continue
                    if any(nf[0].to_tuple() == t for nf in new_this_cycle):
                        continue
                    new_this_cycle.append((cf, used))
            if not new_this_cycle:
                return facts, cycles
            for cf, used in new_this_cycle:
                facts.append(cf)
                self.trace.append(TraceEntry(
                    cycle=cycles,
                    rule_id=cf.rule_id,
                    fact=cf.to_tuple(),
                    derived_from=used,
                ))
        raise CycleLimitError(f"max_cycles={self.max_cycles}")


# ---------- explicacao positiva ----------
def find_trace(fact_tuple, trace):
    for entry in trace:
        if entry.fact == fact_tuple:
            return entry
    return None


def explain(fact_tuple, trace, seed_tuples) -> dict:
    entry = find_trace(fact_tuple, trace)
    if entry is not None:
        return {
            "source": "derived",
            "rule_id": entry.rule_id,
            "cycle": entry.cycle,
            "derived_from": entry.derived_from,
        }
    if fact_tuple in seed_tuples:
        return {"source": "seed"}
    return {"source": "unknown"}


def _render_chain(fact_tuple, trace, seed_tuples, indent, lines):
    prefix = "  " * indent
    entry = find_trace(fact_tuple, trace)
    if entry is not None:
        lines.append(
            f"{prefix}{render(fact_tuple)} <- {entry.rule_id} @ c{entry.cycle}"
        )
        for parent in entry.derived_from:
            _render_chain(parent, trace, seed_tuples, indent + 1, lines)
        return
    if fact_tuple in seed_tuples:
        lines.append(f"{prefix}{render(fact_tuple)} [seed]")
        return
    lines.append(f"{prefix}{render(fact_tuple)} [unknown]")


def explain_chain(fact_tuple, trace, seed_tuples) -> list[str]:
    lines: list[str] = []
    _render_chain(fact_tuple, trace, seed_tuples, 0, lines)
    return lines


# ---------- explicacao negativa ----------
def unify_conclusion(conclusion, target_triple):
    """Unifica conclusao (com Vars) com target (strings). Bindings ou None."""
    bindings: dict[str, str] = {}
    for term, value in zip(conclusion, target_triple):
        if isinstance(term, Var):
            if term.name in bindings:
                if bindings[term.name] != value:
                    return None
            else:
                bindings[term.name] = value
        else:
            if term != value:
                return None
    return bindings


def match_with_diagnostic(conditions, fact_tuples, initial_bindings):
    """Backtracking com diagnostico: (matches, deepest_fail).

    deepest_fail = (idx, cond, bindings) no nivel mais profundo onde
    todas as extensoes morreram.
    """
    matches: list = []
    deepest_fail: list = [None]

    def recurse(idx, binds):
        if idx == len(conditions):
            matches.append(binds)
            return
        extended = False
        for ft in fact_tuples:
            b = unify(conditions[idx], ft, binds)
            if b is None:
                continue
            extended = True
            recurse(idx + 1, b)
        if not extended:
            if deepest_fail[0] is None or idx > deepest_fail[0][0]:
                deepest_fail[0] = (idx, conditions[idx], binds)

    recurse(0, initial_bindings)
    if matches:
        return matches, None
    return [], deepest_fail[0]


def why_not(target_tuple, rules, all_facts, seed_tuples) -> dict:
    fact_tuples = [f.to_tuple() for f in all_facts]
    if target_tuple in fact_tuples:
        return {"status": "present"}
    explanations = []
    for rule in rules:
        bindings = unify_conclusion(rule.conclusion, target_tuple)
        if bindings is None:
            continue
        matches, failed = match_with_diagnostic(
            rule.conditions, fact_tuples, bindings
        )
        if matches:
            explanations.append({
                "rule_id": rule.id,
                "status": "should_have_fired",
            })
        else:
            explanations.append({
                "rule_id": rule.id,
                "status": "failed",
                "failed_at": failed,
            })
    if not explanations:
        return {"status": "no_rule_matches"}
    return {"status": "not_derived", "explanations": explanations}


# ---------- completeness ----------
def check_completeness(facts, trace, seed_tuples) -> dict:
    fact_tuples = {f.to_tuple() for f in facts}
    trace_facts = {e.fact for e in trace}
    derived = fact_tuples - seed_tuples
    missing_trace = derived - trace_facts
    orphans = set()
    for e in trace:
        for parent in e.derived_from:
            if parent not in seed_tuples and parent not in trace_facts:
                orphans.add(parent)
    return {
        "all_derived_have_trace": len(missing_trace) == 0,
        "missing_trace": sorted(missing_trace),
        "all_parents_traceable": len(orphans) == 0,
        "orphans": sorted(orphans),
        "derived_count": len(derived),
        "trace_count": len(trace),
    }


# ============================================================
# Cenario
# ============================================================
X = Var("X")
Y = Var("Y")
Z = Var("Z")

RULES = [
    Rule("R_trans",
         conditions=((X, "pai", Y), (Y, "pai", Z)),
         conclusion=(X, "avo", Z)),
    Rule("R_bisavo",
         conditions=((X, "avo", Y), (Y, "pai", Z)),
         conclusion=(X, "bisavo", Z)),
]

SEED_FACTS = [
    Triple("joao", "pai", "maria"),
    Triple("maria", "pai", "pedro"),
    Triple("pedro", "pai", "ana"),
]

SEED_TUPLES = {(f.s, f.p, f.o) for f in SEED_FACTS}


def run_scenario():
    engine = Engine()
    facts, cycles = engine.run(SEED_FACTS, RULES)
    return facts, engine.trace, cycles


# ============================================================
# Sub-sondas
# ============================================================
def run_p50a() -> dict:
    _, trace, _ = run_scenario()
    return explain(("joao", "avo", "pedro"), trace, SEED_TUPLES)


def run_p50b() -> list[str]:
    _, trace, _ = run_scenario()
    return explain_chain(("joao", "bisavo", "ana"), trace, SEED_TUPLES)


def run_p50c() -> dict:
    facts, _, _ = run_scenario()
    return why_not(("joao", "avo", "ana"), RULES, facts, SEED_TUPLES)


def run_p50d() -> dict:
    _, trace, _ = run_scenario()
    return explain(("joao", "pai", "maria"), trace, SEED_TUPLES)


def run_p50e() -> dict:
    _, trace, _ = run_scenario()
    return explain(("zed", "avo", "yan"), trace, SEED_TUPLES)


def run_p50f() -> dict:
    facts, trace, _ = run_scenario()
    return check_completeness(facts, trace, SEED_TUPLES)


def run_p50g() -> dict:
    sigs: set = set()
    for _ in range(100):
        _, trace, _ = run_scenario()
        sig = tuple(sorted((e.rule_id, e.fact) for e in trace))
        sigs.add(sig)
    return {"n": 100, "unique_count": len(sigs)}


# ============================================================
# main
# ============================================================
def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P50a ----------
    lines.append("=== P50a: explain(avo(joao, pedro)) ===")
    a = run_p50a()
    lines.append(f"fact: {render(('joao', 'avo', 'pedro'))}")
    lines.append(f"source: {a['source']}")
    if a["source"] == "derived":
        lines.append(f"rule_id: {a['rule_id']}")
        lines.append(f"cycle: {a['cycle']}")
        lines.append("derived_from:")
        for p in a["derived_from"]:
            lines.append(f"  - {render(p)}")
    lines.append("")

    if a.get("rule_id") != "R_trans" or a.get("cycle") != 1:
        falhas.append(f"P50a: inesperado: {a}")
    if a.get("derived_from") != [
        ("joao", "pai", "maria"),
        ("maria", "pai", "pedro"),
    ]:
        falhas.append(f"P50a: parents inesperados: {a.get('derived_from')}")

    # ---------- P50b ----------
    lines.append("=== P50b: explain_chain(bisavo(joao, ana)) ===")
    b_result = run_p50b()
    for ln in b_result:
        lines.append(ln)
    lines.append("")

    expected_b = [
        "(joao, bisavo, ana) <- R_bisavo @ c2",
        "  (joao, avo, pedro) <- R_trans @ c1",
        "    (joao, pai, maria) [seed]",
        "    (maria, pai, pedro) [seed]",
        "  (pedro, pai, ana) [seed]",
    ]
    if b_result != expected_b:
        falhas.append(f"P50b: chain inesperada: {b_result}")

    # ---------- P50c ----------
    lines.append("=== P50c: why_not(avo(joao, ana)) ===")
    c = run_p50c()
    lines.append(f"status: {c['status']}")
    if c["status"] == "not_derived":
        for expl in c["explanations"]:
            if expl["status"] == "failed":
                idx, cond, binds = expl["failed_at"]
                lines.append(f"rule {expl['rule_id']}:")
                lines.append(f"  failed at condition[{idx}]: {render(cond)}")
                lines.append(f"  bindings: {render_bindings(binds)}")
            else:
                lines.append(f"rule {expl['rule_id']}: {expl['status']}")
    lines.append("")

    if c["status"] != "not_derived":
        falhas.append(f"P50c: status inesperado: {c['status']}")
    else:
        failed = next(
            (e for e in c["explanations"] if e["status"] == "failed"), None
        )
        if failed is None:
            falhas.append("P50c: nenhuma explicacao 'failed'")
        else:
            idx, cond, binds = failed["failed_at"]
            if idx != 1:
                falhas.append(f"P50c: failed_at idx={idx}, esperado 1")
            if binds != {"X": "joao", "Y": "maria", "Z": "ana"}:
                falhas.append(f"P50c: bindings inesperados: {binds}")

    # ---------- P50d ----------
    lines.append("=== P50d: explain(seed) ===")
    d = run_p50d()
    lines.append(f"fact: {render(('joao', 'pai', 'maria'))}")
    lines.append(f"source: {d['source']}")
    lines.append("")
    if d["source"] != "seed":
        falhas.append(f"P50d: source={d['source']}")

    # ---------- P50e ----------
    lines.append("=== P50e: explain(unknown) ===")
    e = run_p50e()
    lines.append(f"fact: {render(('zed', 'avo', 'yan'))}")
    lines.append(f"source: {e['source']}")
    lines.append("")
    if e["source"] != "unknown":
        falhas.append(f"P50e: source={e['source']}")

    # ---------- P50f ----------
    lines.append("=== P50f: completeness ===")
    f = run_p50f()
    lines.append(f"all_derived_have_trace: {f['all_derived_have_trace']}")
    lines.append(f"all_parents_traceable: {f['all_parents_traceable']}")
    lines.append(f"derived_count: {f['derived_count']}")
    lines.append(f"trace_count: {f['trace_count']}")
    lines.append("")
    if not f["all_derived_have_trace"]:
        falhas.append(f"P50f: missing trace: {f['missing_trace']}")
    if not f["all_parents_traceable"]:
        falhas.append(f"P50f: orphans: {f['orphans']}")
    if f["derived_count"] != 3:
        falhas.append(f"P50f: derived_count={f['derived_count']}")
    if f["trace_count"] != 3:
        falhas.append(f"P50f: trace_count={f['trace_count']}")

    # ---------- P50g ----------
    lines.append("=== P50g: determinism (100 runs) ===")
    g = run_p50g()
    lines.append(f"n: {g['n']}")
    lines.append(f"unique_count: {g['unique_count']}")
    lines.append("")
    if g["unique_count"] != 1:
        falhas.append(f"P50g: {g['unique_count']} variacoes")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("P50 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P50 PASS")
        LOG.info("P50 PASS")
        resultado = 0

    for ln in lines:
        print(ln)

    output_path = Path(__file__).parent / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return resultado


if __name__ == "__main__":
    sys.exit(main())
