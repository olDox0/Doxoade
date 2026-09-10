# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/thumbnail_engine.py
"""
🖼️ DOXOADE THUMBNAIL ENGINE — Geração de Sidecars Binários DOXRLE1 (CAS V2.0).
Contrato imutável com suporte polimórfico a Dict/Dataclass (Zero-Breakage).
"""
from __future__ import annotations
import os
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# =============================================================================
# 📦 CONSTANTES GLOBAIS EXPORTADAS (CONTRATO DO __INIT__.PY)
# =============================================================================
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

PRESETS = {
    "card": {"max_w": 120, "max_h": 68, "color_tolerance": 6},
    "compact": {"max_w": 60, "max_h": 34, "color_tolerance": 8},
    "hd_preview": {"max_w": 240, "max_h": 136, "color_tolerance": 4},
}


@dataclass
class ThumbResult:
    ok: bool
    status: str
    rects: int = 0
    bytes: int = 0
    orig_w: int = 0
    orig_h: int = 0
    grid_w: int = 0
    grid_h: int = 0
    sidecar_path: Optional[Path] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.sidecar_path:
            d["sidecar_path"] = str(self.sidecar_path)
        return d

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"ThumbResult não possui o campo: {key}")


class ThumbnailEngine:
    HEADER_MAGIC = b"DOXRLE1"
    VERSION = 1
    PRESETS = PRESETS
    IMAGE_EXTS = IMAGE_EXTS

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root or os.getcwd()).resolve()

    def generate(
        self,
        image_path: Union[str, Path],
        preset: str = "card",
        force: bool = False
    ) -> ThumbResult:
        if not PIL_AVAILABLE:
            return ThumbResult(
                ok=False,
                status="NO_PILLOW",
                error="Biblioteca Pillow não instalada. Execute: pip install pillow"
            )

        img_p = Path(image_path).resolve()
        if not img_p.exists() or not img_p.is_file():
            return ThumbResult(ok=False, status="FILE_NOT_FOUND", error=f"Arquivo inexistente: {img_p}")

        sidecar_p = img_p.with_name(f"{img_p.stem}.thumb.rlebin")

        if not force and sidecar_p.exists():
            try:
                if sidecar_p.stat().st_mtime >= img_p.stat().st_mtime and sidecar_p.stat().st_size > 20:
                    return ThumbResult(
                        ok=True,
                        status="CACHE_HIT",
                        bytes=sidecar_p.stat().st_size,
                        sidecar_path=sidecar_p
                    )
            except OSError:
                pass

        cfg = PRESETS.get(preset, PRESETS["card"])
        max_w = cfg["max_w"]
        max_h = cfg["max_h"]
        tol = cfg["color_tolerance"]

        try:
            with Image.open(img_p) as img:
                img = img.convert("RGB")
                orig_w, orig_h = img.size

                ratio = min(max_w / max(1, orig_w), max_h / max(1, orig_h))
                target_w = max(4, int(orig_w * ratio))
                target_h = max(4, int(orig_h * ratio))

                resized = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
                pixels = resized.load()

                rects_payload = bytearray()
                rect_count = 0

                for y in range(target_h):
                    run_start = 0
                    cur_c = pixels[0, y]
                    run_len = 1

                    for x in range(1, target_w):
                        c = pixels[x, y]
                        if (
                            abs(c[0] - cur_c[0]) <= tol
                            and abs(c[1] - cur_c[1]) <= tol
                            and abs(c[2] - cur_c[2]) <= tol
                        ):
                            run_len += 1
                        else:
                            rects_payload.extend(struct.pack("<HHHBBB", run_start, y, run_len, cur_c[0], cur_c[1], cur_c[2]))
                            rect_count += 1
                            run_start = x
                            cur_c = c
                            run_len = 1

                    rects_payload.extend(struct.pack("<HHHBBB", run_start, y, run_len, cur_c[0], cur_c[1], cur_c[2]))
                    rect_count += 1

                header = struct.pack(
                    "<7sBHHHHI",
                    self.HEADER_MAGIC,
                    self.VERSION,
                    target_w,
                    target_h,
                    orig_w,
                    orig_h,
                    rect_count
                )

                full_data = header + rects_payload
                sidecar_p.write_bytes(full_data)

                return ThumbResult(
                    ok=True,
                    status="GENERATED",
                    rects=rect_count,
                    bytes=len(full_data),
                    orig_w=orig_w,
                    orig_h=orig_h,
                    grid_w=target_w,
                    grid_h=target_h,
                    sidecar_path=sidecar_p
                )

        except Exception as e:
            return ThumbResult(ok=False, status="ERROR", error=str(e), sidecar_path=sidecar_p)

    def scan(self, target_dir: Any = None, force: bool = False, **kwargs) -> Dict[str, Any]:
        """Varre e sincroniza thumbnails (imune a argumentos em formato dict)."""
        from .image_manager import ImageAssetManager
        if isinstance(target_dir, dict):
            force = target_dir.get("force", force)
            target_dir = None
        if not target_dir or not isinstance(target_dir, (str, Path)):
            root = Path(self.project_root).resolve()
        else:
            root = Path(target_dir).resolve()
        return ImageAssetManager.sync_project_thumbnails(root, force=force)

    def batch(self, target_dir: Any = None, force: bool = False, **kwargs) -> Dict[str, Any]:
        return self.scan(target_dir, force=force, **kwargs)


