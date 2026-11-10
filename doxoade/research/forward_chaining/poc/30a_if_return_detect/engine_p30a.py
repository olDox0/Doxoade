# doxoade/research/forward_chaining/poc/30a_if_return_detect/engine_p30a.py
"""
P30a - AST real -> fatos -> inferencia (C2+C3, SEM rewrite).

Contrato: C2 (Adaptacao) + C3 (Expressividade) sobre AST Python real.
NAO faz rewrite (C4). Isso e P30b.

Subset declarado:
    def NAME(PARAM):
        if COND:
            return VALUE
        return FALLBACK

    Exatamente: FunctionDef com body de 2 stmts. stmt[0] = If com 1
    body stmt Return. stmt[1] = Return. Qualquer desvio ->
    UnsupportedNodeError.

P30a - 'def f(x): if x > 0: return x\\n    return None' deriva
        (f, pattern, if_return_guard).
P30b - 'def f(): return 42' -> UnsupportedNodeError.
P30c - 'x = a + b' -> UnsupportedNodeError (Assign nao e FunctionDef).
P30d - determinismo (100 runs).

Rodar: run_30a.bat
"""
from __future__ import annotations

import ast
import dataclasses
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc30a")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


class UnsupportedNodeError(RuntimeError):
    """AST node fora do subset declarado."""


@dataclasses.dataclass(frozen=True)
class Var:
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

    def conclusion_fact(self, bindings: dict[str, str], cycle: int) -> TripleFact | None:
        r = substitute(self.conclusion, bindings)
        if r is None:
            return None
        s, p, o = r
        return TripleFact(s, p, o, source="derived",
                          rule_id=self.id, cycle=cycle)


def unify_term(pattern: Term, value: str,
               bindings: dict[str, str]) -> dict[str, str] | None:
    if isinstance(pattern, Var):
        if pattern.name in bindings:
            return bindings if bindings[pattern.name] == value else None
        return {**bindings, pattern.name: value}
    return bindings if pattern == value else None


def unify(pattern: Pattern, fact: TripleFact,
          bindings: dict[str, str]) -> dict[str, str] | None:
    b = bindings
    for pat_t, fact_v in zip(pattern, (fact.s, fact.p, fact.o)):
        b = unify_term(pat_t, fact_v, b)
        if b is None:
            return None
    return b


def substitute(pattern: Pattern, bindings: dict[str, str]) -> tuple[str, str, str] | None:
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
                     bindings: dict[str, str] | None = None) -> list[dict[str, str]]:
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


class ForwardChainingEngine:
    def __init__(self, max_cycles: int = 100):
        self.max_cycles = max_cycles
        self.trace: list[dict] = []
        self.cycles_used: int = 0

    def run(self, initial_facts: list[TripleFact],
            rules: list[Rule]) -> list[TripleFact]:
        facts: list[TripleFact] = list(initial_facts)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            existing = frozenset(f.to_tuple() for f in facts)
            new_facts: list[TripleFact] = []
            seen: set[tuple[str, str, str]] = set()
            for rule in sorted(rules, key=lambda r: -r.priority):
                for bindings in match_conditions(rule.conditions, facts):
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        continue
                    key = cf.to_tuple()
                    if key in existing or key in seen:
                        continue
                    new_facts.append(cf)
                    seen.add(key)
            if not new_facts:
                self.cycles_used = cycles
                return facts
            for nf in new_facts:
                facts.append(nf)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": nf.rule_id,
                    "fact": nf.to_tuple(),
                })
        raise CycleLimitError(f"max_cycles={self.max_cycles}")


class CycleLimitError(RuntimeError):
    pass


# ============================================================
# C2 - AST -> fatos
# ============================================================

