# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/01_cycle/engine_p01.py
"""
P01 - Terminacao em ciclos e falha explicita, com debug estruturado.

Debug:
    py engine_p01.py --debug
    Emite [DEBUG] em stderr. stdout/output.txt inalterados.

P01a - ciclo de regras quiesce via idempotencia.
P01b - cadeia > max_cycles levanta CycleLimitError explicito.

O debug mostra:
- P01a: cycle-by-cycle (matches, candidates, idempotent, quiescence).
- P01b: cycle-by-cycle ATE o limite, momento da falha, trace preservado.
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
    logger = logging.getLogger("poc01")
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

    def match(self, snapshot: frozenset[tuple[str, str]]) -> bool:
        return all(c in snapshot for c in self.conditions)

    def conclusion_fact(self, cycle: int) -> Fact:
        k, v = self.conclusion
        return Fact(k, v, source="derived", rule_id=self.id, cycle=cycle)


class ForwardChainingEngine:
    """
    Snapshot por ciclo (semantica B estrita).

    Ciclo = rodada de match sobre snapshot congelado + fire.
    Cadeias lineares exigem N ciclos. max_cycles conta rodadas.
    """

    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.cycles_used = 0
        self.cycle_history: list[dict] = []
        self.rules_attempted = 0
        self.rule_attempts: dict[str, int] = {}
        self.limit_reached = False

    def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
        facts: list[Fact] = list(initial_facts)
        ordered_rules = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            snapshot: frozenset[tuple[str, str]] = frozenset(
                f.to_pair() for f in facts
            )
            existing: set[tuple[str, str]] = set(snapshot)
            new_facts: list[Fact] = []
            seen_in_cycle: set[tuple[str, str]] = set()

            cycle_info = {
                "cycle": cycles,
                "matches": {},
                "candidates": [],
                "idempotent": [],
                "quiescence": False,
            }

            for rule in ordered_rules:
                self.rules_attempted += 1
                self.rule_attempts[rule.id] = self.rule_attempts.get(rule.id, 0) + 1

                matched = rule.match(snapshot)
                cycle_info["matches"][rule.id] = matched
                if not matched:
                    continue

                new_fact = rule.conclusion_fact(cycle=cycles)
                pair = new_fact.to_pair()
                if pair in existing or pair in seen_in_cycle:
                    cycle_info["idempotent"].append((rule.id, pair))
                    continue

                cycle_info["candidates"].append((rule.id, rule.priority, pair))
                new_facts.append(new_fact)
                seen_in_cycle.add(pair)

            self.cycle_history.append(cycle_info)

            if not new_facts:
                cycle_info["quiescence"] = True
                self.cycles_used = cycles
                return facts

            for nf in new_facts:
                facts.append(nf)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": nf.rule_id,
                    "conclusion": nf.to_pair(),
                })

        self.limit_reached = True
        raise CycleLimitError(
            f"max_cycles={self.max_cycles} sem quiescencia "
            f"(trace tem {len(self.trace)} entrada(s))"
        )


# ============================================================
# P01a - ciclo de regras
# ============================================================
RULES_P01A: list[Rule] = [
    Rule("R1", conditions=(("x", "1"),), conclusion=("y", "1")),
    Rule("R2", conditions=(("y", "1"),), conclusion=("z", "1")),
    Rule("R3", conditions=(("z", "1"),), conclusion=("x", "1")),
]


def _dbg_cycle(cycle_info: dict) -> None:
    _dbg(f"  cycle {cycle_info['cycle']}:")
    matches_str = " ".join(
        f"{rid}={v}" for rid, v in cycle_info["matches"].items()
    )
    _dbg(f"    matches: {matches_str}")
    for rid, prio, fact in cycle_info["candidates"]:
        _dbg(f"    candidate: {rid} prio={prio} -> {fact}")
    for rid, fact in cycle_info["idempotent"]:
        _dbg(f"    idempotent: {rid} -> {fact}")
    if cycle_info["quiescence"]:
        _dbg("    quiescence")


def run_p01a() -> dict:
    seed = [Fact("x", "1")]
    if DEBUG:
        _dbg("--- P01a: ciclo de regras ---")
        _dbg(f"  seed_facts: {[f.to_pair() for f in seed]}")
        _dbg(f"  rules: {[r.id for r in RULES_P01A]} "
             f"(priorities: {[r.priority for r in RULES_P01A]})")

    t0 = time.perf_counter()
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run(seed, RULES_P01A)
    t_ms = (time.perf_counter() - t0) * 1000

    if DEBUG:
        for ci in engine.cycle_history:
            _dbg_cycle(ci)
        _dbg(f"  result: cycles={engine.cycles_used} trace_len={len(engine.trace)}")
        _dbg(f"  timing: {t_ms:.3f}ms")
        _dbg("")

    return {
        "terminou": True,
        "ciclos": engine.cycles_used,
        "trace": engine.trace,
        "fatos_finais": sorted(f"{f.key}={f.value}" for f in facts),
    }


# ============================================================
# P01b - cadeia > max_cycles
# ============================================================
def build_chain(n: int) -> list[Rule]:
    return [
        Rule(f"R_{i:02d}",
             conditions=((f"a{i}", "ok"),),
             conclusion=(f"a{i+1}", "ok"))
        for i in range(n)
    ]


def run_p01b() -> dict:
    chain_len = 6
    max_cycles = 3
    rules = build_chain(chain_len)
    seed = [Fact("a0", "ok")]

    if DEBUG:
        _dbg("--- P01b: cadeia > max_cycles ---")
        _dbg(f"  seed_facts: {[f.to_pair() for f in seed]}")
        _dbg(f"  chain_length: {chain_len} (rules: {[r.id for r in rules]})")
        _dbg(f"  max_cycles: {max_cycles}")

    t0 = time.perf_counter()
    engine = ForwardChainingEngine(max_cycles=max_cycles)
    try:
        engine.run(seed, rules)
    except CycleLimitError as e:
        t_ms = (time.perf_counter() - t0) * 1000
        if DEBUG:
            for ci in engine.cycle_history:
                _dbg_cycle(ci)
            _dbg(f"  max_cycles={max_cycles} reached WITHOUT quiescence")
            _dbg(f"  CycleLimitError raised:")
            _dbg(f"    \"{e}\"")
            _dbg(f"  trace_at_failure (preservado):")
            for step in engine.trace:
                _dbg(f"    ciclo {step['cycle']}: {step['rule_id']} -> "
                     f"{step['conclusion'][0]}={step['conclusion'][1]}")
            _dbg(f"  timing: {t_ms:.3f}ms")
            _dbg("")
        LOG.info("P01b: CycleLimitError como esperado: %s", e)
        return {"levantou_erro": True, "erro": str(e), "trace": engine.trace}
    LOG.error("P01b: NAO levantou CycleLimitError - engine mentiu")
    return {"levantou_erro": False, "erro": None, "trace": engine.trace}


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_p01.py ===")
        _dbg("mode: debug")
        _dbg("engine_semantics: B (snapshot per cycle)")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P01a ----------
    lines.append("=== P01a: ciclo de regras ===")
    a = run_p01a()
    lines.append(f"terminou: {a['terminou']}")
    lines.append(f"ciclos_usados: {a['ciclos']}")
    lines.append(f"trace_len: {len(a['trace'])}")
    for s in a["trace"]:
        k, v = s["conclusion"]
        lines.append(f"  ciclo {s['cycle']}: {s['rule_id']} -> {k}={v}")
    lines.append(f"fatos_finais: {a['fatos_finais']}")
    lines.append("")

    if len(a["trace"]) != 2:
        falhas.append(f"P01a: esperado 2 entradas no trace, veio {len(a['trace'])}")
    if a["ciclos"] != 3:
        falhas.append(f"P01a: esperado 3 ciclos, veio {a['ciclos']}")

    # ---------- P01b ----------
    lines.append("=== P01b: cadeia > max_cycles ===")
    b = run_p01b()
    lines.append(f"levantou_erro: {b['levantou_erro']}")
    if b["erro"] is not None:
        lines.append(f"mensagem: {b['erro']}")
    lines.append(f"trace_len: {len(b['trace'])}")
    for s in b["trace"]:
        k, v = s["conclusion"]
        lines.append(f"  ciclo {s['cycle']}: {s['rule_id']} -> {k}={v}")
    lines.append("")

    if not b["levantou_erro"]:
        falhas.append("P01b: esperado CycleLimitError, nao foi levantado")
    if len(b["trace"]) != 3:
        falhas.append(f"P01b: esperado 3 entradas no trace, veio {len(b['trace'])}")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("P01 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P01 PASS")
        LOG.info("P01 PASS")
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
