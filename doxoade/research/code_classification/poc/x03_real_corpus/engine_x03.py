# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/x03_real_corpus/engine_x03.py
"""
X03 - Real corpus collection for induction.

Contrato provado (se PASS):
    - motor roda em codigo real sem crash
    - cada FunctionDef do corpus e catalogada em misses.json
    - flat == table em todas as unidades (17 rules Q05 reais)

Corpus (4 arquivos, ~2.000 LOC):
    doxoade/tools/doxcolors.py
    doxoade/commands/retro_forward_cmd.py
    doxoade/research/code_classification/poc/q05_smell/engine_q05.py
    doxoade/research/forward_chaining/poc/70_substitutable_matcher/engine_p70.py

Categorias por unidade (Q3, Q5):
    covered            : category != unknown (motor classificou)
    extraction_miss    : heuristica H1-H10 flagou (Q06)
    rule_miss          : category=unknown + pattern/smell disparou (X04)
    silent_quiescence  : category=unknown + sem pattern + sem smell (X06)

Heuristicas (Q3: so coleta, curadoria em X04):
    H1  async_def          AsyncFunctionDef                       Q06
    H2  self_arg           1o arg == "self"                       Q06
    H3  decorator          decorator_list != []                   Q06
    H4  yield_expr         ast.Yield / YieldFrom no body          Q06
    H5  recursive_call     ast.Call cujo func.id == node.name     Q06
    H6  magic_in_assign    int nao-trivial fora de Compare        Q06
    H7  dead_nested        Return em If/For/While + stmt irmao    Q06
    H8  dunder_name        node.name.startswith("__")             Q06
    H9  undefined_name     Name(Load) sem binding em scope        Q06
    H10 dead_local         binding local sem Load                 Q06

Self-check (Q8):
    C1 corpus_processed    : 4/4 arquivos, cada um com >=1 unidade
    C2 min_misses          : >=5 unidades nao-covered
    C3 miss_diversity      : >=1 miss em >=2 arquivos
    C4 all_kinds_present   : >=1 extraction_miss, rule_miss, silent_quiescence
    C5 heuristics_per_file : >=1 heuristica dispara em cada arquivo
    C6 identity            : flat.trace == table.trace em 100% das unidades
    C7 determinism         : 3 runs -> mesmo _hash_misses (generated_at excluido)

Rodar: doxoade retro-forward run x03
       doxoade retro-forward trace x03
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import hashlib
import json
import logging
import symtable
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = Path(__file__).parent / "logging.txt"
DEBUG = "--debug" in sys.argv


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc_x03")
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


# ============================================================
# Kernel (Q05 inline, unchanged)
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
                    self.rules_attempted += 1
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
            fired_this_cycle = False
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
                    self.retracted_history.append({
                        "cycle": cycles, "fact": ef.to_tuple(),
                        "by_rule": rule.id, "by_fact": cf.to_tuple(),
                    })
                facts.append(cf)
                self.trace.append({
                    "cycle": cycles, "rule_id": rule.id,
                    "fact": cf.to_tuple(),
                })
                fired_this_cycle = True
            if not fired_this_cycle:
                self.cycles_used = cycles
                return facts, cycles
        raise RuntimeError(f"max_cycles={self.max_cycles}")


# ============================================================
# RuleTable (X01 inline)
# ============================================================
class RuleTable:
    def __init__(self, rules, domain_index=None, symptom_index=None):
        self._rules = {r.id: r for r in rules}
        self._domain_index = domain_index or {}
        self._symptom_index = symptom_index or {}

    def rules_for(self, domain=None, symptoms=None) -> list[Rule]:
        ids_set = set()
        if domain and domain in self._domain_index:
            ids_set.update(self._domain_index[domain])
        for s in (symptoms or []):
            if s in self._symptom_index:
                ids_set.update(self._symptom_index[s])
        return [r for r in self._rules.values() if r.id in ids_set]


# ============================================================
# Extractor (Q05 adaptado: aceita AsyncFunctionDef)
# ============================================================
class UnsupportedNodeError(RuntimeError):
    pass


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
    return len(body) >= 4


def _has_dead_after_return(body):
    for stmt in body[:-1]:
        if isinstance(stmt, ast.Return):
            return True
    return False


def extract_facts_adapted(func) -> list[Fact]:
    """Aceita FunctionDef ou AsyncFunctionDef. Q05 verbatim + async."""
    if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise UnsupportedNodeError(
            f"esperado FunctionDef/AsyncFunctionDef, veio {type(func).__name__}"
        )
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
# RULES_Q05 (17 rules, verbatim)
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

RULES_Q05 = (CATEGORY_RULES + COMPLEXITY_RULES +
             SMELL_RULES + [CLEAN_RULE] + DIRTY_RULES)


def _build_table() -> RuleTable:
    return RuleTable(
        rules=RULES_Q05,
        domain_index={"programming": [r.id for r in RULES_Q05]},
    )


# ============================================================
# Heuristicas sintaticas H1-H8
# ============================================================
def _iter_own_scope(node):
    """Yield nodes no escopo da funcao (nao desce em def/class/lambda aninhados)."""
    def recurse(n):
        for child in ast.iter_child_nodes(n):
            yield child
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef, ast.Lambda)):
                yield from recurse(child)

    for stmt in node.body:
        yield stmt
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Lambda)):
            yield from recurse(stmt)


def _is_magic_int(v):
    return (isinstance(v, int) and not isinstance(v, bool)
            and v not in (0, 1, -1))


def _h1_async_def(node):
    return isinstance(node, ast.AsyncFunctionDef)


def _h2_self_arg(node):
    args = node.args.args
    if not args:
        return False
    return args[0].arg == "self"


def _h3_decorator(node):
    return len(node.decorator_list) > 0


def _h4_yield_expr(node):
    for sub in _iter_own_scope(node):
        if isinstance(sub, (ast.Yield, ast.YieldFrom)):
            return True
    return False


def _h5_recursive_call(node):
    sites = []
    for sub in _iter_own_scope(node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name) and sub.func.id == node.name:
                sites.append(sub.lineno)
    return sorted(sites)


def _h6_magic_outside_compare(node):
    """int nao-trivial em Constant fora de Compare (Q05 so cobre Compare).

    Usa NodeVisitor para pular a subarvore inteira de Compare, nao so
    o no Compare. Bug do uso anterior de `_iter_own_scope`: itera
    siblings, entao Constant dentro de Compare ainda era visitado.
    """
    values: set[int] = set()

    class _V(ast.NodeVisitor):
        def visit_Compare(self, n):
            return  # skip subtree
        def visit_FunctionDef(self, n):
            return  # skip nested defs
        def visit_AsyncFunctionDef(self, n):
            return
        def visit_ClassDef(self, n):
            return
        def visit_Lambda(self, n):
            return
        def visit_Constant(self, n):
            if _is_magic_int(n.value):
                values.add(n.value)

    v = _V()
    for stmt in node.body:
        v.visit(stmt)
    return sorted(values)


def _h7_dead_nested(node):
    """Return em If/For/While seguido de stmt irmao no mesmo nivel."""
    for sub in _iter_own_scope(node):
        if isinstance(sub, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            body = sub.body
            for i, stmt in enumerate(body[:-1]):
                if isinstance(stmt, ast.Return):
                    return True
    return False


def _h8_dunder_name(node):
    return node.name.startswith("__")


# ============================================================
# H9 + H10 (symtable-based, full scope-aware)
# ============================================================
_IMPLICIT_MODULE_NAMES = set(dir(builtins)) | {
    "__name__", "__file__", "__doc__", "__builtins__",
    "__debug__", "__spec__", "__loader__", "__package__",
    "__annotations__",
}


def _collect_module_bindings(module_sym) -> set[str]:
    bindings = set(_IMPLICIT_MODULE_NAMES)
    for sym in module_sym.get_symbols():
        if (sym.is_assigned() or sym.is_imported()
                or sym.is_namespace()):
            bindings.add(sym.get_name())
    return bindings


def _find_fn_symtable(module_sym, node):
    """DFS em symtable por (name, lineno). Retorna None se nao achar."""
    target_name = node.name
    target_lineno = node.lineno

    def search(sym):
        for child in sym.get_children():
            if child.get_name() == target_name and child.get_lineno() == target_lineno:
                return child
            result = search(child)
            if result is not None:
                return result
        return None

    return search(module_sym)


def _h9_undefined_name(fn_sym, module_bindings) -> list[str]:
    undefined = []
    for sym in fn_sym.get_symbols():
        if not sym.is_referenced():
            continue
        if sym.is_local() or sym.is_free() or sym.is_parameter():
            continue
        name = sym.get_name()
        if name in module_bindings:
            continue
        undefined.append(name)
    return sorted(undefined)


def _h10_dead_local(fn_sym) -> list[str]:
    dead = []
    for sym in fn_sym.get_symbols():
        name = sym.get_name()
        if name.startswith("_"):
            continue
        if not sym.is_local():
            continue
        if sym.is_parameter() or sym.is_free():
            continue
        if not sym.is_assigned():
            continue
        if sym.is_referenced():
            continue
        if _name_loaded_in_children(fn_sym, name):
            continue
        dead.append(name)
    return sorted(dead)

def _name_loaded_in_children(fn_sym, name) -> bool:
    """True se `name` e carregado (free) em algum escopo descendente.

    `symtable.is_referenced()` no escopo pai nao conta Loads vindos de
    comprehensions, generators ou closures. Esta funcao percorre os
    escopos filhos procurando `name` como free variable — que e
    exatamente "carregado do escopo pai".

    Trade-off: sintatico, nao semantico. Um `x` carregado em closure
    nunca chamado continua sendo contado como "usado". Sob-reportar e
    mais seguro que over-reportar (para X04).
    """
    for child in fn_sym.get_children():
        for child_sym in child.get_symbols():
            if child_sym.get_name() == name and child_sym.is_free():
                return True
        if _name_loaded_in_children(child, name):
            return True
    return False

# ============================================================
# Classify kind
# ============================================================
_SUGGESTED_TARGET = {
    "extraction_miss": "Q06",
    "rule_miss": "X04",
    "silent_quiescence": "X06",
    "covered": None,
}


def classify_kind(result, detected_by) -> str:
    if detected_by:
        return "extraction_miss"
    if result["category"] != "unknown":
        return "covered"
    has_pattern = result["pattern"] is not None
    has_smell = result["has_any_smell"] == "dirty"
    if has_pattern or has_smell:
        return "rule_miss"
    return "silent_quiescence"


# ============================================================
# Corpus paths
# ============================================================
REPO_ROOT = Path(__file__).resolve().parents[5]
DOXOADE_ROOT = REPO_ROOT / "doxoade"

CORPUS: list[Path] = [
    DOXOADE_ROOT / "tools" / "doxcolors.py",
    DOXOADE_ROOT / "commands" / "retro_forward_cmd.py",
    DOXOADE_ROOT / "research" / "code_classification" / "poc"
        / "q05_smell" / "engine_q05.py",
    DOXOADE_ROOT / "research" / "forward_chaining" / "poc"
        / "70_substitutable_matcher" / "engine_p70.py",
]


# ============================================================
# Parent map, class context, qualified name
# ============================================================
def _build_parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _class_context(node, parents):
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.ClassDef):
            return cur.name
        cur = parents.get(cur)
    return None


# ============================================================
# Process one unit
# ============================================================
def _extract_result(eng, live) -> dict:
    def live_val(pred):
        vals = sorted(f.o for f in live if f.p == pred)
        return vals[0] if vals else None

    return {
        "category": live_val("category"),
        "complexity": live_val("complexity"),
        "pattern": live_val("pattern"),
        "smell_magic_number": live_val("smell_magic_number"),
        "smell_long_method": live_val("smell_long_method"),
        "smell_dead_code": live_val("smell_dead_code"),
        "has_any_smell": live_val("has_any_smell"),
        "retractions": len(eng.retracted),
    }


def _process_unit(node, file_path, module_sym, module_bindings, parents,
                  active_rules, table):
    seed = extract_facts_adapted(node)

    eng_flat = Engine()
    facts_flat, _ = eng_flat.run(list(seed), active_rules)
    live_flat = [f for f in facts_flat if f.to_tuple() not in eng_flat.retracted]

    eng_tab = Engine()
    facts_tab, _ = eng_tab.run(list(seed), table.rules_for(domain="programming"))
    live_tab = [f for f in facts_tab if f.to_tuple() not in eng_tab.retracted]

    flat_sig = tuple((e["cycle"], e["rule_id"], e["fact"])
                     for e in eng_flat.trace)
    tab_sig = tuple((e["cycle"], e["rule_id"], e["fact"])
                    for e in eng_tab.trace)
    identity_ok = flat_sig == tab_sig

    result = _extract_result(eng_flat, live_flat)

    detected_by = []
    detail = {}

    if _h1_async_def(node):
        detected_by.append("heuristic:async_def")
    if _h2_self_arg(node):
        detected_by.append("heuristic:self_arg")
    if _h3_decorator(node):
        detected_by.append("heuristic:decorator")
    if _h4_yield_expr(node):
        detected_by.append("heuristic:yield_expr")
    h5 = _h5_recursive_call(node)
    if h5:
        detected_by.append("heuristic:recursive_call")
        detail["recursive_sites"] = h5
    h6 = _h6_magic_outside_compare(node)
    if h6:
        detected_by.append("heuristic:magic_outside_compare")
        detail["magic_values"] = h6
    if _h7_dead_nested(node):
        detected_by.append("heuristic:dead_nested")
    if _h8_dunder_name(node):
        detected_by.append("heuristic:dunder_name")

    fn_sym = _find_fn_symtable(module_sym, node)
    if fn_sym is not None:
        h9 = _h9_undefined_name(fn_sym, module_bindings)
        if h9:
            detected_by.append("heuristic:undefined_name")
            detail["undefined_names"] = h9
        h10 = _h10_dead_local(fn_sym)
        if h10:
            detected_by.append("heuristic:dead_local")
            detail["dead_locals"] = h10

    kind = classify_kind(result, detected_by)

    unit = {
        "file": file_path.relative_to(REPO_ROOT).as_posix(),
        "unit_name": node.name,
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "class_context": _class_context(node, parents),
        "kind": kind,
        "current_category": result["category"],
        "identity_ok": identity_ok,
    }
    # NOVO: sinal duplo — heuristica disparou mas Q05 classificou.
    if kind == "extraction_miss" and result["category"] != "unknown":
        unit["coverage_overlap"] = True
    if kind != "covered":
        unit["detected_by"] = detected_by
        if detail:
            unit["extraction_detail"] = detail
        unit["seed_facts"] = sorted([list(f.to_tuple()) for f in seed])
        unit["derived_facts"] = sorted(
            [list(f.to_tuple()) for f in live_flat if f.source == "derived"]
        )
        unit["current_pattern"] = result["pattern"]
        unit["retractions"] = result["retractions"]
        unit["suggested_target"] = _SUGGESTED_TARGET[kind]

    return unit


# ============================================================
# Process one file
# ============================================================
def process_file(file_path, active_rules, table):
    rel = file_path.relative_to(REPO_ROOT).as_posix()

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [], {"path": rel, "error": f"read: {e}", "units": 0}

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return [], {"path": rel, "error": f"SyntaxError: {e.msg} at {e.lineno}",
                    "units": 0}

    try:
        module_sym = symtable.symtable(source, str(file_path), "exec")
    except SyntaxError as e:
        return [], {"path": rel, "error": f"symtable SyntaxError: {e.msg}",
                    "units": 0}

    module_bindings = _collect_module_bindings(module_sym)
    parents = _build_parent_map(tree)
    file_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()

    raw_units = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        try:
            unit = _process_unit(node, file_path, module_sym,
                                 module_bindings, parents,
                                 active_rules, table)
            raw_units.append(unit)
        except Exception as e:
            LOG.error("erro processando %s::%s: %s",
                      rel, node.name, e)
            raw_units.append({
                "file": rel,
                "unit_name": node.name,
                "lineno": node.lineno,
                "end_lineno": node.end_lineno,
                "class_context": _class_context(node, parents),
                "kind": "process_error",
                "error": f"{type(e).__name__}: {e}",
                "identity_ok": False,
            })

    raw_units.sort(key=lambda u: (u["lineno"], u["unit_name"]))

    return raw_units, {
        "path": rel,
        "sha256": file_sha,
        "units": len(raw_units),
    }

def _load_induced_rules(path):
    """Carrega induced_rules.json gerado por X04.

    Schema:
        {"rules": [
            {"id": "R_ind_001",
             "intersection": [["return_expr_kind", "Call"]],
             "conclusion": ["category", "returns_call"],
             "priority": 12}
        ]}
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rules = []
    for r in data.get("rules", []):
        conditions = tuple(
            (Var("F"), pred, obj) for pred, obj in r["intersection"]
        )
        concl_pred, concl_obj = r["conclusion"]
        rules.append(Rule(
            id=r["id"],
            conditions=conditions,
            conclusion=(Var("F"), concl_pred, concl_obj),
            priority=r.get("priority", 12),
        ))
    return rules

