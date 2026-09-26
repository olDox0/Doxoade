# -*- coding: utf-8 -*-
# doxoade/tools/metalcraft/metal_toolchain.py
"""
Nexus Toolchain — Fachada de Compiladores (Janus Integrated).
Delega a detecção soberana ao janus_systems.
"""
from __future__ import annotations

import os
from pathlib import Path
from doxoade.tools.janus_systems import Janus


class NexusToolchain:
    """Especialista em detecção de compiladores e SDKs (Janus Adapter)."""

    def __init__(self):
        self.compiler_path = None
        self.type = None

    def detect(self) -> bool:
        """Descobre o compilador via Janus e injeta no PATH se necessário."""
        info = Janus.get_info()
        if info:
            self.compiler_path = info.compiler_path
            self.type = info.compiler_type
            Janus.ensure_active()
            return True
        return False

    def get_version(self) -> str:
        """Retorna a versão do compilador detectado pelo Janus."""
        info = Janus.get_info()
        return info.version if info else "N/A"
