# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/31_for_range_len/engine_p31.py
"""
P31 - Segundo padrao de rewrite (C4 puro, sem engine).

Contrato: C4 (Atuacao). AST + padrao -> AST nova via ast.unparse.

Diferenca de P30b:
    P30b usava fato derivado por P30a. P31 NAO usa engine.
    Pergunta distinta: C4 generaliza ou e one-shot?

Padrao: for IDX in range(len(SEQ)): <body>  ->  for SEQ_item in SEQ: <body'>
    - Substitui SEQ[IDX] por SEQ_item em todo o body.
    - Nome derivado: f"{SEQ}_item" (deterministico).
    - Validade: toda ocorrencia de IDX deve estar DENTRO de SEQ[IDX].
    - Uso livre de IDX (ex: print(i)) -> passthrough (nao levanta).

P31a - rewrite basico.
P31b - idempotencia (rewrite de rewrite = no-op).
P31c - passthrough: "for x in y: print(x)" nao casa.
P31d - passthrough: "for i in range(len(x)): print(i)" usa IDX como valor.
P31e - passthrough: "for i in range(len(x)): print(y[i])" indices diferentes.
P31f - output compila.
P31g - determinismo (100 runs).

Rodar: doxoade retro-forward run 31
"""
from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc31")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


# ============================================================
# Padrao: for IDX in range(len(SEQ)):
# ============================================================
def _is_range_len_iter(iter_node: ast.AST) -> tuple[str, str] | None:
    """Retorna (seq_name, index_name) se for range(len(SEQ)), senao None."""
    if not isinstance(iter_node, ast.Call):
        return None
    if not (isinstance(iter_node.func, ast.Name) and iter_node.func.id == "range"):
        return None
    if len(iter_node.args) != 1:
        return None
    inner = iter_node.args[0]
    if not isinstance(inner, ast.Call):
        return None
    if not (isinstance(inner.func, ast.Name) and inner.func.id == "len"):
        return None
    if len(inner.args) != 1:
        return None
    seq_arg = inner.args[0]
    if not isinstance(seq_arg, ast.Name):
        return None
    return seq_arg.id  # so o seq_name; index vem do target


class _BodyChecker(ast.NodeVisitor):
    """Valida: toda ocorrencia de IDX (Load) esta em SEQ[IDX]."""

    def __init__(self, seq_name: str, index_name: str):
        self.seq_name = seq_name
        self.index_name = index_name
        self.free_index_use = False
        self.subscript_count = 0

    def visit_Subscript(self, node: ast.Subscript):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == self.seq_name
            and isinstance(node.slice, ast.Name)
            and node.slice.id == self.index_name
        ):
            self.subscript_count += 1
            return  # consome: nao recursa em SEQ nem em IDX
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if node.id == self.index_name and isinstance(node.ctx, ast.Load):
            self.free_index_use = True


def _body_is_valid(body: list[ast.stmt], seq_name: str, index_name: str) -> bool:
    checker = _BodyChecker(seq_name, index_name)
    for stmt in body:
        checker.visit(stmt)
    return not checker.free_index_use and checker.subscript_count > 0


class _SeqIndexSubstituter(ast.NodeTransformer):
    """Substitui SEQ[IDX] por item_name."""

    def __init__(self, seq_name: str, index_name: str, item_name: str):
        self.seq_name = seq_name
        self.index_name = index_name
        self.item_name = item_name

    def visit_Subscript(self, node: ast.Subscript):
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == self.seq_name
            and isinstance(node.slice, ast.Name)
            and node.slice.id == self.index_name
        ):
            return ast.copy_location(
                ast.Name(id=self.item_name, ctx=ast.Load()),
                node,
            )
        return self.generic_visit(node)


