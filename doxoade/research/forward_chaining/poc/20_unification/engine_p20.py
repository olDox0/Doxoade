# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/20_unification/engine_p20.py
"""
P20 â€” Unificacao sobre triplas (C1 estendido).

Contrato: C1 (Inferencia) + C3 (Expressividade com variaveis).

MUDANCA DE CONTRATO em relacao a P00-P02:
    Fatos passam de (key, value) para (subject, predicate, object).
    Motivo: unificacao precisa de relacoes binarias. Encoding comprimido
    viola o principio C-verb (verbosidade = controle).

MODELO:
    Var(name)    -> variavel, casa com qualquer string e liga
    str          -> constante, casa so com igual
    TripleFact   -> (s, p, o) + metadados

MATCHER: backtracking exaustivo (todas as solucoes), sem indexacao.
    Complexidade: O(|facts|^|conditions|). Aceitavel em PoC, alvo de
    otimizacao em P70.

P20a â€” transitividade: pai(X,Y) AND pai(Y,Z) -> avo(X,Z).
P20b â€” var repetida: r(X,X) -> self(X,X). Only self-loops casam.
P20c â€” duas regras compondo sem conflito.
P20d â€” falha de unificacao (nenhum match).
P20e â€” determinismo (100 runs de P20a).
P20f â€” ciclo via trans: (a,r,b),(b,r,a) quiesce sem explodir.

NAO usa: indexacao (P70), negacao (P21), AST aqui (P10/P11).

Rodar: run.bat / run.ps1
"""
from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc20")
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
    """Variavel: casa com qualquer string e liga. Nome unico por escopo de regra."""
    name: str

    def __repr__(self) -> str:
        return f"Var({self.name})"


Term = str | Var
Pattern = tuple[Term, Term, Term]


@dataclasses.dataclass(frozen=True)
class TripleFact:
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
    priority: int = 0
    description: str = ""

    def conclusion_fact(self, bindings: dict[str, str], cycle: int) -> TripleFact | None:
        resolved = substitute(self.conclusion, bindings)
        if resolved is None:
            return None
        s, p, o = resolved
        return TripleFact(s, p, o, source="derived",
                          rule_id=self.id, cycle=cycle)


# ---------- Unificacao ----------
def unify_term(pattern: Term, value: str,
               bindings: dict[str, str]) -> dict[str, str] | None:
    """Retorna bindings estendidos ou None se inconsistente."""
    if isinstance(pattern, Var):
        if pattern.name in bindings:
            return bindings if bindings[pattern.name] == value else None
        return {**bindings, pattern.name: value}
    return bindings if pattern == value else None


def unify(pattern: Pattern, fact: TripleFact,
          bindings: dict[str, str]) -> dict[str, str] | None:
    b = bindings
    b = unify_term(pattern[0], fact.s, b)
    if b is None:
        return None
    b = unify_term(pattern[1], fact.p, b)
    if b is None:
        return None
    b = unify_term(pattern[2], fact.o, b)
    return b


def substitute(pattern: Pattern,
               bindings: dict[str, str]) -> tuple[str, str, str] | None:
    out: list[str] = []
    for t in pattern:
        if isinstance(t, Var):
            if t.name not in bindings:
                return None
            out.append(bindings[t.name])
        else:
            out.append(t)
    return (out[0], out[1], out[2])


def match_conditions(conditions: tuple[Pattern, ...],
                     facts: list[TripleFact],
                     bindings: dict[str, str] | None = None
                     ) -> list[dict[str, str]]:
    """Backtracking: retorna TODAS as bindings que satisfazem todas as condicoes."""
    if bindings is None:
        bindings = {}
    if not conditions:
        return [bindings]
    first, *rest = conditions
    results: list[dict[str, str]] = []
    for f in facts:
        b = unify(first, f, bindings)
        if b is None:
            continue
        results.extend(match_conditions(tuple(rest), facts, b))
    return results


