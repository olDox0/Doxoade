# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/x01_ruletable/engine_x01.py
"""
X01 - Rule Table basico (domain index preserves result).

Pergunta: tabling por `domain` preserva resultado?

Teste:
  X01a - rules_for("programming") expoe exatamente o ruleset esperado
  X01b - run(raw) == run(via table, domain="programming") byte-a-byte
  X01c - boundary: programming != diagnosis (stub isolado por domain)
  X01d - determinism (100 runs de X01b)

Kernel: Q04 inlined (retraction-aware). Sem modificacao.
RuleTable: nova abstracao — filtro por domain preserva rules.

Fixture:
  seed: (f, kind, function), (f, has_signal, yes)

Rules em domain="programming":
  R_a         (prio 10): kind=function          -> a_flag=yes
  R_b         (prio 15): has_signal=yes         -> b_flag=yes
  R_default   (prio 1) : kind=function, NAF b_flag -> status=default
  R_b_override(prio 20): b_flag=yes             -> status=b_active (retrai default)

Stub em domain="diagnosis":
  R_stub      (prio 10): kind=function          -> diagnostic=yes

Cenario:
  Cycle 1 (programming): R_a, R_b, R_default (via NAF). 3 winners.
  Cycle 2: R_default bloqueada (NAF falha); R_b_override retrai default.
  Cycle 3: quiescencia.
  Final: a_flag, b_flag, status=b_active, default retratado.
  Retractions: 1. Cycles: 3. Trace: 4.

Cenario:
  Cycle 1 (diagnosis): R_stub. 1 winner.
  Cycle 2: quiescencia.
  Final: diagnostic=yes. Retractions: 0. Cycles: 2. Trace: 1.

Rodar: doxoade retro-forward run x01
"""
from __future__ import annotations

import dataclasses
import logging
import sys
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"
DEBUG = "--debug" in sys.argv


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc_x01")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


class _Quiet:
    __slots__ = ("level",)
    def __init__(self) -> None:
        self.level = 0
    def __enter__(self):
        self.level += 1
        return self
    def __exit__(self, *exc):
        self.level -= 1


QUIET = _Quiet()


def _dbg(*parts) -> None:
    if DEBUG and QUIET.level == 0:
        print("[DEBUG]", *parts, file=sys.stderr)


# ============================================================
# Kernel (Q04 inlined, unchanged)
# ============================================================
@dataclasses.dataclass(frozen=True)
class Var:
    name: str
    def __repr__(self) -> str:
        return f"Var({self.name})"


class _Wild:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __repr__(self) -> str:
        return "_"


WILD = _Wild()
Term = str | Var | _Wild
Pattern = tuple[Term, Term, Term]


@dataclasses.dataclass(frozen=True)
class Fact:
    s: str
    p: str
    o: str
    source: str = "seed"
    rule_id: str | None = None
    cycle: int = 0
    priority: int = 0

    def to_tuple(self) -> tuple[str, str, str]:
        return (self.s, self.p, self.o)


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    conditions: tuple[Pattern, ...]
    conclusion: Pattern
    negations: tuple[Pattern, ...] = ()
    priority: int = 0

    def conclusion_fact(self, bindings, cycle):
        r = substitute(self.conclusion, bindings)
        if r is None:
            return None
        s, p, o = r
        return Fact(s, p, o, source="derived",
                    rule_id=self.id, cycle=cycle, priority=self.priority)


def unify_term(pattern, value, bindings):
    if isinstance(pattern, _Wild):
        return bindings
    if isinstance(pattern, Var):
        if pattern.name in bindings:
            return bindings if bindings[pattern.name] == value else None
        return {**bindings, pattern.name: value}
    return bindings if pattern == value else None


def unify(pattern, fact_triple, bindings):
    b = bindings
    for p_t, f_v in zip(pattern, fact_triple):
        b = unify_term(p_t, f_v, b)
        if b is None:
            return None
    return b


def substitute(pattern, bindings):
    out = []
    for t in pattern:
        if isinstance(t, _Wild):
            return None
        if isinstance(t, Var):
            if t.name not in bindings:
                return None
            out.append(bindings[t.name])
        else:
            out.append(t)
    return (out[0], out[1], out[2])


