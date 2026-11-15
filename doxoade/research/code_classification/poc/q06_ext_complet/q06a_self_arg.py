# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/q06_ext_complet/q06a_self_arg.py
"""
Q06a - Self-arg detection (extraction completeness, sub-probe).

Problema (dado de X03): 37 de 38 units com self_arg=yes ficam
category=unknown. Q05 nao ve `self` de forma alguma — mesmo em
__init__ com body_0_kind=Assign.

Solucao (Q06a): extrair `has_self_arg` como fato. Rules novas
derivam `method_role` (dimensao ortogonal a `category`):
    - initializer : __init__ com self
    - repr        : __repr__ com self
    - getter      : return self.x (Attribute)
    - method      : qualquer outro self
    - (ausente)   : funcao sem self (passthrough Q05)

Sub-sondas:
    Q06a1 - method initializer
    Q06a2 - method getter
    Q06a3 - plain function (self_arg=no, passthrough)
    Q06a4 - method dunder repr
    Q06a5 - determinism (100 runs de Q06a1)

Contrato provado (se PASS):
    has_self_arg=yes adiciona `method_role` sem quebrar `category`.
    category continua Q05 literal. method_role e ortogonal.

NAO prova:
    - que metodos serao 100% cobertos no corpus real (X03 mede)
    - que Q06a resolve os 37 units (pode haver self_arg com
      outros problemas; X03 re-run mede)

Rodar: py q06a_self_arg.py
"""

from __future__ import annotations
import ast
import dataclasses
import logging
import sys
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging_q06a.txt"
DEBUG = "--debug" in sys.argv


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc_q06a")
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
# Kernel (Q05 inlined)
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
class Fact:
    s: str
    p: str
    o: str
    source: str = "seed"
    rule_id: str | None = None
    cycle: int = 0
    priority: int = 0
    def to_tuple(self) -> tuple[str, str, str]:
        return (self.s, self.p, self.o)


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
        return Fact(s, p, o, source="derived",
                    rule_id=self.id, cycle=cycle, priority=self.priority)


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


def match_with_negations(conditions, negations, live_facts):
    results = []
    def recurse(conds, binds, wit):
        if not conds:
            for neg in negations:
                if any(unify(neg, f.to_tuple(), binds) is not None
                       for f in live_facts):
                    return
            results.append((binds, wit))
            return
        first = conds[0]
        rest = conds[1:]
        for f in live_facts:
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
        self.retracted: set = set()
        self.cycles_used = 0
        self.rule_attempts: dict[str, int] = {}
        self.shadowed: list = []

    def run(self, initial_facts, rules):
        facts = list(initial_facts)
        ordered = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            live_facts = [f for f in facts if f.to_tuple() not in self.retracted]
            existing = set(f.to_tuple() for f in live_facts)
            candidates = []
            for rule in ordered:
                matches = match_with_negations(
                    rule.conditions, rule.negations, live_facts
                )
                for bindings, wit in matches:
                    self.rule_attempts[rule.id] = (
                        self.rule_attempts.get(rule.id, 0) + 1
                    )
                    cf = rule.conclusion_fact(bindings, cycle=cycles)
                    if cf is None:
                        continue
                    if cf.to_tuple() in existing:
                        continue
                    candidates.append((rule, cf, wit))
            winners = {}
            for rule, cf, wit in candidates:
                key = (cf.s, cf.p)
                if key not in winners:
                    winners[key] = (rule, cf, wit)
                    continue
                prev_rule, prev_cf, _ = winners[key]
                if rule.priority > prev_rule.priority:
                    self.shadowed.append((prev_rule.id, prev_cf.to_tuple()))
                    winners[key] = (rule, cf, wit)
                else:
                    self.shadowed.append((rule.id, cf.to_tuple()))
            fired = False
            for (s, p), (rule, cf, wit) in winners.items():
                to_retract = []
                shadow_new = False
                for ef in live_facts:
                    if ef.s != s or ef.p != p:
                        continue
                    if ef.o == cf.o:
                        shadow_new = True
                        break
                    ef_prio = ef.priority if ef.source == "derived" else 999999
                    if cf.priority > ef_prio:
                        to_retract.append(ef)
                    else:
                        shadow_new = True
                        break
                if shadow_new:
                    self.shadowed.append((rule.id, cf.to_tuple()))
                    continue
                for ef in to_retract:
                    self.retracted.add(ef.to_tuple())
                facts.append(cf)
                self.trace.append({
                    "cycle": cycles, "rule_id": rule.id,
                    "fact": cf.to_tuple(),
                })
                fired = True
            if not fired:
                self.cycles_used = cycles
                return facts, cycles
        raise RuntimeError(f"max_cycles={self.max_cycles}")