# ---------- Engine ----------
class ForwardChainingEngine:
    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.cycles_used: int = 0

    def run(self, initial_facts: list[TripleFact],
            rules: list[Rule]) -> list[TripleFact]:
        facts: list[TripleFact] = list(initial_facts)
        ordered = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        LOG.info("run: %d fatos, %d regras, max_cycles=%d",
                 len(facts), len(ordered), self.max_cycles)

        while cycles < self.max_cycles:
            cycles += 1
            existing = frozenset(f.to_tuple() for f in facts)
            new_facts: list[TripleFact] = []
            seen_in_cycle: set[tuple[str, str, str]] = set()

            for rule in ordered:
                for bindings in match_conditions(rule.conditions, facts):
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        LOG.warning("ciclo %d: %s conclusao com var livre",
                                    cycles, rule.id)
                        continue
                    key = cf.to_tuple()
                    if key in existing or key in seen_in_cycle:
                        continue
                    new_facts.append(cf)
                    seen_in_cycle.add(key)

            if not new_facts:
                self.cycles_used = cycles
                LOG.info("quiescencia em %d ciclo(s)", cycles)
                return facts

            for nf in new_facts:
                facts.append(nf)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": nf.rule_id,
                    "fact": nf.to_tuple(),
                })
                LOG.debug("ciclo %d: %s -> %s",
                          cycles, nf.rule_id, nf.render())

        raise CycleLimitError(
            f"max_cycles={self.max_cycles} sem quiescencia "
            f"(trace tem {len(self.trace)} entrada(s))"
        )


# ---------- Helpers de teste ----------
def F(s: str, p: str, o: str) -> TripleFact:
    return TripleFact(s, p, o)


def fact_set(facts: list[TripleFact], filter_source: str | None = None) -> list[str]:
    items = facts if filter_source is None else [f for f in facts if f.source == filter_source]
    return sorted(f.render() for f in items)


