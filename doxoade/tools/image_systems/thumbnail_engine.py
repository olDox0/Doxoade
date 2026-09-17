# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/thumbnail_engine.py
"""
🖼️ DOXOADE THUMBNAIL ENGINE & RLE BINARY CODEC (DOXRLE1)
Compliance: ProDeNov 1.2.1, PASC-6.1, Limite < 50KB.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
PRESETS = {
    "card": {"max_w": 240, "max_h": 136, "tolerance": 4, "suffix": ".thumb.rlebin"},
    "canvas_hd": {"max_w": 1920, "max_h": 1080, "tolerance": 1, "suffix": ".canvas.rlebin"},
    "tiny": {"max_w": 60,  "max_h": 34,  "tolerance": 6, "suffix": ".tiny.rlebin"},
}


@dataclass
class ThumbResult:
    ok: bool
    status: str  # "GENERATED", "CACHE_HIT", "SKIPPED", "ERROR"
    rects: int = 0
    bytes: int = 0
    error: Optional[str] = None
    file_name: str = ""

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class RleCodec:
    MAGIC = b"DOXRLE1"
    VERSION = 1
    HEADER_STRUCT = "<7sBHHHHI"
    RECT_STRUCT = "<HHHBBB"

    @classmethod
    def encode_binary(
        cls,
        grid_w: int,
        grid_h: int,
        orig_w: int,
        orig_h: int,
        rects: List[Tuple[int, int, int, int, int, int]]
    ) -> bytes:
        count = len(rects)
        header = struct.pack(
            cls.HEADER_STRUCT,
            cls.MAGIC,
            cls.VERSION,
            grid_w,
            grid_h,
            orig_w,
            orig_h,
            count
        )
        body = bytearray()
        for rx, ry, rw, r, g, b in rects:
            body.extend(struct.pack(cls.RECT_STRUCT, rx, ry, rw, r, g, b))
        return header + bytes(body)

    @classmethod
    def build_runs(
        cls,
        pixels_flat: List[Tuple[int, int, int]],
        grid_w: int,
        grid_h: int,
        tolerance: int = 1
    ) -> List[Tuple[int, int, int, int, int, int]]:
        rects = []
        for y in range(grid_h):
            row_offset = y * grid_w
            if row_offset >= len(pixels_flat):
                break
            run_start_x = 0
            cur_c = pixels_flat[row_offset]
            run_len = 1

            for x in range(1, grid_w):
                idx = row_offset + x
                if idx >= len(pixels_flat):
                    break
                c = pixels_flat[idx]

                if (abs(c[0] - cur_c[0]) <= tolerance and
                    abs(c[1] - cur_c[1]) <= tolerance and
                    abs(c[2] - cur_c[2]) <= tolerance):
                    run_len += 1
                else:
                    rects.append((run_start_x, y, run_len, cur_c[0], cur_c[1], cur_c[2]))
                    run_start_x = x
                    cur_c = c
                    run_len = 1

            rects.append((run_start_x, y, run_len, cur_c[0], cur_c[1], cur_c[2]))
        return rects


class ThumbnailEngine:
    PRESETS = PRESETS
    IMAGE_EXTS = IMAGE_EXTS

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        self.project_root = Path(project_root or os.getcwd()).resolve()

    def generate(
        self,
        img_path: Union[str, Path],
        preset: str = "card",
        force: bool = False
    ) -> ThumbResult:
        src_path = Path(img_path).resolve()
        if not src_path.exists() or not src_path.is_file():
            return ThumbResult(ok=False, status="ERROR", error=f"Arquivo inexistente: {src_path}", file_name=src_path.name)

        p_cfg = self.PRESETS.get(preset, self.PRESETS["card"])
        sidecar_suffix = p_cfg.get("suffix", ".thumb.rlebin")
        sidecar_path = src_path.with_name(src_path.stem + sidecar_suffix)

        if not force and sidecar_path.exists():
            try:
                if sidecar_path.stat().st_mtime >= src_path.stat().st_mtime:
                    return ThumbResult(ok=True, status="CACHE_HIT", bytes=sidecar_path.stat().st_size, file_name=src_path.name)
            except Exception:
                pass

        try:
            from PIL import Image
        except ImportError:
            return ThumbResult(ok=False, status="SKIPPED", error="Pillow não instalada.", file_name=src_path.name)

        try:
            with Image.open(src_path) as img:
                img_rgb = img.convert("RGB")
                orig_w, orig_h = img_rgb.size
                if orig_w == 0 or orig_h == 0:
                    return ThumbResult(ok=False, status="ERROR", error="Dimensões nulas", file_name=src_path.name)

                target_w = min(p_cfg["max_w"], orig_w)
                target_h = max(10, int(orig_h * (target_w / orig_w)))

                if target_h > p_cfg["max_h"]:
                    target_h = p_cfg["max_h"]
                    target_w = max(10, int(orig_w * (target_h / orig_h)))

                resized = img_rgb.resize((target_w, target_h), Image.Resampling.BILINEAR)
                pixels_flat = list(resized.getdata())
                rects = RleCodec.build_runs(pixels_flat, target_w, target_h, tolerance=p_cfg.get("tolerance", 1))
                blob = RleCodec.encode_binary(target_w, target_h, orig_w, orig_h, rects)
                sidecar_path.write_bytes(blob)
                return ThumbResult(ok=True, status="GENERATED", rects=len(rects), bytes=len(blob), file_name=src_path.name)
        except Exception as e:
            return ThumbResult(ok=False, status="ERROR", error=str(e), file_name=src_path.name)

    def scan(self, target_dir: Any = None, force: bool = False, **kwargs) -> Dict[str, Any]:
        """Varre e sincroniza thumbnails (compatível com chamadas de deploy)."""
        from .image_manager import ImageAssetManager
        if isinstance(target_dir, dict):
            force = target_dir.get("force", force)
            target_dir = None
        root = Path(target_dir or self.project_root).resolve()
        return ImageAssetManager.sync_project_thumbnails(root, force=force)

    def batch(self, target_dir: Any = None, force: bool = False, **kwargs) -> Dict[str, Any]:
        return self.scan(target_dir, force=force, **kwargs)
