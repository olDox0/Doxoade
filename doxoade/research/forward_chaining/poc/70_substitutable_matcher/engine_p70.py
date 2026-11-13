# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py
"""
P70 - Substitutibilidade de matcher (C7) + mensuracao (C6).

Contrato: C7 (Substitutibilidade).
    Contrato + 2 implementacoes -> mesmo comportamento.

C6 embutido: toda sub-sonda reporta metricas (cycles, facts_derived,
rules_fired, lookups). O argumento de que indexar vale a pena E a metrica.

INTERFACE DOS MATCHERS:
    match(conditions, negations, facts) -> list[(bindings, witnesses)]

Dois matchers, mesmo contrato:
    NaiveMatcher   - backtracking forcabruto sobre todos os fatos
    IndexedMatcher - bucket por predicado (facts_by_predicate)

P70a - FizzBuzz-like: trace identico nos 2 matchers.
P70b - Transitive: trace identico.
P70c - NAF: trace identico (negations tambem indexadas).
P70d - Mixed predicates (many facts): trace identico.
P70e - Indexed reduz lookups em P70d (metrico).
P70f - Determinismo: 100 runs, hash do trace estavel.

Se P70 falha, "modular" e teatro. Se passa, C1-C7 cobertos e a arquitetura
pode promover para src/.

Rodar: doxoade retro-forward run 70
"""
from __future__ import annotations

import dataclasses
import hashlib
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc70")
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


# ============================================================
# Tipos comuns
# ============================================================
@dataclasses.dataclass(frozen=True)
class Var:
    name: str

    def __repr__(self) -> str:
        return f"Var({self.name})"


Term = str | Var
Pattern = tuple[Term, Term, Term]


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

    def render(self) -> str:
        return f"({self.s}, {self.p}, {self.o})"


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    conditions: tuple[Pattern, ...]
    conclusion: Pattern
    negations: tuple[Pattern, ...] = ()

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


# ============================================================
# Unificacao (compartilhada pelos dois matchers)
# ============================================================
def unify_term(pattern: Term, value: str,
               bindings: dict) -> dict | None:
    if isinstance(pattern, Var):
        if pattern.name in bindings:
            return bindings if bindings[pattern.name] == value else None
        return {**bindings, pattern.name: value}
    return bindings if pattern == value else None


def unify(pattern: Pattern, fact_tuple: tuple,
          bindings: dict) -> dict | None:
    b = bindings
    for p_t, f_v in zip(pattern, fact_tuple):
        b = unify_term(p_t, f_v, b)
        if b is None:
            return None
    return b


def substitute(pattern: Pattern, bindings: dict):
    out = []
    for t in pattern:
        if isinstance(t, Var):
            if t.name not in bindings:
                return None
            out.append(bindings[t.name])
        else:
            out.append(t)
    return (out[0], out[1], out[2])


# ============================================================
# MATCHER 1: naive (backtracking forcabruto)
# ============================================================
class NaiveMatcher:
    """
    Backtracking que varre TODOS os fatos para cada condicao.
    Negation as failure tambem varre todos os fatos.
    """
    name = "naive"

    def __init__(self):
        self.fact_lookups = 0

    def match(self, conditions, negations, facts):
        self.fact_lookups = 0
        results: list[tuple[dict, list]] = []
        self._recurse(conditions, negations, facts, {}, [], results)
        return results

    def _recurse(self, conds, negs, facts, bindings, witnesses, out):
        if not conds:
            for neg in negs:
                self.fact_lookups += len(facts)
                if any(unify(neg, f.to_tuple(), bindings) is not None
                       for f in facts):
                    return
            out.append((bindings, witnesses))
            return
        first = conds[0]
        rest = conds[1:]
        for f in facts:
            self.fact_lookups += 1
            b = unify(first, f.to_tuple(), bindings)
            if b is None:
                continue
            self._recurse(rest, negs, facts, b,
                          witnesses + [f.to_tuple()], out)

    def stats(self):
        return {"fact_lookups": self.fact_lookups}


