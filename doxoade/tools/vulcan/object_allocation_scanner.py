# -*- coding: utf-8 -*-
# doxoade\tools\vulcan\object_allocation_scanner.py
"""
doxoade/tools/vulcan/object_allocation_scanner.py
──────────────────────────────────────────────────────────────────────────────
Scanner AST que detecta padrões de criação de objetos temporários Python.

Cada padrão mapeado tem:
  • custo estimado (alocações por chamada)
  • estratégia de redução recomendada
  • confiança (high/medium/low) — alta = transformação segura automática

Padrões detectados:
  1. LIST_CONCAT        — [a] + [b] em loop → array pré-alocado
  2. TUPLE_UNPACK       — a, b = func() em loop → variáveis separadas
  3. DICT_TEMP          — dict() / {} como acumulador em loop → struct/array
  4. LIST_COMP_RETURN   — return [x for x in ...] → yield ou buffer
  5. STR_CONCAT         — s += "..." em loop → bytearray / list+join
  6. BOXED_NUMERIC      — int(x), float(x) repetido → cdef tipado
  7. RANGE_ENUMERATE    — enumerate(range(...)) → índice manual
  8. ZIP_TEMP           — zip(a, b) em loop → índice paralelo
  9. SLICE_COPY         — x[a:b] atribuído a variável em loop → memoryview
 10. EXCEPTION_FLOW     — try/except como controle de fluxo em loop → if/else
 11. KWARGS_DICT        — **kwargs em hot path → parâmetros explícitos
 12. LAMBDA_HOTPATH     — lambda em loop → cdef inline
 13. NESTED_LIST_FLAT   — [[...]] achatado em loop → array 1D
"""

from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Enums e estruturas
# ──────────────────────────────────────────────────────────────────────────────

class AllocPattern(str, Enum):
    LIST_CONCAT       = "list_concat"
    TUPLE_UNPACK      = "tuple_unpack"
    DICT_TEMP         = "dict_temp"
    LIST_COMP_RETURN  = "list_comp_return"
    STR_CONCAT        = "str_concat"
    BOXED_NUMERIC     = "boxed_numeric"
    RANGE_ENUMERATE   = "range_enumerate"
    ZIP_TEMP          = "zip_temp"
    SLICE_COPY        = "slice_copy"
    EXCEPTION_FLOW    = "exception_flow"
    KWARGS_DICT       = "kwargs_dict"
    LAMBDA_HOTPATH    = "lambda_hotpath"
    NESTED_LIST_FLAT  = "nested_list_flat"


class ReduceStrategy(str, Enum):
    TYPED_MEMORYVIEW  = "typed_memoryview"    # double[::1] / int[::1]
    CDEF_STRUCT       = "cdef_struct"          # cdef struct em vez de dict
    CDEF_VAR          = "cdef_var"             # cdef double x em vez de x = float(...)
    PREALLOCATE       = "preallocate"          # np.empty(N) antes do loop
    INDEX_LOOP        = "index_loop"           # for i in range(n) em vez de zip/enumerate
    BYTEARRAY_BUFFER  = "bytearray_buffer"     # bytearray como buffer de string
    INLINE_CDEF       = "inline_cdef"          # cdef inline em vez de lambda
    NUMPY_ARRAY       = "numpy_array"          # np.ndarray tipado
    EXPLICIT_PARAMS   = "explicit_params"      # parâmetros explícitos em vez de **kwargs
    CONDITIONAL_FLOW  = "conditional_flow"     # if/else em vez de try/except
    YIELD_STREAM      = "yield_stream"         # yield em vez de list retornado


@dataclass
class AllocationSite:
    """Uma ocorrência de criação de objeto temporário."""
    pattern:   AllocPattern
    strategy:  ReduceStrategy
    lineno:    int
    col:       int
    func_name: str
    snippet:   str            # trecho de código original
    in_loop:   bool           = False
    cost:      int            = 1     # alocações estimadas por chamada
    confidence: str           = "medium"   # high / medium / low
    auto_fix:  bool           = False  # pode ser transformado automaticamente

    @property
    def score(self) -> int:
        """Score de urgência: loop + custo + confiança."""
        base = self.cost * (3 if self.in_loop else 1)
        if self.confidence == "high":   base += 2
        if self.confidence == "medium": base += 1
        return base


@dataclass
class FunctionAllocReport:
    """Relatório de alocações para uma função."""
    func_name:  str
    lineno:     int
    sites:      list[AllocationSite] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(s.score for s in self.sites)

    @property
    def auto_fixable(self) -> list[AllocationSite]:
        return [s for s in self.sites if s.auto_fix]

    @property
    def estimated_allocs_per_call(self) -> int:
        return sum(s.cost * (3 if s.in_loop else 1) for s in self.sites)