# ============================================================
# Extractor Q05 + Q06a (has_self_arg, is_dunder)
# ============================================================
BRANCH_NODE_TYPES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler,
)


def _count_branches(body):
    count = 0
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, BRANCH_NODE_TYPES):
                count += 1
    return count


def _name_prefix(name):
    if name.startswith("create_"):
        return "create"
    if name.startswith("get_"):
        return "get"
    if name.startswith("is_"):
        return "is"
    return "other"


def _has_magic_number(body):
    for stmt in body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Compare):
                for comp in sub.comparators:
                    if (isinstance(comp, ast.Constant)
                            and isinstance(comp.value, int)
                            and not isinstance(comp.value, bool)
                            and comp.value not in (0, 1, -1)):
                        return True
    return False


def _is_long_body(body):
    return len(body) >= 4


def _has_dead_after_return(body):
    for stmt in body[:-1]:
        if isinstance(stmt, ast.Return):
            return True
    return False


def extract_facts(src: str) -> list[Fact]:
    tree = ast.parse(src)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise UnsupportedNodeError(
            f"esperado 1 FunctionDef, veio {[type(n).__name__ for n in tree.body]}"
        )
    func = tree.body[0]
    has_doc = ast.get_docstring(func) is not None
    body_stmts = func.body[1:] if has_doc else func.body
    branch_count = _count_branches(body_stmts)

    # Q06a: self_arg detection
    is_method = bool(func.args.args) and func.args.args[0].arg == "self"
    is_dunder = (func.name.startswith("__") and func.name.endswith("__"))

    facts = [
        Fact(func.name, "kind", "function"),
        Fact(func.name, "name", func.name),
        Fact(func.name, "name_prefix", _name_prefix(func.name)),
        Fact(func.name, "has_docstring", "yes" if has_doc else "no"),
        Fact(func.name, "body_len", str(len(body_stmts))),
        Fact(func.name, "branch_count", str(branch_count)),
        Fact(func.name, "has_magic_number",
             "yes" if _has_magic_number(body_stmts) else "no"),
        Fact(func.name, "long_body",
             "yes" if _is_long_body(body_stmts) else "no"),
        Fact(func.name, "dead_after_return",
             "yes" if _has_dead_after_return(body_stmts) else "no"),
        # Q06a novo:
        Fact(func.name, "has_self_arg", "yes" if is_method else "no"),
        Fact(func.name, "is_dunder", "yes" if is_dunder else "no"),
    ]
    if branch_count >= 4:
        facts.append(Fact(func.name, "branch_count_ge_4", "yes"))
    if body_stmts:
        first = body_stmts[0]
        facts.append(Fact(func.name, "body_0_kind", type(first).__name__))
        if isinstance(first, ast.Return) and first.value is not None:
            facts.append(Fact(
                func.name, "return_expr_kind", type(first.value).__name__
            ))
    return facts


# ============================================================
# Rules: Q05 + Q06a
# ============================================================
F = Var("F")

CATEGORY_RULES = [
    Rule("R_arith",
         conditions=((F, "kind", "function"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "BinOp")),
         conclusion=(F, "category", "arithmetic_return"), priority=10),
    Rule("R_ident",
         conditions=((F, "kind", "function"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "Name")),
         conclusion=(F, "category", "identity_return"), priority=10),
    Rule("R_const",
         conditions=((F, "kind", "function"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "Constant")),
         conclusion=(F, "category", "constant_return"), priority=10),
    Rule("R_unknown",
         conditions=((F, "kind", "function"),),
         negations=((F, "category", WILD),),
         conclusion=(F, "category", "unknown"), priority=1),
]

