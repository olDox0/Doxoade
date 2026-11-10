
# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/02_conflict/engine_p02.py
"""
P02 â€” Conflito entre regras e determinismo.

Contrato: C1 (InferÃªncia) extendido com resoluÃ§Ã£o de contradiÃ§Ã£o por prioridade.

ExtensÃ£o sobre P01:
- engine.collect: candidatos do ciclo (sem merge imediato)
- engine.resolve: por key, maior prioridade vence; empate â†’ primeira em `rules`
- engine.shadowed: fatos rejeitados nunca re-entram
- engine.conflicts: histÃ³rico rastreÃ¡vel

P02a â€” 2 regras, mesma key 'out', prioridades 10 vs 1.
       R_high (prio=10, out=Y) vence. R_low (prio=1, out=X) sombreada.
P02b â€” 2 regras, keys distintas, ambas disparam sem conflito.
P02c â€” 100 runs de P02a â†’ saÃ­da idÃªntica (determinismo).
P02d â€” Empate de prioridade â†’ ordem em `rules` decide o vencedor.

Rodar: run.bat / run.ps1
"""
from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


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
    Ciclo: snapshot â†’ collect candidatos â†’ resolve conflito por key
           â†’ merge vencedores â†’ repeat.

    ResoluÃ§Ã£o de conflito (contrato P02):
    - Agrupa candidatos por `key`.
    - Maior prioridade vence.
    - Empate: primeira regra em `rules` vence.
    - Perdedores vÃ£o para `shadowed` (nunca re-entram).
    - Cada resoluÃ§Ã£o gera entrada em `conflicts`.
    """

    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.conflicts: list[dict] = []
        self.shadowed: set[tuple[str, str]] = set()
        self.cycles_used: int = 0

    def run(self, initial_facts: list[Fact], rules: list[Rule]) -> list[Fact]:
        facts: list[Fact] = list(initial_facts)
        # Ordem de iteracao: prioridade desc, empate preserva ordem em `rules`.
        ordered_rules = sorted(
            enumerate(rules),
            key=lambda pair: (-pair[1].priority, pair[0]),
        )
        ordered_rules = [r for _, r in ordered_rules]
        cycles = 0
        LOG.info("run: %d fatos, %d regras, max_cycles=%d",
                 len(facts), len(ordered_rules), self.max_cycles)

        while cycles < self.max_cycles:
            cycles += 1
            snapshot = frozenset(f.to_pair() for f in facts)
            existing = set(snapshot)

            # Collect candidatos
            candidates: list[tuple[Rule, Fact]] = []
            for rule in ordered_rules:
                if not rule.match(snapshot):
                    continue
                new_fact = rule.conclusion_fact(cycle=cycles)
                pair = new_fact.to_pair()
                if pair in existing:
                    LOG.debug("ciclo %d: %s idempotente (%s)",
                              cycles, rule.id, pair)
                    continue
                if pair in self.shadowed:
                    LOG.debug("ciclo %d: %s sombreada (%s)",
                              cycles, rule.id, pair)
                    continue
                candidates.append((rule, new_fact))

            if not candidates:
                self.cycles_used = cycles
                LOG.info("quiescencia em %d ciclo(s)", cycles)
                return facts

            # Resolve conflitos por key
            winners: dict[str, tuple[Rule, Fact]] = {}
            for rule, fact in candidates:
                k = fact.key
                if k not in winners:
                    winners[k] = (rule, fact)
                    continue
                prev_rule, prev_fact = winners[k]
                if rule.priority > prev_rule.priority:
                    self._log_conflict(
                        cycles, k, rule, fact, prev_rule, prev_fact,
                        reason="higher_priority",
                    )
                    self.shadowed.add(prev_fact.to_pair())
                    winners[k] = (rule, fact)
                else:
                    reason = (
                        "equal_priority_first_wins"
                        if rule.priority == prev_rule.priority
                        else "higher_priority"
                    )
                    self._log_conflict(
                        cycles, k, prev_rule, prev_fact, rule, fact,
                        reason=reason,
                    )
                    self.shadowed.add(fact.to_pair())

            # Merge vencedores
            for k, (rule, fact) in winners.items():
                facts.append(fact)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": rule.id,
                    "conclusion": fact.to_pair(),
                })
                LOG.debug("ciclo %d: %s -> %s",
                          cycles, rule.id, fact.to_pair())

        raise CycleLimitError(
            f"max_cycles={self.max_cycles} sem quiescencia "
            f"(trace tem {len(self.trace)} entrada(s))"
        )

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
        LOG.info("conflito ciclo %d key=%s: %s vence (%s)",
                 cycle, key, winner_rule.id, reason)


# ============================================================
# P02a â€” conflito resolvido por prioridade
# ============================================================

def run_p02a() -> dict:
    rules = [
        Rule("R_high", conditions=(("trigger", "yes"),),
             conclusion=("out", "Y"), priority=10),
        Rule("R_low", conditions=(("trigger", "yes"),),
             conclusion=("out", "X"), priority=1),
    ]
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run([Fact("trigger", "yes")], rules)
    return {
        "terminou": True,
        "ciclos": engine.cycles_used,
        "trace": engine.trace,
        "conflicts": engine.conflicts,
        "out_values": [f.value for f in facts if f.key == "out"],
    }


# ============================================================
# P02b â€” sem conflito
# ============================================================

def run_p02b() -> dict:
    rules = [
        Rule("R_a", conditions=(("trigger", "yes"),),
             conclusion=("out_a", "1"), priority=5),
        Rule("R_b", conditions=(("trigger", "yes"),),
             conclusion=("out_b", "2"), priority=3),
    ]
    engine = ForwardChainingEngine(max_cycles=10)
    facts = engine.run([Fact("trigger", "yes")], rules)
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
# P02c â€” determinismo
# ============================================================

def run_p02c() -> dict:
    results = [tuple(run_p02a()["out_values"]) for _ in range(100)]
    return {
        "n": len(results),
        "unique_outputs": set(results),
    }


# ============================================================
# P02d â€” tie-break por ordem de definicao
# ============================================================

def run_p02d() -> dict:
    r_first = Rule("R_first", conditions=(("trigger", "yes"),),
                   conclusion=("out", "first"), priority=5)
    r_second = Rule("R_second", conditions=(("trigger", "yes"),),
                    conclusion=("out", "second"), priority=5)

    eng1 = ForwardChainingEngine(max_cycles=10)
    facts1 = eng1.run([Fact("trigger", "yes")], [r_first, r_second])
    out1 = [f.value for f in facts1 if f.key == "out"]

    eng2 = ForwardChainingEngine(max_cycles=10)
    facts2 = eng2.run([Fact("trigger", "yes")], [r_second, r_first])
    out2 = [f.value for f in facts2 if f.key == "out"]

    return {
        "order_a_winner": out1,
        "order_b_winner": out2,
    }


# ============================================================
# main
# ============================================================

def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P02a ----------
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

    # ---------- P02b ----------
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

    # ---------- P02c ----------
    lines.append("=== P02c: determinismo (100 runs) ===")
    c = run_p02c()
    lines.append(f"n: {c['n']}")
    lines.append(f"unique_outputs: {sorted(c['unique_outputs'])}")
    lines.append("")

    if c["unique_outputs"] != {("Y",)}:
        falhas.append(
            f"P02c: outputs nao-deterministicos: {c['unique_outputs']}"
        )

    # ---------- P02d ----------
    lines.append("=== P02d: tie-break por ordem de definicao ===")
    d = run_p02d()
    lines.append(f"order_a_winner: {d['order_a_winner']}")
    lines.append(f"order_b_winner: {d['order_b_winner']}")
    lines.append("")

    if d["order_a_winner"] != ["first"]:
        falhas.append(f"P02d: ordem A deveria dar 'first', veio {d['order_a_winner']}")
    if d["order_b_winner"] != ["second"]:
        falhas.append(f"P02d: ordem B deveria dar 'second', veio {d['order_b_winner']}")

    # ---------- veredito ----------
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
