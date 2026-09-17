# -*- coding: utf-8 -*-
# doxoade/tools/terminal_pty/__init__.py
"""
🖥️ DOXOADE TERMINAL PTY — Motor de Terminal Real Embutido.

Fornece um terminal interativo real (ConPTY no Windows, PTY no Unix)
comunicando-se com o Lite XL via Socket TCP Local autenticado.

Suporte:
  - Windows 10 (1809+) / Windows 11 → ConPTY via pywinpty
  - Linux (incl. Alpine/musl)       → pty stdlib
  - macOS                            → pty stdlib

Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations

import platform
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

__version__ = "1.0.0"
__author__ = "Doxoade Nexus Core / Hefesto & Hermes"


class PlatformKind(Enum):
    """Classificação da plataforma para seleção do backend PTY."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


def detect_platform() -> PlatformKind:
    """Detecta a plataforma atual de forma robusta."""
    system = platform.system().lower()
    if system == "windows":
        return PlatformKind.WINDOWS
    elif system == "linux":
        return PlatformKind.LINUX
    elif system == "darwin":
        return PlatformKind.MACOS
    return PlatformKind.UNKNOWN


def get_windows_build() -> Optional[int]:
    """
    Retorna o build number do Windows.
    ConPTY requer build >= 17763 (Windows 10 1809).
    """
    if detect_platform() != PlatformKind.WINDOWS:
        return None
    try:
        version = platform.version()  # ex: "10.0.19045"
        parts = version.split(".")
        if len(parts) >= 3:
            return int(parts[2])
    except (ValueError, IndexError):
        pass
    return None


def is_conpty_available() -> bool:
    """Verifica se o ConPTY está disponível no sistema atual."""
    if detect_platform() != PlatformKind.WINDOWS:
        return False
    build = get_windows_build()
    if build is None:
        return False
    return build >= 17763


def is_pywinpty_installed() -> bool:
    """Verifica se a biblioteca pywinpty está instalada."""
    try:
        import winpty  # noqa: F401
        return True
    except ImportError:
        return False


# Re-exports para uso conveniente
__all__ = [
    "PlatformKind",
    "detect_platform",
    "get_windows_build",
    "is_conpty_available",
    "is_pywinpty_installed",
]
