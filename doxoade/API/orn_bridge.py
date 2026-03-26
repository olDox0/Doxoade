# -*- coding: utf-8 -*-
"""Ponte ORN↔DOXOADE para encaminhar falhas do `doxoade check`."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
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


def _command_from_path(path: Path) -> list[str] | None:
    """Converte caminho conhecido (arquivo/pasta ORN) em comando executável."""
    p = path.expanduser().resolve()

    if p.is_dir():
        dir_candidates = [
            p / "orn",
            p / "orn.exe",
            p / "orn.py",
            p / "engine" / "cli.py",
        ]
        for candidate in dir_candidates:
            cmd = _command_from_path(candidate)
            if cmd:
                return cmd
        return None

    if not p.exists():
        return None

    if p.suffix.lower() == ".py":
        return [sys.executable, str(p)]
    return [str(p)]


def _resolve_from_env_cmd() -> tuple[list[str] | None, str]:
    raw_cmd = os.environ.get("ORN_CMD", "").strip()
    if not raw_cmd:
        return None, ""

    # Compatível com `set ORN_CMD=C:\...\ORN` no CMD/PowerShell.
    direct_path = Path(raw_cmd.strip().strip('"'))
    cmd_from_path = _command_from_path(direct_path)
    if cmd_from_path:
        return cmd_from_path, "env:ORN_CMD(path)"

    # Comando composto: respeita parse da plataforma.
    try:
        parsed = shlex.split(raw_cmd, posix=(os.name != "nt"))
    except ValueError:
        return None, ""
    if not parsed:
        return None, ""

    token_path = _command_from_path(Path(parsed[0].strip('"')))
    if token_path:
        return [*token_path, *parsed[1:]], "env:ORN_CMD(cmd+path)"

    return parsed, "env:ORN_CMD"


def _resolve_from_env_bin() -> tuple[list[str] | None, str]:
    raw_bin = os.environ.get("ORN_BIN", "").strip()
    if not raw_bin:
        return None, ""

    cmd_from_path = _command_from_path(Path(raw_bin.strip().strip('"')))
    if cmd_from_path:
        return cmd_from_path, "env:ORN_BIN(path)"

    resolved = shutil.which(raw_bin)
    if resolved:
        return [resolved], "env:ORN_BIN(which)"
    return None, ""


def _candidate_bases() -> list[Path]:
    bases = [Path.cwd()]
    for parent in Path.cwd().parents:
        bases.append(parent)
    return bases


def _resolve_from_common_paths() -> tuple[list[str] | None, str]:
    names = ("orn", "orn.exe")
    for name in names:
        found = shutil.which(name)
        if found:
            return [found], f"path:{name}"

    rel_candidates = [
        Path("ORN") / "orn",
        Path("ORN") / "orn.exe",
        Path("ORN") / "orn.py",
        Path("orn.py"),
        Path("engine") / "cli.py",
        Path("ORN") / "engine" / "cli.py",
    ]

    for base in _candidate_bases():
        for rel in rel_candidates:
            candidate = (base / rel).resolve()
            if not candidate.exists():
                continue
            if candidate.suffix.lower() == ".py":
                return [sys.executable, str(candidate)], f"scan:{candidate}"
            return [str(candidate)], f"scan:{candidate}"

    return None, ""


def _resolve_orn_command() -> tuple[list[str] | None, str]:
    for resolver in (_resolve_from_env_cmd, _resolve_from_env_bin, _resolve_from_common_paths):
        command, source = resolver()
        if command:
            return command, source
    return None, ""


def _register_orn_location(command: list[str], source: str) -> None:
    reg_dir = Path(".doxoade")
    reg_dir.mkdir(parents=True, exist_ok=True)
    reg_file = reg_dir / "orn_registry.json"
    payload = {
        "updated_at_unix": int(time.time()),
        "source": source,
        "command": command,
    }
    reg_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dispatch_check_errors_to_orn(*, path: str, summary: dict[str, int], findings: list[dict[str, Any]]) -> list[BridgeAttempt]:
    """Encaminha erros do check ao ORN em dois modos: servidor e direto."""
    attempts: list[BridgeAttempt] = []

    if not _bridge_enabled():
        return [BridgeAttempt(mode="disabled", ok=False, detail="DOXOADE_ORN_BRIDGE=0")]

    total_errors = int(summary.get("errors", 0)) + int(summary.get("critical", 0))
    if total_errors <= 0:
        return [BridgeAttempt(mode="skipped", ok=True, detail="sem erros")]

    orn_cmd, source = _resolve_orn_command()
    if not orn_cmd:
        return [
            BridgeAttempt(
                mode="unavailable",
                ok=False,
                detail="ORN não localizado (defina ORN_CMD ou ORN_BIN, ou deixe 'orn' no PATH)",
            )
        ]

    _register_orn_location(orn_cmd, source)
    attempts.append(BridgeAttempt(mode="locator", ok=True, detail=f"{source} -> {' '.join(orn_cmd)}"))

    prompt = _build_prompt(path, summary, findings)
    timeout_s = int(os.environ.get("DOXOADE_ORN_TIMEOUT", "25"))

    server_cmd = [*orn_cmd, "server", "ask", prompt, "--tokens", "220"]
    ok, detail = _run_orn_cli(server_cmd, timeout_s)
    attempts.append(BridgeAttempt(mode="server", ok=ok, detail=detail))

    direct_cmd = [*orn_cmd, "think", prompt, "--direct", "--tokens", "220"]
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
