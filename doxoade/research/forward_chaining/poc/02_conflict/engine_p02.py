# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/02_conflict/engine_p02.py
"""
P02 - Conflito e determinismo (C1) com debug estruturado.

Debug:
    py engine_p02.py --debug
    Emite [DEBUG] em stderr. stdout/output.txt inalterados.
    Mostra: per-sonda, cycle-by-cycle, resolucao de conflito com
    reason explicito, timing.

P02a - conflito (prioridade decide)
P02b - sem conflito (chaves distintas)
P02c - determinismo (100 runs) - debug so do run 1 + agregado
P02d - tie-break por ordem de definicao
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
    logger = logging.getLogger("poc02")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


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


class CycleLimitError(RuntimeError):
    pass


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

    def match(self, snapshot: frozenset[tuple[str, str]]) -> bool:
        return all(c in snapshot for c in self.conditions)

    def conclusion_fact(self, cycle: int) -> Fact:
        k, v = self.conclusion
        return Fact(k, v, source="derived", rule_id=self.id, cycle=cycle)


class ForwardChainingEngine:
    """
    Snapshot por ciclo + resolucao de conflito por prioridade.
    Fato perdedor vai para `shadowed` (nunca re-entra).
    """

    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.conflicts: list[dict] = []
        self.shadowed: set[tuple[str, str]] = set()
        self.cycles_used = 0
        self.cycle_history: list[dict] = []
        self.rules_attempted = 0
        self.rule_attempts: dict[str, int] = {}

    def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
        facts: list[Fact] = list(initial_facts)
        ordered = sorted(
            enumerate(rules), key=lambda p: (-p[1].priority, p[0])
        )
        ordered = [r for _, r in ordered]
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            snapshot = frozenset(f.to_pair() for f in facts)
            existing = set(snapshot)
            cycle_info = {
                "cycle": cycles,
                "matches": {},
                "candidates": [],
                "idempotent": [],
                "already_shadowed": [],
                "winners": {},
                "shadowed_this_cycle": [],
                "quiescence": False,
            }

            candidates: list[tuple[Rule, Fact]] = []
            for rule in ordered:
                self.rules_attempted += 1
                self.rule_attempts[rule.id] = self.rule_attempts.get(rule.id, 0) + 1

                if not rule.match(snapshot):
                    cycle_info["matches"][rule.id] = 0
                    continue
                cycle_info["matches"][rule.id] = 1

                new_fact = rule.conclusion_fact(cycle=cycles)
                pair = new_fact.to_pair()
                if pair in existing:
                    cycle_info["idempotent"].append((rule.id, pair))
                    continue
                if pair in self.shadowed:
                    cycle_info["already_shadowed"].append((rule.id, pair))
                    continue
                candidates.append((rule, new_fact))
                cycle_info["candidates"].append((rule.id, rule.priority, pair))

            if not candidates:
                cycle_info["quiescence"] = True
                self.cycle_history.append(cycle_info)
                self.cycles_used = cycles
                return facts

            winners: dict[str, tuple[Rule, Fact, str]] = {}
            for rule, fact in candidates:
                k = fact.key
                if k not in winners:
                    winners[k] = (rule, fact, "first_candidate")
                    continue
                prev_rule, prev_fact, _ = winners[k]
                if rule.priority > prev_rule.priority:
                    self._log_conflict(cycles, k, rule, fact, prev_rule, prev_fact,
                                       "higher_priority")
                    self.shadowed.add(prev_fact.to_pair())
                    cycle_info["shadowed_this_cycle"].append(
                        (prev_rule.id, prev_fact.to_pair(), "outranked_by_higher_priority")
                    )
                    winners[k] = (rule, fact, "higher_priority")
                else:
                    reason = ("equal_priority_first_wins"
                              if rule.priority == prev_rule.priority
                              else "higher_priority")
                    self._log_conflict(cycles, k, prev_rule, prev_fact, rule, fact, reason)
                    self.shadowed.add(fact.to_pair())
                    cycle_info["shadowed_this_cycle"].append(
                        (rule.id, fact.to_pair(), reason)
                    )

            for k, (rule, fact, reason) in winners.items():
                cycle_info["winners"][k] = (rule.id, rule.priority, fact.to_pair(), reason)

            for k, (rule, fact, _) in winners.items():
                facts.append(fact)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": rule.id,
                    "conclusion": fact.to_pair(),
                })

            self.cycle_history.append(cycle_info)

        raise CycleLimitError(f"max_cycles={self.max_cycles}")

    def _log_conflict(self, cycle, key, winner_rule, winner_fact,
                      loser_rule, loser_fact, reason):
        self.conflicts.append({
            "cycle": cycle,
            "key": key,
            "winner_rule": winner_rule.id,
            "winner_pair": winner_fact.to_pair(),
            "loser_rule": loser_rule.id,
            "loser_pair": loser_fact.to_pair(),
            "reason": reason,
        })


def _dbg_cycle_p02(cycle_info: dict) -> None:
    _dbg(f"  cycle {cycle_info['cycle']}:")
    m = cycle_info["matches"]
    _dbg("    matches: " + " ".join(f"{rid}={v}" for rid, v in m.items()))
    for rid, prio, fact in cycle_info["candidates"]:
        _dbg(f"    candidate: {rid} prio={prio} -> {fact}")
    for k, (rid, prio, fact, reason) in cycle_info["winners"].items():
        _dbg(f"    winner key={k}: {rid} prio={prio} -> {fact} [{reason}]")
    for rid, fact, reason in cycle_info["shadowed_this_cycle"]:
        _dbg(f"    shadowed: {rid} -> {fact} [{reason}]")
    for rid, fact in cycle_info["idempotent"]:
        _dbg(f"    idempotent: {rid} -> {fact}")
    for rid, fact in cycle_info["already_shadowed"]:
        _dbg(f"    already_shadowed: {rid} -> {fact}")
    if cycle_info["quiescence"]:
        _dbg("    quiescence")


def _dbg_engine(name: str, engine: ForwardChainingEngine,
                seed: list[Fact], t_ms: float) -> None:
    _dbg(f"--- {name} ---")
    _dbg(f"  seed_facts: {[f.to_pair() for f in seed]}")
    for ci in engine.cycle_history:
        _dbg_cycle_p02(ci)
    _dbg(f"  result: cycles={engine.cycles_used} trace_len={len(engine.trace)} "
         f"conflicts={len(engine.conflicts)}")
    _dbg(f"  timing: {t_ms:.3f}ms")
    _dbg("")


# ============================================================
# P02a - conflito (prioridade decide)
# ============================================================
def run_p02a() -> dict:
    rules = [
        Rule("R_high", conditions=(("trigger", "yes"),),
             conclusion=("out", "Y"), priority=10),
        Rule("R_low", conditions=(("trigger", "yes"),),
             conclusion=("out", "X"), priority=1),
    ]
    seed = [Fact("trigger", "yes")]
    t0 = time.perf_counter()
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run(seed, rules)
    t_ms = (time.perf_counter() - t0) * 1000
    _dbg_engine("P02a: conflito (prioridade decide)", engine, seed, t_ms)
    return {
        "terminou": True,
        "ciclos": engine.cycles_used,
        "trace": engine.trace,
        "conflicts": engine.conflicts,
        "out_values": [f.value for f in facts if f.key == "out"],
    }


# ============================================================
# P02b - sem conflito
# ============================================================
def run_p02b() -> dict:
    rules = [
        Rule("R_a", conditions=(("trigger", "yes"),),
             conclusion=("out_a", "1"), priority=5),
        Rule("R_b", conditions=(("trigger", "yes"),),
             conclusion=("out_b", "2"), priority=3),
    ]
    seed = [Fact("trigger", "yes")]
    t0 = time.perf_counter()
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run(seed, rules)
    t_ms = (time.perf_counter() - t0) * 1000
    _dbg_engine("P02b: sem conflito (chaves distintas)", engine, seed, t_ms)
    return {
        "ciclos": engine.cycles_used,
        "trace": engine.trace,
        "conflicts": engine.conflicts,
        "out_pairs": sorted(
            f"{k}={v}" for k, v in
            (f.to_pair() for f in facts if f.source == "derived")
        ),
    }


# ============================================================
# P02c - determinismo
# ============================================================
def run_p02c() -> dict:
    t0 = time.perf_counter()
    results = []
    with QUIET:
        for i in range(100):
            r = run_p02a()
            results.append(tuple(r["out_values"]))
    t_total = (time.perf_counter() - t0) * 1000

    if DEBUG:
        _dbg("--- P02c: determinismo (100 runs de P02a) ---")
        _dbg(f"  n: 100")
        _dbg(f"  unique_outputs: {len(set(results))}")
        _dbg(f"  time_total: {t_total:.3f}ms")
        _dbg(f"  time_per_run: {t_total/100:.3f}ms")
        _dbg("")

    return {"n": len(results), "unique_outputs": set(results)}


# ============================================================
# P02d - tie-break por ordem
# ============================================================
def _run_order(order_name: str, rules: list[Rule]) -> tuple[list[str], ForwardChainingEngine]:
    seed = [Fact("trigger", "yes")]
    t0 = time.perf_counter()
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run(seed, rules)
    t_ms = (time.perf_counter() - t0) * 1000
    _dbg_engine(f"P02d/{order_name}", engine, seed, t_ms)
    return [f.value for f in facts if f.key == "out"], engine


def run_p02d() -> dict:
    r_first = Rule("R_first", conditions=(("trigger", "yes"),),
                   conclusion=("out", "first"), priority=5)
    r_second = Rule("R_second", conditions=(("trigger", "yes"),),
                    conclusion=("out", "second"), priority=5)

    if DEBUG:
        _dbg("--- P02d: tie-break por ordem de definicao ---")
        _dbg(f"  rules: R_first prio=5, R_second prio=5")

    out1, _ = _run_order("order_a=[R_first,R_second]", [r_first, r_second])
    out2, _ = _run_order("order_b=[R_second,R_first]", [r_second, r_first])

    return {
        "order_a_winner": out1,
        "order_b_winner": out2,
    }


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_p02.py ===")
        _dbg("mode: debug")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    # P02a
    lines.append("=== P02a: conflito (prioridade decide) ===")
    a = run_p02a()
    lines.append(f"terminou: {a['terminou']}")
    lines.append(f"ciclos_usados: {a['ciclos']}")
    lines.append(f"trace_len: {len(a['trace'])}")
    lines.append(f"conflicts_len: {len(a['conflicts'])}")
    for c in a["conflicts"]:
        wk, wv = c["winner_pair"]
        lk, lv = c["loser_pair"]
        lines.append(
            f"  conflito: ciclo {c['cycle']}, key={c['key']}, "
            f"winner={c['winner_rule']} ({wk}={wv}), "
            f"loser={c['loser_rule']} ({lk}={lv}), reason={c['reason']}"
        )
    lines.append(f"out_values: {a['out_values']}")
    lines.append("")

    if a["trace"] != [{"cycle": 1, "rule_id": "R_high",
                       "conclusion": ("out", "Y")}]:
        falhas.append(f"P02a: trace inesperado: {a['trace']}")
    if len(a["conflicts"]) != 1:
        falhas.append(f"P02a: esperado 1 conflito, veio {len(a['conflicts'])}")
    if a["out_values"] != ["Y"]:
        falhas.append(f"P02a: esperado ['Y'], veio {a['out_values']}")

    # P02b
    lines.append("=== P02b: sem conflito (chaves distintas) ===")
    b = run_p02b()
    lines.append(f"ciclos_usados: {b['ciclos']}")
    lines.append(f"trace_len: {len(b['trace'])}")
    lines.append(f"conflicts_len: {len(b['conflicts'])}")
    lines.append(f"out_pairs: {b['out_pairs']}")
    lines.append("")

    if len(b["trace"]) != 2:
        falhas.append(f"P02b: esperado 2 no trace, veio {len(b['trace'])}")
    if len(b["conflicts"]) != 0:
        falhas.append(f"P02b: esperado 0 conflitos, veio {len(b['conflicts'])}")
    if b["out_pairs"] != ["out_a=1", "out_b=2"]:
        falhas.append(f"P02b: out_pairs inesperado: {b['out_pairs']}")

    # P02c
    lines.append("=== P02c: determinismo (100 runs) ===")
    c = run_p02c()
    lines.append(f"n: {c['n']}")
    lines.append(f"unique_outputs: {sorted(c['unique_outputs'])}")
    lines.append("")

    if c["unique_outputs"] != {("Y",)}:
        falhas.append(f"P02c: nao-deterministico: {c['unique_outputs']}")

    # P02d
    lines.append("=== P02d: tie-break por ordem de definicao ===")
    d = run_p02d()
    lines.append(f"order_a_winner: {d['order_a_winner']}")
    lines.append(f"order_b_winner: {d['order_b_winner']}")
    lines.append("")

    if d["order_a_winner"] != ["first"]:
        falhas.append(f"P02d: ordem A deveria dar 'first', veio {d['order_a_winner']}")
    if d["order_b_winner"] != ["second"]:
        falhas.append(f"P02d: ordem B deveria dar 'second', veio {d['order_b_winner']}")

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for f in falhas:
            lines.append(f"  - {f}")
        LOG.error("P02 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P02 PASS")
        LOG.info("P02 PASS")
        resultado = 0
        if DEBUG:
            _dbg("=== done: all checks passed ===")

    for line in lines:
        print(line)

    output_path = Path(__file__).parent / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return resultado


if __name__ == "__main__":
    sys.exit(main())
