
# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/30b_if_return_rewrite/engine_p30b.py
"""
P30b - Rewrite de AST (C4, puro).

Contrato: C4 (Atuacao). AST + fato -> AST nova.

NAO faz:
- re-parse do output
- re-inferencia (o fato ja foi derivado por P30a)
- multi-pattern (so if_return_guard)

Faz:
- recebe src, detecta padrao if_return_guard
- reescreve body: [If[Return], Return] -> [Return[IfExp]]
- ast.unparse -> str
- idempotencia: rewrite(rewrite(x)) == rewrite(x) via nao-match natural
- passthrough: input sem padrao fica inalterado

P30b-1 - rewrite de "if x>0: return x\\nreturn None" -> "return x if x>0 else None"
P30b-2 - idempotencia: 2 rewrites = 1 rewrite
P30b-3 - passthrough: "def f(x): return x+1" inalterado
P30b-4 - output compila com compile()
P30b-5 - determinismo (100 runs)

Rodar: run_30b.bat
"""
from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc30b")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


class RewriteError(RuntimeError):
    """Rewrite encontrou estado invalido (nao deveria acontecer)."""


# ============================================================
# Pattern detection (identico a P30a, inlined)
# ============================================================
def is_if_return_guard(func: ast.FunctionDef) -> bool:
    if len(func.body) != 2:
        return False
    if not isinstance(func.body[0], ast.If):
        return False
    if len(func.body[0].body) != 1:
        return False
    if not isinstance(func.body[0].body[0], ast.Return):
        return False
    if not isinstance(func.body[1], ast.Return):
        return False
    return True


# ============================================================
# Rewrite (C4)
# ============================================================
def rewrite_if_return_guard(src: str) -> str:
    """
    Aplica rewrite se pattern casar. Senao, retorna unparse do original.
    Nao levanta para nao-matches - passthrough e comportamento correto.
    """
    tree = ast.parse(src)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return ast.unparse(tree)

    func = tree.body[0]
    if not is_if_return_guard(func):
        return ast.unparse(tree)

    if_node = func.body[0]
    then_ret = if_node.body[0]
    else_ret = func.body[1]

    new_ifexp = ast.IfExp(
        test=if_node.test,
        body=then_ret.value,
        orelse=else_ret.value,
    )
    new_return = ast.Return(value=new_ifexp)

    func.body = [new_return]
    ast.fix_missing_locations(func)

    LOG.debug("rewrite aplicado em '%s'", func.name)
    return ast.unparse(tree)


# ============================================================
# Sub-sondas
# ============================================================
SRC_GUARD = "def f(x):\n    if x > 0:\n        return x\n    return None"
SRC_PASSTHROUGH = "def f(x): return x + 1"


def run_p30b_1() -> dict:
    out = rewrite_if_return_guard(SRC_GUARD)
    return {"input": SRC_GUARD, "output": out}


def run_p30b_2() -> dict:
    once = rewrite_if_return_guard(SRC_GUARD)
    twice = rewrite_if_return_guard(once)
    return {"once": once, "twice": twice, "idempotent": once == twice}


def run_p30b_3() -> dict:
    out = rewrite_if_return_guard(SRC_PASSTHROUGH)
    baseline = ast.unparse(ast.parse(SRC_PASSTHROUGH))
    return {
        "input": SRC_PASSTHROUGH,
        "output": out,
        "baseline": baseline,
        "passthrough": out == baseline,
    }


def run_p30b_4() -> dict:
    out = rewrite_if_return_guard(SRC_GUARD)
    try:
        compile(out, "<p30b>", "exec")
        return {"output": out, "compiles": True, "error": None}
    except SyntaxError as e:
        return {"output": out, "compiles": False, "error": str(e)}


def run_p30b_5() -> dict:
    outs: set[str] = set()
    for _ in range(100):
        outs.add(rewrite_if_return_guard(SRC_GUARD))
    return {"n": 100, "unique": outs}


# ============================================================
# main
# ============================================================
def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P30b-1 ----------
    lines.append("=== P30b-1: rewrite if_return_guard -> ternary ===")
    r1 = run_p30b_1()
    lines.append(f"input: {r1['input']!r}")
    lines.append("output:")
    for ln in r1["output"].splitlines():
        lines.append(f"  {ln}")
    lines.append("")

    expected_1 = "def f(x):\n    return x if x > 0 else None"
    if r1["output"] != expected_1:
        falhas.append(f"P30b-1: output inesperado: {r1['output']!r}")

    # ---------- P30b-2 ----------
    lines.append("=== P30b-2: idempotencia ===")
    r2 = run_p30b_2()
    lines.append(f"idempotent: {r2['idempotent']}")
    lines.append("")

    if not r2["idempotent"]:
        falhas.append(f"P30b-2: nao idempotente (once={r2['once']!r}, twice={r2['twice']!r})")

    # ---------- P30b-3 ----------
    lines.append("=== P30b-3: passthrough (sem pattern) ===")
    r3 = run_p30b_3()
    lines.append(f"input: {r3['input']!r}")
    lines.append(f"passthrough: {r3['passthrough']}")
    lines.append("")

    if not r3["passthrough"]:
        falhas.append(
            f"P30b-3: nao preservou (out={r3['output']!r}, base={r3['baseline']!r})"
        )

    # ---------- P30b-4 ----------
    lines.append("=== P30b-4: output compila ===")
    r4 = run_p30b_4()
    lines.append(f"compiles: {r4['compiles']}")
    if r4["error"]:
        lines.append(f"error: {r4['error']}")
    lines.append("")

    if not r4["compiles"]:
        falhas.append(f"P30b-4: output nao compila: {r4['error']}")

    # ---------- P30b-5 ----------
    lines.append("=== P30b-5: determinismo (100 runs) ===")
    r5 = run_p30b_5()
    lines.append(f"n: {r5['n']}")
    lines.append(f"unique_count: {len(r5['unique'])}")
    lines.append("")

    if len(r5["unique"]) != 1:
        falhas.append(f"P30b-5: {len(r5['unique'])} variacoes")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for x in falhas:
            lines.append(f"  - {x}")
        LOG.error("P30b FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P30b PASS")
        LOG.info("P30b PASS")
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
