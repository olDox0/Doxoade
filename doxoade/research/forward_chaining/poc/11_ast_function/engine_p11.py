# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/11_ast_function/engine_p11.py
"""
P11 â€” AST de funcao simples -> fatos (C2). Sem engine.

Contrato provado: C2 (Adaptacao), extensao de P10.

SUBSET DECLARADO (contrato do PoC):
    Aceita APENAS "def NAME(PARAM): return PARAM + INT_LITERAL"
    - FunctionDef com 1 arg (ast.arg)
    - 1 body stmt (Return)
    - Return.expr = BinOp(op=Add)
    - BinOp.left = Name
    - BinOp.right = Constant com valor int

Qualquer variacao -> UnsupportedNodeError explicito.
Assign (de P10) -> UnsupportedNodeError em P11 (subset distinto).

P11a â€” def f(x): return x + 1 -> frozenset exato de 11 fatos.
P11b â€” def g(n): return n + 42 -> 11 fatos (nao hardcoded).
P11c â€” 100 runs sobre P11a -> serializacao determinista.
P11d â€” def f(): return 42 (0 args) -> UnsupportedNodeError.
P11e â€” def f(x): return x (Return sem BinOp) -> UnsupportedNodeError.
P11f â€” x = a + b (Assign de P10) -> UnsupportedNodeError.

NAO usa: engine (C1 nao entra aqui).

Rodar: run.bat / run.ps1
"""
from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc11")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


class UnsupportedNodeError(RuntimeError):
    """AST node fora do subset declarado para esta PoC."""


class AstShapeError(RuntimeError):
    """Fonte parseavel, mas fora do contrato de 1 statement."""


FactPair = tuple[str, str]
SUPPORTED_STMTS = (ast.FunctionDef,)


def parse_single(src: str) -> ast.stmt:
    tree = ast.parse(src)
    if len(tree.body) != 1:
        raise AstShapeError(f"esperado 1 statement, veio {len(tree.body)}")
    return tree.body[0]


def serialize_function(node: ast.FunctionDef) -> frozenset[FactPair]:
    facts: set[FactPair] = {("stmt", "FunctionDef"), ("func.name", node.name)}

    # --- args: exatamente 1 ---
    if len(node.args.args) != 1:
        raise UnsupportedNodeError(
            f"FunctionDef com {len(node.args.args)} args; subset exige 1"
        )
    arg = node.args.args[0]
    facts.add(("func.args_len", "1"))
    facts.add(("func.arg", arg.arg))

    # --- body: exatamente 1 stmt Return ---
    if len(node.body) != 1:
        raise UnsupportedNodeError(
            f"FunctionDef com {len(node.body)} body stmts; subset exige 1"
        )
    body_stmt = node.body[0]
    if not isinstance(body_stmt, ast.Return):
        raise UnsupportedNodeError(
            f"FunctionDef body {type(body_stmt).__name__}; subset exige Return"
        )
    facts.add(("func.body.kind", "Return"))

    if body_stmt.value is None:
        raise UnsupportedNodeError("Return sem expressao; subset exige expr")
    expr = body_stmt.value
    if not isinstance(expr, ast.BinOp):
        raise UnsupportedNodeError(
            f"Return.expr {type(expr).__name__}; subset exige BinOp"
        )
    if not isinstance(expr.op, ast.Add):
        raise UnsupportedNodeError(
            f"BinOp.op {type(expr.op).__name__}; subset exige Add"
        )
    facts.add(("func.body.expr", "BinOp"))
    facts.add(("binop.op", "Add"))

    # --- BinOp.left: Name ---
    if not isinstance(expr.left, ast.Name):
        raise UnsupportedNodeError(
            f"BinOp.left {type(expr.left).__name__}; subset exige Name"
        )
    facts.add(("binop.left.kind", "Name"))
    facts.add(("binop.left.name", expr.left.id))

    # --- BinOp.right: Constant int ---
    if not isinstance(expr.right, ast.Constant):
        raise UnsupportedNodeError(
            f"BinOp.right {type(expr.right).__name__}; subset exige Constant"
        )
    if not isinstance(expr.right.value, int) or isinstance(expr.right.value, bool):
        raise UnsupportedNodeError(
            f"BinOp.right.value tipo {type(expr.right.value).__name__}; subset exige int"
        )
    facts.add(("binop.right.kind", "Constant"))
    facts.add(("binop.right.value", str(expr.right.value)))

    return frozenset(facts)


def extract(src: str) -> frozenset[FactPair]:
    node = parse_single(src)
    if not isinstance(node, SUPPORTED_STMTS):
        raise UnsupportedNodeError(
            f"stmt tipo {type(node).__name__} fora do subset P11 "
            f"(P11 aceita apenas FunctionDef)"
        )
    return serialize_function(node)


def sorted_lines(facts: frozenset[FactPair]) -> list[str]:
    return sorted(f"{k}={v}" for k, v in facts)


