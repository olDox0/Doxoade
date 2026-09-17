# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/image_manager.py
"""
🖼️ DOXOADE IMAGE ASSET MANAGER — Sincronizador de Galeria e Auditor de Sidecars.
Compliance: ProDeNov 1.2.1, PASC-6.1, Limite < 50KB.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from .thumbnail_engine import ThumbnailEngine, ThumbResult


class ImageAssetManager:
    ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

    @classmethod
    def get_asset_directories(cls, project_root: Optional[Path] = None) -> List[Path]:
        root = Path(project_root or os.getcwd()).resolve()
        dirs = [
            root / ".doxoade" / "assets" / "images",
            root / "doxoade" / ".doxoade" / "assets" / "images",
            root / "assets" / "images",
            root / "docs" / "assets" / "images",
        ]
        return [d for d in dirs if d.exists() and d.is_dir()]

    @classmethod
    def sync_project_thumbnails(
        cls,
        project_root: Optional[Path] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        root = Path(project_root or os.getcwd()).resolve()
        engine = ThumbnailEngine(root)
        asset_dirs = cls.get_asset_directories(root)

        if not asset_dirs:
            default_dir = root / ".doxoade" / "assets" / "images"
            default_dir.mkdir(parents=True, exist_ok=True)
            asset_dirs = [default_dir]

        total_scanned = 0
        generated = 0
        cache_hits = 0
        failed = 0
        results: List[Dict[str, Any]] = []

        for adir in asset_dirs:
            for img_file in sorted(adir.iterdir()):
                if img_file.is_file() and img_file.suffix.lower() in cls.ALLOWED_IMAGE_EXTS:
                    total_scanned += 1
                    res = engine.generate(img_file, preset="card", force=force)
                    if res.ok:
                        if res.status == "GENERATED":
                            generated += 1
                        else:
                            cache_hits += 1
                    else:
                        failed += 1

                    results.append({
                        "file": img_file.name,
                        "status": res.status,
                        "bytes": res.bytes,
                        "rects": res.rects,
                        "error": res.error
                    })

        return {
            "total_scanned": total_scanned,
            "generated": generated,
            "cache_hits": cache_hits,
            "failed": failed,
            "results": results
        }