# ============================================================
# MATCHER 2: indexed (bucket por predicado)
# ============================================================
class IndexedMatcher:
    """
    Backtracking com indice facts_by_predicate. Rule.get_conditions com
    predicado fixo so varre o bucket; predicado com Var cai para todos.

    NAF tambem usa bucket do predicado negado.
    """
    name = "indexed"

    def __init__(self):
        self.fact_lookups = 0
        self._index: dict[str, list] = {}
        self._signature: tuple | None = None

    def _ensure_index(self, facts):
        sig = tuple(f.to_tuple() for f in facts)
        if sig == self._signature:
            return
        idx: dict[str, list] = {}
        for f in facts:
            idx.setdefault(f.p, []).append(f)
        self._index = idx
        self._signature = sig

    def _candidates(self, pattern: Pattern, facts):
        pred = pattern[1]
        if isinstance(pred, Var):
            return facts
        return self._index.get(pred, [])

    def match(self, conditions, negations, facts):
        self.fact_lookups = 0
        self._ensure_index(facts)
        results: list[tuple[dict, list]] = []
        self._recurse(conditions, negations, facts, {}, [], results)
        return results

    def _recurse(self, conds, negs, facts, bindings, witnesses, out):
        if not conds:
            for neg in negs:
                candidates = self._candidates(neg, facts)
                self.fact_lookups += len(candidates)
                if any(unify(neg, f.to_tuple(), bindings) is not None
                       for f in candidates):
                    return
            out.append((bindings, witnesses))
            return
        first = conds[0]
        rest = conds[1:]
        candidates = self._candidates(first, facts)
        for f in candidates:
            self.fact_lookups += 1
            b = unify(first, f.to_tuple(), bindings)
            if b is None:
                continue
            self._recurse(rest, negs, facts, b,
                          witnesses + [f.to_tuple()], out)

    def stats(self):
        return {"fact_lookups": self.fact_lookups}


# ============================================================
# Engine (identico para ambos matchers)
# ============================================================
class Engine:
    def __init__(self, matcher, max_cycles: int = 100):
        self.matcher = matcher
        self.max_cycles = max_cycles
        self.trace: list[TraceEntry] = []
        self.rules_fired = 0

    def run(self, initial_facts, rules):
        self.trace = []
        self.rules_fired = 0
        facts = list(initial_facts)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            existing = frozenset(f.to_tuple() for f in facts)
            new_this_cycle = []
            for rule in rules:
                for bindings, used in self.matcher.match(
                    rule.conditions, rule.negations, facts
                ):
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        continue
                    t = cf.to_tuple()
                    if t in existing:
                        continue
                    if any(nf[0].to_tuple() == t for nf in new_this_cycle):
                        continue
                    new_this_cycle.append((cf, used))
                    self.rules_fired += 1
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


# ============================================================
# Cenario helper
# ============================================================
def run_scenario(facts_builder, rules_builder, matcher):
    facts, rules = facts_builder(), rules_builder()
    eng = Engine(matcher)
    result_facts, cycles = eng.run(facts, rules)
    stats = matcher.stats()
    return {
        "trace": eng.trace,
        "cycles": cycles,
        "derived": sum(1 for f in result_facts if f.source == "derived"),
        "rules_fired": eng.rules_fired,
        "lookups": stats["fact_lookups"],
    }


def trace_signature(trace: list[TraceEntry]) -> str:
    """Hash canonico do trace - usado para comparacao entre matchers."""
    parts = []
    for e in trace:
        parts.append(
            f"{e.cycle}|{e.rule_id}|{e.fact}|{tuple(e.derived_from)}"
        )
    return hashlib.sha256(";;".join(parts).encode("utf-8")).hexdigest()[:16]


# ============================================================
# Cenarios (inline, espelhando P00/P20/P21 e stress)
# ============================================================
def scenario_fizzbuzz_facts():
    return [
        Triple("n", "div3", "yes"),
        Triple("n", "div5", "yes"),
        Triple("n", "div3", "no"),
        Triple("n", "div5", "no"),
        Triple("n", "div3", "yes"),
        Triple("n", "div5", "no"),
        Triple("n", "div3", "no"),
        Triple("n", "div5", "yes"),
    ]


