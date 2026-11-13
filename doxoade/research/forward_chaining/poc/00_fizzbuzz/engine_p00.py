# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/00_fizzbuzz/engine_p00.py
"""
P00 - FizzBuzz (C1) com debug estruturado.

Debug:
    py engine_p00.py --debug
    Emite [DEBUG] em stderr. stdout/output.txt inalterados.
    Mostra: bulk aggregate (100 casos) + trace completo (n=15),
    cycle-by-cycle, timing.
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
    logger = logging.getLogger("poc00")
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


class CycleLimitError(RuntimeError):
    """Motor nao atingiu quiescencia dentro de max_cycles."""


@dataclasses.dataclass(frozen=True)
class Fact:
    key: str
    value: str
    source: str = "seed"
    rule_id: str | None = None
    cycle: int = 0

    def to_pair(self) -> tuple[str, str]:
        return (self.key, self.value)


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    conditions: tuple[tuple[str, str], ...]
    conclusion: tuple[str, str]
    priority: int = 0
    description: str = ""

    def match(self, facts: list[Fact]) -> bool:
        pairs = {f.to_pair() for f in facts}
        return all(c in pairs for c in self.conditions)

    def conclusion_fact(self, cycle: int) -> Fact:
        k, v = self.conclusion
        return Fact(k, v, source="derived", rule_id=self.id, cycle=cycle)


class ForwardChainingEngine:
    """
    Varredura continua (semantica A: sem snapshot).

    Cada ciclo varre regras em ordem decrescente de prioridade. Fatos
    derivados durante o ciclo ficam visiveis para regras seguintes.
    Para FizzBuzz (trigger exclusivo), A e B sao equivalentes.
    P01+ usam B (snapshot).
    """

    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.cycles_used = 0
        self.rules_attempted = 0
        self.rule_attempts: dict[str, int] = {}
        self.cycle_history: list[dict] = []

    def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
        facts = list(initial_facts)
        ordered = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            fired_this_cycle = False
            cycle_info = {
                "cycle": cycles,
                "matches": {},
                "candidates": [],
                "idempotent": [],
                "quiescence": False,
            }

            for rule in ordered:
                self.rules_attempted += 1
                self.rule_attempts[rule.id] = self.rule_attempts.get(rule.id, 0) + 1

                if not rule.match(facts):
                    cycle_info["matches"][rule.id] = False
                    continue
                cycle_info["matches"][rule.id] = True

                new_fact = rule.conclusion_fact(cycle=cycles)
                pair = new_fact.to_pair()
                if any(f.to_pair() == pair for f in facts):
                    cycle_info["idempotent"].append((rule.id, pair))
                    continue

                cycle_info["candidates"].append((rule.id, rule.priority, pair))
                facts.append(new_fact)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": rule.id,
                    "conditions": rule.conditions,
                    "conclusion": pair,
                })
                fired_this_cycle = True

            if not fired_this_cycle:
                cycle_info["quiescence"] = True
                self.cycle_history.append(cycle_info)
                self.cycles_used = cycles
                return facts

            self.cycle_history.append(cycle_info)

        raise CycleLimitError(f"max_cycles={self.max_cycles} sem quiescencia")


RULES: list[Rule] = [
    Rule("R_fizzbuzz",
         conditions=(("div3", "yes"), ("div5", "yes")),
         conclusion=("out", "fizzbuzz"),
         priority=30),
    Rule("R_fizz",
         conditions=(("div3", "yes"), ("div5", "no")),
         conclusion=("out", "fizz"),
         priority=20),
    Rule("R_buzz",
         conditions=(("div3", "no"), ("div5", "yes")),
         conclusion=("out", "buzz"),
         priority=20),
]


def facts_for(n: int) -> list[Fact]:
    return [
        Fact("div3", "yes" if n % 3 == 0 else "no"),
        Fact("div5", "yes" if n % 5 == 0 else "no"),
    ]


def solve_with_engine(n: int) -> tuple[str, ForwardChainingEngine]:
    engine = ForwardChainingEngine()
    facts = engine.run(facts_for(n), RULES)
    outs = [f for f in facts if f.key == "out"]
    result = outs[0].value if outs else str(n)
    return result, engine


def solve(n: int) -> str:
    result, _ = solve_with_engine(n)
    return result


def reference(n: int) -> str:
    if n % 15 == 0:
        return "fizzbuzz"
    if n % 3 == 0:
        return "fizz"
    if n % 5 == 0:
        return "buzz"
    return str(n)


def _dbg_cycle_p00(cycle_info: dict) -> None:
    _dbg(f"  cycle {cycle_info['cycle']}:")
    m = cycle_info["matches"]
    _dbg("    matches: " + " ".join(f"{rid}={v}" for rid, v in m.items()))
    for rid, prio, fact in cycle_info["candidates"]:
        _dbg(f"    candidate: {rid} prio={prio} -> {fact}")
    for rid, fact in cycle_info["idempotent"]:
        _dbg(f"    idempotent: {rid} -> {fact}")
    if cycle_info["quiescence"]:
        _dbg("    quiescence")


def _debug_bulk_aggregate(bulk_metrics: list[dict], t_total: float) -> None:
    _dbg("--- bulk: 100 FizzBuzz ---")
    _dbg("  n: 100")
    _dbg("  oracle_matches: 100/100")

    hist: dict[int, int] = {}
    for m in bulk_metrics:
        hist[m["cycles"]] = hist.get(m["cycles"], 0) + 1
    _dbg(f"  cycles_histogram: {dict(sorted(hist.items()))}")

    total_attempts = sum(m["rules_attempted"] for m in bulk_metrics)
    max_attempts = max(m["rules_attempted"] for m in bulk_metrics)
    _dbg(f"  rules_attempted_total: {total_attempts}")
    _dbg(f"  rules_attempted_max_per_n: {max_attempts}")

    per_rule: dict[str, int] = {}
    for m in bulk_metrics:
        for rid, cnt in m["rule_attempts"].items():
            per_rule[rid] = per_rule.get(rid, 0) + cnt
    _dbg("  per_rule_attempts: " + " ".join(f"{k}={v}" for k, v in sorted(per_rule.items())))

    _dbg(f"  time_total: {t_total:.3f}ms")
    _dbg(f"  time_per_n_avg: {t_total/100:.3f}ms")
    _dbg("")


def main() -> int:
    if DEBUG:
        _dbg("=== engine_p00.py ===")
        _dbg("mode: debug")
        _dbg("engine_semantics: A (continuous scan, no snapshot)")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    # Bulk 100 FizzBuzz
    t_bulk_start = time.perf_counter()
    answers: list[str] = []
    bulk_metrics: list[dict] = []
    for n in range(1, 101):
        t0 = time.perf_counter()
        result, engine = solve_with_engine(n)
        t_ms = (time.perf_counter() - t0) * 1000
        answers.append(result)
        if DEBUG:
            bulk_metrics.append({
                "n": n,
                "time_ms": t_ms,
                "cycles": engine.cycles_used,
                "rules_attempted": engine.rules_attempted,
                "rule_attempts": dict(engine.rule_attempts),
            })
    t_bulk = (time.perf_counter() - t_bulk_start) * 1000

    refs = [reference(n) for n in range(1, 101)]
    if answers != refs:
        mismatches = [
            (i + 1, a, r)
            for i, (a, r) in enumerate(zip(answers, refs))
            if a != r
        ]
        print(f"FAIL: {len(mismatches)} divergencia(s)", file=sys.stderr)
        for n, a, r in mismatches[:5]:
            print(f"  n={n}: motor={a!r} oraculo={r!r}", file=sys.stderr)
        LOG.error("divergencia do oraculo: %d casos", len(mismatches))
        return 1

    if DEBUG:
        _debug_bulk_aggregate(bulk_metrics, t_bulk)

    # Trace case
    t0 = time.perf_counter()
    engine = ForwardChainingEngine()
    engine.run(facts_for(15), RULES)
    t_trace = (time.perf_counter() - t0) * 1000

    if DEBUG:
        _dbg("--- trace case: n=15 ---")
        seed = facts_for(15)
        _dbg(f"  seed_facts: {[f.to_pair() for f in seed]}")
        for ci in engine.cycle_history:
            _dbg_cycle_p00(ci)
        _dbg(f"  trace_len: {len(engine.trace)}")
        _dbg(f"  timing: {t_trace:.3f}ms")
        _dbg("")

    # Output canonico
    lines: list[str] = ["=== FIZZBUZZ 1..100 ==="]
    lines.extend(answers)

    lines.append("=== TRACE n=15 ===")
    for step in engine.trace:
        conds = ", ".join(f"{k}={v}" for k, v in step["conditions"])
        k, v = step["conclusion"]
        lines.append(
            f"ciclo {step['cycle']}: {step['rule_id']} "
            f"[{conds}] -> {k}={v}"
        )

    for line in lines:
        print(line)

    output_path = Path(__file__).parent / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if DEBUG:
        _dbg("=== done: all checks passed ===")
    LOG.info("P00 PASS: 100/100")
    return 0

class _Quiet:
    """Context manager que suspende _dbg durante execucoes em massa."""
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

if __name__ == "__main__":
    sys.exit(main())