COMPLEXITY_RULES = [
    Rule("R_c_1", conditions=((F, "branch_count", "0"),),
         conclusion=(F, "complexity", "1"), priority=15),
    Rule("R_c_2", conditions=((F, "branch_count", "1"),),
         conclusion=(F, "complexity", "2"), priority=15),
    Rule("R_c_3a", conditions=((F, "branch_count", "2"),),
         conclusion=(F, "complexity", "3"), priority=15),
    Rule("R_c_3b", conditions=((F, "branch_count", "3"),),
         conclusion=(F, "complexity", "3"), priority=15),
    Rule("R_c_4plus", conditions=((F, "branch_count_ge_4", "yes"),),
         conclusion=(F, "complexity", "4+"), priority=15),
]

SMELL_RULES = [
    Rule("R_magic", conditions=((F, "has_magic_number", "yes"),),
         conclusion=(F, "smell_magic_number", "yes"), priority=15),
    Rule("R_long", conditions=((F, "long_body", "yes"),),
         conclusion=(F, "smell_long_method", "yes"), priority=15),
    Rule("R_dead", conditions=((F, "dead_after_return", "yes"),),
         conclusion=(F, "smell_dead_code", "yes"), priority=15),
]

CLEAN_RULE = Rule("R_clean",
    conditions=((F, "kind", "function"),),
    negations=((F, "smell_magic_number", WILD),
               (F, "smell_long_method", WILD),
               (F, "smell_dead_code", WILD)),
    conclusion=(F, "has_any_smell", "none"), priority=1)

DIRTY_RULES = [
    Rule("R_dirty_magic",
         conditions=((F, "smell_magic_number", "yes"),),
         conclusion=(F, "has_any_smell", "dirty"), priority=20),
    Rule("R_dirty_long",
         conditions=((F, "smell_long_method", "yes"),),
         conclusion=(F, "has_any_smell", "dirty"), priority=20),
    Rule("R_dirty_dead",
         conditions=((F, "smell_dead_code", "yes"),),
         conclusion=(F, "has_any_smell", "dirty"), priority=20),
]

# Q06a: method_role (dimensao ortogonal a category)
Q06A_RULES = [
    Rule("R_method_init",
         conditions=((F, "has_self_arg", "yes"),
                     (F, "is_dunder", "yes"),
                     (F, "name", "__init__"),
                     (F, "body_0_kind", "Assign")),
         conclusion=(F, "method_role", "initializer"), priority=25),
    Rule("R_method_repr",
         conditions=((F, "has_self_arg", "yes"),
                     (F, "is_dunder", "yes"),
                     (F, "name", "__repr__")),
         conclusion=(F, "method_role", "repr"), priority=25),
    Rule("R_method_getter",
         conditions=((F, "has_self_arg", "yes"),
                     (F, "body_0_kind", "Return"),
                     (F, "return_expr_kind", "Attribute")),
         conclusion=(F, "method_role", "getter"), priority=20),
    Rule("R_method",
         conditions=((F, "has_self_arg", "yes"),),
         conclusion=(F, "method_role", "method"), priority=10),
]

RULES = (CATEGORY_RULES + COMPLEXITY_RULES + SMELL_RULES +
         [CLEAN_RULE] + DIRTY_RULES + Q06A_RULES)


# ============================================================
# classify
# ============================================================
def _live_val(live, pred):
    vals = sorted(f.o for f in live if f.p == pred)
    return vals[0] if vals else None


