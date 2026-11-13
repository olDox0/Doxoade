# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/q05_smell/engine_q05.py
"""
Q05 - Code smell detection as 5th dim (DC2, domain expansion).

Contrato: DC2 (Classification) com 5 dimensoes.
    category, has_docstring, complexity, pattern (herdados de Q04)
    + has_any_smell (derivado, aggregate com retracao)

NAO faz upgrade de engine. Q04 kernel inlined (retraction-aware).
Q05 testa Q04 retraction em cenario real: aggregate default
"has_any_smell=none" (prio 1, NAF) retratado por "has_any_smell=dirty"
(prio 20) quando qualquer smell_* aparece.

Smells (ortogonais, predicados distintos):
    smell_magic_number : Constant int nao-trivial em Compare
    smell_long_method  : body_len >= 4 (apos docstring)
    smell_dead_code    : Return no body-level seguido por stmt

NAO detecta (fora de escopo Q05):
    - Magic em Assign/If/BinOp (so Compare)
    - Dead nested (Return dentro de If)
    - Long method com threshold != 4
    - Smells estilo-oriented (god class, feature envy)

Q05a - clean                          -> has_any_smell=none, retr=0
Q05b - magic (x > 42)                 -> smell_magic_number=yes, dirty, retr=1
Q05c - long body (4 stmts)            -> smell_long_method=yes, dirty, retr=1
Q05d - dead (return x; print)         -> smell_dead_code=yes, dirty, retr=1
Q05e - 3 smells coexistem             -> 3 smells, dirty (retr=1)
Q05f - determinism (100 runs de Q05b)

Rodar: doxoade retro-forward run q05
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
    logger = logging.getLogger("poc_q05")
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
# Kernel (Q04 inlined, unchanged)
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
        self.retracted_history: list[dict] = []
        self.shadowed: list = []
        self.cycles_used = 0
        self.rules_attempted = 0
        self.rule_attempts: dict[str, int] = {}
        self.cycle_history: list[dict] = []

    def run(self, initial_facts, rules):
        facts = list(initial_facts)
        ordered = sorted(rules, key=lambda r: -r.priority)
        cycles = 0
        while cycles < self.max_cycles:
            cycles += 1
            live_facts = [f for f in facts if f.to_tuple() not in self.retracted]
            existing = set(f.to_tuple() for f in live_facts)
            candidates = []
            cycle_info = {
                "cycle": cycles, "matches": {}, "idempotent": [],
                "candidates": [], "winners": [], "shadowed": [], "retracted": [],
            }

            for rule in ordered:
                matches = match_with_negations(
                    rule.conditions, rule.negations, live_facts
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
                        cycle_info["idempotent"].append((rule.id, cf.to_tuple()))
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
                    cycle_info["shadowed"].append((prev_rule.id, prev_cf.to_tuple()))
                    self.shadowed.append((prev_rule.id, prev_cf.to_tuple()))
                    winners[key] = (rule, cf, wit)
                else:
                    cycle_info["shadowed"].append((rule.id, cf.to_tuple()))
                    self.shadowed.append((rule.id, cf.to_tuple()))

            for (s, p), (rule, cf, wit) in winners.items():
                to_retract = []
                shadow_new = False
                for ef in live_facts:
                    if ef.s != s or ef.p != p:
                        continue
                    if ef.o == cf.o:
                        cycle_info["idempotent"].append((rule.id, cf.to_tuple()))
                        shadow_new = True
                        break
                    ef_prio = ef.priority if ef.source == "derived" else 999999
                    if cf.priority > ef_prio:
                        to_retract.append(ef)
                    else:
                        shadow_new = True
                        break

                if shadow_new:
                    cycle_info["shadowed"].append((rule.id, cf.to_tuple()))
                    self.shadowed.append((rule.id, cf.to_tuple()))
                    continue

                for ef in to_retract:
                    self.retracted.add(ef.to_tuple())
                    self.retracted_history.append({
                        "cycle": cycles, "fact": ef.to_tuple(),
                        "by_rule": rule.id, "by_fact": cf.to_tuple(),
                    })
                    cycle_info["retracted"].append(
                        (ef.rule_id, ef.to_tuple(), rule.id)
                    )

                facts.append(cf)
                self.trace.append({
                    "cycle": cycles, "rule_id": rule.id,
                    "fact": cf.to_tuple(), "derived_from": wit,
                })
                cycle_info["winners"].append((rule.id, rule.priority, cf.to_tuple()))

            self.cycle_history.append(cycle_info)
            if not cycle_info["winners"]:
                self.cycles_used = cycles
                return facts, cycles
        raise RuntimeError(f"max_cycles={self.max_cycles}")


# ============================================================
# DC1 - AST -> facts
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
    """Constant int (nao 0, 1, -1, nao bool) em Compare.comparators."""
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
    """body_len >= 4."""
    return len(body) >= 4


def _has_dead_after_return(body):
    """Return no body-level seguido por outro stmt (body-level only)."""
    for stmt in body[:-1]:
        if isinstance(stmt, ast.Return):
            return True
    return False


def extract_facts(src: str) -> list[Fact]:
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
# DC2 - Rules
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
    Rule("R_c_1",
         conditions=((F, "branch_count", "0"),),
         conclusion=(F, "complexity", "1"), priority=15),
    Rule("R_c_2",
         conditions=((F, "branch_count", "1"),),
         conclusion=(F, "complexity", "2"), priority=15),
    Rule("R_c_3a",
         conditions=((F, "branch_count", "2"),),
         conclusion=(F, "complexity", "3"), priority=15),
    Rule("R_c_3b",
         conditions=((F, "branch_count", "3"),),
         conclusion=(F, "complexity", "3"), priority=15),
    Rule("R_c_4plus",
         conditions=((F, "branch_count_ge_4", "yes"),),
         conclusion=(F, "complexity", "4+"), priority=15),
]

# Smell specifics (cycle 1, from seed)
SMELL_RULES = [
    Rule("R_magic",
         conditions=((F, "has_magic_number", "yes"),),
         conclusion=(F, "smell_magic_number", "yes"), priority=15),
    Rule("R_long",
         conditions=((F, "long_body", "yes"),),
         conclusion=(F, "smell_long_method", "yes"), priority=15),
    Rule("R_dead",
         conditions=((F, "dead_after_return", "yes"),),
         conclusion=(F, "smell_dead_code", "yes"), priority=15),
]

# Aggregate default (cycle 1, NAF all smell_*)
CLEAN_RULE = Rule("R_clean",
    conditions=((F, "kind", "function"),),
    negations=((F, "smell_magic_number", WILD),
               (F, "smell_long_method", WILD),
               (F, "smell_dead_code", WILD)),
    conclusion=(F, "has_any_smell", "none"), priority=1)

# Aggregate specific (cycle 2, from derived smell_*)
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

RULES = (CATEGORY_RULES + COMPLEXITY_RULES +
         SMELL_RULES + [CLEAN_RULE] + DIRTY_RULES)


# ============================================================
# classify + debug
# ============================================================
def _dbg_cycle(cycle_info):
    _dbg(f"  cycle {cycle_info['cycle']}:")
    m = cycle_info["matches"]
    fired = {k: v for k, v in m.items() if v > 0}
    if fired:
        _dbg("    matches: " + " ".join(f"{rid}={v}" for rid, v in fired.items()))
    for rid, prio, fact in cycle_info["candidates"]:
        _dbg(f"    candidate: {rid} prio={prio} -> {fact}")
    for rid, prio, fact in cycle_info["winners"]:
        _dbg(f"    winner: {rid} -> {fact}")
    for rid, fact in cycle_info["shadowed"]:
        _dbg(f"    shadowed: {rid} -> {fact}")
    for ef_rid, ef_pair, by_rid in cycle_info["retracted"]:
        _dbg(f"    RETRACTED: {ef_rid} -> {ef_pair} (by {by_rid})")
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

    live = [f for f in result_facts if f.to_tuple() not in eng.retracted]

    def live_val(pred):
        vals = sorted(f.o for f in live if f.p == pred)
        return vals[0] if vals else None

    return {
        "input": src,
        "category": live_val("category"),
        "complexity": live_val("complexity"),
        "smell_magic_number": live_val("smell_magic_number"),
        "smell_long_method": live_val("smell_long_method"),
        "smell_dead_code": live_val("smell_dead_code"),
        "has_any_smell": live_val("has_any_smell"),
        "retractions": len(eng.retracted),
        "retracted_history": list(eng.retracted_history),
        "cycles": cycles,
        "trace_len": len(eng.trace),
        "metrics": {
            "seed": [f.to_tuple() for f in seed],
            "cycle_history": list(eng.cycle_history),
            "rules_attempted": eng.rules_attempted,
            "t_extract_ms": t_extract,
            "t_infer_ms": t_infer,
        },
    }


def _classify_and_debug(label, src):
    r = classify(src)
    m = r["metrics"]

    _dbg(f"--- {label} ---")
    _dbg(f"  input: {src!r}")
    _dbg(f"  seed: {len(m['seed'])} fatos in {m['t_extract_ms']:.3f}ms")
    for fact in m["seed"]:
        _dbg(f"    {fact}")
    for ci in m["cycle_history"]:
        _dbg_cycle(ci)
    _dbg(f"  result: category={r['category']} "
         f"complexity={r['complexity']} has_any_smell={r['has_any_smell']}")
    _dbg(f"    smell_magic_number={r['smell_magic_number']} "
         f"smell_long_method={r['smell_long_method']} "
         f"smell_dead_code={r['smell_dead_code']}")
    _dbg(f"  retractions: {r['retractions']}")
    for rh in r["retracted_history"]:
        _dbg(f"    cycle {rh['cycle']}: {rh['fact']} retratado "
             f"por {rh['by_rule']} ({rh['by_fact']})")
    _dbg(f"  cycles={r['cycles']} trace_len={r['trace_len']}")
    _dbg(f"  timing: extract={m['t_extract_ms']:.3f}ms "
         f"infer={m['t_infer_ms']:.3f}ms")
    _dbg("")
    return r


# ============================================================
# Sub-sondas
# ============================================================
SRC_Q05A = "def f(x): return x + 1"
SRC_Q05B = "def f(x): return x > 42"
SRC_Q05C = ("def f(x):\n"
            "    a = 1\n    b = 2\n    c = 3\n    return a + b + c")
SRC_Q05D = ("def f(x):\n"
            "    return x\n    print(x)")
SRC_Q05E = ("def f(x):\n"
            "    a = 1\n    b = 2\n    if x > 42:\n"
            "        return x\n    return 0\n    print(x)")


def run_q05a():
    return _classify_and_debug("Q05a: clean (return x+1)", SRC_Q05A)


def run_q05b():
    return _classify_and_debug("Q05b: magic (x > 42)", SRC_Q05B)


def run_q05c():
    return _classify_and_debug("Q05c: long body (4 stmts)", SRC_Q05C)


def run_q05d():
    return _classify_and_debug("Q05d: dead (return x; print)", SRC_Q05D)


def run_q05e():
    return _classify_and_debug("Q05e: 3 smells coexistem", SRC_Q05E)


def run_q05f():
    t0 = time.perf_counter()
    outs = set()
    with QUIET:
        for _ in range(100):
            r = run_q05b()
            outs.add((r["has_any_smell"], r["smell_magic_number"],
                      r["retractions"]))
    t_total = (time.perf_counter() - t0) * 1000

    if DEBUG:
        _dbg("--- Q05f: determinism (100 runs of Q05b) ---")
        _dbg(f"  runs: 100")
        _dbg(f"  unique: {len(outs)}")
        _dbg(f"  values: {sorted(outs)}")
        _dbg(f"  time_total: {t_total:.3f}ms")
        _dbg(f"  time_per_run: {t_total/100:.3f}ms")
        _dbg("")
    return {"n": 100, "unique_count": len(outs), "values": outs}


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_q05.py ===")
        _dbg("mode: debug")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    checks = [
        ("Q05a", "clean", run_q05a,
         {"has_any_smell": "none", "retractions": 0,
          "smell_magic_number": None, "smell_long_method": None,
          "smell_dead_code": None}),
        ("Q05b", "magic", run_q05b,
         {"has_any_smell": "dirty", "retractions": 1,
          "smell_magic_number": "yes", "smell_long_method": None}),
        ("Q05c", "long", run_q05c,
         {"has_any_smell": "dirty", "retractions": 1,
          "smell_long_method": "yes", "smell_magic_number": None}),
        ("Q05d", "dead", run_q05d,
         {"has_any_smell": "dirty", "retractions": 1,
          "smell_dead_code": "yes", "smell_magic_number": None}),
        ("Q05e", "3 smells", run_q05e,
         {"has_any_smell": "dirty", "retractions": 1,
          "smell_magic_number": "yes", "smell_long_method": "yes",
          "smell_dead_code": "yes"}),
    ]

    for label, desc, fn, expect in checks:
        r = fn()
        lines.append(f"=== {label} ===")
        lines.append(f"desc:              {desc}")
        lines.append(f"category:          {r['category']}")
        lines.append(f"complexity:        {r['complexity']}")
        lines.append(f"smell_magic_number: {r['smell_magic_number']}")
        lines.append(f"smell_long_method:  {r['smell_long_method']}")
        lines.append(f"smell_dead_code:    {r['smell_dead_code']}")
        lines.append(f"has_any_smell:     {r['has_any_smell']}")
        lines.append(f"retractions:       {r['retractions']}")
        for rh in r["retracted_history"]:
            lines.append(
                f"  retracted cycle {rh['cycle']}: {rh['fact']} "
                f"by {rh['by_rule']}"
            )
        lines.append(f"cycles:            {r['cycles']}")
        lines.append(f"trace_len:         {r['trace_len']}")
        lines.append("")
        for k, v in expect.items():
            if r[k] != v:
                falhas.append(f"{label}: {k}={r[k]!r}, esperado {v!r}")

    lines.append("=== Q05f: determinism (100 runs of Q05b) ===")
    f = run_q05f()
    lines.append(f"n:            {f['n']}")
    lines.append(f"unique_count: {f['unique_count']}")
    lines.append("")
    if f["unique_count"] != 1:
        falhas.append(f"Q05f: {f['unique_count']} variacoes")

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("Q05 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("Q05 PASS")
        LOG.info("Q05 PASS")
        resultado = 0
        if DEBUG:
            _dbg("=== done: all checks passed ===")

    for line in lines:
        print(line)

    output_path = Path(__file__).parent / "output.txt"
    output_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return resultado


if __name__ == "__main__":
    sys.exit(main())