# ============================================================
# P20a â€” transitividade
# ============================================================
def run_p20a() -> dict:
    X, Y, Z = Var("X"), Var("Y"), Var("Z")
    rules = [
        Rule("R_trans",
             conditions=((X, "pai", Y), (Y, "pai", Z)),
             conclusion=(X, "avo", Z)),
    ]
    facts = [F("joao", "pai", "maria"), F("maria", "pai", "pedro")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {
        "ciclos": eng.cycles_used,
        "trace": eng.trace,
        "derived": fact_set(result, filter_source="derived"),
        "all": fact_set(result),
    }


# ============================================================
# P20b â€” variavel repetida
# ============================================================
def run_p20b() -> dict:
    X = Var("X")
    rules = [Rule("R_self", conditions=((X, "r", X),), conclusion=(X, "self", X))]
    facts = [F("a", "r", "a"), F("a", "r", "b"), F("b", "r", "b")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {
        "ciclos": eng.cycles_used,
        "derived": fact_set(result, filter_source="derived"),
    }


# ============================================================
# P20c â€” duas regras compondo
# ============================================================
def run_p20c() -> dict:
    X, Y = Var("X"), Var("Y")
    rules = [
        Rule("R_inv", conditions=((X, "r", Y),), conclusion=(Y, "r_inv", X)),
        Rule("R_sym", conditions=((X, "r", Y),), conclusion=(X, "r_sym", Y)),
    ]
    facts = [F("a", "r", "b")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {
        "ciclos": eng.cycles_used,
        "derived": fact_set(result, filter_source="derived"),
    }


# ============================================================
# P20d â€” falha de unificacao
# ============================================================
def run_p20d() -> dict:
    X, Y, Z = Var("X"), Var("Y"), Var("Z")
    rules = [
        Rule("R_bad",
             conditions=((X, "r", Y), (Y, "r", Z)),
             conclusion=(X, "trans", Z)),
    ]
    facts = [F("a", "r", "b")]  # b nao tem 'r' saindo
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {
        "ciclos": eng.cycles_used,
        "derived": fact_set(result, filter_source="derived"),
    }


# ============================================================
# P20e â€” determinismo
# ============================================================
def run_p20e() -> dict:
    runs = set()
    for _ in range(100):
        runs.add(tuple(run_p20a()["derived"]))
    return {"n": 100, "unique": runs}


# ============================================================
# P20f â€” ciclo via trans
# ============================================================
def run_p20f() -> dict:
    X, Y, Z = Var("X"), Var("Y"), Var("Z")
    rules = [
        Rule("R_trans",
             conditions=((X, "r", Y), (Y, "r", Z)),
             conclusion=(X, "trans", Z)),
    ]
    facts = [F("a", "r", "b"), F("b", "r", "a")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {
        "ciclos": eng.cycles_used,
        "trace_len": len(eng.trace),
        "derived": fact_set(result, filter_source="derived"),
    }


# ============================================================
# main
# ============================================================
def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P20a ----------
    lines.append("=== P20a: transitividade ===")
    a = run_p20a()
    lines.append(f"ciclos_usados: {a['ciclos']}")
    lines.append(f"trace_len: {len(a['trace'])}")
    lines.append("derived:")
    for d in a["derived"]:
        lines.append(f"  {d}")
    lines.append("all:")
    for d in a["all"]:
        lines.append(f"  {d}")
    lines.append("")
    if a["derived"] != ["(joao, avo, pedro)"]:
        falhas.append(f"P20a: derived inesperado: {a['derived']}")

    # ---------- P20b ----------
    lines.append("=== P20b: var repetida r(X,X) ===")
    b = run_p20b()
    lines.append(f"ciclos_usados: {b['ciclos']}")
    lines.append("derived:")
    for d in b["derived"]:
        lines.append(f"  {d}")
    lines.append("")
    esperado_b = ["(a, self, a)", "(b, self, b)"]
    if b["derived"] != esperado_b:
        falhas.append(f"P20b: derived inesperado: {b['derived']} (esperado {esperado_b})")

    # ---------- P20c ----------
    lines.append("=== P20c: duas regras compondo ===")
    c = run_p20c()
    lines.append(f"ciclos_usados: {c['ciclos']}")
    lines.append("derived:")
    for d in c["derived"]:
        lines.append(f"  {d}")
    lines.append("")
    esperado_c = ["(a, r_sym, b)", "(b, r_inv, a)"]
    if c["derived"] != esperado_c:
        falhas.append(f"P20c: derived inesperado: {c['derived']} (esperado {esperado_c})")

    # ---------- P20d ----------
    lines.append("=== P20d: falha de unificacao ===")
    d = run_p20d()
    lines.append(f"ciclos_usados: {d['ciclos']}")
    lines.append(f"derived: {d['derived']}")
    lines.append("")
    if d["derived"] != []:
        falhas.append(f"P20d: derived deveria ser vazio, veio {d['derived']}")

    # ---------- P20e ----------
    lines.append("=== P20e: determinismo (100 runs) ===")
    e = run_p20e()
    lines.append(f"n: {e['n']}")
    lines.append(f"unique_outputs: {sorted(e['unique'])}")
    lines.append("")
    if e["unique"] != {("(joao, avo, pedro)",)}:
        falhas.append(f"P20e: nao-deterministico: {e['unique']}")

    # ---------- P20f ----------
    lines.append("=== P20f: ciclo via trans ===")
    f = run_p20f()
    lines.append(f"ciclos_usados: {f['ciclos']}")
    lines.append(f"trace_len: {f['trace_len']}")
    lines.append("derived:")
    for d in f["derived"]:
        lines.append(f"  {d}")
    lines.append("")
    esperado_f = ["(a, trans, a)", "(b, trans, b)"]
    if f["derived"] != esperado_f:
        falhas.append(f"P20f: derived inesperado: {f['derived']} (esperado {esperado_f})")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for item in falhas:
            lines.append(f"  - {item}")
        LOG.error("P20 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P20 PASS")
        LOG.info("P20 PASS")
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
