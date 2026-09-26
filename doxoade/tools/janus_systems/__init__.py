# -*- coding: utf-8 -*-
# doxoade/tools/janus_systems/__init__.py
"""
🏛️ JANUS TOOLCHAIN ECOSYSTEM — Gestão Soberana de Compiladores C/C++.
Substitui o w64devkit acoplado por detecção adaptativa em tempo real.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List

from .janus_detector import CompilerInfo, JanusDetector
from .janus_manifest import JanusManifest
from .janus_bridge import JanusBridge


class Janus:
    """Fachada pública central para todos os subsistemas do Doxoade."""

    _cached_bridge: Optional[JanusBridge] = None

    @classmethod
    def get_info(cls, project_root: Optional[Path] = None, force_scan: bool = False) -> Optional[CompilerInfo]:
        """Obtém informações do compilador ativo (via cache ou nova varredura)."""
        root = project_root or Path.cwd()
        manifest = JanusManifest(root)
        
        if not force_scan:
            cached = manifest.get_cached()
            if cached:
                return cached

        return manifest.refresh()

    @classmethod
    def get_bridge(cls, project_root: Optional[Path] = None) -> Optional[JanusBridge]:
        """Retorna a ponte de compilação pronta para uso."""
        info = cls.get_info(project_root)
        if not info:
            return None
        if not cls._cached_bridge or cls._cached_bridge.info.compiler_path != info.compiler_path:
            cls._cached_bridge = JanusBridge(info)
        return cls._cached_bridge

    @classmethod
    def ensure_active(cls, project_root: Optional[Path] = None) -> bool:
        """Injeta o compilador no PATH do ambiente atual."""
        bridge = cls.get_bridge(project_root)
        if bridge:
            bridge.ensure_in_path()
            return True
        return False

    @classmethod
    def get_compiler_path(cls) -> Optional[str]:
        """Retorna o caminho do binário gcc/clang ativo."""
        info = cls.get_info()
        return info.compiler_path if info else None
