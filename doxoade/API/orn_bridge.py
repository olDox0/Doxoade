# -*- coding: utf-8 -*-
"""Ponte ORN↔DOXOADE para encaminhar falhas do `doxoade check`."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
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


@dataclass
class ResolvedOrnCommand:
    command: list[str]
    workdir: str | None = None


def _bridge_enabled() -> bool:
    return os.environ.get("DOXOADE_ORN_BRIDGE", "1") not in {"0", "false", "False"}


def _build_prompt(path: str, summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    top_findings = findings[:3]
    findings_text = []
    for item in top_findings:
        findings_text.append(
            {
                "severity": item.get("severity"),
                "category": item.get("category"),
                "file": item.get("file"),
                "line": item.get("line"),
                "message": str(item.get("message", ""))[:180],
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


def _run_orn_cli(command: list[str], timeout_s: int, workdir: str | None = None) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(5, timeout_s),
            check=False,
            cwd=workdir,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, err or f"exit={proc.returncode}"

    out = (proc.stdout or "").strip()
    err_out = (proc.stderr or "").strip()
    if not out and err_out:
        low = err_out.lower()
        if "traceback" in low or "error" in low:
            return False, err_out[:180]
        return True, err_out[:180]
    if not out:
        return False, "sem stdout/stderr"

    # Evita falso-positivo de sucesso com retorno genérico.
    if out.lower() == "ok":
        return False, "resposta genérica 'ok' (sem conteúdo da IA)"

    preview = " ".join(line.strip() for line in out.splitlines() if line.strip())
    return True, preview[:180]


def _query_orn_server_tcp(prompt: str, max_tokens: int, timeout_s: int) -> tuple[bool, str]:
    """Consulta ORN server por TCP direto (compatível com engine/tools/server_client.py)."""
    host = os.environ.get("ORN_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("ORN_SERVER_PORT", "8371"))
    payload = (json.dumps({"prompt": prompt, "max_tokens": max_tokens}) + "\n").encode("utf-8")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Timeout curto só para conectar; leitura pode levar mais sem estourar.
            s.settimeout(max(1.0, min(5.0, float(timeout_s))))
            s.connect((host, port))
            s.settimeout(None)
            s.sendall(payload)

            data = bytearray()
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data.extend(chunk)
                if data.endswith(b"\n"):
                    break
    except OSError as exc:
        return False, f"tcp:{host}:{port} {exc}"

    try:
        resp = json.loads(data.decode("utf-8").strip())
    except Exception as exc:
        return False, f"tcp resposta inválida: {exc}"

    if not isinstance(resp, dict):
        return False, "tcp resposta não-dict"
    if resp.get("error"):
        return False, str(resp.get("error"))

    output = str(resp.get("output", "")).strip()
    if not output:
        return True, "ok"
    return True, output[:160].replace("\n", " ")


def _infer_workdir_for_path(path: Path) -> str | None:
    """Define cwd ideal para execução do ORN."""
    p = path.resolve()
    if p.name.lower() == "cli.py" and p.parent.name.lower() == "engine":
        return str(p.parent.parent)
    return str(p.parent)


def _command_from_path(path: Path) -> ResolvedOrnCommand | None:
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

    if p.name.lower() == "cli.py" and p.parent.name.lower() == "engine":
        project_root = p.parent.parent
        return ResolvedOrnCommand(
            command=[sys.executable, "-m", "engine.cli"],
            workdir=str(project_root),
        )

    if p.suffix.lower() == ".py":
        return ResolvedOrnCommand(
            command=[sys.executable, str(p)],
            workdir=_infer_workdir_for_path(p),
        )
    return ResolvedOrnCommand(command=[str(p)], workdir=str(p.parent))


def _resolve_from_env_cmd() -> tuple[ResolvedOrnCommand | None, str]:
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
        return ResolvedOrnCommand(
            command=[*token_path.command, *parsed[1:]],
            workdir=token_path.workdir,
        ), "env:ORN_CMD(cmd+path)"

    return ResolvedOrnCommand(command=parsed), "env:ORN_CMD"


def _resolve_from_env_bin() -> tuple[ResolvedOrnCommand | None, str]:
    raw_bin = os.environ.get("ORN_BIN", "").strip()
    if not raw_bin:
        return None, ""

    cmd_from_path = _command_from_path(Path(raw_bin.strip().strip('"')))
    if cmd_from_path:
        return cmd_from_path, "env:ORN_BIN(path)"

    resolved = shutil.which(raw_bin)
    if resolved:
        return ResolvedOrnCommand(command=[resolved], workdir=str(Path(resolved).parent)), "env:ORN_BIN(which)"
    return None, ""


def _candidate_bases() -> list[Path]:
    bases = [Path.cwd()]
    for parent in Path.cwd().parents:
        bases.append(parent)
    return bases


def _resolve_from_common_paths() -> tuple[ResolvedOrnCommand | None, str]:
    names = ("orn", "orn.exe")
    for name in names:
        found = shutil.which(name)
        if found:
            return ResolvedOrnCommand(command=[found], workdir=str(Path(found).parent)), f"path:{name}"

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
                return ResolvedOrnCommand(
                    command=[sys.executable, str(candidate)],
                    workdir=_infer_workdir_for_path(candidate),
                ), f"scan:{candidate}"
            return ResolvedOrnCommand(command=[str(candidate)], workdir=str(candidate.parent)), f"scan:{candidate}"

    return None, ""


def _resolve_orn_command() -> tuple[ResolvedOrnCommand | None, str]:
    for resolver in (_resolve_from_env_cmd, _resolve_from_env_bin, _resolve_from_common_paths):
        command, source = resolver()
        if command:
            return command, source
    return None, ""


def _register_orn_location(command: ResolvedOrnCommand, source: str) -> None:
    reg_dir = Path(".doxoade")
    reg_dir.mkdir(parents=True, exist_ok=True)
    reg_file = reg_dir / "orn_registry.json"
    payload = {
        "updated_at_unix": int(time.time()),
        "source": source,
        "command": command.command,
        "workdir": command.workdir,
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

    orn_target, source = _resolve_orn_command()
    if not orn_target:
        return [
            BridgeAttempt(
                mode="unavailable",
                ok=False,
                detail="ORN não localizado (defina ORN_CMD ou ORN_BIN, ou deixe 'orn' no PATH)",
            )
        ]

    _register_orn_location(orn_target, source)
    wd = f" (cwd={orn_target.workdir})" if orn_target.workdir else ""
    attempts.append(BridgeAttempt(mode="locator", ok=True, detail=f"{source} -> {' '.join(orn_target.command)}{wd}"))

    prompt = _build_prompt(path, summary, findings)
    timeout_s = int(os.environ.get("DOXOADE_ORN_TIMEOUT", "25"))
    max_tokens = int(os.environ.get("DOXOADE_ORN_MAX_TOKENS", "96"))

    # 1) canal servidor: TCP direto (estado real do servidor).
    ok, detail = _query_orn_server_tcp(prompt, max_tokens=max_tokens, timeout_s=timeout_s)
    if (not ok) and ("exceed context window" in detail.lower() or "context window" in detail.lower()):
        ok, detail = _query_orn_server_tcp(prompt, max_tokens=48, timeout_s=timeout_s)
    attempts.append(BridgeAttempt(mode="server", ok=ok, detail=detail))

    direct_cmd = [*orn_target.command, "think", prompt, "--direct", "--tokens", str(max_tokens)]
    ok, detail = _run_orn_cli(direct_cmd, timeout_s, workdir=orn_target.workdir)
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
