# -*- coding: utf-8 -*-
# doxoade/research/forward_chaining/poc/10_ast_to_facts/engine_p10.py
"""
P10 â€” AST -> fatos (C2). Sem engine.

Contrato provado: C2 (Adaptacao)
    Fonte (str) -> frozenset[FactPair]

SUBSET DECLARADO (contrato do PoC, nao do sistema):
    Aceita APENAS "x = a + b" (Assign + BinOp + Name em ambos os lados).
    Qualquer outro shape -> UnsupportedNodeError explicito.
    Fonte malformada -> SyntaxError explicito (herdado de ast.parse).

P10a â€” 'x = a + b' -> frozenset exato de 6 fatos.
P10b â€” 100 extracoes -> serializacao determinista (diffavel).
P10c â€” 'x = ' (malformado) -> SyntaxError explicito, nao silencioso.
P10d â€” 'pass' (parsable, fora do subset) -> UnsupportedNodeError explicito.

NAO usa: engine (C1 nao entra aqui). Unificacao (P20).

Rodar: run.bat / run.ps1
"""
from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logging.txt"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc10")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


# ---------- Erros (ProDeNov 5.2) ----------
class UnsupportedNodeError(RuntimeError):
    """AST node fora do subset declarado para esta PoC."""


class AstShapeError(RuntimeError):
    """Fonte parseavel, mas fora do contrato de 1 statement."""


FactPair = tuple[str, str]


# ---------- Serializer ----------
SUPPORTED_NODES = (ast.Assign,)
SUPPORTED_VALUE_NODES = (ast.BinOp,)
SUPPORTED_LEAVES = (ast.Name,)


def parse_single(src: str) -> ast.stmt:
    """Extrai 1 statement. Multi-statement -> AstShapeError."""
    tree = ast.parse(src)
    if len(tree.body) != 1:
        raise AstShapeError(
            f"esperado 1 statement, veio {len(tree.body)}"
        )
    return tree.body[0]


def serialize_stmt(node: ast.stmt) -> frozenset[FactPair]:
    """Extrai fatos do subset. Fora do subset -> UnsupportedNodeError."""
    if not isinstance(node, SUPPORTED_NODES):
        raise UnsupportedNodeError(
            f"node tipo {type(node).__name__} fora do subset"
        )

    facts: set[FactPair] = {("stmt", type(node).__name__)}

    # Assign: exige 1 target Name, value BinOp
    if len(node.targets) != 1:
        raise UnsupportedNodeError(
            f"Assign com {len(node.targets)} targets; subset exige 1"
        )
    tgt = node.targets[0]
    if not isinstance(tgt, SUPPORTED_LEAVES):
        raise UnsupportedNodeError(
            f"Assign target {type(tgt).__name__} fora do subset"
        )
    facts.add(("assign.target", tgt.id))

    val = node.value
    if not isinstance(val, SUPPORTED_VALUE_NODES):
        raise UnsupportedNodeError(
            f"Assign value {type(val).__name__} fora do subset"
        )
    facts.add(("assign.value", type(val).__name__))
    facts.add(("binop.op", type(val.op).__name__))

    for side_name, side_node in (("left", val.left), ("right", val.right)):
        if not isinstance(side_node, SUPPORTED_LEAVES):
            raise UnsupportedNodeError(
                f"BinOp.{side_name} {type(side_node).__name__} fora do subset"
            )
        facts.add((f"binop.{side_name}", side_node.id))

    return frozenset(facts)


def extract(src: str) -> frozenset[FactPair]:
    """Fonte -> frozenset[FactPair]. Falha loud em qualquer desvio."""
    node = parse_single(src)
    return serialize_stmt(node)


def sorted_lines(facts: frozenset[FactPair]) -> list[str]:
    """Serializacao determinista (para diff de output.txt)."""
    return sorted(f"{k}={v}" for k, v in facts)


# ---------- Caso de teste canonico ----------
INPUT_P10A = "x = a + b"

EXPECTED_P10A: frozenset[FactPair] = frozenset({
    ("stmt", "Assign"),
    ("assign.target", "x"),
    ("assign.value", "BinOp"),
    ("binop.op", "Add"),
    ("binop.left", "a"),
    ("binop.right", "b"),
})


