# -*- coding: utf-8 -*-
"""
Doxoade Assembly Systems — Facade Pública.
Forja de baixo nível para NASM e GNU AS.
"""
from .asm_detector import AssemblyDetector, AssemblerInfo
from .asm_manifest import AssemblyManifest
from .asm_builder import AssemblyBuilder
from .asm_linker import AssemblyLinker
from .asm_engine import AssemblyEngine

__all__ = [
    "AssemblyDetector",
    "AssemblerInfo",
    "AssemblyManifest",
    "AssemblyBuilder",
    "AssemblyLinker",
    "AssemblyEngine",
]
