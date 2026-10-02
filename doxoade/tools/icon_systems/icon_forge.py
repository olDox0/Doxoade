# -*- coding: utf-8 -*-
# doxoade/tools/icon_systems/icon_forge.py
"""
🔨 HEFESTO — Icon Forge: PNG customizável → RLE (DOXRLE1) + fallback procedural.
Uso: python -m doxoade.tools.icon_systems.icon_forge
Lê (opcional): ~/.doxoade/assets/icons_src/<nome>.png  (16x16 RGBA, seus PNGs custom)
Gera:          ~/.doxoade/assets/icons/<nome>.icon.rlebin
"""
import struct
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("[ERRO] Pillow não instalado. Rode: pip install pillow")
    sys.exit(1)

HOME = Path.home()
SRC = HOME / ".doxoade" / "assets" / "icons_src"
OUT = HOME / ".doxoade" / "assets" / "icons"
SIZE = 16
W = (255, 255, 255, 255)

def procedural(name: str) -> Image.Image:
    """Desenha ícones minimalistas 16x16 se nenhum PNG custom existir."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if name == "leap":
        d.line([(2, 5), (10, 5)], W, 2); d.polygon([(10, 2), (14, 5), (10, 8)])
        d.line([(13, 11), (5, 11)], W, 2); d.polygon([(5, 8), (1, 11), (5, 14)])
    elif name == "lock":
        d.rectangle([4, 8, 11, 14], outline=W, width=2)
        d.arc([5, 2, 10, 9], 180, 0, fill=W, width=2)
    elif name == "note":
        d.rectangle([4, 2, 11, 13], outline=W, width=1)
        d.line([(6, 5), (9, 5)], W); d.line([(6, 8), (9, 8)], W); d.line([(6, 11), (8, 11)], W)
    elif name == "search":
        d.ellipse([3, 3, 10, 10], outline=W, width=2)
        d.line([(9, 9), (13, 13)], W, 2)
    elif name == "term":
        d.line([(3, 4), (7, 7), (3, 10)], W, 2)
        d.line([(8, 11), (13, 11)], W, 2)
    elif name == "check":
        d.line([(3, 8), (6, 11), (12, 4)], W, 2)
    elif name == "indent":
        d.line([(3, 3), (3, 12)], W, 2)
        d.line([(6, 5), (12, 5)], W); d.line([(9, 8), (12, 8)], W); d.line([(6, 11), (12, 11)], W)
    elif name == "scroll":
        d.rectangle([5, 2, 10, 13], outline=W, width=1)
        d.line([(6, 5), (9, 5)], W); d.line([(6, 8), (9, 8)], W)
    else:
        d.rectangle([3, 3, 12, 12], outline=W, width=2)
    return img

def encode_rle(img: Image.Image) -> bytes:
    """Encode DOXRLE1 pulando pixels transparentes (ícone recortado, sem fundo)."""
    px = img.convert("RGBA").load()
    w, h = img.size
    rects = []
    for y in range(h):
        x = 0
        while x < w:
            if px[x, y][3] >= 128:
                x0 = x
                r, g, b = px[x, y][0], px[x, y][1], px[x, y][2]
                while x < w and px[x, y][3] >= 128:
                    x += 1
                rects.append((x0, y, x - x0, r, g, b))
            else:
                x += 1
    header = struct.pack("<7sBHHHHI", b"DOXRLE1", 1, w, h, w, h, len(rects))
    body = b"".join(struct.pack("<HHHBBB", *rc) for rc in rects)
    return header + body

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    names = ["leap", "lock", "note", "search", "term", "check", "indent", "scroll"]
    made = 0
    for nm in names:
        src_png = SRC / f"{nm}.png"
        if src_png.exists():
            img = Image.open(src_png).convert("RGBA").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
            origin = "PNG custom"
        else:
            img = procedural(nm)
            origin = "procedural"
        (OUT / f"{nm}.icon.rlebin").write_bytes(encode_rle(img))
        print(f"  ✔ {nm:<8} [{origin}]")
        made += 1
    print(f"✔ [HEFESTO] {made} ícones forjados em: {OUT}")

if __name__ == "__main__":
    main()