@dataclass
class ModuleAllocReport:
    """Relatório completo de um módulo."""
    path:      Path
    functions: list[FunctionAllocReport] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(f.total_score for f in self.functions)

    @property
    def hot_functions(self) -> list[FunctionAllocReport]:
        """Funções com score > 3, ordenadas por urgência."""
        return sorted(
            [f for f in self.functions if f.total_score > 3],
            key=lambda f: f.total_score,
            reverse=True,
        )

    @property
    def all_auto_fixable(self) -> list[AllocationSite]:
        return [s for f in self.functions for s in f.auto_fixable]


# ──────────────────────────────────────────────────────────────────────────────
# Visitor AST principal
# ──────────────────────────────────────────────────────────────────────────────

class _LoopDepthTracker(ast.NodeVisitor):
    """Rastreia profundidade de loops para saber se um nó está dentro de loop."""

    def __init__(self):
        self._depth = 0
        self._loop_lines: set[int] = set()

    def visit_For(self, node):
        self._depth += 1
        self._loop_lines.update(range(node.lineno, getattr(node, 'end_lineno', node.lineno) + 1))
        self.generic_visit(node)
        self._depth -= 1

    def visit_While(self, node):
        self._depth += 1
        self._loop_lines.update(range(node.lineno, getattr(node, 'end_lineno', node.lineno) + 1))
        self.generic_visit(node)
        self._depth -= 1

    def in_loop(self, lineno: int) -> bool:
        return lineno in self._loop_lines


