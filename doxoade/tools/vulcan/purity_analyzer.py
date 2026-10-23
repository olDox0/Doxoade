# doxoade/doxoade/tools/vulcan/purity_analyzer.py
"""
OptimizationHeadroomAnalyzer — métrica de retorno Cython por função.

Diferente de BodyPurityScanner (que mede "pode rodar sob nogil?"),
este analisador mede "quanto Cython ganharia se esta função fosse
reescrita com tipagem explícita?".

O objetivo é reunir DADOS para formular templates de reescrita — não
aplicar transformações. É pura instrumentação de leitura.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field, asdict
from typing import Optional


POSITIVE_WEIGHTS = {
    "numeric_loops":          12,
    "indexed_access":          6,
    "local_arithmetic":        8,
    "branchless_candidates":   5,
    "native_kernels_used":    15,
}

NEGATIVE_WEIGHTS = {
    "python_calls_in_loop":   10,
    "dict_lookups_in_loop":    8,
    "string_ops_in_loop":      8,
    "io_calls":               20,
    "dynamic_attrs":          25,
    "exceptions_in_loop":     15,
}

_SAFE_CALLS = frozenset({
    "len", "range", "enumerate", "zip", "min", "max", "abs", "round",
    "int", "float", "bool", "isinstance", "type",
})

_IO_CALLS = frozenset({
    "print", "input", "open", "write", "read", "flush", "close",
    "send", "recv", "connect", "accept",
})

_STRING_METHODS = frozenset({
    "format", "join", "split", "strip", "lstrip", "rstrip",
    "lower", "upper", "replace", "startswith", "endswith",
    "encode", "decode", "find", "rfind", "count", "splitlines",
})


@dataclass
class FunctionHeadroom:
    file: str
    name: str
    lineno: int
    end_lineno: int
    n_nodes: int
    score: int
    grade: str
    color: str
    numeric_loops: int = 0
    indexed_access: int = 0
    local_arithmetic: int = 0
    branchless_candidates: int = 0
    native_kernels_used: int = 0
    python_calls_in_loop: int = 0
    dict_lookups_in_loop: int = 0
    string_ops_in_loop: int = 0
    io_calls: int = 0
    dynamic_attrs: int = 0
    exceptions_in_loop: int = 0
    args_annotated: bool = False
    returns_annotated: bool = False
    has_loops: bool = False
    max_loop_depth: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileHeadroomReport:
    file: str
    total_functions: int = 0
    total_score: int = 0
    avg_score: float = 0.0
    functions: list[FunctionHeadroom] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "total_functions": self.total_functions,
            "total_score": self.total_score,
            "avg_score": round(self.avg_score, 2),
            "functions": [f.to_dict() for f in self.functions],
        }


class OptimizationHeadroomAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path: str, func_node: ast.FunctionDef):
        self.file = file_path
        self.func = func_node
        self.numeric_loops = 0
        self.indexed_access = 0
        self.local_arithmetic = 0
        self.branchless_candidates = 0
        self.native_kernels_used = 0
        self.python_calls_in_loop = 0
        self.dict_lookups_in_loop = 0
        self.string_ops_in_loop = 0
        self.io_calls = 0
        self.dynamic_attrs = 0
        self.exceptions_in_loop = 0
        self.loop_depth = 0
        self.max_loop_depth = 0
        self._annotated_args = self._check_args_annotated(func_node)
        self._annotated_return = func_node.returns is not None
        self._has_loops = False

    @staticmethod
    def _check_args_annotated(node: ast.FunctionDef) -> bool:
        all_args = (list(node.args.posonlyargs) + list(node.args.args)
                    + list(node.args.kwonlyargs))
        if not all_args:
            return False
        return all(a.annotation is not None for a in all_args)

    def _in_loop(self) -> bool:
        return self.loop_depth > 0

    @staticmethod
    def _call_name(node: ast.Call) -> str:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    @staticmethod
    def _is_numeric_literal(node) -> bool:
        return (isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool))

    def visit_For(self, node: ast.For):
        self._has_loops = True
        self.loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        is_range = (isinstance(node.iter, ast.Call)
                    and isinstance(node.iter.func, ast.Name)
                    and node.iter.func.id == "range")
        if is_range and isinstance(node.target, ast.Name):
            self.numeric_loops += 1
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_While(self, node: ast.While):
        self._has_loops = True
        self.loop_depth += 1
        self.max_loop_depth = max(self.max_loop_depth, self.loop_depth)
        self.generic_visit(node)
        self.loop_depth -= 1

    def visit_Subscript(self, node: ast.Subscript):
        if self._in_loop():
            if isinstance(node.slice, ast.Name) and isinstance(node.value, ast.Name):
                self.indexed_access += 1
            elif self._is_numeric_literal(node.slice) and isinstance(node.value, ast.Name):
                self.indexed_access += 1
            if isinstance(node.value, ast.Name) and isinstance(node.slice, ast.Name):
                name_lower = node.value.id.lower()
                if any(t in name_lower for t in ("dict", "map", "lookup", "cache")):
                    self.dict_lookups_in_loop += 1
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if self._in_loop():
            if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
                if isinstance(node.target, ast.Name):
                    if isinstance(node.value, ast.Name):
                        self.local_arithmetic += 1
                    elif self._is_numeric_literal(node.value):
                        self.local_arithmetic += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp):
        if self._in_loop():
            if self._is_numeric_literal(node.body) and self._is_numeric_literal(node.orelse):
                self.branchless_candidates += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func_name = self._call_name(node)
        if func_name.startswith("nexus_"):
            self.native_kernels_used += 1
            self.generic_visit(node)
            return
        if func_name in _IO_CALLS:
            self.io_calls += 1
            self.generic_visit(node)
            return
        if self._in_loop():
            if func_name in _SAFE_CALLS:
                pass
            elif func_name in _STRING_METHODS:
                self.string_ops_in_loop += 1
            else:
                self.python_calls_in_loop += 1
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if self._in_loop() and node.attr in _STRING_METHODS:
            self.string_ops_in_loop += 1
        if isinstance(node.value, ast.Name) and node.value.id in ("getattr", "setattr", "hasattr", "delattr"):
            self.dynamic_attrs += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        if self._in_loop() and node.handlers:
            self.exceptions_in_loop += 1
        self.generic_visit(node)

    def _compute_score(self) -> int:
        """
        Score = ganho potencial de Cython, medido APENAS por evidência positiva.

        Regra: sem fatores positivos → SLAG (0 pontos). Não há "neutro".
        Um loop numérico atenuado por N calls ainda pode valer se as calls
        forem refatoráveis (HOIST/SAFE), então penalidade de calls é suave.
        """
        positive = sum(getattr(self, a) * w for a, w in POSITIVE_WEIGHTS.items())
        negative = sum(getattr(self, a) * w for a, w in NEGATIVE_WEIGHTS.items())

        # Sem evidência positiva → nada a otimizar
        if positive == 0:
            return 0

        # Atenuação parcial: 50% do peso negativo (assume que refatoração é possível)
        net = max(0, positive - negative // 2)
        return min(100, net)

    @staticmethod
    def _grade(score: int) -> tuple[str, str]:
        if score >= 80:
            return "ADAMANTIUM", "\x1b[35m"
        if score >= 40:
            return "STEEL", "\x1b[34m"
        if score >= 15:
            return "BRONZE", "\x1b[33m"
        return "SLAG", "\x1b[31m"

    @staticmethod
    def _grade(score: int) -> tuple[str, str]:
        if score >= 80:
            return "ADAMANTIUM", "\x1b[35m"
        if score >= 50:
            return "STEEL", "\x1b[34m"
        if score >= 20:
            return "BRONZE", "\x1b[33m"
        return "SLAG", "\x1b[31m"

    def get_report(self) -> FunctionHeadroom:
        score = self._compute_score()
        grade, color = self._grade(score)
        n_nodes = sum(1 for _ in ast.walk(self.func))
        return FunctionHeadroom(
            file=self.file, name=self.func.name,
            lineno=self.func.lineno,
            end_lineno=getattr(self.func, "end_lineno", self.func.lineno),
            n_nodes=n_nodes, score=score, grade=grade, color=color,
            numeric_loops=self.numeric_loops,
            indexed_access=self.indexed_access,
            local_arithmetic=self.local_arithmetic,
            branchless_candidates=self.branchless_candidates,
            native_kernels_used=self.native_kernels_used,
            python_calls_in_loop=self.python_calls_in_loop,
            dict_lookups_in_loop=self.dict_lookups_in_loop,
            string_ops_in_loop=self.string_ops_in_loop,
            io_calls=self.io_calls,
            dynamic_attrs=self.dynamic_attrs,
            exceptions_in_loop=self.exceptions_in_loop,
            args_annotated=self._annotated_args,
            returns_annotated=self._annotated_return,
            has_loops=self._has_loops,
            max_loop_depth=self.max_loop_depth,
        )


def analyze_file(file_path: str, *, include_methods: bool = False) -> FileHeadroomReport:
    from pathlib import Path
    report = FileHeadroomReport(file=str(file_path))
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return report

    functions: list[FunctionHeadroom] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            a = OptimizationHeadroomAnalyzer(str(file_path), node)
            a.visit(node)
            functions.append(a.get_report())
        elif isinstance(node, ast.ClassDef) and include_methods:
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    a = OptimizationHeadroomAnalyzer(str(file_path), sub)
                    a.visit(sub)
                    functions.append(a.get_report())

    functions.sort(key=lambda f: f.score, reverse=True)
    report.functions = functions
    report.total_functions = len(functions)
    report.total_score = sum(f.score for f in functions)
    report.avg_score = report.total_score / len(functions) if functions else 0.0
    return report


def aggregate_corpus(file_reports: list[FileHeadroomReport]) -> dict:
    from collections import Counter
    grade_counter = Counter()
    score_buckets = Counter()
    positive_totals = Counter()
    negative_totals = Counter()
    high_score_functions = []
    low_score_functions = []

    for fr in file_reports:
        for f in fr.functions:
            grade_counter[f.grade] += 1
            bucket = (f.score // 10) * 10
            score_buckets[f"{bucket}-{bucket + 9}"] += 1
            for attr in POSITIVE_WEIGHTS:
                positive_totals[attr] += getattr(f, attr)
            for attr in NEGATIVE_WEIGHTS:
                negative_totals[attr] += getattr(f, attr)
            if f.score >= 80:
                high_score_functions.append(f)
            elif f.score < 25:
                low_score_functions.append(f)

    high_pos = Counter()
    high_neg = Counter()
    for f in high_score_functions:
        for attr in POSITIVE_WEIGHTS:
            if getattr(f, attr) > 0:
                high_pos[attr] += 1
        for attr in NEGATIVE_WEIGHTS:
            if getattr(f, attr) > 0:
                high_neg[attr] += 1

    low_pos = Counter()
    low_neg = Counter()
    for f in low_score_functions:
        for attr in POSITIVE_WEIGHTS:
            if getattr(f, attr) > 0:
                low_pos[attr] += 1
        for attr in NEGATIVE_WEIGHTS:
            if getattr(f, attr) > 0:
                low_neg[attr] += 1

    return {
        "total_files": len(file_reports),
        "total_functions": sum(fr.total_functions for fr in file_reports),
        "grade_distribution": dict(grade_counter),
        "score_histogram": dict(sorted(score_buckets.items())),
        "positive_totals": dict(positive_totals),
        "negative_totals": dict(negative_totals),
        "high_score_patterns": {
            "count": len(high_score_functions),
            "positive_factors": dict(high_pos),
            "negative_factors": dict(high_neg),
        },
        "low_score_patterns": {
            "count": len(low_score_functions),
            "positive_factors": dict(low_pos),
            "negative_factors": dict(low_neg),
        },
    }

# ============================================================
# FASE 2: Classificador de calls em loop
# ============================================================
# Categorias de refatoração possível para cada `python_call_in_loop`.
# ============================================================

CALL_CATEGORY_HOIST = "HOIST"       # call não depende da var de loop — mover pra fora
CALL_CATEGORY_BATCH = "BATCH"       # padrão append(f(x)) — coletar e processar depois
CALL_CATEGORY_BUFFER = "BUFFER"     # padrão acumulador — usar join/+= antes do loop
CALL_CATEGORY_SAFE = "SAFE"         # builtin que Cython já otimiza (len, isinstance, etc)
CALL_CATEGORY_INLINE = "INLINE"     # função local pequena — pode ser inline
CALL_CATEGORY_NATIVE = "NATIVE"     # kernel nativo já ligado (nexus_*)
CALL_CATEGORY_BLOCKED = "BLOCKED"   # I/O puro — nunca otimizável
CALL_CATEGORY_UNKNOWN = "UNKNOWN"   # precisa análise humana


@dataclass
class CallInLoopEvent:
    """Classificação de uma chamada Python dentro de um loop."""
    file: str
    func_name: str
    lineno: int
    call_target: str          # nome da função/método chamado
    call_repr: str            # representação curta: `f(x)` ou `obj.method(y)`
    loop_var: Optional[str]   # variável do loop mais próximo (for x in ...)
    loop_depth: int           # profundidade do loop (1 = loop simples, 2 = nested)
    category: str             # HOIST/BATCH/BUFFER/SAFE/INLINE/NATIVE/BLOCKED/UNKNOWN
    reason: str               # justificativa curta
    args_depend_on_loop: bool # True se args contêm a var de loop
    in_accumulator: bool      # True se está dentro de `acc += f(...)` ou `acc.append(f(...))`

    def to_dict(self) -> dict:
        return asdict(self)


# Builtins que Cython reduz a ~1 instrução C (sem Python call overhead)
_SAFE_BUILTINS = frozenset({
    "len", "isinstance", "issubclass", "type", "id",
    "range", "enumerate", "zip", "map", "filter",
    "int", "float", "bool", "str", "bytes", "bytearray",
    "min", "max", "abs", "round", "sum", "any", "all",
    "sorted", "reversed", "list", "tuple", "set", "dict", "frozenset",
    "ord", "chr", "hex", "bin", "oct",
})

# Funções que Cython não otimiza (I/O real)
_IO_FUNCS = frozenset({
    "print", "input", "open", "write", "read", "flush", "close",
    "send", "recv", "connect", "accept", "urlopen", "urlretrieve",
    "sleep", "wait", "waitpid", "poll", "select",
})

# Métodos que são "coleta" (acumuladores)
_ACCUMULATOR_METHODS = frozenset({"append", "extend", "insert", "add", "update", "push"})

# Métodos de string (I/O de objetos Python)
_STRING_METHODS = frozenset({
    "format", "join", "split", "strip", "lstrip", "rstrip",
    "lower", "upper", "replace", "startswith", "endswith",
    "encode", "decode", "find", "rfind", "count", "splitlines",
})


class CallClassifier(ast.NodeVisitor):
    """
    Visita uma função e classifica cada `python_call_in_loop`.

    Uso:
        clf = CallClassifier(file_path, func_node)
        clf.visit(func_node)
        events = clf.get_events()
    """

    def __init__(self, file_path: str, func_node: ast.FunctionDef):
        self.file = file_path
        self.func = func_node
        self.func_name = func_node.name

        self._events: list[CallInLoopEvent] = []

        # Stack de loops (cada item é a variável de loop, se houver)
        self._loop_stack: list[Optional[str]] = []

        # Stack de contextos de acumulador (acc.append(...), acc += ...)
        self._accumulator_stack: list[bool] = []

        # Nomes de funções definidas no mesmo arquivo (para detectar INLINE)
        self._local_funcs: set[str] = set()

    def set_local_funcs(self, funcs: set[str]) -> None:
        self._local_funcs = funcs

    # ------------------------------------------------------------
    # Loop tracking
    # ------------------------------------------------------------
    def visit_For(self, node: ast.For):
        loop_var = node.target.id if isinstance(node.target, ast.Name) else None
        self._loop_stack.append(loop_var)
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_While(self, node: ast.While):
        self._loop_stack.append(None)
        self.generic_visit(node)
        self._loop_stack.pop()

    # ------------------------------------------------------------
    # Accumulator context: acc += ..., acc.append(...)
    # ------------------------------------------------------------
    def visit_AugAssign(self, node: ast.AugAssign):
        self._accumulator_stack.append(True)
        self.generic_visit(node)
        self._accumulator_stack.pop()

    def _in_loop(self) -> bool:
        return len(self._loop_stack) > 0

    def _loop_var(self) -> Optional[str]:
        # Pega a variável de loop mais próxima
        for v in reversed(self._loop_stack):
            if v is not None:
                return v
        return None

    # ------------------------------------------------------------
    # Call detection
    # ------------------------------------------------------------
    def visit_Call(self, node: ast.Call):
        if not self._in_loop():
            self.generic_visit(node)
            return

        # Extrai nome da call
        target_name = ""
        call_repr = ""

        if isinstance(node.func, ast.Name):
            target_name = node.func.id
            call_repr = f"{target_name}(...)"
        elif isinstance(node.func, ast.Attribute):
            target_name = node.func.attr
            obj_name = ""
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
            call_repr = f"{obj_name}.{target_name}(...)"
        else:
            call_repr = "<complex>(...)"

        # Verifica se args contêm a var de loop
        loop_var = self._loop_var()
        args_depend_on_loop = False
        if loop_var:
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if any(
                    isinstance(n, ast.Name) and n.id == loop_var
                    for n in ast.walk(arg)
                ):
                    args_depend_on_loop = True
                    break

        # Verifica se está dentro de um acumulador
        in_accumulator = any(self._accumulator_stack)

        # Classifica
        category, reason = self._classify(
            target_name=target_name,
            args_depend_on_loop=args_depend_on_loop,
            in_accumulator=in_accumulator,
            call_node=node,
        )

        self._events.append(CallInLoopEvent(
            file=self.file,
            func_name=self.func_name,
            lineno=node.lineno,
            call_target=target_name,
            call_repr=call_repr,
            loop_var=loop_var,
            loop_depth=len(self._loop_stack),
            category=category,
            reason=reason,
            args_depend_on_loop=args_depend_on_loop,
            in_accumulator=in_accumulator,
        ))

        self.generic_visit(node)

    # ------------------------------------------------------------
    # Classification rules
    # ------------------------------------------------------------
    def _classify(
        self,
        target_name: str,
        args_depend_on_loop: bool,
        in_accumulator: bool,
        call_node: ast.Call,
    ) -> tuple[str, str]:
        # 1. Kernels nativos → NATIVE
        if target_name.startswith("nexus_"):
            return CALL_CATEGORY_NATIVE, "kernel nativo já ligado"

        # 2. I/O puro → BLOCKED
        if target_name in _IO_FUNCS:
            return CALL_CATEGORY_BLOCKED, f"I/O: {target_name}"

        # 3. Métodos de string → BLOCKED (PyUnicode exige GIL)
        if target_name in _STRING_METHODS:
            return CALL_CATEGORY_BLOCKED, f"string method: {target_name}"

        # 4. Builtins safe → SAFE
        if target_name in _SAFE_BUILTINS:
            return CALL_CATEGORY_SAFE, f"builtin otimizável: {target_name}"

        # 5. Se está em acumulador + args dependem de loop → BATCH
        if in_accumulator and args_depend_on_loop:
            return CALL_CATEGORY_BATCH, "padrão acc.append(f(x)) — batchable"

        # 6. Se NÃO depende da var de loop → HOIST
        if not args_depend_on_loop:
            return CALL_CATEGORY_HOIST, "args independentes do loop — pode mover"

        # 7. Função local pequena → INLINE
        if target_name in self._local_funcs:
            return CALL_CATEGORY_INLINE, f"função local: {target_name}"

        # 8. Fallback
        return CALL_CATEGORY_UNKNOWN, f"precisa análise: {target_name}"

    # ------------------------------------------------------------
    def get_events(self) -> list[CallInLoopEvent]:
        return self._events


def classify_calls_in_file(file_path: str) -> list[CallInLoopEvent]:
    """Analisa todas as funções de um arquivo, classificando calls em loop."""
    from pathlib import Path

    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except Exception:
        return []

    # Coleta nomes de funções locais
    local_funcs = {
        n.name for n in tree.body if isinstance(n, ast.FunctionDef)
    }

    events: list[CallInLoopEvent] = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            clf = CallClassifier(str(file_path), node)
            clf.set_local_funcs(local_funcs)
            clf.visit(node)
            events.extend(clf.get_events())

    return events


def aggregate_call_events(all_events: list[CallInLoopEvent]) -> dict:
    """Agrega estatísticas de calls em loop para análise de refatoração."""
    from collections import Counter

    by_category = Counter()
    by_target = Counter()

    # Por categoria, quais targets dominam
    targets_by_category: dict[str, Counter] = {}
    for ev in all_events:
        by_category[ev.category] += 1
        by_target[ev.call_target] += 1
        if ev.category not in targets_by_category:
            targets_by_category[ev.category] = Counter()
        targets_by_category[ev.category][ev.call_target] += 1

    # ROI por função: quantas calls são refatoráveis (HOIST/BATCH/SAFE)
    func_roi: dict[tuple[str, str], dict] = {}
    for ev in all_events:
        key = (ev.file, ev.func_name)
        if key not in func_roi:
            func_roi[key] = {
                "file": ev.file,
                "func_name": ev.func_name,
                "total_calls": 0,
                "refactorable": 0,
                "blocked": 0,
                "unknown": 0,
            }
        func_roi[key]["total_calls"] += 1
        if ev.category in (CALL_CATEGORY_HOIST, CALL_CATEGORY_BATCH,
                           CALL_CATEGORY_SAFE, CALL_CATEGORY_NATIVE):
            func_roi[key]["refactorable"] += 1
        elif ev.category == CALL_CATEGORY_BLOCKED:
            func_roi[key]["blocked"] += 1
        else:
            func_roi[key]["unknown"] += 1

    # Top funções por ROI
    roi_list = sorted(
        func_roi.values(),
        key=lambda x: (-x["refactorable"], x["blocked"]),
    )

    return {
        "total_calls": len(all_events),
        "by_category": dict(by_category),
        "by_target_top": dict(by_target.most_common(30)),
        "targets_per_category": {
            cat: dict(counter.most_common(10))
            for cat, counter in targets_by_category.items()
        },
        "roi_by_function": roi_list[:50],
    }

