# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/00_fizzbuzz/engine_p00.py
"""
P00 - FizzBuzz como smoke test do motor de forward chaining.

Contrato provado: C1 (Inferencia)
    Fatos + Regras -> Fatos derivados, com terminacao e trace.

Rodar: run_00.bat
"""
from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


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
    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []

    def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
        facts = list(initial_facts)
        cycles = 0
        LOG.info("run: %d fatos, %d regras, max_cycles=%d",
                 len(facts), len(rules), self.max_cycles)

        while cycles < self.max_cycles:
            cycles += 1
            fired_this_cycle = False

            for rule in sorted(rules, key=lambda r: -r.priority):
                if not rule.match(facts):
                    continue
                new_fact = rule.conclusion_fact(cycle=cycles)
                if any(f.to_pair() == new_fact.to_pair() for f in facts):
                    LOG.debug("ciclo %d: %s ja presente", cycles, rule.id)
                    continue
                facts.append(new_fact)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": rule.id,
                    "conditions": rule.conditions,
                    "conclusion": new_fact.to_pair(),
                })
                LOG.debug("ciclo %d: %s -> %s",
                          cycles, rule.id, new_fact.to_pair())
                fired_this_cycle = True

            if not fired_this_cycle:
                LOG.info("quiescencia em %d ciclo(s)", cycles)
                return facts

        raise CycleLimitError(f"max_cycles={self.max_cycles} sem quiescencia")


RULES: list[Rule] = [
    Rule("R_fizzbuzz",
         conditions=(("div3", "yes"), ("div5", "yes")),
         conclusion=("out", "fizzbuzz"),
         priority=30,
         description="Divisivel por 3 e 5"),
    Rule("R_fizz",
         conditions=(("div3", "yes"), ("div5", "no")),
         conclusion=("out", "fizz"),
         priority=20,
         description="Divisivel por 3 apenas"),
    Rule("R_buzz",
         conditions=(("div3", "no"), ("div5", "yes")),
         conclusion=("out", "buzz"),
         priority=20,
         description="Divisivel por 5 apenas"),
]


def facts_for(n: int) -> list[Fact]:
    return [
        Fact("div3", "yes" if n % 3 == 0 else "no"),
        Fact("div5", "yes" if n % 5 == 0 else "no"),
    ]


def solve(n: int) -> str:
    engine = ForwardChainingEngine()
    facts = engine.run(facts_for(n), RULES)
    outs = [f for f in facts if f.key == "out"]
    return outs[0].value if outs else str(n)


def reference(n: int) -> str:
    if n % 15 == 0:
        return "fizzbuzz"
    if n % 3 == 0:
        return "fizz"
    if n % 5 == 0:
        return "buzz"
    return str(n)


def main() -> int:
    answers = [solve(n) for n in range(1, 101)]
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

    lines: list[str] = ["=== FIZZBUZZ 1..100 ==="]
    lines.extend(answers)

    lines.append("=== TRACE n=15 ===")
    engine = ForwardChainingEngine()
    engine.run(facts_for(15), RULES)
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

    LOG.info("P00 PASS: 100/100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
