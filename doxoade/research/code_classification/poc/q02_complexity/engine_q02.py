# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/q02_complexity/engine_q02.py
"""
Q02 - Complexity as 3rd dimension (DC2).

Contrato: DC2 (Classification) estendido.
    StructuralFact + rules -> CategoryFact (3 dimensoes simultaneas).

3 dimensoes ortogonais:
    dim1: category       (Q00/Q01 - derivada de R_arith/R_ident/R_const/R_unknown)
    dim2: has_docstring  (Q01 - seed)
    dim3: complexity     (Q02 - derivada de branch_count)

Branch count:
    Conta nos de controle de fluxo recursivamente no body (sem docstring):
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler.
    Nao conta IfExp (ternary), comprehensions (If/For internos).

Bucketing:
    branch_count = 0     -> complexity = "1"
    branch_count = 1     -> complexity = "2"
    branch_count = 2     -> complexity = "3"
    branch_count = 3     -> complexity = "3"
    branch_count >= 4    -> complexity = "4+"

Por que buckets 2 e 3 compartilham "3": evita proliferacao de buckets
sem agregar valor ao estimador de complexidade.

Por que "4+" e range marker: extractor emite `branch_count_ge_4=yes`
quando N>=4 — hint estrutural honesto, nao classificacao.

Q02a - return x+1                              -> {arith, no, "1"}
Q02b - if x>0: return x / return 0            -> {unknown, no, "2"}
Q02c - for x in xs: print(x) / return len(xs) -> {unknown, no, "2"}
Q02d - if x>0: for i in range(x): print(i)     -> {unknown, no, "3"}
Q02e - if x: if x>0: for i in range(x): ...   -> {unknown, no, "3"}
Q02f - 4+ branches                            -> {unknown, no, "4+"}
Q02g - doc + if x>0: return x+1               -> {unknown, yes, "2"}
Q02h - determinism (100 runs de Q02a)

Rodar: doxoade retro-forward run q02
"""
from __future__ import annotations

import ast
import dataclasses
import logging
import sys
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"
DEBUG = "--debug" in sys.argv


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc_q02")
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


class UnsupportedNodeError(RuntimeError):
    pass


# ============================================================
# Kernel inline (mesmo de Q00/Q01)
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
class Triple:
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

    def conclusion_fact(self, bindings, cycle):
        r = substitute(self.conclusion, bindings)
        if r is None:
            return None
        s, p, o = r
        return Triple(s, p, o, source="derived", rule_id=self.id, cycle=cycle)


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


def match_with_negations(conditions, negations, facts):
    results = []

    def recurse(conds, binds, wit):
        if not conds:
            for neg in negations:
                if any(unify(neg, f.to_tuple(), binds) is not None
                       for f in facts):
                    return
            results.append((binds, wit))
            return
        first = conds[0]
        rest = conds[1:]
        for f in facts:
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
        self.cycles_used = 0
        self.rules_attempted = 0
        self.rule_attempts: dict[str, int] = {}
        self.shadowed: list[tuple[str, tuple]] = []
        self.cycle_history: list[dict] = []

    def run(self, initial_facts, rules):
        facts = list(initial_facts)
        ordered = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            existing = set(f.to_tuple() for f in facts)
            candidates = []
            cycle_info = {
                "cycle": cycles,
                "matches": {},
                "idempotent": [],
                "candidates": [],
                "winners": [],
                "shadowed": [],
            }

            for rule in ordered:
                matches = match_with_negations(
                    rule.conditions, rule.negations, facts
                )
                cycle_info["matches"][rule.id] = len(matches)
                for bindings, wit in matches:
                    self.rules_attempted += 1
                    self.rule_attempts[rule.id] = (
                        self.rule_attempts.get(rule.id, 0) + 1
                    )
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        continue
                    if cf.to_tuple() in existing:
                        cycle_info["idempotent"].append(
                            (rule.id, cf.to_tuple())
                        )
                        continue
                    candidates.append((rule, cf, wit))
                    cycle_info["candidates"].append(
                        (rule.id, rule.priority, cf.to_tuple())
                    )

            winners = {}
            for rule, cf, wit in candidates:
                key = (cf.s, cf.p)
                if key not in winners:
                    winners[key] = (rule, cf, wit)
                    continue
                prev_rule, prev_cf, _ = winners[key]
                if rule.priority > prev_rule.priority:
                    cycle_info["shadowed"].append(
                        (prev_rule.id, prev_cf.to_tuple())
                    )
                    self.shadowed.append(
                        (prev_rule.id, prev_cf.to_tuple())
                    )
                    winners[key] = (rule, cf, wit)
                else:
                    cycle_info["shadowed"].append(
                        (rule.id, cf.to_tuple())
                    )
                    self.shadowed.append(
                        (rule.id, cf.to_tuple())
                    )

            for (s, p), (rule, cf, wit) in winners.items():
                cycle_info["winners"].append(
                    (rule.id, rule.priority, cf.to_tuple())
                )

            self.cycle_history.append(cycle_info)

            if not winners:
                self.cycles_used = cycles
                return facts, cycles

            for (s, p), (rule, cf, wit) in winners.items():
                facts.append(cf)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": rule.id,
                    "fact": cf.to_tuple(),
                    "derived_from": wit,
                })
        raise RuntimeError(f"max_cycles={self.max_cycles}")