# ============================================================
# P10a â€” extracao exata
# ============================================================
def run_p10a() -> dict:
    facts = extract(INPUT_P10A)
    return {"input": INPUT_P10A, "facts": facts, "lines": sorted_lines(facts)}


# ============================================================
# P10b â€” determinismo de serializacao
# ============================================================
def run_p10b() -> dict:
    serialized: set[str] = set()
    for _ in range(100):
        serialized.add("|".join(sorted_lines(extract(INPUT_P10A))))
    return {"n": 100, "unique": serialized}


# ============================================================
# P10c â€” input malformado
# ============================================================
def run_p10c() -> dict:
    try:
        extract("x = ")
    except SyntaxError:
        return {"levantou_erro": True, "type": "SyntaxError"}
    except Exception as e:
        return {"levantou_erro": True, "type": type(e).__name__}
    return {"levantou_erro": False, "type": None}


# ============================================================
# P10d â€” node fora do subset
# ============================================================
def run_p10d() -> dict:
    try:
        extract("pass")
    except UnsupportedNodeError:
        return {"levantou_erro": True, "type": "UnsupportedNodeError"}
    except Exception as e:
        return {"levantou_erro": True, "type": type(e).__name__}
    return {"levantou_erro": False, "type": None}


# ============================================================
# main
# ============================================================
def main() -> int:
    lines: list[str] = []
    falhas: list[str] = []

    # ---------- P10a ----------
    lines.append("=== P10a: 'x = a + b' -> fatos ===")
    a = run_p10a()
    lines.append(f"input: {a['input']!r}")
    lines.append(f"fatos_len: {len(a['facts'])}")
    lines.append("fatos (sorted):")
    for line in a["lines"]:
        lines.append(f"  {line}")
    lines.append("")

    if a["facts"] != EXPECTED_P10A:
        extras = a["facts"] - EXPECTED_P10A
        missing = EXPECTED_P10A - a["facts"]
        falhas.append(
            f"P10a: conjunto divergente (extras={sorted(extras)}, "
            f"missing={sorted(missing)})"
        )

    # ---------- P10b ----------
    lines.append("=== P10b: determinismo de serializacao (100 runs) ===")
    b = run_p10b()
    lines.append(f"n: {b['n']}")
    lines.append(f"unique_outputs: {sorted(b['unique'])}")
    lines.append("")

    if len(b["unique"]) != 1:
        falhas.append(
            f"P10b: serializacao nao-deterministica ({len(b['unique'])} variacoes)"
        )

    # ---------- P10c ----------
    lines.append("=== P10c: input malformado -> SyntaxError explicito ===")
    c = run_p10c()
    lines.append("input: 'x = '")
    lines.append(f"levantou_erro: {c['levantou_erro']}")
    lines.append(f"type: {c['type']}")
    lines.append("")

    if not c["levantou_erro"]:
        falhas.append("P10c: input malformado nao levantou erro")
    if c["type"] != "SyntaxError":
        falhas.append(f"P10c: esperado SyntaxError, veio {c['type']}")

    # ---------- P10d ----------
    lines.append("=== P10d: node fora do subset -> UnsupportedNodeError explicito ===")
    d = run_p10d()
    lines.append("input: 'pass'")
    lines.append(f"levantou_erro: {d['levantou_erro']}")
    lines.append(f"type: {d['type']}")
    lines.append("")

    if not d["levantou_erro"]:
        falhas.append("P10d: node fora do subset nao levantou erro")
    if d["type"] != "UnsupportedNodeError":
        falhas.append(f"P10d: esperado UnsupportedNodeError, veio {d['type']}")

    # ---------- veredito ----------
    if falhas:
        lines.append(f"FAIL: {len(falhas)} falha(s)")
        for f in falhas:
            lines.append(f"  - {f}")
        LOG.error("P10 FAIL: %s", falhas)
        resultado = 1
    else:
        lines.append("P10 PASS")
        LOG.info("P10 PASS")
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