def extract_facts(src: str) -> list[TripleFact]:
    """AST -> fatos. Fora do subset -> UnsupportedNodeError."""
    tree = ast.parse(src)
    if len(tree.body) != 1:
        raise UnsupportedNodeError(f"esperado 1 stmt, veio {len(tree.body)}")
    func = tree.body[0]
    if not isinstance(func, ast.FunctionDef):
        raise UnsupportedNodeError(
            f"esperado FunctionDef, veio {type(func).__name__}"
        )
    if len(func.body) != 2:
        raise UnsupportedNodeError(
            f"esperado body de 2 stmts, veio {len(func.body)}"
        )
    if not isinstance(func.body[0], ast.If):
        raise UnsupportedNodeError(
            f"esperado If em body[0], veio {type(func.body[0]).__name__}"
        )
    if len(func.body[0].body) != 1:
        raise UnsupportedNodeError(
            f"esperado If.body de 1 stmt, veio {len(func.body[0].body)}"
        )
    if not isinstance(func.body[0].body[0], ast.Return):
        raise UnsupportedNodeError(
            f"esperado Return em If.body, veio {type(func.body[0].body[0]).__name__}"
        )
    if not isinstance(func.body[1], ast.Return):
        raise UnsupportedNodeError(
            f"esperado Return em body[1], veio {type(func.body[1]).__name__}"
        )

    f = func.name
    return [
        TripleFact(f, "body_len", str(len(func.body))),
        TripleFact(f, "body_0_kind", type(func.body[0]).__name__),
        TripleFact(f, "if_body_len", str(len(func.body[0].body))),
        TripleFact(f, "if_body_0_kind", type(func.body[0].body[0]).__name__),
        TripleFact(f, "body_1_kind", type(func.body[1]).__name__),
    ]


# ============================================================
# C3 - regra que deriva pattern
# ============================================================

RULES: list[Rule] = [
    Rule("R_if_return_guard",
         conditions=(
             (Var("F"), "body_len", "2"),
             (Var("F"), "body_0_kind", "If"),
             (Var("F"), "if_body_len", "1"),
             (Var("F"), "if_body_0_kind", "Return"),
             (Var("F"), "body_1_kind", "Return"),
         ),
         conclusion=(Var("F"), "pattern", "if_return_guard")),
]


# ============================================================
# sub-sondas
# ============================================================

def run_p30a() -> dict:
    src = "def f(x):\n    if x > 0:\n        return x\n    return None"
    facts = extract_facts(src)
    eng = ForwardChainingEngine()
    result = eng.run(facts, RULES)
    derived = sorted(f.render() for f in result if f.source == "derived")
    return {
        "input": src,
        "seed_facts": sorted(f.render() for f in facts),
        "derived": derived,
        "ciclos": eng.cycles_used,
    }


def _expect_error(src: str) -> dict:
    try:
        extract_facts(src)
    except UnsupportedNodeError:
        return {"levantou_erro": True, "type": "UnsupportedNodeError"}
    except Exception as e:
        return {"levantou_erro": True, "type": type(e).__name__}
    return {"levantou_erro": False, "type": None}


def run_p30b() -> dict:
    src = "def f(): return 42"
    return {"input": src, **_expect_error(src)}


def run_p30c() -> dict:
    src = "x = a + b"
    return {"input": src, **_expect_error(src)}


def run_p30d() -> dict:
    outs: set[tuple[str, ...]] = set()
    for _ in range(100):
        outs.add(tuple(run_p30a()["derived"]))
    return {"n": 100, "unique": outs}


# ============================================================
# main
# ============================================================

def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    lines.append("=== P30a: AST real -> pattern fatos ===")
    a = run_p30a()
    lines.append(f"input: {a['input']!r}")
    lines.append(f"ciclos_usados: {a['ciclos']}")
    lines.append(f"seed_facts_len: {len(a['seed_facts'])}")
    lines.append("derived:")
    for d in a["derived"]:
        lines.append(f"  {d}")
    lines.append("")

    if a["derived"] != ["(f, pattern, if_return_guard)"]:
        falhas.append(f"P30a: derived inesperado: {a['derived']}")

    for label, runner in (("P30b", run_p30b), ("P30c", run_p30c)):
        r = runner()
        lines.append(f"=== {label}: input {r['input']!r} ===")
        lines.append(f"levantou_erro: {r['levantou_erro']}")
        lines.append(f"type: {r['type']}")
        lines.append("")
        if not r["levantou_erro"]:
            falhas.append(f"{label}: esperado erro, veio OK")
        if r["type"] != "UnsupportedNodeError":
            falhas.append(f"{label}: esperado UnsupportedNodeError, veio {r['type']}")

    lines.append("=== P30d: determinismo (100 runs) ===")
    d = run_p30d()
    lines.append(f"n: {d['n']}")
    lines.append(f"unique_outputs: {sorted(d['unique'])}")
    lines.append("")
    if d["unique"] != {("(f, pattern, if_return_guard)",)}:
        falhas.append(f"P30d: nao-deterministico: {d['unique']}")

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("P30a FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P30a PASS")
        LOG.info("P30a PASS")
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