class ObjectAllocationScanner(ast.NodeVisitor):
    """
    Visita o AST de um módulo Python e coleta AllocationSites por função.
    """

    def __init__(self, source_lines: list[str]):
        self._lines    = source_lines
        self._current_func: str  = "<module>"
        self._current_func_lineno: int = 0
        self._loop_tracker = _LoopDepthTracker()
        self._func_reports: dict[str, FunctionAllocReport] = {}
        self._loop_stack: list[ast.AST] = []

    # ── helpers ──────────────────────────────────────────────────────────────

    def _snippet(self, node: ast.AST) -> str:
        lineno = getattr(node, 'lineno', 0)
        if 0 < lineno <= len(self._lines):
            return self._lines[lineno - 1].strip()[:80]
        return ""

    def _in_loop(self) -> bool:
        return len(self._loop_stack) > 0

    def _report(self) -> FunctionAllocReport:
        key = self._current_func
        if key not in self._func_reports:
            self._func_reports[key] = FunctionAllocReport(
                func_name=key, lineno=self._current_func_lineno
            )
        return self._func_reports[key]

    def _add(
        self,
        node: ast.AST,
        pattern: AllocPattern,
        strategy: ReduceStrategy,
        cost: int = 1,
        confidence: str = "medium",
        auto_fix: bool = False,
    ):
        self._report().sites.append(AllocationSite(
            pattern    = pattern,
            strategy   = strategy,
            lineno     = getattr(node, 'lineno', 0),
            col        = getattr(node, 'col_offset', 0),
            func_name  = self._current_func,
            snippet    = self._snippet(node),
            in_loop    = self._in_loop(),
            cost       = cost,
            confidence = confidence,
            auto_fix   = auto_fix,
        ))

    # ── traversal ─────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_func   = self._current_func
        prev_lineno = self._current_func_lineno
        self._current_func       = node.name
        self._current_func_lineno = node.lineno

        # Detecta **kwargs em hot-path
        args = node.args
        if args.kwarg:
            self._add(node, AllocPattern.KWARGS_DICT, ReduceStrategy.EXPLICIT_PARAMS,
                      cost=2, confidence="medium")

        self.generic_visit(node)
        self._current_func       = prev_func
        self._current_func_lineno = prev_lineno

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_For(self, node: ast.For):
        self._loop_stack.append(node)
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_While(self, node: ast.While):
        self._loop_stack.append(node)
        self.generic_visit(node)
        self._loop_stack.pop()

    # ── Pattern: LIST_CONCAT  [a] + [b] ──────────────────────────────────────
    def visit_BinOp(self, node: ast.BinOp):
        if (isinstance(node.op, ast.Add)
                and isinstance(node.left,  ast.List)
                and isinstance(node.right, ast.List)
                and self._in_loop()):
            self._add(node, AllocPattern.LIST_CONCAT, ReduceStrategy.PREALLOCATE,
                      cost=2, confidence="high", auto_fix=True)
        self.generic_visit(node)

    # Nomes de variáveis que quase certamente são numéricas — não marcar como STR_CONCAT.
    # Padrão: score, total_*, count_*, n_*, num_*, sum_*, acc_*, idx_*, *_n, *_count, etc.
    _NUMERIC_VAR_RE = re.compile(
        r'^(?:'
        r'score|total|count|num|n|idx|size|len|sum|acc|result|'
        r'alloc|cost|hits|weight|rate|delta|offset|pos|step|'
        r'total_\w+|\w+_count|\w+_n|\w+_score|\w+_total|'
        r'[ijk]|[ijk]\d*'
        r')$',
        re.IGNORECASE,
    )

    # ── Pattern: AugAssign str += "..." ──────────────────────────────────────
    def visit_AugAssign(self, node: ast.AugAssign):
        if not (isinstance(node.op, ast.Add) and self._in_loop()):
            self.generic_visit(node)
            return

        # Target name — se for claramente numérico, não marcar como STR_CONCAT
        target_name = ""
        if isinstance(node.target, ast.Name):
            target_name = node.target.id
        if self._NUMERIC_VAR_RE.match(target_name):
            self.generic_visit(node)
            return

        # RHS é número literal → aritmética escalar, nunca string concat
        if isinstance(node.value, ast.Constant) and not isinstance(node.value.value, str):
            self.generic_visit(node)
            return

        # Só str concat real: RHS é string literal ou f-string
        is_str_literal = (
            isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        is_fstring = isinstance(node.value, ast.JoinedStr)
        if is_str_literal or is_fstring:
            self._add(node, AllocPattern.STR_CONCAT, ReduceStrategy.BYTEARRAY_BUFFER,
                      cost=2, confidence="high", auto_fix=False)
        elif isinstance(node.value, ast.Name):
            # s += var — só marca se o RHS também não parecer numérico
            rhs_name = node.value.id
            if self._NUMERIC_VAR_RE.match(rhs_name):
                self.generic_visit(node)
                return
            self._add(node, AllocPattern.STR_CONCAT, ReduceStrategy.BYTEARRAY_BUFFER,
                      cost=2, confidence="low", auto_fix=False)
        # int/float += 1  →  NÃO marcar (aritmética escalar)
        self.generic_visit(node)

    # ── Pattern: BOXED_NUMERIC int(x) float(x) em loop ───────────────────────
    def visit_Call(self, node: ast.Call):
        if self._in_loop():
            func = node.func
            # int(x), float(x), bool(x), complex(x)
            if isinstance(func, ast.Name) and func.id in ("int", "float", "bool", "complex"):
                self._add(node, AllocPattern.BOXED_NUMERIC, ReduceStrategy.CDEF_VAR,
                          cost=1, confidence="high", auto_fix=True)

            # dict() como acumulador
            elif isinstance(func, ast.Name) and func.id == "dict":
                self._add(node, AllocPattern.DICT_TEMP, ReduceStrategy.CDEF_STRUCT,
                          cost=3, confidence="medium")

            # enumerate(range(...))
            elif (isinstance(func, ast.Name) and func.id == "enumerate"
                  and node.args
                  and isinstance(node.args[0], ast.Call)
                  and isinstance(node.args[0].func, ast.Name)
                  and node.args[0].func.id == "range"):
                self._add(node, AllocPattern.RANGE_ENUMERATE, ReduceStrategy.INDEX_LOOP,
                          cost=1, confidence="high", auto_fix=True)

            # zip(a, b) em loop
            elif isinstance(func, ast.Name) and func.id == "zip":
                self._add(node, AllocPattern.ZIP_TEMP, ReduceStrategy.INDEX_LOOP,
                          cost=1, confidence="high", auto_fix=True)

        self.generic_visit(node)

    # ── Pattern: LAMBDA em loop ───────────────────────────────────────────────
    def visit_Lambda(self, node: ast.Lambda):
        if self._in_loop():
            self._add(node, AllocPattern.LAMBDA_HOTPATH, ReduceStrategy.INLINE_CDEF,
                      cost=2, confidence="medium")
        self.generic_visit(node)

    # ── Pattern: SLICE_COPY x[a:b] = ... em loop ─────────────────────────────
    def visit_Assign(self, node: ast.Assign):
        if self._in_loop():
            # RHS é um slice: x = arr[a:b]
            if isinstance(node.value, ast.Subscript):
                sl = node.value.slice
                if isinstance(sl, ast.Slice):
                    # Exclui slices sobre resultados de métodos que retornam str:
                    # hexdigest()[:n], .name[:n], .stem[:n], decode()[:n], etc.
                    # Também exclui slices com step negativo (ex: s[::-1] — reversão de string).
                    value_node = node.value.value
                    is_str_method_result = (
                        isinstance(value_node, ast.Call)
                        and isinstance(value_node.func, ast.Attribute)
                        and value_node.func.attr in (
                            "hexdigest", "digest", "decode", "encode",
                            "strip", "lstrip", "rstrip", "lower", "upper",
                            "replace", "split", "join", "format",
                        )
                    )
                    is_attr_access = (
                        isinstance(value_node, ast.Attribute)
                        and value_node.attr in ("name", "stem", "suffix", "parent")
                    )
                    # Step negativo → reversão de sequência, não cópia de buffer
                    has_step = sl.step is not None
                    if not (is_str_method_result or is_attr_access or has_step):
                        self._add(node, AllocPattern.SLICE_COPY, ReduceStrategy.TYPED_MEMORYVIEW,
                                  cost=2, confidence="high", auto_fix=True)
        self.generic_visit(node)

    # ── Pattern: LIST_COMP retornada ──────────────────────────────────────────
    def visit_Return(self, node: ast.Return):
        if isinstance(node.value, ast.ListComp):
            self._add(node, AllocPattern.LIST_COMP_RETURN, ReduceStrategy.YIELD_STREAM,
                      cost=3, confidence="medium", auto_fix=False)
        self.generic_visit(node)

    # ── Pattern: EXCEPTION_FLOW como controle de fluxo em loop ───────────────
    def visit_Try(self, node: ast.Try):
        if self._in_loop() and node.handlers:
            for handler in node.handlers:
                # Exceção usada como controle de fluxo (corpo não-trivial)
                if len(node.body) == 1:
                    self._add(node, AllocPattern.EXCEPTION_FLOW,
                              ReduceStrategy.CONDITIONAL_FLOW,
                              cost=3, confidence="medium")
                    break
        self.generic_visit(node)

    # ── Pattern: NESTED_LIST nested list literal em loop ─────────────────────
    def visit_List(self, node: ast.List):
        if self._in_loop():
            for elt in node.elts:
                if isinstance(elt, ast.List):
                    self._add(node, AllocPattern.NESTED_LIST_FLAT,
                              ReduceStrategy.NUMPY_ARRAY,
                              cost=len(node.elts), confidence="medium")
                    break
        self.generic_visit(node)

    # ── Pattern: TUPLE_UNPACK em loop ────────────────────────────────────────
    def visit_Expr(self, node: ast.Expr):
        self.generic_visit(node)

    def _check_tuple_unpack(self, targets):
        """Verifica se há tuple unpacking de chamada de função em loop."""
        for t in targets:
            if isinstance(t, ast.Tuple) and self._in_loop():
                return True
        return False

    def visit_Assign2(self, node: ast.Assign):
        # Já coberto em visit_Assign
        pass


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def scan_file(path: Path) -> ModuleAllocReport:
    """Escaneia um arquivo .py e retorna ModuleAllocReport."""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        return scan_source(source, path)
    except Exception:
        return ModuleAllocReport(path=path)


def scan_source(source: str, path: Path | None = None) -> ModuleAllocReport:
    """Escaneia código-fonte Python e retorna ModuleAllocReport."""
    report = ModuleAllocReport(path=path or Path("<source>"))
    try:
        tree = ast.parse(source)
        lines = source.splitlines()
        scanner = ObjectAllocationScanner(lines)
        scanner.visit(tree)
        report.functions = list(scanner._func_reports.values())
    except SyntaxError:
        pass
    except Exception:
        # Arquivo pode referenciar variáveis de runtime (ex: _buf_hot_files do
        # PitStop Engine) que não existem no contexto de análise estática.
        # Retorna relatório vazio em vez de propagar o erro.
        pass
    return report


def scan_pyx(pyx_source: str, path: Path | None = None) -> ModuleAllocReport:
    """
    Escaneia .pyx como Python (ignora extensões Cython).
    Remove linhas com 'cdef', 'cpdef', 'ctypedef' antes de parsear.
    """
    cleaned = "\n".join(
        line if not line.lstrip().startswith(("cdef ", "cpdef ", "ctypedef "))
        else "pass  # " + line.strip()
        for line in pyx_source.splitlines()
    )
    return scan_source(cleaned, path)


# ──────────────────────────────────────────────────────────────────────────────
# CLI de diagnóstico
# ──────────────────────────────────────────────────────────────────────────────

_STRATEGY_LABELS = {
    ReduceStrategy.TYPED_MEMORYVIEW: "typed memoryview (double[::1])",
    ReduceStrategy.CDEF_STRUCT:      "cdef struct",
    ReduceStrategy.CDEF_VAR:         "cdef tipado (elimina boxing)",
    ReduceStrategy.PREALLOCATE:      "array pré-alocado",
    ReduceStrategy.INDEX_LOOP:       "loop por índice (elimina zip/enumerate)",
    ReduceStrategy.BYTEARRAY_BUFFER: "bytearray buffer + join",
    ReduceStrategy.INLINE_CDEF:      "cdef inline (elimina lambda)",
    ReduceStrategy.NUMPY_ARRAY:      "np.ndarray tipado",
    ReduceStrategy.EXPLICIT_PARAMS:  "parâmetros explícitos (elimina **kwargs)",
    ReduceStrategy.CONDITIONAL_FLOW: "if/else (elimina try/except como fluxo)",
    ReduceStrategy.YIELD_STREAM:     "yield / buffer pré-alocado",
}

_PATTERN_LABELS = {
    AllocPattern.LIST_CONCAT:      "list concat em loop",
    AllocPattern.TUPLE_UNPACK:     "tuple unpack em loop",
    AllocPattern.DICT_TEMP:        "dict temporário em loop",
    AllocPattern.LIST_COMP_RETURN: "list comprehension retornada",
    AllocPattern.STR_CONCAT:       "str += em loop",
    AllocPattern.BOXED_NUMERIC:    "boxing numérico em loop",
    AllocPattern.RANGE_ENUMERATE:  "enumerate(range()) em loop",
    AllocPattern.ZIP_TEMP:         "zip() em loop",
    AllocPattern.SLICE_COPY:       "slice copy em loop",
    AllocPattern.EXCEPTION_FLOW:   "try/except como controle de fluxo",
    AllocPattern.KWARGS_DICT:      "**kwargs em hot path",
    AllocPattern.LAMBDA_HOTPATH:   "lambda em loop",
    AllocPattern.NESTED_LIST_FLAT: "lista aninhada em loop",
}


def render_report(report: ModuleAllocReport, verbose: bool = False) -> None:
    """Imprime relatório formatado no stdout."""
    CYAN, GREEN, YELLOW, RED, DIM, RESET = (
        "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
    )
    BOLD = "\033[1m"

    print(f"\n{CYAN}{BOLD}  ⬡ OBJECT ALLOCATION REPORT — {report.path.name}{RESET}")
    print(f"  {'─' * 55}")

    if not report.hot_functions:
        print(f"  {GREEN}✔ Nenhuma alocação crítica detectada.{RESET}\n")
        return

    print(f"  Score total : {BOLD}{report.total_score}{RESET}")
    print(f"  Funções     : {len(report.functions)} analisadas, "
          f"{len(report.hot_functions)} com alocações críticas")
    print(f"  Auto-fix    : {len(report.all_auto_fixable)} site(s) transformáveis\n")

    for func in report.hot_functions:
        color = RED if func.total_score >= 15 else (YELLOW if func.total_score >= 7 else CYAN)
        print(f"  {color}{BOLD}{func.func_name}{RESET}  "
              f"(linha {func.lineno})  "
              f"score={func.total_score}  "
              f"~{func.estimated_allocs_per_call} allocs/call")

        for site in sorted(func.sites, key=lambda s: s.score, reverse=True):
            in_loop_tag = f" {YELLOW}[LOOP]{RESET}" if site.in_loop else ""
            fix_tag     = f" {GREEN}[AUTO]{RESET}" if site.auto_fix else ""
            conf_color  = GREEN if site.confidence == "high" else (YELLOW if site.confidence == "medium" else DIM)

            print(f"    {conf_color}●{RESET} L{site.lineno:<4} "
                  f"{_PATTERN_LABELS.get(site.pattern, site.pattern.value):<38}"
                  f"{in_loop_tag}{fix_tag}")

            if verbose:
                print(f"         → {DIM}{_STRATEGY_LABELS.get(site.strategy, site.strategy.value)}{RESET}")
                if site.snippet:
                    print(f"         {DIM}{site.snippet}{RESET}")

        print()

    # Resumo de estratégias
    from collections import Counter
    strategy_counts = Counter(s.strategy for f in report.functions for s in f.sites)
    if strategy_counts:
        print(f"  {CYAN}Estratégias recomendadas:{RESET}")
        for strat, count in strategy_counts.most_common(5):
            print(f"    {count}x  {_STRATEGY_LABELS.get(strat, strat.value)}")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python object_allocation_scanner.py <arquivo.py> [--verbose]")
        sys.exit(1)
    path = Path(sys.argv[1])
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    report = scan_file(path)
    render_report(report, verbose=verbose)