# ---------- casos canonicos ----------
INPUT_P11A = "def f(x): return x + 1"
EXPECTED_P11A: frozenset[FactPair] = frozenset({
    ("stmt", "FunctionDef"),
    ("func.name", "f"),
    ("func.args_len", "1"),
    ("func.arg", "x"),
    ("func.body.kind", "Return"),
    ("func.body.expr", "BinOp"),
    ("binop.op", "Add"),
    ("binop.left.kind", "Name"),
    ("binop.left.name", "x"),
    ("binop.right.kind", "Constant"),
    ("binop.right.value", "1"),
})

INPUT_P11B = "def g(n): return n + 42"
EXPECTED_P11B: frozenset[FactPair] = frozenset({
    ("stmt", "FunctionDef"),
    ("func.name", "g"),
    ("func.args_len", "1"),
    ("func.arg", "n"),
    ("func.body.kind", "Return"),
    ("func.body.expr", "BinOp"),
    ("binop.op", "Add"),
    ("binop.left.kind", "Name"),
    ("binop.left.name", "n"),
    ("binop.right.kind", "Constant"),
    ("binop.right.value", "42"),
})


def run_p11a() -> dict:
    facts = extract(INPUT_P11A)
    return {"input": INPUT_P11A, "facts": facts, "lines": sorted_lines(facts)}


def run_p11b() -> dict:
    facts = extract(INPUT_P11B)
    return {"input": INPUT_P11B, "facts": facts, "lines": sorted_lines(facts)}


def run_p11c() -> dict:
    serialized: set[str] = set()
    for _ in range(100):
        serialized.add("|".join(sorted_lines(extract(INPUT_P11A))))
    return {"n": 100, "unique": serialized}


def _expect_error(src: str, expected_type: str) -> dict:
    try:
        extract(src)
    except Exception as e:
        return {"levantou_erro": True, "type": type(e).__name__,
                "matches_expected": type(e).__name__ == expected_type}
    return {"levantou_erro": False, "type": None, "matches_expected": False}


def run_p11d() -> dict:
    return {"input": "def f(): return 42",
            **_expect_error("def f(): return 42", "UnsupportedNodeError")}


def run_p11e() -> dict:
    return {"input": "def f(x): return x",
            **_expect_error("def f(x): return x", "UnsupportedNodeError")}


def run_p11f() -> dict:
    return {"input": "x = a + b",
            **_expect_error("x = a + b", "UnsupportedNodeError")}


def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P11a ----------
    lines.append("=== P11a: 'def f(x): return x + 1' -> fatos ===")
    a = run_p11a()
    lines.append(f"input: {a['input']!r}")
    lines.append(f"fatos_len: {len(a['facts'])}")
    lines.append("fatos (sorted):")
    for line in a["lines"]:
        lines.append(f"  {line}")
    lines.append("")

    if a["facts"] != EXPECTED_P11A:
        extras = a["facts"] - EXPECTED_P11A
        missing = EXPECTED_P11A - a["facts"]
        falhas.append(
            f"P11a: conjunto divergente (extras={sorted(extras)}, "
            f"missing={sorted(missing)})"
        )

    # ---------- P11b ----------
    lines.append("=== P11b: 'def g(n): return n + 42' -> fatos ===")
    b = run_p11b()
    lines.append(f"input: {b['input']!r}")
    lines.append(f"fatos_len: {len(b['facts'])}")
    lines.append("fatos (sorted):")
    for line in b["lines"]:
        lines.append(f"  {line}")
    lines.append("")

    if b["facts"] != EXPECTED_P11B:
        extras = b["facts"] - EXPECTED_P11B
        missing = EXPECTED_P11B - b["facts"]
        falhas.append(
            f"P11b: conjunto divergente (extras={sorted(extras)}, "
            f"missing={sorted(missing)})"
        )

    # ---------- P11c ----------
    lines.append("=== P11c: determinismo de serializacao (100 runs) ===")
    c = run_p11c()
    lines.append(f"n: {c['n']}")
    lines.append(f"unique_outputs: {sorted(c['unique'])}")
    lines.append("")

    if len(c["unique"]) != 1:
        falhas.append(
            f"P11c: serializacao nao-deterministica ({len(c['unique'])} variacoes)"
        )

    # ---------- P11d-f ----------
    for label, runner in (("P11d", run_p11d), ("P11e", run_p11e),
                          ("P11f", run_p11f)):
        r = runner()
        lines.append(f"=== {label}: input {r['input']!r} ===")
        lines.append(f"levantou_erro: {r['levantou_erro']}")
        lines.append(f"type: {r['type']}")
        lines.append(f"matches_expected: {r['matches_expected']}")
        lines.append("")
        if not r["levantou_erro"]:
            falhas.append(f"{label}: input nao levantou erro")
        if not r["matches_expected"]:
            falhas.append(f"{label}: esperado UnsupportedNodeError, veio {r['type']}")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for f in falhas:
            lines.append(f"  - {f}")
        LOG.error("P11 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P11 PASS")
        LOG.info("P11 PASS")
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
