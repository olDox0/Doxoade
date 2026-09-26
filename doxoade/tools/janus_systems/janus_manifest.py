# -*- coding: utf-8 -*-
# doxoade/tools/janus_systems/janus_manifest.py
"""
🏛️ JANUS MANIFEST — Registro Persistente de Toolchain.
Evita re-varreduras de disco a cada comando com auto-validação de integridade.
"""
from __future__ import annotations

import os
import json
import time
import platform
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from .janus_cpu import JanusCPU
from .janus_detector import CompilerInfo, JanusDetector


class JanusManifest:
    """Gerencia o manifesto .doxoade/janus/compiler_manifest.json."""

    def __init__(self, project_root: Path):
        self.root = Path(project_root).resolve()
        self.manifest_file = self.root / ".doxoade" / "janus" / "compiler_manifest.json"

    def get_cached(self) -> Optional[CompilerInfo]:
        """Retorna o compilador em cache se o binário ainda existir fisicamente."""
        if not self.manifest_file.exists():
            return None

        try:
            with open(self.manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            c_path = data.get("compiler_path", "")
            if c_path and os.path.exists(c_path):
                return CompilerInfo(
                    compiler_path=c_path,
                    gpp_path=data.get("gpp_path"),
                    compiler_type=data.get("compiler_type", "gcc"),
                    version=data.get("version", "unknown"),
                    target_machine=data.get("target_machine", platform.machine()),
                    is_clang=data.get("is_clang", False),
                    supports_simd=data.get("supports_simd", True),
                    provider=data.get("provider", "manifest_cache")
                )
        except Exception:
            pass

        return None

    def save(self, info: CompilerInfo):
        """Grava os dados do compilador e da CPU detectada."""
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(info)
        
        # 🛑 INJETA O PERFIL DE CPU E FLAGS IDEAIS
        cpu_prof = JanusCPU.profile()
        payload["cpu_profile"] = asdict(cpu_prof)
        payload["station"] = platform.node().lower().replace(" ", "_").strip()
        payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def refresh(self) -> Optional[CompilerInfo]:
        """Força nova detecção no hospedeiro e atualiza o manifesto."""
        detector = JanusDetector()
        info = detector.detect(self.root)
        if info:
            self.save(info)
        return info
