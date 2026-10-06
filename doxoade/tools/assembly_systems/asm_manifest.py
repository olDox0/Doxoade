# -*- coding: utf-8 -*-
"""
[MA'AT] Assembly Manifest.
Cache JSON da toolchain detectada para evitar re-escaneamento.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from .asm_detector import AssemblyDetector, AssemblerInfo


class AssemblyManifest:
    MANIFEST_NAME = ".doxoade_assembly.json"
    CACHE_TTL_SECONDS = 3600  # 1 hora

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.manifest_path = self.root / self.MANIFEST_NAME
        self.data = self._load()

    def _load(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "assemblers": {}, "timestamp": None}
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": 1, "assemblers": {}, "timestamp": None}

    def save(self) -> None:
        self.data["timestamp"] = datetime.now().isoformat()
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def is_fresh(self) -> bool:
        ts = self.data.get("timestamp")
        if not ts:
            return False
        try:
            then = datetime.fromisoformat(ts)
            age = (datetime.now() - then).total_seconds()
            return age < self.CACHE_TTL_SECONDS
        except Exception:
            return False

    def refresh(self, force: bool = False) -> dict:
        """Re-detecta a toolchain e atualiza o cache."""
        if self.is_fresh() and not force:
            return self.data.get("assemblers", {})

        detected = AssemblyDetector.detect_all()
        serialized = {}
        for asm_type, info in detected.items():
            if info:
                serialized[asm_type] = {
                    "name": info.name,
                    "path": info.path,
                    "version": info.version,
                }
        self.data["assemblers"] = serialized
        self.save()
        return serialized

    def get(self, asm_type: str) -> Optional[AssemblerInfo]:
        """Retorna AssemblerInfo do cache (ou None)."""
        entry = self.data.get("assemblers", {}).get(asm_type)
        if not entry:
            return None
        return AssemblerInfo(
            name=entry["name"],
            path=entry["path"],
            version=entry["version"],
            raw_output="",
        )

    def get_for_extension(self, ext: str) -> Optional[AssemblerInfo]:
        ext = ext.lower()
        if ext == ".asm":
            return self.get("nasm")
        elif ext == ".s":
            return self.get("gas")
        return None