# ============================================================
# Rewrite (C4)
# ============================================================
def rewrite_for_range_len(src: str) -> tuple[str, bool]:
    """
    Retorna (new_src, applied).
    applied=True se algum For foi reescrito; False se passthrough total.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src, False

    applied_any = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        seq_name = _is_range_len_iter(node.iter)
        if seq_name is None:
            continue
        index_name = node.target.id

        if not _body_is_valid(node.body, seq_name, index_name):
            LOG.debug(
                "for range-len com IDX '%s' usado livremente; passthrough",
                index_name,
            )
            continue

        item_name = f"{seq_name}_item"
        subst = _SeqIndexSubstituter(seq_name, index_name, item_name)
        node.body = [subst.visit(stmt) for stmt in node.body]
        node.target = ast.Name(id=item_name, ctx=ast.Store())
        node.iter = ast.Name(id=seq_name, ctx=ast.Load())
        ast.fix_missing_locations(node)
        applied_any = True
        LOG.debug("rewrite aplicado: %s -> %s", index_name, item_name)

    if not applied_any:
        return ast.unparse(tree), False
    return ast.unparse(tree), True


# ============================================================
# Sub-sondas
# ============================================================
SRC_P31A = (
    "def g(x):\n"
    "    for i in range(len(x)):\n"
    "        print(x[i])"
)
SRC_P31C = "def g(y):\n    for x in y:\n        print(x)"
SRC_P31D = (
    "def g(x):\n"
    "    for i in range(len(x)):\n"
    "        print(i)"
)
SRC_P31E = (
    "def g(x, y):\n"
    "    for i in range(len(x)):\n"
    "        print(y[i])"
)


def run_p31a() -> dict:
    out, applied = rewrite_for_range_len(SRC_P31A)
    return {"input": SRC_P31A, "output": out, "applied": applied}


def run_p31b() -> dict:
    once, applied1 = rewrite_for_range_len(SRC_P31A)
    twice, applied2 = rewrite_for_range_len(once)
    return {
        "once": once,
        "twice": twice,
        "idempotent": once == twice,
        "applied_2nd": applied2,
    }


def _passthrough(src: str) -> dict:
    out, applied = rewrite_for_range_len(src)
    baseline = ast.unparse(ast.parse(src))
    return {
        "input": src,
        "passthrough": (out == baseline) and (applied is False),
        "applied": applied,
    }


def run_p31c() -> dict:
    return _passthrough(SRC_P31C)


def run_p31d() -> dict:
    return _passthrough(SRC_P31D)


def run_p31e() -> dict:
    return _passthrough(SRC_P31E)


def run_p31f() -> dict:
    out, _ = rewrite_for_range_len(SRC_P31A)
    try:
        compile(out, "<p31>", "exec")
        return {"compiles": True, "error": None}
    except SyntaxError as e:
        return {"compiles": False, "error": str(e)}


def run_p31g() -> dict:
    outs: set[str] = set()
    for _ in range(100):
        out, _ = rewrite_for_range_len(SRC_P31A)
        outs.add(out)
    return {"n": 100, "unique": outs}


# ============================================================
# main
# ============================================================
def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P31a ----------
    lines.append("=== P31a: for-range-len -> direct iteration ===")
    a = run_p31a()
    lines.append(f"input: {a['input']!r}")
    lines.append("output:")
    for ln in a["output"].splitlines():
        lines.append(f"  {ln}")
    lines.append("")

    expected_a = "def g(x):\n    for x_item in x:\n        print(x_item)"
    if a["output"] != expected_a:
        falhas.append(f"P31a: output inesperado: {a['output']!r}")
    if not a["applied"]:
        falhas.append("P31a: applied deveria ser True")

    # ---------- P31b ----------
    lines.append("=== P31b: idempotencia ===")
    b = run_p31b()
    lines.append(f"idempotent: {b['idempotent']}")
    lines.append(f"applied_2nd: {b['applied_2nd']}")
    lines.append("")
    if not b["idempotent"]:
        falhas.append("P31b: nao idempotente")
    if b["applied_2nd"]:
        falhas.append("P31b: segunda aplicacao deveria ser no-op")

    # ---------- P31c, P31d, P31e ----------
    for label, fn in (("P31c", run_p31c), ("P31d", run_p31d), ("P31e", run_p31e)):
        r = fn()
        lines.append(f"=== {label}: passthrough ===")
        lines.append(f"input: {r['input']!r}")
        lines.append(f"passthrough: {r['passthrough']}")
        lines.append(f"applied: {r['applied']}")
        lines.append("")
        if not r["passthrough"]:
            falhas.append(f"{label}: deveria ser passthrough")

    # ---------- P31f ----------
    lines.append("=== P31f: output compila ===")
    f = run_p31f()
    lines.append(f"compiles: {f['compiles']}")
    lines.append("")
    if not f["compiles"]:
        falhas.append(f"P31f: output nao compila: {f['error']}")

    # ---------- P31g ----------
    lines.append("=== P31g: determinismo (100 runs) ===")
    g = run_p31g()
    lines.append(f"n: {g['n']}")
    lines.append(f"unique_count: {len(g['unique'])}")
    lines.append("")
    if len(g["unique"]) != 1:
        falhas.append(f"P31g: {len(g['unique'])} variacoes")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("P31 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P31 PASS")
        LOG.info("P31 PASS")
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