def match_with_negations(conditions, negations, live_facts):
    results = []

    def recurse(conds, binds, wit):
        if not conds:
            for neg in negations:
                if any(unify(neg, f.to_tuple(), binds) is not None
                       for f in live_facts):
                    return
            results.append((binds, wit))
            return
        first = conds[0]
        rest = conds[1:]
        for f in live_facts:
            b = unify(first, f.to_tuple(), binds)
            if b is None:
                continue
            recurse(rest, b, wit + [f.to_tuple()])

    recurse(conditions, {}, [])
    return results


class Engine:
    def __init__(self, max_cycles=100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.retracted: set = set()
        self.retracted_history: list[dict] = []
        self.shadowed: list = []
        self.cycles_used = 0
        self.rules_attempted = 0
        self.rule_attempts: dict[str, int] = {}

    def run(self, initial_facts, rules):
        facts = list(initial_facts)
        ordered = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            live_facts = [f for f in facts if f.to_tuple() not in self.retracted]
            existing = set(f.to_tuple() for f in live_facts)
            candidates = []
            for rule in ordered:
                matches = match_with_negations(
                    rule.conditions, rule.negations, live_facts
                )
                for bindings, wit in matches:
                    self.rules_attempted += 1
                    self.rule_attempts[rule.id] = (
                        self.rule_attempts.get(rule.id, 0) + 1
                    )
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        continue
                    if cf.to_tuple() in existing:
                        continue
                    candidates.append((rule, cf, wit))

            winners = {}
            for rule, cf, wit in candidates:
                key = (cf.s, cf.p)
                if key not in winners:
                    winners[key] = (rule, cf, wit)
                    continue
                prev_rule, prev_cf, _ = winners[key]
                if rule.priority > prev_rule.priority:
                    self.shadowed.append((prev_rule.id, prev_cf.to_tuple()))
                    winners[key] = (rule, cf, wit)
                else:
                    self.shadowed.append((rule.id, cf.to_tuple()))

            fired_this_cycle = False
            for (s, p), (rule, cf, wit) in winners.items():
                to_retract = []
                shadow_new = False
                for ef in live_facts:
                    if ef.s != s or ef.p != p:
                        continue
                    if ef.o == cf.o:
                        shadow_new = True
                        break
                    ef_prio = ef.priority if ef.source == "derived" else 999999
                    if cf.priority > ef_prio:
                        to_retract.append(ef)
                    else:
                        shadow_new = True
                        break
                if shadow_new:
                    self.shadowed.append((rule.id, cf.to_tuple()))
                    continue
                for ef in to_retract:
                    self.retracted.add(ef.to_tuple())
                    self.retracted_history.append({
                        "cycle": cycles, "fact": ef.to_tuple(),
                        "by_rule": rule.id, "by_fact": cf.to_tuple(),
                    })
                facts.append(cf)
                self.trace.append({
                    "cycle": cycles, "rule_id": rule.id,
                    "fact": cf.to_tuple(),
                })
                fired_this_cycle = True

            if not fired_this_cycle:
                self.cycles_used = cycles
                return facts, cycles
        raise RuntimeError(f"max_cycles={self.max_cycles}")


# ============================================================
# RuleTable (novo em X01)
# ============================================================
class RuleTable:
    """Index de regras por domain e symptom. Fonte unica de truth.

    Layout:
      rules: dict[rule_id, Rule]
      domain_index: dict[domain, list[rule_id]]
      symptom_index: dict[symptom, list[rule_id]]

    rules_for(domain, symptoms) retorna rules de domain + rules de cada
    symptom, dedup por rule_id. Ordem nao importa: engine ordena por
    priority (stable sort).
    """

    def __init__(self, rules, domain_index=None, symptom_index=None):
        self._rules = {r.id: r for r in rules}
        self._domain_index = domain_index or {}
        self._symptom_index = symptom_index or {}

    def rules_for(self, domain=None, symptoms=None) -> list[Rule]:
        """Filtra por domain/symptoms preservando ordem de construcao.

        Ordem e a do dict `_rules` (== ordem em que as rules foram
        passadas ao __init__). Filtro nao reordena — engine ordena
        por priority via stable sort, empates preservam esta ordem.
        """
        ids_set = set()
        if domain and domain in self._domain_index:
            ids_set.update(self._domain_index[domain])
        for s in (symptoms or []):
            if s in self._symptom_index:
                ids_set.update(self._symptom_index[s])
        return [r for r in self._rules.values() if r.id in ids_set]

    def domain_rules(self, domain) -> list[Rule]:
        return [self._rules[i] for i in self._domain_index.get(domain, [])
                if i in self._rules]

    def known_domains(self) -> list[str]:
        return sorted(self._domain_index.keys())


# ============================================================
# Fixture (rules Q05-style, reducao minima)
# ============================================================
F = Var("F")

RULES_PROGRAMMING = [
    Rule("R_a",
         conditions=((F, "kind", "function"),),
         conclusion=(F, "a_flag", "yes"),
         priority=10),
    Rule("R_b",
         conditions=((F, "has_signal", "yes"),),
         conclusion=(F, "b_flag", "yes"),
         priority=15),
    Rule("R_default",
         conditions=((F, "kind", "function"),),
         negations=((F, "b_flag", WILD),),
         conclusion=(F, "status", "default"),
         priority=1),
    Rule("R_b_override",
         conditions=((F, "b_flag", "yes"),),
         conclusion=(F, "status", "b_active"),
         priority=20),
]

RULES_DIAGNOSIS = [
    Rule("R_stub",
         conditions=((F, "kind", "function"),),
         conclusion=(F, "diagnostic", "yes"),
         priority=10),
]

SEED = [
    Fact("f", "kind", "function"),
    Fact("f", "has_signal", "yes"),
]


def build_table():
    return RuleTable(
        rules=RULES_PROGRAMMING + RULES_DIAGNOSIS,
        domain_index={
            "programming": [r.id for r in RULES_PROGRAMMING],
            "diagnosis": [r.id for r in RULES_DIAGNOSIS],
        },
    )


# ============================================================
# Sub-sondas
# ============================================================
def _run_and_snapshot(rules, seed):
    eng = Engine()
    facts, cycles = eng.run(list(seed), rules)
    live = [f for f in facts if f.to_tuple() not in eng.retracted]
    return {
        "live_tuples": sorted(f.to_tuple() for f in live),
        "cycles": cycles,
        "retractions": len(eng.retracted),
        "retracted_history": list(eng.retracted_history),
        "trace_len": len(eng.trace),
        "rules_attempted": eng.rules_attempted,
    }


def _has(live_tuples, s, p, o=None):
    for t in live_tuples:
        if t[0] == s and t[1] == p:
            if o is None or t[2] == o:
                return True
    return False


def run_x01a():
    table = build_table()
    programming_rules = table.domain_rules("programming")
    prog_ids = sorted(r.id for r in programming_rules)
    raw_ids = sorted(r.id for r in RULES_PROGRAMMING)
    return {
        "programming_ids": prog_ids,
        "raw_ids": raw_ids,
        "identical": prog_ids == raw_ids,
    }


def run_x01b():
    raw = _run_and_snapshot(RULES_PROGRAMMING, SEED)
    table = build_table()
    via = _run_and_snapshot(table.rules_for(domain="programming"), SEED)
    identical = (
        raw["live_tuples"] == via["live_tuples"]
        and raw["cycles"] == via["cycles"]
        and raw["retractions"] == via["retractions"]
        and raw["trace_len"] == via["trace_len"]
        and raw["rules_attempted"] == via["rules_attempted"]
    )
    return {"raw": raw, "tab": via, "identical": identical}


def run_x01c():
    table = build_table()
    prog = _run_and_snapshot(table.rules_for(domain="programming"), SEED)
    diag = _run_and_snapshot(table.rules_for(domain="diagnosis"), SEED)

    prog_status_b_active = _has(prog["live_tuples"], "f", "status", "b_active")
    prog_has_diagnostic = _has(prog["live_tuples"], "f", "diagnostic")
    diag_has_diagnostic = _has(diag["live_tuples"], "f", "diagnostic", "yes")
    diag_has_status = _has(diag["live_tuples"], "f", "status")
    diag_has_b_flag = _has(diag["live_tuples"], "f", "b_flag")

    boundary_ok = (
        prog_status_b_active
        and diag_has_diagnostic
        and not prog_has_diagnostic
        and not diag_has_status
        and not diag_has_b_flag
    )
    return {
        "prog_status_b_active": prog_status_b_active,
        "prog_has_diagnostic": prog_has_diagnostic,
        "diag_has_diagnostic": diag_has_diagnostic,
        "diag_has_status": diag_has_status,
        "diag_has_b_flag": diag_has_b_flag,
        "boundary_ok": boundary_ok,
    }


def run_x01d():
    t0 = time.perf_counter()
    outs = set()
    with QUIET:
        for _ in range(100):
            r = run_x01b()
            outs.add((r["identical"],
                      tuple(r["raw"]["live_tuples"]),
                      r["raw"]["cycles"],
                      r["raw"]["retractions"]))
    t_total = (time.perf_counter() - t0) * 1000
    if DEBUG:
        _dbg(f"  X01d time_total: {t_total:.3f}ms")
    return {"n": 100, "unique_count": len(outs), "unique": outs}


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_x01.py ===")
        _dbg("mode: debug")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    # --- X01a ---
    lines.append("=== X01a: programming domain rules == raw rules ===")
    a = run_x01a()
    lines.append(f"programming_rules_ids: {a['programming_ids']}")
    lines.append(f"raw_rules_ids:         {a['raw_ids']}")
    lines.append(f"identical:             {a['identical']}")
    lines.append("")
    if not a["identical"]:
        falhas.append("X01a: rule sets divergem")

    # --- X01b ---
    lines.append("=== X01b: programming run == raw run ===")
    b = run_x01b()
    lines.append(f"identical:        {b['identical']}")
    lines.append(f"raw_cycles:       {b['raw']['cycles']}")
    lines.append(f"tab_cycles:       {b['tab']['cycles']}")
    lines.append(f"raw_retractions:  {b['raw']['retractions']}")
    lines.append(f"tab_retractions:  {b['tab']['retractions']}")
    lines.append(f"raw_trace_len:    {b['raw']['trace_len']}")
    lines.append(f"tab_trace_len:    {b['tab']['trace_len']}")
    lines.append("raw_live_facts:")
    for t in b["raw"]["live_tuples"]:
        lines.append(f"  {t}")
    lines.append("")
    if not b["identical"]:
        falhas.append("X01b: raw e tab divergem")
    if b["raw"]["retractions"] != 1:
        falhas.append(f"X01b: esperado 1 retracao, veio {b['raw']['retractions']}")

    # --- X01c ---
    lines.append("=== X01c: domain boundary enforced ===")
    c = run_x01c()
    lines.append("programming:")
    lines.append(f"  status=b_active:      {c['prog_status_b_active']}")
    lines.append(f"  has diagnostic fact:  {c['prog_has_diagnostic']}")
    lines.append("diagnosis:")
    lines.append(f"  diagnostic=yes:       {c['diag_has_diagnostic']}")
    lines.append(f"  has status fact:      {c['diag_has_status']}")
    lines.append(f"  has b_flag fact:      {c['diag_has_b_flag']}")
    lines.append(f"boundary_ok: {c['boundary_ok']}")
    lines.append("")
    if not c["boundary_ok"]:
        falhas.append("X01c: boundary violado")

    # --- X01d ---
    lines.append("=== X01d: determinism (100 runs of X01b) ===")
    d = run_x01d()
    lines.append(f"n:            {d['n']}")
    lines.append(f"unique_count: {d['unique_count']}")
    lines.append("")
    if d["unique_count"] != 1:
        falhas.append(f"X01d: {d['unique_count']} variacoes")

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("X01 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("X01 PASS")
        LOG.info("X01 PASS")
        resultado = 0

    for line in lines:
        print(line)

    output_path = Path(__file__).parent / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return resultado


if __name__ == "__main__":
    sys.exit(main())
