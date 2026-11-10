# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/21_negation_as_failure/engine_p21.py
"""
P21 â€” Negation as failure (C3, aquecimento).

Contrato: C1 (Inferencia) + C3 (Expressividade).

NAF: "NOT C" significa "C nao e derivavel do WM atual".
    - C e um unico padrao (nao composto, nesta PoC).
    - Avaliado contra o SNAPSHOT do ciclo (consistente com P01/P02/P20).
    - Multiplas negacoes numa regra = conjuncao.
    - Wildcard "_" casa com qualquer valor, nao liga.

Snapshot e essencial: sem ele, "IF NOT done THEN done" entra em loop.
P21e testa esse caso explicitamente.

P21a â€” NAF basico: deriva quando nao ha blocker.
P21b â€” NAF bloqueia: blocker presente, nao deriva.
P21c â€” NAF com var repetida: (X,r,X) como negacao exclui self-loops.
P21d â€” NAF em grafo ciclico: nega a reciproca, nada deriva.
P21e â€” self-defeating: "IF NOT done THEN done" quiesce via snapshot.
P21f â€” duas negacoes (conjuncao): ambas devem falhar para derivar.
P21g â€” determinismo (100 runs de P21a).

DIFERENCA vs P22 (futuro):
    P21 = NAF (procedural: "nao provavel agora").
    P22 = negacao explicita (declarativa: "provado que e falso").
    A distincao vira relevante quando houver fatos negativos.

Rodar: run.bat / run.ps1
"""
from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc21")
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


