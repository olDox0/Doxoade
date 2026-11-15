# -*- coding: utf-8 -*-
# doxoade/research/code_classification/poc/q06_ext_complet/engine_q06.py
"""
Q06 - Extraction completeness (orchestrator).

Roda 4 sub-probes (q06a..q06d) via subprocess, concatena output,
compara com expected_q06.txt.

Estado (incremental):
    q06a (self_arg)            : implementado
    q06b (dunder_name)         : stub
    q06c (magic_outside_compare): stub
    q06d (decorator)           : stub

Exit codes:
    0 = todos sub-probes PASS (Q06 PASS)
    1 = algum sub-probe FAIL (Q06 FAIL)
    2 = algum sub-probe PENDING mas nenhum FAIL (Q06 PARTIAL)

Rodar: doxoade retro-forward run q06
"""

from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "logging_q06.txt"
DEBUG = "--debug" in sys.argv


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("poc_q06")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    return logger


LOG = setup_logging()


SUB_PROBES = [
    ("q06a_self_arg.py", "output_q06a.txt"),
    ("q06b_dunder_name.py", "output_q06b.txt"),
    ("q06c_magic_outside_compare.py", "output_q06c.txt"),
    ("q06d_decorator.py", "output_q06d.txt"),
]


def _run_sub(engine_name: str) -> tuple[int, str]:
    path = HERE / engine_name
    if not path.exists():
        return 2, f"[{engine_name} nao existe — PENDING]"
    try:
        r = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(HERE), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=60, stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return 1, f"[{engine_name} timeout 60s]"
    return r.returncode, (r.stdout or "")


def main() -> int:
    lines: list[str] = []
    lines.append("=== Q06: extraction completeness ===")
    lines.append("")

    pass_count = 0
    fail_count = 0
    pending_count = 0

    for engine_name, _ in SUB_PROBES:
        code, out = _run_sub(engine_name)
        lines.append(f"=== {engine_name} ===")
        lines.append(out.rstrip("\n"))
        lines.append("")
        if code == 0:
            pass_count += 1
        elif code == 2:
            pending_count += 1
        else:
            fail_count += 1

    lines.append("=== AGGREGATE ===")
    lines.append(f"PASS: {pass_count} | PENDING: {pending_count} | FAIL: {fail_count}")
    if fail_count > 0:
        lines.append("Q06 FAIL")
        resultado = 1
    elif pending_count > 0:
        lines.append("Q06 PARTIAL PASS")
        resultado = 0
    else:
        lines.append("Q06 PASS")
        resultado = 0
    lines.append("")

    for ln in lines:
        print(ln)

    out_path = HERE / "output.txt"
    out_path.write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
    )

    if resultado == 0:
        LOG.info("Q06 PASS")
    elif resultado == 2:
        LOG.warning("Q06 PARTIAL PASS (%d pending)", pending_count)
    else:
        LOG.error("Q06 FAIL (%d fail)", fail_count)
    return resultado


if __name__ == "__main__":
    sys.exit(main())
