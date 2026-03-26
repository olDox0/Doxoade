# -*- coding: utf-8 -*-
"""Ponte ORN↔DOXOADE para encaminhar falhas do `doxoade check`."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class BridgeAttempt:
    mode: str
    ok: bool
    detail: str


def _bridge_enabled() -> bool:
    return os.environ.get("DOXOADE_ORN_BRIDGE", "1") not in {"0", "false", "False"}


def _build_prompt(path: str, summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    top_findings = findings[:6]
    findings_text = []
    for item in top_findings:
        findings_text.append(
            {
                "severity": item.get("severity"),
                "category": item.get("category"),
                "file": item.get("file"),
                "line": item.get("line"),
                "message": item.get("message"),
            }
        )

    payload = {
        "source": "doxoade-check",
        "path": path,
        "summary": summary,
        "findings": findings_text,
        "timestamp": int(time.time()),
    }
    return (
        "ORN, analise o diagnóstico do doxoade check e retorne plano curto de correção priorizado.\n"
        "Responda em português com passos objetivos.\n"
        f"DADOS_JSON: {json.dumps(payload, ensure_ascii=False)}"
    )


def _run_orn_cli(command: list[str], timeout_s: int) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(5, timeout_s),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, err or f"exit={proc.returncode}"

    out = (proc.stdout or "").strip()
    return True, out.splitlines()[-1] if out else "ok"


def dispatch_check_errors_to_orn(*, path: str, summary: dict[str, int], findings: list[dict[str, Any]]) -> list[BridgeAttempt]:
    """Encaminha erros do check ao ORN em dois modos: servidor e direto."""
    attempts: list[BridgeAttempt] = []

    if not _bridge_enabled():
        return [BridgeAttempt(mode="disabled", ok=False, detail="DOXOADE_ORN_BRIDGE=0")]

    total_errors = int(summary.get("errors", 0)) + int(summary.get("critical", 0))
    if total_errors <= 0:
        return [BridgeAttempt(mode="skipped", ok=True, detail="sem erros")]

    orn_bin = shutil.which(os.environ.get("ORN_BIN", "orn"))
    if not orn_bin:
        return [BridgeAttempt(mode="unavailable", ok=False, detail="binário 'orn' não encontrado")]

    prompt = _build_prompt(path, summary, findings)
    timeout_s = int(os.environ.get("DOXOADE_ORN_TIMEOUT", "25"))

    server_cmd = [orn_bin, "server", "ask", prompt, "--tokens", "220"]
    ok, detail = _run_orn_cli(server_cmd, timeout_s)
    attempts.append(BridgeAttempt(mode="server", ok=ok, detail=detail))

    direct_cmd = [orn_bin, "think", prompt, "--direct", "--tokens", "220"]
    ok, detail = _run_orn_cli(direct_cmd, timeout_s)
    attempts.append(BridgeAttempt(mode="direct", ok=ok, detail=detail))

    _persist_bridge_log(path=path, summary=summary, attempts=attempts)
    return attempts


def _persist_bridge_log(*, path: str, summary: dict[str, int], attempts: list[BridgeAttempt]) -> None:
    telemetry_dir = Path("telemetry")
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    out = telemetry_dir / "orn_bridge.jsonl"

    row = {
        "timestamp": int(time.time()),
        "source": "doxoade-check",
        "path": path,
        "summary": summary,
        "attempts": [a.__dict__ for a in attempts],
    }
    with out.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False) + "\n")