class _Wild:
    """Wildcard: casa com qualquer valor, nao liga variavel."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "_"


WILD = _Wild()


@dataclasses.dataclass(frozen=True)
class Var:
    name: str

    def __repr__(self) -> str:
        return f"Var({self.name})"


Term = str | Var | _Wild
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
    negations: tuple[Pattern, ...] = ()
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
    if isinstance(pattern, _Wild):
        return bindings
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
        if isinstance(t, _Wild):
            return None  # wildcard nao pode ir para conclusao
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


def negation_blocks(neg: Pattern, facts: list[TripleFact],
                    bindings: dict[str, str]) -> bool:
    """True se o padrao negado encontra QUALQUER match sob bindings."""
    return any(unify(neg, f, bindings) is not None for f in facts)


def match_rule(rule: Rule, facts: list[TripleFact]) -> list[dict[str, str]]:
    """Retorna bindings que satisfazem positivos E todas as negacoes."""
    results: list[dict[str, str]] = []
    for bindings in match_conditions(rule.conditions, facts):
        blocked = False
        for neg in rule.negations:
            if negation_blocks(neg, facts, bindings):
                blocked = True
                LOG.debug("%s: negacao %s bloqueou (bindings=%s)",
                          rule.id, neg, bindings)
                break
        if not blocked:
            results.append(bindings)
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
            # Snapshot: negacoes avaliadas sobre `facts` (nao incluindo
            # derivados deste ciclo). Sem isso, P21e entraria em loop.
            new_facts: list[TripleFact] = []
            seen_in_cycle: set[tuple[str, str, str]] = set()

            for rule in ordered:
                for bindings in match_rule(rule, facts):
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        LOG.warning("ciclo %d: %s conclusao invalida",
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


def F(s: str, p: str, o: str) -> TripleFact:
    return TripleFact(s, p, o)


def derived_set(facts: list[TripleFact]) -> list[str]:
    return sorted(f.render() for f in facts if f.source == "derived")


# ============================================================
# P21a â€” NAF basico (deriva)
# ============================================================
def run_p21a() -> dict:
    X, Y = Var("X"), Var("Y")
    rules = [Rule("R_ok",
                  conditions=((X, "r", Y),),
                  negations=((X, "is_bad", WILD),),
                  conclusion=(X, "ok", Y))]
    facts = [F("a", "r", "b")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {"ciclos": eng.cycles_used, "derived": derived_set(result)}


# ============================================================
# P21b â€” NAF bloqueia
# ============================================================
def run_p21b() -> dict:
    X, Y = Var("X"), Var("Y")
    rules = [Rule("R_ok",
                  conditions=((X, "r", Y),),
                  negations=((X, "is_bad", WILD),),
                  conclusion=(X, "ok", Y))]
    facts = [F("a", "r", "b"), F("a", "is_bad", "yes")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {"ciclos": eng.cycles_used, "derived": derived_set(result)}


# ============================================================
# P21c â€” NAF avalia por binding de X, nao por par (X,Y)
# ============================================================
def run_p21c() -> dict:
    """
    Fatos: (a,r,a), (a,r,b), (b,r,c).
    Regra: IF (X,r,Y) AND NOT (X,r,X) THEN (X,not_self,Y).

    NAF 'NOT (X,r,X)' significa: "nao existe fato (v,r,v) para o valor
    de X". E por SUJEITO, nao por par (X,Y).

    - (a,r,a): X=a. Existe (a,r,a) -> BLOCK.
    - (a,r,b): X=a. Existe (a,r,a) -> BLOCK.
    - (b,r,c): X=b. Existe (b,r,b)? Nao -> DERIVE (b,not_self,c).

    Isto prova NAF correto. NAO prova exclusao de Y==X (que exigiria
    constraint X != Y â€” direcao futura, ver README).
    """
    X, Y = Var("X"), Var("Y")
    rules = [Rule("R_ns",
                  conditions=((X, "r", Y),),
                  negations=((X, "r", X),),
                  conclusion=(X, "not_self", Y))]
    facts = [F("a", "r", "a"), F("a", "r", "b"), F("b", "r", "c")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {"ciclos": eng.cycles_used, "derived": derived_set(result)}


# ============================================================
# P21d â€” NAF em grafo ciclico
# ============================================================
def run_p21d() -> dict:
    X, Y = Var("X"), Var("Y")
    rules = [Rule("R_oneway",
                  conditions=((X, "r", Y),),
                  negations=((Y, "r", X),),
                  conclusion=(X, "one_way", Y))]
    facts = [F("a", "r", "b"), F("b", "r", "a")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {"ciclos": eng.cycles_used, "derived": derived_set(result)}


# ============================================================
# P21e â€” self-defeating quiesce via snapshot
# ============================================================
def run_p21e() -> dict:
    X = Var("X")
    rules = [Rule("R_done",
                  conditions=((X, "trigger", "yes"),),
                  negations=((X, "done", "yes"),),
                  conclusion=(X, "done", "yes"))]
    facts = [F("a", "trigger", "yes")]
    eng = ForwardChainingEngine(max_cycles=10)
    result = eng.run(facts, rules)
    return {
        "ciclos": eng.cycles_used,
        "trace_len": len(eng.trace),
        "derived": derived_set(result),
    }


# ============================================================
# P21f â€” duas negacoes (conjuncao)
# ============================================================
def run_p21f() -> dict:
    X, Y = Var("X"), Var("Y")
    rules = [Rule("R_super",
                  conditions=((X, "r", Y),),
                  negations=((X, "is_bad", WILD), (X, "is_ugly", WILD)),
                  conclusion=(X, "super_ok", Y))]

    cases = {}
    for name, extra in (
        ("none", []),
        ("bad_only", [F("a", "is_bad", "yes")]),
        ("ugly_only", [F("a", "is_ugly", "yes")]),
        ("both", [F("a", "is_bad", "yes"), F("a", "is_ugly", "yes")]),
    ):
        eng = ForwardChainingEngine(max_cycles=10)
        result = eng.run([F("a", "r", "b"), *extra], rules)
        cases[name] = derived_set(result)
    return cases


# ============================================================
# P21g â€” determinismo
# ============================================================
def run_p21g() -> dict:
    runs: set[tuple[str, ...]] = set()
    for _ in range(100):
        runs.add(tuple(run_p21a()["derived"]))
    return {"n": 100, "unique": runs}


# ============================================================
# main
# ============================================================
def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P21a ----------
    lines.append("=== P21a: NAF basico (deriva) ===")
    a = run_p21a()
    lines.append(f"ciclos_usados: {a['ciclos']}")
    lines.append("derived:")
    for d in a["derived"]:
        lines.append(f"  {d}")
    lines.append("")
    if a["derived"] != ["(a, ok, b)"]:
        falhas.append(f"P21a: derived inesperado: {a['derived']}")

    # ---------- P21b ----------
    lines.append("=== P21b: NAF bloqueia ===")
    b = run_p21b()
    lines.append(f"ciclos_usados: {b['ciclos']}")
    lines.append(f"derived: {b['derived']}")
    lines.append("")
    if b["derived"] != []:
        falhas.append(f"P21b: derived deveria ser vazio, veio {b['derived']}")

    # ---------- P21c ----------
    lines.append("=== P21c: NAF avalia por binding de X, nao por par (X,Y) ===")
    c = run_p21c()
    lines.append(f"ciclos_usados: {c['ciclos']}")
    lines.append("derived:")
    for d in c["derived"]:
        lines.append(f"  {d}")
    lines.append("")
    if c["derived"] != ["(b, not_self, c)"]:
        falhas.append(f"P21c: derived inesperado: {c['derived']}")
    if c["derived"] != ["(b, not_self, c)"]:
        falhas.append(f"P21c: derived inesperado: {c['derived']}")

    # ---------- P21d ----------
    lines.append("=== P21d: NAF em grafo ciclico ===")
    d = run_p21d()
    lines.append(f"ciclos_usados: {d['ciclos']}")
    lines.append(f"derived: {d['derived']}")
    lines.append("")
    if d["derived"] != []:
        falhas.append(f"P21d: derived deveria ser vazio, veio {d['derived']}")

    # ---------- P21e ----------
    lines.append("=== P21e: self-defeating quiesce via snapshot ===")
    e = run_p21e()
    lines.append(f"ciclos_usados: {e['ciclos']}")
    lines.append(f"trace_len: {e['trace_len']}")
    lines.append("derived:")
    for d_item in e["derived"]:
        lines.append(f"  {d_item}")
    lines.append("")
    if e["derived"] != ["(a, done, yes)"]:
        falhas.append(f"P21e: derived inesperado: {e['derived']}")
    if e["trace_len"] != 1:
        falhas.append(f"P21e: esperado trace_len 1, veio {e['trace_len']}")

    # ---------- P21f ----------
    lines.append("=== P21f: duas negacoes (conjuncao) ===")
    f = run_p21f()
    for case, outs in f.items():
        lines.append(f"  {case}: {outs}")
    lines.append("")
    if f["none"] != ["(a, super_ok, b)"]:
        falhas.append(f"P21f(none): esperado derivar, veio {f['none']}")
    if f["bad_only"] != []:
        falhas.append(f"P21f(bad_only): deveria bloquear, veio {f['bad_only']}")
    if f["ugly_only"] != []:
        falhas.append(f"P21f(ugly_only): deveria bloquear, veio {f['ugly_only']}")
    if f["both"] != []:
        falhas.append(f"P21f(both): deveria bloquear, veio {f['both']}")

    # ---------- P21g ----------
    lines.append("=== P21g: determinismo (100 runs) ===")
    g = run_p21g()
    lines.append(f"n: {g['n']}")
    lines.append(f"unique_outputs: {sorted(g['unique'])}")
    lines.append("")
    if g["unique"] != {("(a, ok, b)",)}:
        falhas.append(f"P21g: nao-deterministico: {g['unique']}")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for item in falhas:
            lines.append(f"  - {item}")
        LOG.error("P21 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P21 PASS")
        LOG.info("P21 PASS")
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