def classify(src: str) -> dict:
    seed = extract_facts(src)
    eng = Engine()
    facts, cycles = eng.run(seed, RULES)
    live = [f for f in facts if f.to_tuple() not in eng.retracted]
    return {
        "input": src,
        "category": _live_val(live, "category"),
        "method_role": _live_val(live, "method_role"),
        "has_self_arg": _live_val(live, "has_self_arg"),
        "is_dunder": _live_val(live, "is_dunder"),
        "complexity": _live_val(live, "complexity"),
        "cycles": cycles,
        "trace_len": len(eng.trace),
        "seed": [f.to_tuple() for f in seed],
    }


def _classify_and_debug(label, src):
    r = classify(src)
    _dbg(f"--- {label} ---")
    _dbg(f"  input: {src!r}")
    _dbg(f"  seed: {len(r['seed'])} facts")
    for f in r["seed"]:
        _dbg(f"    {f}")
    _dbg(f"  result: category={r['category']} "
         f"method_role={r['method_role']}")
    _dbg(f"  cycles={r['cycles']} trace_len={r['trace_len']}")
    _dbg("")
    return r


# ============================================================
# Sub-sondas
# ============================================================
SRC_Q06A1 = "def __init__(self):\n    self.x = 1"
SRC_Q06A2 = "def get_x(self):\n    return self.x"
SRC_Q06A3 = "def helper(x):\n    return x + 1"
SRC_Q06A4 = 'def __repr__(self):\n    return "Var"'


def run_q06a1():
    return _classify_and_debug("Q06a1: method initializer", SRC_Q06A1)


def run_q06a2():
    return _classify_and_debug("Q06a2: method getter", SRC_Q06A2)


def run_q06a3():
    return _classify_and_debug("Q06a3: plain function (passthrough)", SRC_Q06A3)


def run_q06a4():
    return _classify_and_debug("Q06a4: method dunder repr", SRC_Q06A4)


def run_q06a5():
    t0 = time.perf_counter()
    outs = set()
    with QUIET:
        for _ in range(100):
            r = run_q06a1()
            outs.add((r["category"], r["method_role"]))
    t_total = (time.perf_counter() - t0) * 1000
    _dbg(f"Q06a5 time_total: {t_total:.3f}ms")
    return {"n": 100, "unique_count": len(outs)}


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== q06a_self_arg.py ===")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    checks = [
        ("Q06a1", SRC_Q06A1, "unknown", "initializer", run_q06a1),
        ("Q06a2", SRC_Q06A2, "unknown", "getter", run_q06a2),
        ("Q06a3", SRC_Q06A3, "arithmetic_return", None, run_q06a3),
        ("Q06a4", SRC_Q06A4, "constant_return", "repr", run_q06a4),
    ]

    for label, src, exp_cat, exp_role, fn in checks:
        r = fn()
        lines.append(f"=== {label} ===")
        lines.append(f"input: {src!r}")
        lines.append(f"self_arg:     {r['has_self_arg']}")
        lines.append(f"is_dunder:    {r['is_dunder']}")
        lines.append(f"category:     {r['category']}")
        lines.append(f"method_role:  {r['method_role']}")
        lines.append(f"cycles:       {r['cycles']}")
        lines.append(f"trace_len:    {r['trace_len']}")
        lines.append("")
        if r["category"] != exp_cat:
            falhas.append(f"{label}: category={r['category']!r}, "
                          f"esperado {exp_cat!r}")
        if r["method_role"] != exp_role:
            falhas.append(f"{label}: method_role={r['method_role']!r}, "
                          f"esperado {exp_role!r}")

    lines.append("=== Q06a5: determinism (100 runs of Q06a1) ===")
    d = run_q06a5()
    lines.append(f"n:            {d['n']}")
    lines.append(f"unique_count: {d['unique_count']}")
    lines.append("")
    if d["unique_count"] != 1:
        falhas.append(f"Q06a5: {d['unique_count']} variacoes")

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("Q06a FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("Q06a PASS")
        LOG.info("Q06a PASS")
        resultado = 0

    for ln in lines:
        print(ln)

    output_path = Path(__file__).parent / "output_q06a.txt"
    output_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
    )
    return resultado


if __name__ == "__main__":
    sys.exit(main())
