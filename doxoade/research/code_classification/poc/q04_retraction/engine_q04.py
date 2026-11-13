
# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/q04_retraction/engine_q04.py
"""
Q04 - Cross-cycle retraction (engine upgrade).

Contrato: C1 (Inferencia) estendido com retracao.
    Fatos derivados podem ser retratados por fatos de prioridade maior,
    mesmo em ciclos posteriores.

Diferenca de Q03:
    Q03 nao tinha retracao. R_utility (default via NAF) e R_factory
    coexistiam em `pattern` = contradicao. Q04 adiciona retracao por
    prioridade. Seeds sao protegidos.

Mecanismo:
    Fact ganha priority (herdada da rule que derivou).
    Engine.run() apos merge de winners:
      - Se novo (s,p,o_new) prio P_new > existente (s,p,o_old) prio P_old
        -> retrata o_old, adiciona o_new.
      - Se P_new < P_old -> shadow novo (nao retrata).
      - Se P_new == P_old -> shadow novo (tie-break first-wins).
      - Seeds (source="seed") tem prio efetiva infinito -> nunca retratados.

Q04a - utility (prio 1) retratada por factory (prio 20). Assert retracted=1.
Q04b - utility sozinha. Assert retracted=0, pattern=utility.
Q04c - tie prio (10=10, cross-cycle). Assert retracted=0, pattern=first_fired.
Q04d - higher fires first, lower crosses next. Assert retracted=0, pattern=high.
Q04e - determinism (100 runs de Q04a).

Rodar: doxoade retro-forward run q04
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
    logger = logging.getLogger("poc_q04")
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
# Kernel (Q04: retraction-aware)
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
        self.retracted: set[tuple[str, str, str]] = set()
        self.retracted_history: list[dict] = []
        self.shadowed: list[tuple[str, tuple]] = []
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
            # live = facts not retracted
            live_facts = [f for f in facts if f.to_tuple() not in self.retracted]
            existing = set(f.to_tuple() for f in live_facts)
            candidates = []
            cycle_info = {
                "cycle": cycles,
                "matches": {},
                "idempotent": [],
                "candidates": [],
                "winners": [],
                "shadowed": [],
                "retracted": [],
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
                        cycle_info["idempotent"].append(
                            (rule.id, cf.to_tuple())
                        )
                        continue
                    candidates.append((rule, cf, wit))
                    cycle_info["candidates"].append(
                        (rule.id, rule.priority, cf.to_tuple())
                    )

            # Within-cycle winners (mesmo de P02/Q00-Q03)
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

            # Q04: cross-cycle retraction check + merge
            for (s, p), (rule, cf, wit) in winners.items():
                to_retract: list[Fact] = []
                shadow_new = False
                for ef in live_facts:
                    if ef.s != s or ef.p != p:
                        continue
                    if ef.o == cf.o:
                        # exato mesmo valor, idempotente
                        cycle_info["idempotent"].append(
                            (rule.id, cf.to_tuple())
                        )
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
                        "cycle": cycles,
                        "fact": ef.to_tuple(),
                        "by_rule": rule.id,
                        "by_fact": cf.to_tuple(),
                    })
                    cycle_info["retracted"].append(
                        (ef.rule_id, ef.to_tuple(), rule.id)
                    )

                facts.append(cf)
                self.trace.append({
                    "cycle": cycles,
                    "rule_id": rule.id,
                    "fact": cf.to_tuple(),
                    "derived_from": wit,
                })
                cycle_info["winners"].append(
                    (rule.id, rule.priority, cf.to_tuple())
                )

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


def _count_branches(body: list) -> int:
    count = 0
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, BRANCH_NODE_TYPES):
                count += 1
    return count


def _name_prefix(name: str) -> str:
    if name.startswith("create_"):
        return "create"
    if name.startswith("get_"):
        return "get"
    if name.startswith("is_"):
        return "is"
    return "other"


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

NAMING_RULES = [
    Rule("R_create_prefix",
         conditions=((F, "name_prefix", "create"),),
         conclusion=(F, "has_naming", "create"),
         priority=10),
    Rule("R_get_prefix",
         conditions=((F, "name_prefix", "get"),),
         conclusion=(F, "has_naming", "get"),
         priority=10),
    Rule("R_is_prefix",
         conditions=((F, "name_prefix", "is"),),
         conclusion=(F, "has_naming", "is"),
         priority=10),
]

BEHAVIOR_RULES = [
    Rule("R_returns_call",
         conditions=((F, "return_expr_kind", "Call"),),
         conclusion=(F, "has_behavior", "returns_call"),
         priority=10),
    Rule("R_returns_name",
         conditions=((F, "return_expr_kind", "Name"),),
         conclusion=(F, "has_behavior", "returns_name"),
         priority=10),
    Rule("R_returns_compare",
         conditions=((F, "return_expr_kind", "Compare"),),
         conclusion=(F, "has_behavior", "returns_compare"),
         priority=10),
]

PATTERN_RULES = [
    Rule("R_factory",
         conditions=((F, "has_naming", "create"),
                     (F, "has_behavior", "returns_call")),
         conclusion=(F, "pattern", "factory"),
         priority=20),
    Rule("R_accessor",
         conditions=((F, "has_naming", "get"),
                     (F, "has_behavior", "returns_name")),
         conclusion=(F, "pattern", "accessor"),
         priority=20),
    Rule("R_predicate",
         conditions=((F, "has_naming", "is"),
                     (F, "has_behavior", "returns_compare")),
         conclusion=(F, "pattern", "predicate"),
         priority=20),
]

# Q04-specific rules for retraction tests
RETRACTION_RULES = [
    Rule("R_utility",
         conditions=((F, "kind", "function"),),
         negations=((F, "pattern", WILD),),
         conclusion=(F, "pattern", "utility"),
         priority=1),
    Rule("R_a_low",
         conditions=((F, "trigger_c", "yes"),),
         conclusion=(F, "pattern", "first_fired"),
         priority=10),
    Rule("R_a_high",
         conditions=((F, "trigger_d", "yes"),),
         conclusion=(F, "pattern", "high"),
         priority=20),
    Rule("R_stub",
         conditions=((F, "trigger_b_stub", "yes"),),
         conclusion=(F, "stage_done", "yes"),
         priority=5),
    Rule("R_b_low",
         conditions=((F, "stage_done", "yes"),),
         conclusion=(F, "pattern", "second_fired"),
         priority=10),
    Rule("R_b_verylow",
         conditions=((F, "stage_done", "yes"),),
         conclusion=(F, "pattern", "low"),
         priority=1),
]

RULES = (CATEGORY_RULES + COMPLEXITY_RULES +
         NAMING_RULES + BEHAVIOR_RULES + PATTERN_RULES + RETRACTION_RULES)


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
    for ef_rid, ef_pair, by_rid in cycle_info["retracted"]:
        _dbg(f"    RETRACTED: {ef_rid} -> {ef_pair} (by {by_rid})")
    for rid, fact in cycle_info["idempotent"]:
        _dbg(f"    idempotent: {rid} -> {fact}")
    if not cycle_info["winners"]:
        _dbg("    quiescence")


def classify(src, seed=None, rules=None) -> dict:
    t0 = time.perf_counter()
    facts = seed if seed is not None else extract_facts(src)
    t_extract = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    eng = Engine()
    result_facts, cycles = eng.run(facts, rules if rules is not None else RULES)
    t_infer = (time.perf_counter() - t0) * 1000

    live = [f for f in result_facts if f.to_tuple() not in eng.retracted]
    categories = sorted(f.o for f in live if f.p == "category")
    has_doc_vals = sorted(f.o for f in live if f.p == "has_docstring")
    complexities = sorted(f.o for f in live if f.p == "complexity")
    patterns = sorted(f.o for f in live if f.p == "pattern")

    return {
        "input": src,
        "category": categories[0] if categories else None,
        "has_docstring": has_doc_vals[0] if has_doc_vals else None,
        "complexity": complexities[0] if complexities else None,
        "pattern": patterns[0] if patterns else None,
        "retractions": len(eng.retracted),
        "retracted_history": list(eng.retracted_history),
        "cycles": cycles,
        "trace_len": len(eng.trace),
        "metrics": {
            "seed": [f.to_tuple() for f in facts],
            "rules_attempted": eng.rules_attempted,
            "rule_attempts": dict(eng.rule_attempts),
            "shadowed": list(eng.shadowed),
            "cycle_history": list(eng.cycle_history),
            "t_extract_ms": t_extract,
            "t_infer_ms": t_infer,
        },
    }


def _classify_and_debug(label, src=None, seed=None, rules=None):
    r = classify(src, seed=seed, rules=rules)
    m = r["metrics"]

    _dbg(f"--- {label} ---")
    if src:
        _dbg(f"  input: {src!r}")
    _dbg(f"  seed: {len(m['seed'])} fatos in {m['t_extract_ms']:.3f}ms")
    for fact in m["seed"]:
        _dbg(f"    {fact}")
    for cycle_info in m["cycle_history"]:
        _dbg_cycle(cycle_info)
    dims = [d for d, v in
            [("category", r["category"]),
             ("has_docstring", r["has_docstring"]),
             ("complexity", r["complexity"]),
             ("pattern", r["pattern"])]
            if v is not None]
    _dbg(f"  result: category={r['category']} "
         f"has_docstring={r['has_docstring']} "
         f"complexity={r['complexity']} pattern={r['pattern']}")
    _dbg(f"  dims: {len(dims)} ({', '.join(dims)})")
    _dbg(f"  retractions: {r['retractions']}")
    for rh in r["retracted_history"]:
        _dbg(f"    cycle {rh['cycle']}: {rh['fact']} retratado "
             f"por {rh['by_rule']} ({rh['by_fact']})")
    _dbg(f"  cycles={r['cycles']} trace_len={r['trace_len']}")
    _dbg(f"  timing: extract={m['t_extract_ms']:.3f}ms "
         f"infer={m['t_infer_ms']:.3f}ms "
         f"total={(m['t_extract_ms'] + m['t_infer_ms']):.3f}ms")
    _dbg("")
    return r


# ============================================================
# Sub-sondas
# ============================================================
SRC_Q04A = "def create_user(name): return User(name)"
SRC_Q04B = "def foo(x): return x"

SEED_Q04C = [
    Fact("f", "kind", "function"),
    Fact("f", "trigger_c", "yes"),
    Fact("f", "trigger_b_stub", "yes"),
]

SEED_Q04D = [
    Fact("f", "kind", "function"),
    Fact("f", "trigger_d", "yes"),
    Fact("f", "trigger_b_stub", "yes"),
]


def run_q04a():
    return _classify_and_debug("Q04a: utility (prio 1) retratada por factory (prio 20)",
                               src=SRC_Q04A)


def run_q04b():
    return _classify_and_debug("Q04b: utility sozinha (sem factory)",
                               src=SRC_Q04B)


def run_q04c():
    return _classify_and_debug("Q04c: tie prio 10=10, cross-cycle",
                               seed=SEED_Q04C)


def run_q04d():
    return _classify_and_debug("Q04d: higher fires cycle 1, lower cycle 2",
                               seed=SEED_Q04D)


def run_q04e():
    t0 = time.perf_counter()
    outs = set()
    with QUIET:
        for _ in range(100):
            r = run_q04a()
            outs.add((r["pattern"], r["retractions"]))
    t_total = (time.perf_counter() - t0) * 1000

    if DEBUG:
        _dbg("--- Q04e: determinism (100 runs of Q04a) ---")
        _dbg(f"  runs: 100")
        _dbg(f"  unique: {len(outs)}")
        _dbg(f"  values: {sorted(outs)}")
        _dbg(f"  time_total: {t_total:.3f}ms")
        _dbg(f"  time_per_run: {t_total/100:.3f}ms")
        _dbg("")
    return {"n": 100, "unique_count": len(outs), "values": outs}


def _debug_aggregate(results):
    if not DEBUG:
        return
    n = len(results)
    total_seed = sum(len(r["metrics"]["seed"]) for r in results)
    total_shadowed = sum(len(r["metrics"]["shadowed"]) for r in results)
    total_retracted = sum(r["retractions"] for r in results)
    total_attempts = sum(r["metrics"]["rules_attempted"] for r in results)
    total_cycles = sum(r["cycles"] for r in results)

    _dbg("--- aggregate (4 classify calls) ---")
    _dbg(f"  functions: {n}")
    _dbg(f"  total_seed_facts: {total_seed}")
    _dbg(f"  total_shadowed: {total_shadowed}")
    _dbg(f"  total_retracted: {total_retracted}")
    _dbg(f"  total_rules_attempted: {total_attempts}")
    _dbg(f"  total_cycles: {total_cycles}")
    _dbg(f"  avg_cycles: {total_cycles/n:.2f}")
    _dbg("")


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_q04.py ===")
        _dbg("mode: debug")
        _dbg(f"args: {sys.argv}")
        _dbg("")

    lines: list[str] = []
    falhas: list[str] = []

    checks = [
        ("Q04a", "utility retratada por factory", run_q04a,
         {"pattern": "factory", "retractions": 1}),
        ("Q04b", "utility sozinha", run_q04b,
         {"pattern": "utility", "retractions": 0}),
        ("Q04c", "tie prio cross-cycle", run_q04c,
         {"pattern": "first_fired", "retractions": 0}),
        ("Q04d", "higher fires cycle 1, lower cycle 2", run_q04d,
         {"pattern": "high", "retractions": 0}),
    ]

    results_for_agg = []
    for label, desc, fn, expect in checks:
        r = fn()
        results_for_agg.append(r)
        lines.append(f"=== {label} ===")
        lines.append(f"desc:          {desc}")
        lines.append(f"pattern:       {r['pattern']}")
        lines.append(f"retractions:   {r['retractions']}")
        for rh in r["retracted_history"]:
            lines.append(
                f"  retracted cycle {rh['cycle']}: "
                f"{rh['fact']} by {rh['by_rule']} ({rh['by_fact']})"
            )
        lines.append(f"cycles:        {r['cycles']}")
        lines.append(f"trace_len:     {r['trace_len']}")
        lines.append("")
        for k, v in expect.items():
            if r[k] != v:
                falhas.append(
                    f"{label}: {k}={r[k]!r}, esperado {v!r}"
                )

    lines.append("=== Q04e: determinism (100 runs of Q04a) ===")
    e = run_q04e()
    lines.append(f"n:            {e['n']}")
    lines.append(f"unique_count: {e['unique_count']}")
    lines.append("")
    if e["unique_count"] != 1:
        falhas.append(f"Q04e: {e['unique_count']} variacoes")

    _debug_aggregate(results_for_agg)

    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("Q04 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("Q04 PASS")
        LOG.info("Q04 PASS")
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