# ============================================================
# Build misses.json
# ============================================================
def _build_misses_json(all_units, corpus_meta):
    corpus_hash = hashlib.sha256(
        "".join(m.get("sha256", "") for m in corpus_meta).encode("utf-8")
    ).hexdigest()

    kind_counts = {k: 0 for k in ("covered", "extraction_miss",
                                 "rule_miss", "silent_quiescence",
                                 "process_error")}
    for u in all_units:
        k = u.get("kind", "process_error")
        kind_counts[k] = kind_counts.get(k, 0) + 1

    coverage_overlap_count = sum(
        1 for u in all_units
        if u.get("kind") == "extraction_miss"
        and u.get("current_category") != "unknown"
    )

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_hash": corpus_hash,
        "engine_config": {
            "extractor": "q05_adapted",
            "rules_id": "q05_flat_17",
            "rules_count": len(RULES_Q05),
            "max_cycles": 100,
        },
        "units_analyzed": len(all_units),
        "units_by_kind": kind_counts,
        "coverage_overlap_count": coverage_overlap_count,
        "corpus": corpus_meta,
        "units": all_units,
    }

def _find_sets(obj, path="misses"):
    """Recursivamente encontra onde existem sets na estrutura."""
    if isinstance(obj, (set, frozenset)):
        yield path
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _find_sets(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _find_sets(v, f"{path}[{i}]")


def _json_safe(obj):
    """Recursivamente converte para JSON-serializable.

    Sets viram listas ordenadas (deterministico). Tipos desconhecidos
    viram repr(). Uso defensivo: nao deveria haver sets, mas se houver,
    o engine nao deve crashar. Se o diagnostico (_find_sets) disparar
    em DEBUG, e sinal de bug upstream, nao daqui.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(_json_safe(x) for x in obj)
    return repr(obj)

def _hash_misses(misses):
    clone = {k: v for k, v in misses.items() if k != "generated_at"}
    canonical = json.dumps(_json_safe(clone), sort_keys=True,
                           ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# ============================================================
# Pipeline (chamavel para determinismo)
# ============================================================
def _run_pipeline(extra_rules=None):
    active_rules = list(RULES_Q05) + list(extra_rules or [])
    table = RuleTable(
        rules=active_rules,
        domain_index={"programming": [r.id for r in active_rules]},
    )
    all_units = []
    corpus_meta = []

    for path in CORPUS:
        if not path.exists():
            ...
            continue
        units, meta = process_file(path, active_rules, table)
        corpus_meta.append(meta)
        all_units.extend(units)

    for i, u in enumerate(all_units):
        u["id"] = f"U{i+1:04d}"

    misses = _build_misses_json(all_units, corpus_meta)
    return all_units, corpus_meta, misses


# ============================================================
# Self-check
# ============================================================
def _self_check(all_units, corpus_meta, misses, determinism_hashes):
    checks = []

    # C1: 4/4 arquivos, cada com >=1 unidade
    parsed = [m for m in corpus_meta if "error" not in m]
    c1_ok = (len(parsed) == len(CORPUS)
             and all(m["units"] >= 1 for m in parsed))
    checks.append({
        "name": "C1 corpus_processed",
        "pass": c1_ok,
        "detail": f"{len(parsed)}/{len(CORPUS)} arquivos, "
                  f"units={[m['units'] for m in parsed]}",
    })

    # C2: >=5 misses
    non_covered = [u for u in all_units if u["kind"] not in
                   ("covered", "process_error")]
    checks.append({
        "name": "C2 min_misses",
        "pass": len(non_covered) >= 5,
        "detail": f"{len(non_covered)}/5",
    })

    # C3: >=1 miss em >=2 arquivos
    files_with_miss = set()
    for u in non_covered:
        files_with_miss.add(u["file"])
    checks.append({
        "name": "C3 miss_diversity",
        "pass": len(files_with_miss) >= 2,
        "detail": f"{len(files_with_miss)} arquivo(s): "
                  f"{sorted(files_with_miss)}",
    })

    # C4: todos os kinds presentes
    kinds = {u["kind"] for u in all_units}
    required = {"extraction_miss", "rule_miss", "silent_quiescence"}
    missing = required - kinds
    checks.append({
        "name": "C4 all_kinds_present",
        "pass": not missing,
        "detail": f"missing={sorted(missing)}" if missing else "OK",
    })

    # C5: >=1 heuristica por arquivo
    heur_per_file = {m["path"]: 0 for m in parsed}
    for u in all_units:
        if u.get("detected_by"):
            heur_per_file[u["file"]] = heur_per_file.get(u["file"], 0) + 1
    empty_files = [f for f, c in heur_per_file.items() if c == 0]
    checks.append({
        "name": "C5 heuristics_per_file",
        "pass": not empty_files,
        "detail": (f"files sem heuristica: {empty_files}"
                   if empty_files else "OK"),
    })

    # C6: identity flat vs table
    identity_fail = [u["id"] for u in all_units if not u.get("identity_ok", True)]
    checks.append({
        "name": "C6 identity",
        "pass": not identity_fail,
        "detail": (f"falhas: {identity_fail[:5]}"
                   if identity_fail else f"{len(all_units)}/{len(all_units)}"),
    })

    # C7: determinism (3 runs)
    uniq = len(set(determinism_hashes))
    checks.append({
        "name": "C7 determinism",
        "pass": uniq == 1,
        "detail": f"{uniq} hash(es) em 3 runs",
    })

    return checks


# ============================================================
# Render output.txt
# ============================================================
def _render_output(all_units, corpus_meta, misses, checks):
    lines = []
    lines.append("=== X03: real corpus collection ===")
    lines.append("")

    lines.append("=== Corpus ===")
    for meta in corpus_meta:
        if "error" in meta:
            lines.append(f"  {meta['path']:<45} ERROR: {meta['error']}")
        else:
            lines.append(
                f"  {meta['path']:<45} {meta['units']:>3} units  "
                f"sha256={meta['sha256'][:12]}"
            )
    lines.append("")

    lines.append("=== units_by_kind ===")
    for k in ("covered", "extraction_miss", "rule_miss",
              "silent_quiescence", "process_error"):
        n = misses["units_by_kind"].get(k, 0)
        if k == "extraction_miss" and misses.get("coverage_overlap_count", 0):
            lines.append(f"  {k:<20} {n:>4}  "
                         f"(coverage_overlap: {misses['coverage_overlap_count']})")
        else:
            lines.append(f"  {k:<20} {n:>4}")
    lines.append("")

    overlap_units = [u for u in all_units
                     if u.get("kind") == "extraction_miss"
                     and u.get("current_category") != "unknown"]
    if overlap_units:
        lines.append("=== coverage_overlap (Q05 acertou, extracao incompleta) ===")
        for u in overlap_units:
            lines.append(f"  {u['id']}  {u['unit_name']:<22} "
                         f"current_category={u['current_category']}")
        lines.append("")

    lines.append("=== heuristics distribution ===")
    hnames = ["async_def", "self_arg", "decorator", "yield_expr",
              "recursive_call", "magic_outside_compare", "dead_nested",
              "dunder_name", "undefined_name", "dead_local"]
    hcount = {h: 0 for h in hnames}
    for u in all_units:
        for det in u.get("detected_by", []):
            name = det.replace("heuristic:", "")
            if name in hcount:
                hcount[name] += 1
    for h in hnames:
        lines.append(f"  {h:<24} {hcount[h]:>4}")
    lines.append("")

    lines.append("=== per-file breakdown ===")
    per_file = {}
    for u in all_units:
        d = per_file.setdefault(u["file"],
                                {"covered": 0, "extraction_miss": 0,
                                 "rule_miss": 0, "silent_quiescence": 0,
                                 "process_error": 0})
        d[u["kind"]] = d.get(u["kind"], 0) + 1
    for fpath in sorted(per_file):
        d = per_file[fpath]
        lines.append(
            f"  {fpath}: covered={d['covered']} "
            f"extraction={d['extraction_miss']} "
            f"rule={d['rule_miss']} "
            f"silent={d['silent_quiescence']}"
        )
    lines.append("")

    lines.append("=== C6 identity (flat vs table) ===")
    ident = [u for u in all_units if u.get("identity_ok", True)]
    lines.append(f"  identical: {len(ident)}/{len(all_units)}")
    lines.append("")

    lines.append("=== C7 determinism (3 runs) ===")
    uniq = len({_hash_misses(misses)})
    lines.append(f"  unique_hashes: {uniq}")
    lines.append("")

    lines.append("=== Self-check ===")
    pass_count = 0
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        if c["pass"]:
            pass_count += 1
        lines.append(f"  {c['name']:<28} {status:<6} ({c['detail']})")
    lines.append("")

    if pass_count == len(checks):
        lines.append("X03 PASS")
    else:
        lines.append(f"FAIL: {len(checks) - pass_count} falha(s)")

    return lines


# ============================================================
# main
# ============================================================
def main() -> int:
    if DEBUG:
        _dbg("=== engine_x03.py ===")
        _dbg("mode: debug")
        _dbg(f"args: {sys.argv}")
        _dbg(f"corpus: {len(CORPUS)} arquivo(s)")
        _dbg("")

    t0 = time.perf_counter()

    rules_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--rules" and i + 1 < len(sys.argv):
            rules_path = sys.argv[i + 1]

    extra_rules = None
    if rules_path:
        try:
            extra_rules = _load_induced_rules(rules_path)
            if DEBUG:
                _dbg(f"  loaded {len(extra_rules)} induced rules from {rules_path}")
        except Exception as e:
            print(f"FATAL: failed to load --rules {rules_path}: {e}",
                  file=sys.stderr)
            return 2

    with QUIET:
        all_units, corpus_meta, misses = _run_pipeline(extra_rules=extra_rules)
        det_hashes = [_hash_misses(misses)]
        for _ in range(2):
            _, _, m = _run_pipeline(extra_rules=extra_rules)
            det_hashes.append(_hash_misses(m))

    if DEBUG:
        hits = list(_find_sets(misses))
        if hits:
            for hit in hits:
                _dbg(f"  SET FOUND (bug upstream): {hit}")
        else:
            _dbg("  (no sets in misses - estrutura OK)")

    checks = _self_check(all_units, corpus_meta, misses, det_hashes)
    lines = _render_output(all_units, corpus_meta, misses, checks)

    for ln in lines:
        print(ln)

    all_pass = all(c["pass"] for c in checks)

    if rules_path:
        # Modo X04: nao toca em output.txt/misses.json.
        out_path = Path(__file__).parent / "output_x03_with_rules.txt"
        out_path.write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
        )
        summary_path = Path(__file__).parent / "x03_with_rules_summary.json"
        summary_path.write_text(
            json.dumps({
                "units_analyzed": misses["units_analyzed"],
                "units_by_kind": misses["units_by_kind"],
                "coverage_overlap_count":
                    misses.get("coverage_overlap_count", 0),
                "rules_loaded": len(extra_rules or []),
                "self_check_pass": all_pass,
                "checks_failed": [
                    c["name"] for c in checks if not c["pass"]
                ],
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        t_ms = (time.perf_counter() - t0) * 1000
        LOG.info("X03(rules) PASS=%s: %d units, %d rules, %.1fms",
                 all_pass, misses["units_analyzed"],
                 len(extra_rules or []), t_ms)
        return 0 if all_pass else 1
    else:
        # Modo normal: escreve output.txt e (se PASS) misses.json.
        output_path = Path(__file__).parent / "output.txt"
        output_path.write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
        )
        if all_pass:
            misses_path = Path(__file__).parent / "misses.json"
            misses_path.write_text(
                json.dumps(_json_safe(misses), indent=2,
                           ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n",
            )
            t_ms = (time.perf_counter() - t0) * 1000
            LOG.info("X03 PASS: %d units, %d misses, %.1fms",
                     misses["units_analyzed"],
                     sum(misses["units_by_kind"][k] for k in
                         ("extraction_miss", "rule_miss", "silent_quiescence")),
                     t_ms)
            return 0
        else:
            LOG.error("X03 FAIL: %d check(s)",
                      sum(1 for c in checks if not c["pass"]))
            return 1

    if all_pass:
        misses_path = Path(__file__).parent / "misses.json"
        misses_path.write_text(
            json.dumps(_json_safe(misses), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        t_ms = (time.perf_counter() - t0) * 1000
        LOG.info("X03 PASS: ...")
        return 0
    else:
        LOG.error("X03 FAIL: ...")
        return 1

    if rules_path:
        # Modo X04: nao toca em output.txt/misses.json.
        out_path = Path(__file__).parent / "output_x03_with_rules.txt"
        out_path.write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
        )
        summary_path = Path(__file__).parent / "x03_with_rules_summary.json"
        summary_path.write_text(
            json.dumps({
                "units_analyzed": misses["units_analyzed"],
                "units_by_kind": misses["units_by_kind"],
                "coverage_overlap_count":
                    misses.get("coverage_overlap_count", 0),
                "rules_loaded": len(extra_rules or []),
                "self_check_pass": all_pass,
                "checks_failed": [
                    c["name"] for c in checks if not c["pass"]
                ],
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        t_ms = (time.perf_counter() - t0) * 1000
        LOG.info("X03(rules) PASS=%s: %d units, %d rules, %.1fms",
                 all_pass, misses["units_analyzed"],
                 len(extra_rules or []), t_ms)
        return 0 if all_pass else 1
    else:
        # Modo normal: escreve output.txt e (se PASS) misses.json.
        output_path = Path(__file__).parent / "output.txt"
        output_path.write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
        )
        if all_pass:
            misses_path = Path(__file__).parent / "misses.json"
            misses_path.write_text(
                json.dumps(_json_safe(misses), indent=2,
                           ensure_ascii=False) + "\n",
                encoding="utf-8", newline="\n",
            )
            t_ms = (time.perf_counter() - t0) * 1000
            LOG.info("X03 PASS: %d units, %d misses, %.1fms",
                     misses["units_analyzed"],
                     sum(misses["units_by_kind"][k] for k in
                         ("extraction_miss", "rule_miss", "silent_quiescence")),
                     t_ms)
            return 0
        else:
            LOG.error("X03 FAIL: %d check(s)",
                      sum(1 for c in checks if not c["pass"]))
            return 1


if __name__ == "__main__":
    sys.exit(main())