# ============================================================
# DC1 - AST -> facts (com branch count)
# ============================================================
BRANCH_NODE_TYPES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
)


def _count_branches(body: list) -> int:
    count = 0
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, BRANCH_NODE_TYPES):
                count += 1
    return count


def extract_facts(src: str) -> list[Triple]:
    tree = ast.parse(src)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise UnsupportedNodeError(
            f"esperado 1 FunctionDef, veio "
            f"{[type(n).__name__ for n in tree.body]}"
        )
    func = tree.body[0]
    has_doc = ast.get_docstring(func) is not None
    body_stmts = func.body[1:] if has_doc else func.body

    branch_count = _count_branches(body_stmts)

    facts = [
        Triple(func.name, "kind", "function"),
        Triple(func.name, "has_docstring", "yes" if has_doc else "no"),
        Triple(func.name, "body_len", str(len(body_stmts))),
        Triple(func.name, "branch_count", str(branch_count)),
    ]
    if branch_count >= 4:
        facts.append(Triple(func.name, "branch_count_ge_4", "yes"))
    if body_stmts:
        first = body_stmts[0]
        facts.append(Triple(func.name, "body_0_kind", type(first).__name__))
        if isinstance(first, ast.Return) and first.value is not None:
            facts.append(Triple(
                func.name, "return_expr_kind", type(first.value).__name__
            ))
    return facts


# ============================================================
# DC2 - Rules (categoria + complexidade)
# ============================================================
F = Var("F")

CATEGORY_RULES = [
    Rule("R_arith",
         conditions=((F, "kind", "function"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "BinOp")),
         conclusion=(F, "category", "arithmetic_return"),
         priority=10),
    Rule("R_ident",
         conditions=((F, "kind", "function"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "Name")),
         conclusion=(F, "category", "identity_return"),
         priority=10),
    Rule("R_const",
         conditions=((F, "kind", "function"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "Constant")),
         conclusion=(F, "category", "constant_return"),
         priority=10),
    Rule("R_unknown",
         conditions=((F, "kind", "function"),),
         negations=((F, "category", WILD),),
         conclusion=(F, "category", "unknown"),
         priority=1),
]

COMPLEXITY_RULES = [
    Rule("R_c_1",
         conditions=((F, "branch_count", "0"),),
         conclusion=(F, "complexity", "1"),
         priority=15),
    Rule("R_c_2",
         conditions=((F, "branch_count", "1"),),
         conclusion=(F, "complexity", "2"),
         priority=15),
    Rule("R_c_3a",
         conditions=((F, "branch_count", "2"),),
         conclusion=(F, "complexity", "3"),
         priority=15),
    Rule("R_c_3b",
         conditions=((F, "branch_count", "3"),),
         conclusion=(F, "complexity", "3"),
         priority=15),
    Rule("R_c_4plus",
         conditions=((F, "branch_count_ge_4", "yes"),),
         conclusion=(F, "complexity", "4+"),
         priority=15),
]

RULES = CATEGORY_RULES + COMPLEXITY_RULES


# ============================================================
# classify + debug
# ============================================================
def _dbg_cycle(cycle_info):
    _dbg(f"  cycle {cycle_info['cycle']}:")
    m = cycle_info["matches"]
    _dbg("    matches: " + " ".join(f"{rid}={v}" for rid, v in m.items()))
    for rid, prio, fact in cycle_info["candidates"]:
        _dbg(f"    candidate: {rid} prio={prio} -> {fact}")
    for rid, prio, fact in cycle_info["winners"]:
        _dbg(f"    winner: {rid} -> {fact}")
    for rid, fact in cycle_info["shadowed"]:
        _dbg(f"    shadowed: {rid} -> {fact}")
    for rid, fact in cycle_info["idempotent"]:
        _dbg(f"    idempotent: {rid} -> {fact}")
    if not cycle_info["winners"]:
        _dbg("    quiescence")


