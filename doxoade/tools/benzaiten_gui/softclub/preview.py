# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/preview.py
"""SOFTCLUB PREVIEW — Fase 0: PNGs day/night p/ validação visual."""
import hashlib
from pathlib import Path
from .bg_gen import render_background, save_png
from .palette import THEMES

def generate_previews(out_dir, width=800, height=600, seed=7):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    made = []
    for name, theme in THEMES.items():
        key = hashlib.sha256(repr(theme).encode()).hexdigest()[:8]
        raw_path = out / f"sc_{name}_{width}x{height}_{seed}_{key}.raw"
        if raw_path.exists():
            buf = raw_path.read_bytes()          # ⚡ cache hit: instantâneo
        else:
            buf = render_background(theme, width, height, seed)
            raw_path.write_bytes(buf)
        p = out / f'softclub_{name}.png'
        save_png(p, buf, width, height)
        made.append(p)
    return made