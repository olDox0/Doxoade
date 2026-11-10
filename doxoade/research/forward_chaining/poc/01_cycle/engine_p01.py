# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/01_cycle/engine_p01.py
"""
P01 - Terminacao em ciclos e falha explicita.

Contrato: C1 (Inferencia). Semantica de ciclo: B estrita.

DEFINICAO DE CICLO (contrato): um ciclo e uma rodada de match sobre
SNAPSHOT congelado, seguida de fire. Regras do mesmo ciclo nao veem
fatos derivados por outras regras do mesmo ciclo.

P01a - Ciclo de regras quiesce via idempotencia.
P01b - Cadeia > max_cycles levanta CycleLimitError explicito.

Rodar: run_01.bat
"""
from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


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
    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.cycles_used: int = 0

    def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
        facts: list[Fact] = list(initial_facts)
        ordered_rules = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        LOG.info("run: %d fatos, %d regras, max_cycles=%d",
                 len(facts), len(ordered_rules), self.max_cycles)

        while cycles < self.max_cycles:
            cycles += 1
            snapshot: frozenset[tuple[str, str]] = frozenset(
                f.to_pair() for f in facts
            )
            existing: set[tuple[str, str]] = set(snapshot)
            new_facts: list[Fact] = []
            seen_in_cycle: set[tuple[str, str]] = set()

            for rule in ordered_rules:
                if not rule.match(snapshot):
                    continue
                new_fact = rule.conclusion_fact(cycle=cycles)
                pair = new_fact.to_pair()
                if pair in existing or pair in seen_in_cycle:
                    LOG.debug("ciclo %d: %s idempotente (%s)",
                              cycles, rule.id, pair)
                    continue
                new_facts.append(new_fact)
                seen_in_cycle.add(pair)

            if not new_facts:
                self.cycles_used = cycles
                LOG.info("quiescencia em %d ciclo(s)", cycles)
                return facts

            for nf in new_facts:
                facts.append(nf)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": nf.rule_id,
                    "conclusion": nf.to_pair(),
                })
                LOG.debug("ciclo %d: %s -> %s",
                          cycles, nf.rule_id, nf.to_pair())

        raise CycleLimitError(
            f"max_cycles={self.max_cycles} sem quiescencia "
            f"(trace tem {len(self.trace)} entrada(s))"
        )


RULES_P01A: list[Rule] = [
    Rule("R1", conditions=(("x", "1"),), conclusion=("y", "1")),
    Rule("R2", conditions=(("y", "1"),), conclusion=("z", "1")),
    Rule("R3", conditions=(("z", "1"),), conclusion=("x", "1")),
]


def run_p01a() -> dict:
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run([Fact("x", "1")], RULES_P01A)
    return {
        "terminou": True,
        "ciclos": engine.cycles_used,
        "trace": engine.trace,
        "fatos_finais": sorted(f"{f.key}={f.value}" for f in facts),
    }


def build_chain(n: int) -> list[Rule]:
    return [
        Rule(f"R_{i:02d}",
             conditions=((f"a{i}", "ok"),),
             conclusion=(f"a{i+1}", "ok"))
        for i in range(n)
    ]


def run_p01b() -> dict:
    rules = build_chain(6)
    engine = ForwardChainingEngine(max_cycles=3)
    try:
        engine.run([Fact("a0", "ok")], rules)
    except CycleLimitError as e:
        LOG.info("P01b: CycleLimitError como esperado: %s", e)
        return {"levantou_erro": True, "erro": str(e), "trace": engine.trace}
    LOG.error("P01b: NAO levantou CycleLimitError - engine mentiu")
    return {"levantou_erro": False, "erro": None, "trace": engine.trace}


def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

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

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for f in falhas:
            lines.append(f"  - {f}")
        LOG.error("P01 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P01 PASS")
        LOG.info("P01 PASS")
        resultado = 0

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