def scenario_fizzbuzz_rules():
    return [
        Rule("R_fb",
             conditions=(("n", "div3", "yes"), ("n", "div5", "yes")),
             conclusion=("n", "out", "fizzbuzz")),
        Rule("R_f",
             conditions=(("n", "div3", "yes"), ("n", "div5", "no")),
             conclusion=("n", "out", "fizz")),
        Rule("R_b",
             conditions=(("n", "div3", "no"), ("n", "div5", "yes")),
             conclusion=("n", "out", "buzz")),
    ]


X, Y, Z = Var("X"), Var("Y"), Var("Z")


def scenario_transitive_facts():
    return [
        Triple("joao", "pai", "maria"),
        Triple("maria", "pai", "pedro"),
        Triple("pedro", "pai", "ana"),
    ]


def scenario_transitive_rules():
    return [
        Rule("R_trans",
             conditions=((X, "pai", Y), (Y, "pai", Z)),
             conclusion=(X, "avo", Z)),
        Rule("R_bisavo",
             conditions=((X, "avo", Y), (Y, "pai", Z)),
             conclusion=(X, "bisavo", Z)),
    ]


def scenario_naf_facts():
    return [
        Triple("a", "r", "b"),
        Triple("c", "r", "d"),
        Triple("c", "is_bad", "yes"),
    ]


def scenario_naf_rules():
    return [
        Rule("R_ok",
             conditions=((X, "r", Y),),
             negations=((X, "is_bad", "yes"),),
             conclusion=(X, "ok", Y)),
    ]


def scenario_mixed_facts():
    base = [Triple(f"ent_{i}", "label", "x") for i in range(100)]
    base += [
        Triple("seed", "trigger", "yes"),
        Triple("seed", "input", "data"),
    ]
    return base


def scenario_mixed_rules():
    return [
        Rule("R_1",
             conditions=(("seed", "trigger", "yes"),),
             conclusion=("seed", "fired", "yes")),
        Rule("R_2",
             conditions=(("seed", "input", "data"),),
             conclusion=("seed", "processed", "yes")),
    ]


SCENARIOS = [
    ("fizzbuzz", scenario_fizzbuzz_facts, scenario_fizzbuzz_rules),
    ("transitive", scenario_transitive_facts, scenario_transitive_rules),
    ("naf", scenario_naf_facts, scenario_naf_rules),
    ("mixed_many_facts", scenario_mixed_facts, scenario_mixed_rules),
]


def run_both(facts_builder, rules_builder):
    """Roda o mesmo cenario nos dois matchers. Retorna (naive_result, indexed_result)."""
    n = run_scenario(facts_builder, rules_builder, NaiveMatcher())
    i = run_scenario(facts_builder, rules_builder, IndexedMatcher())
    return n, i


# ============================================================
# Sub-sondas
# ============================================================
def run_identity_sonda(label, facts_builder, rules_builder) -> dict:
    n, i = run_both(facts_builder, rules_builder)
    n_sig = trace_signature(n["trace"])
    i_sig = trace_signature(i["trace"])
    return {
        "label": label,
        "naive_sig": n_sig,
        "indexed_sig": i_sig,
        "identical": n_sig == i_sig,
        "naive": n,
        "indexed": i,
    }


def run_p70a():
    return run_identity_sonda("fizzbuzz",
                              scenario_fizzbuzz_facts,
                              scenario_fizzbuzz_rules)


def run_p70b():
    return run_identity_sonda("transitive",
                              scenario_transitive_facts,
                              scenario_transitive_rules)


def run_p70c():
    return run_identity_sonda("naf",
                              scenario_naf_facts,
                              scenario_naf_rules)


def run_p70d():
    return run_identity_sonda("mixed_many_facts",
                              scenario_mixed_facts,
                              scenario_mixed_rules)


def run_p70e() -> dict:
    """Indexed reduz lookups em cenario com muitos fatos irrelevantes."""
    n, i = run_both(scenario_mixed_facts, scenario_mixed_rules)
    speedup = (n["lookups"] / i["lookups"]) if i["lookups"] > 0 else 0.0
    return {
        "naive_lookups": n["lookups"],
        "indexed_lookups": i["lookups"],
        "speedup": round(speedup, 2),
        "strictly_fewer": i["lookups"] < n["lookups"],
    }