def classify(src: str) -> dict:
    t0 = time.perf_counter()
    seed = extract_facts(src)
    t_extract = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    eng = Engine()
    result_facts, cycles = eng.run(seed, RULES)
    t_infer = (time.perf_counter() - t0) * 1000

    categories = sorted(f.o for f in result_facts if f.p == "category")
    has_doc_vals = sorted(f.o for f in result_facts if f.p == "has_docstring")
    complexities = sorted(f.o for f in result_facts if f.p == "complexity")

    return {
        "input": src,
        "category": categories[0] if categories else None,
        "has_docstring": has_doc_vals[0] if has_doc_vals else None,
        "complexity": complexities[0] if complexities else None,
        "cycles": cycles,
        "trace_len": len(eng.trace),
        "metrics": {
            "seed": [f.to_tuple() for f in seed],
            "rules_attempted": eng.rules_attempted,
            "rule_attempts": dict(eng.rule_attempts),
            "shadowed": list(eng.shadowed),
            "cycle_history": list(eng.cycle_history),
            "t_extract_ms": t_extract,
            "t_infer_ms": t_infer,
        },
    }


def _classify_and_debug(label, src):
    r = classify(src)
    m = r["metrics"]

    _dbg(f"--- {label} ---")
    _dbg(f"  input: {src!r}")
    _dbg(f"  extract: {len(m['seed'])} seed facts in {m['t_extract_ms']:.3f}ms")
    for fact in m["seed"]:
        _dbg(f"    {fact}")
    for cycle_info in m["cycle_history"]:
        _dbg_cycle(cycle_info)
    dims = [d for d, v in
            [("category", r["category"]),
             ("has_docstring", r["has_docstring"]),
             ("complexity", r["complexity"])]
            if v is not None]
    _dbg(f"  result: category={r['category']} "
         f"has_docstring={r['has_docstring']} complexity={r['complexity']}")
    _dbg(f"  dims: {len(dims)} ({', '.join(dims)})")
    _dbg(f"  cycles={r['cycles']} trace_len={r['trace_len']}")
    _dbg(f"  timing: extract={m['t_extract_ms']:.3f}ms "
         f"infer={m['t_infer_ms']:.3f}ms "
         f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
    _dbg("")
    return r


# ============================================================
# Sub-sondas
# ============================================================
SRC_Q02A = "def f(x): return x + 1"
SRC_Q02B = "def g(x):\n    if x > 0:\n        return x\n    return 0"
SRC_Q02C = "def h(xs):\n    for x in xs:\n        print(x)\n    return len(xs)"
SRC_Q02D = ("def k(x):\n    if x > 0:\n        for i in range(x):\n"
            "            print(i)\n    return x")
SRC_Q02E = ("def m(x):\n    if x:\n        if x > 0:\n"
            "            for i in range(x):\n                print(i)\n"
            "    return x")
SRC_Q02F = ("def n(x):\n    if x > 0:\n        if x > 1:\n"
            "            for i in range(x):\n                print(i)\n"
            "    while x:\n        x -= 1\n    return x")
SRC_Q02G = ('def p(x):\n    """Doc."""\n    if x > 0:\n'
            '        return x + 1\n    return 0')


def run_q02a():
    return _classify_and_debug("Q02a: return x+1", SRC_Q02A)


def run_q02b():
    return _classify_and_debug("Q02b: if x>0: return x / return 0", SRC_Q02B)


def run_q02c():
    return _classify_and_debug("Q02c: for x in xs: print(x) / return", SRC_Q02C)


def run_q02d():
    return _classify_and_debug("Q02d: if + for", SRC_Q02D)


def run_q02e():
    return _classify_and_debug("Q02e: if + if + for", SRC_Q02E)


def run_q02f():
    return _classify_and_debug("Q02f: 4+ branches", SRC_Q02F)


def run_q02g():
    return _classify_and_debug("Q02g: doc + if", SRC_Q02G)


def run_q02h():
    t0 = time.perf_counter()
    outs = set()
    with QUIET:
        for _ in range(100):
            r = run_q02a()
            outs.add((r["category"], r["has_docstring"], r["complexity"]))
    t_total = (time.perf_counter() - t0) * 1000

    if DEBUG:
        _dbg("--- Q02h: determinism (100 runs of Q02a) ---")
        _dbg(f"  runs: 100")
        _dbg(f"  unique_triples: {len(outs)}")
        _dbg(f"  triples: {sorted(outs)}")
        _dbg(f"  time_total: {t_total:.3f}ms")
        _dbg(f"  time_per_run: {t_total/100:.3f}ms")
        _dbg("")
    return {"n": 100, "unique_count": len(outs), "triples": outs}


def _debug_aggregate(results):
    if not DEBUG:
        return
    n = len(results)
    total_seed = sum(len(r["metrics"]["seed"]) for r in results)
    total_shadowed = sum(len(r["metrics"]["shadowed"]) for r in results)
    total_attempts = sum(r["metrics"]["rules_attempted"] for r in results)
    total_cycles = sum(r["cycles"] for r in results)
    extract_total = sum(r["metrics"]["t_extract_ms"] for r in results)
    infer_total = sum(r["metrics"]["t_infer_ms"] for r in results)

    per_rule: dict[str, int] = {}
    for r in results:
        for rid, k in r["metrics"]["rule_attempts"].items():
            per_rule[rid] = per_rule.get(rid, 0) + k
    per_rule_str = " ".join(f"{k}={v}" for k, v in sorted(per_rule.items()))

    _dbg("--- aggregate (7 classify calls) ---")
    _dbg(f"  functions: {n}")
    _dbg(f"  total_seed_facts: {total_seed}")
    _dbg(f"  total_shadowed: {total_shadowed}")
    _dbg(f"  total_rules_attempted: {total_attempts}")
    _dbg(f"  per_rule_attempts: {per_rule_str}")
    _dbg(f"  total_cycles: {total_cycles}")
    _dbg(f"  avg_cycles: {total_cycles/n:.2f}")
    _dbg(f"  extract_time_total: {extract_total:.3f}ms")
    _dbg(f"  infer_time_total: {infer_total:.3f}ms")
    _dbg(f"  total_time: {(extract_total + infer_total):.3f}ms")
    _dbg("")


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_q02.py ===")
        _dbg("mode: debug")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    checks = [
        ("Q02a", SRC_Q02A, "arithmetic_return", "no",  "1",  run_q02a),
        ("Q02b", SRC_Q02B, "unknown",           "no",  "2",  run_q02b),
        ("Q02c", SRC_Q02C, "unknown",           "no",  "2",  run_q02c),
        ("Q02d", SRC_Q02D, "unknown",           "no",  "3",  run_q02d),
        ("Q02e", SRC_Q02E, "unknown",           "no",  "3",  run_q02e),
        ("Q02f", SRC_Q02F, "unknown",           "no",  "4+", run_q02f),
        ("Q02g", SRC_Q02G, "unknown",           "yes", "2",  run_q02g),
    ]

    results_for_agg = []
    for label, src, exp_cat, exp_doc, exp_cplx, fn in checks:
        r = fn()
        results_for_agg.append(r)
        lines.append(f"=== {label} ===")
        lines.append(f"input: {src!r}")
        lines.append(f"category:      {r['category']}")
        lines.append(f"has_docstring: {r['has_docstring']}")
        lines.append(f"complexity:    {r['complexity']}")
        lines.append(f"cycles:        {r['cycles']}")
        lines.append(f"trace_len:     {r['trace_len']}")
        lines.append("")
        if r["category"] != exp_cat:
            falhas.append(
                f"{label}: category={r['category']!r}, esperado {exp_cat!r}"
            )
        if r["has_docstring"] != exp_doc:
            falhas.append(
                f"{label}: has_docstring={r['has_docstring']!r}, "
                f"esperado {exp_doc!r}"
            )
        if r["complexity"] != exp_cplx:
            falhas.append(
                f"{label}: complexity={r['complexity']!r}, "
                f"esperado {exp_cplx!r}"
            )

    lines.append("=== Q02h: determinism (100 runs of Q02a) ===")
    h = run_q02h()
    lines.append(f"n:            {h['n']}")
    lines.append(f"unique_count: {h['unique_count']}")
    lines.append("")
    if h["unique_count"] != 1:
        falhas.append(f"Q02h: {h['unique_count']} variacoes")

    _debug_aggregate(results_for_agg)

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("Q02 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("Q02 PASS")
        LOG.info("Q02 PASS")
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
