# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/shell_resolver.py
"""
🐚 Shell Resolver — Detecção e Resolução de Shell por Plataforma.

Resolve o binário correto do shell com base na plataforma e preferência:
  - Windows: cmd (default), powershell, pwsh
  - Linux:   $SHELL, /bin/sh, /bin/ash (Alpine), /bin/bash
  - macOS:   $SHELL, /bin/zsh, /bin/bash

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from doxoade.tools.terminal_pty import PlatformKind, detect_platform


@dataclass
class ShellResolution:
    """Resultado da resolução de shell."""
    shell_id: str
    executable: str
    args: List[str] = field(default_factory=list)
    display_name: str = ""
    is_fallback: bool = False
    warning: Optional[str] = None

    @property
    def command_line(self) -> List[str]:
        return [self.executable] + self.args


# ──────────────────────────────────────────────────────────────────────────────
# WINDOWS SHELL RESOLUTION
# ──────────────────────────────────────────────────────────────────────────────

_WINDOWS_SHELLS = {
    "cmd": {
        "display": "CMD (Prompt de Comando)",
        "candidates": [
            lambda: os.environ.get("ComSpec", "cmd.exe"),
        ],
        "args": [],
    },
    "powershell": {
        "display": "Windows PowerShell",
        "candidates": [
            lambda: shutil.which("powershell.exe"),
            lambda: str(
                Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
            ),
        ],
        "args": ["-NoLogo", "-NoProfile"],
    },
    "pwsh": {
        "display": "PowerShell 7+ (pwsh)",
        "candidates": [
            lambda: shutil.which("pwsh.exe"),
            lambda: shutil.which("pwsh"),
        ],
        "args": ["-NoLogo", "-NoProfile"],
    },
}


def _resolve_windows_shell(shell_id: str) -> ShellResolution:
    """Resolve shell no Windows com fallback gracioso."""
    shell_config = _WINDOWS_SHELLS.get(shell_id)

    if shell_config is None:
        # Fallback para cmd
        shell_id = "cmd"
        shell_config = _WINDOWS_SHELLS["cmd"]

    for candidate_fn in shell_config["candidates"]:
        try:
            candidate = candidate_fn()
            if candidate and Path(candidate).exists():
                return ShellResolution(
                    shell_id=shell_id,
                    executable=candidate,
                    args=list(shell_config["args"]),
                    display_name=shell_config["display"],
                )
        except (TypeError, OSError):
            continue

    # Fallback: se PowerShell não encontrado, usa cmd
    if shell_id in ("powershell", "pwsh"):
        cmd_path = os.environ.get("ComSpec", "cmd.exe")
        return ShellResolution(
            shell_id="cmd",
            executable=cmd_path,
            args=[],
            display_name="CMD (fallback)",
            is_fallback=True,
            warning=(
                f"⚠ Shell '{shell_id}' não encontrado. "
                f"Usando cmd.exe como fallback."
            ),
        )

    return ShellResolution(
        shell_id=shell_id,
        executable="cmd.exe",
        args=[],
        display_name="CMD",
        is_fallback=True,
        warning="⚠ Nenhum shell Windows resolvido. Usando cmd.exe.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# UNIX SHELL RESOLUTION (Linux / Alpine / macOS)
# ──────────────────────────────────────────────────────────────────────────────

_UNIX_SHELL_PRIORITY = [
    "/bin/bash",
    "/bin/zsh",
    "/bin/sh",
    "/bin/ash",
    "/usr/bin/bash",
    "/usr/bin/zsh",
    "/usr/bin/sh",
]


def _resolve_unix_shell(shell_id: str) -> ShellResolution:
    """Resolve shell no Unix/Linux/Alpine/macOS."""

    # Se shell_id é um caminho absoluto, tenta usar diretamente
    if shell_id.startswith("/") and Path(shell_id).exists():
        name = Path(shell_id).stem
        return ShellResolution(
            shell_id=name,
            executable=shell_id,
            args=[],
            display_name=f"{name} (custom)",
        )

    # auto: tenta $SHELL primeiro
    if shell_id in ("auto", "default", ""):
        env_shell = os.environ.get("SHELL", "")
        if env_shell and Path(env_shell).exists():
            name = Path(env_shell).stem
            return ShellResolution(
                shell_id=name,
                executable=env_shell,
                args=[],
                display_name=f"{name} ($SHELL)",
            )

        # Fallback: percorre prioridades
        for candidate in _UNIX_SHELL_PRIORITY:
            if Path(candidate).exists():
                name = Path(candidate).stem
                return ShellResolution(
                    shell_id=name,
                    executable=candidate,
                    args=[],
                    display_name=f"{name}",
                )

        # Último recurso
        return ShellResolution(
            shell_id="sh",
            executable="/bin/sh",
            args=[],
            display_name="sh (fallback)",
            is_fallback=True,
            warning="⚠ Nenhum shell Unix encontrado. Tentando /bin/sh.",
        )

    # Shell específico solicitado
    shell_path = shutil.which(shell_id)
    if shell_path:
        return ShellResolution(
            shell_id=shell_id,
            executable=shell_path,
            args=[],
            display_name=f"{shell_id}",
        )

    # Fallback para /bin/sh
    return ShellResolution(
        shell_id="sh",
        executable="/bin/sh",
        args=[],
        display_name="sh (fallback)",
        is_fallback=True,
        warning=f"⚠ Shell '{shell_id}' não encontrado. Usando /bin/sh.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────────────

def resolve_shell(shell_id: str = "auto") -> ShellResolution:
    """
    Resolve o shell com base na plataforma e na preferência do usuário.

    Args:
        shell_id: Identificador do shell desejado.
                  Windows: "cmd", "powershell", "pwsh", "auto"
                  Linux:   "auto", "/bin/bash", "/bin/sh", etc.

    Returns:
        ShellResolution com executável, args e metadados.
    """
    platform_kind = detect_platform()

    if platform_kind == PlatformKind.WINDOWS:
        if shell_id in ("auto", "default", ""):
            shell_id = "cmd"  # Default conservador no Windows
        return _resolve_windows_shell(shell_id)
    else:
        return _resolve_unix_shell(shell_id)


def list_available_shells() -> List[ShellResolution]:
    """Lista todos os shells disponíveis na plataforma atual."""
    platform_kind = detect_platform()
    available = []

    if platform_kind == PlatformKind.WINDOWS:
        for shell_id in ("cmd", "powershell", "pwsh"):
            resolution = resolve_shell(shell_id)
            if not resolution.is_fallback:
                available.append(resolution)
    else:
        for shell_id in ("auto", "bash", "zsh", "sh", "ash"):
            resolution = resolve_shell(shell_id)
            if not resolution.is_fallback:
                available.append(resolution)

    return available


def get_shell_description(resolution: ShellResolution) -> str:
    """Descrição humana do shell resolvido."""
    fallback_note = " [FALLBACK]" if resolution.is_fallback else ""
    args_str = " ".join(resolution.args) if resolution.args else ""
    return (
        f"{resolution.display_name}{fallback_note}"
        f" → {resolution.executable}"
        f"{' ' + args_str if args_str else ''}"
    )


__all__ = [
    "ShellResolution",
    "resolve_shell",
    "list_available_shells",
    "get_shell_description",
]