def run_p70f() -> dict:
    """Determinismo: 100 runs do cenario transitive, hash estavel."""
    sigs_naive = set()
    sigs_indexed = set()
    for _ in range(100):
        n, i = run_both(scenario_transitive_facts, scenario_transitive_rules)
        sigs_naive.add(trace_signature(n["trace"]))
        sigs_indexed.add(trace_signature(i["trace"]))
    return {
        "n": 100,
        "naive_unique": len(sigs_naive),
        "indexed_unique": len(sigs_indexed),
        "naive_sig": next(iter(sigs_naive)) if len(sigs_naive) == 1 else None,
        "indexed_sig": next(iter(sigs_indexed)) if len(sigs_indexed) == 1 else None,
    }


# ============================================================
# main
# ============================================================
def render_stats_line(label, r):
    n = r["naive"]
    i = r["indexed"]
    return (
        f"  {label:<18} cycles={n['cycles']:<3} "
        f"derived={n['derived']:<3} "
        f"rules_fired={n['rules_fired']:<3} "
        f"lookups(N/I)={n['lookups']}/{i['lookups']}"
    )


def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    sonda_results = []

    # ---------- identidade em cada cenario ----------
    identity_sondas = [
        ("P70a", "fizzbuzz-like", run_p70a),
        ("P70b", "transitive", run_p70b),
        ("P70c", "naf", run_p70c),
        ("P70d", "mixed_many_facts", run_p70d),
    ]
    for label, name, fn in identity_sondas:
        r = fn()
        sonda_results.append(r)
        lines.append(f"=== {label}: identity em '{name}' ===")
        lines.append(f"identical: {r['identical']}")
        # sigs vao para logging.txt, nao para stdout
        LOG.info("%s naive_sig=%s indexed_sig=%s",
                 r["label"], r["naive_sig"], r["indexed_sig"])
        if not r["identical"]:
            # se divergir, EMITE as sigs no stdout para debug
            lines.append(f"  naive_sig:   {r['naive_sig']}")
            lines.append(f"  indexed_sig: {r['indexed_sig']}")
            n_tr = r["naive"]["trace"]
            i_tr = r["indexed"]["trace"]
            lines.append(f"  naive_trace_len:   {len(n_tr)}")
            lines.append(f"  indexed_trace_len: {len(i_tr)}")
        lines.append("")
        if not r["identical"]:
            falhas.append(f"{label}: traces divergem em '{name}'")

    # ---------- C6: mensuracao ----------
    lines.append("=== C6: mensuracao por cenario (naive vs indexed) ===")
    for r in sonda_results:
        lines.append(render_stats_line(r["label"], r))
    lines.append("")

    # ---------- P70e: indexed ganha em muitos fatos ----------
    lines.append("=== P70e: indexed reduz lookups (mixed_many_facts) ===")
    e = run_p70e()
    lines.append(f"strictly_fewer: {e['strictly_fewer']}")
    lines.append(f"speedup:        {e['speedup']}x")
    LOG.info("P70e naive_lookups=%d indexed_lookups=%d",
             e["naive_lookups"], e["indexed_lookups"])
    lines.append("")
    if not e["strictly_fewer"]:
        falhas.append("P70e: indexed NAO reduziu lookups - indexacao inutil")

    # ---------- P70f: determinismo ----------
    lines.append("=== P70f: determinismo (100 runs de transitive) ===")
    f = run_p70f()
    lines.append(f"n:              {f['n']}")
    lines.append(f"naive_unique:   {f['naive_unique']}")
    lines.append(f"indexed_unique: {f['indexed_unique']}")
    lines.append("")
    if f["naive_unique"] != 1:
        falhas.append(f"P70f: naive {f['naive_unique']} variacoes")
    if f["indexed_unique"] != 1:
        falhas.append(f"P70f: indexed {f['indexed_unique']} variacoes")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("P70 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P70 PASS")
        LOG.info("P70 PASS")
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
