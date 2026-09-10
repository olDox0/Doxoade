# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/dox_image_bridge.py
"""
🖼️ DOX-IMAGE BRIDGE & CAS INGESTION ENGINE (V2.3 Native Lua Tables)
- Gera .meta.lua nativo (Zero parsing regex no Lite XL / C-speed dofile).
- Matriz RLE de cores comprimida para renderização gráfica imediata.
- Cópia nativa de volta para o clipboard do Windows (CF_DIB) e Linux (xclip).
"""
from __future__ import annotations
import io
import os
import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from PIL import ImageGrab, Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


def _get_clipboard_image_fallback() -> Optional[Image.Image]:
    """Captura bitmap com retentativas para garantir leitura de PrintScreen."""
    if not PILLOW_AVAILABLE:
        return None
    for _ in range(3):
        try:
            data = ImageGrab.grabclipboard()
            if isinstance(data, Image.Image):
                return data
            elif isinstance(data, list):
                valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tiff"}
                for item in data:
                    p = Path(str(item))
                    if p.exists() and p.is_file() and p.suffix.lower() in valid_exts:
                        return Image.open(p)
        except Exception:
            pass
        time.sleep(0.08)
    return None


def copy_image_to_clipboard(image_filename_or_path: str, project_root: Optional[str] = None) -> Dict[str, Any]:
    """Copia a imagem CAS salva de volta para o clipboard como bitmap nativo."""
    proj_path = Path(project_root) if project_root else Path.cwd()
    p = Path(image_filename_or_path)
    if not p.is_absolute():
        p = proj_path / ".doxoade" / "assets" / "images" / p.name

    if not p.exists():
        return {"status": "ERROR", "error": f"Arquivo não encontrado: {p}"}

    if sys.platform == "win32":
        try:
            from PIL import Image
            img = Image.open(p)
            output = io.BytesIO()
            img.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]  # Remove header BMP de 14 bytes
            output.close()

            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            GMEM_MOVEABLE = 0x0002
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            p_mem = kernel32.GlobalLock(h_mem)
            ctypes.memmove(p_mem, data, len(data))
            kernel32.GlobalUnlock(h_mem)

            if user32.OpenClipboard(None):
                user32.EmptyClipboard()
                user32.SetClipboardData(8, h_mem)  # CF_DIB = 8
                user32.CloseClipboard()
                return {"status": "SUCCESS", "message": f"Imagem {p.name} copiada para o clipboard!"}
        except Exception as e:
            return {"status": "ERROR", "error": f"Falha ao copiar: {e}"}
    else:
        try:
            import subprocess
            subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-i", str(p)], check=True)
            return {"status": "SUCCESS", "message": f"Imagem {p.name} copiada!"}
        except Exception as e:
            return {"status": "ERROR", "error": f"Instale xclip: {e}"}

    return {"status": "ERROR", "error": "Plataforma não suportada."}


def capture_and_store_image(project_root: Optional[str] = None) -> Dict[str, Any]:
    """Captura imagem, salva no CAS e gera .meta.lua nativo."""
    if not PILLOW_AVAILABLE:
        return {"status": "ERROR", "error": "Pillow ausente no ambiente Python."}

    proj_path = Path(project_root) if project_root else Path.cwd()
    assets_dir = proj_path / ".doxoade" / "assets" / "images"
    assets_dir.mkdir(parents=True, exist_ok=True)

    img = _get_clipboard_image_fallback()
    if img is None:
        return {"status": "EMPTY", "error": "Nenhuma imagem encontrada na área de transferência."}

    buf = io.BytesIO()
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img.save(buf, format="PNG")
    else:
        img.convert("RGB").save(buf, format="PNG")
    png_bytes = buf.getvalue()

    img_hash = hashlib.sha256(png_bytes).hexdigest()[:12]
    filename = f"img_{img_hash}.png"
    target_file = assets_dir / filename
    target_file.write_bytes(png_bytes)

    w, h = img.size
    res_str = f"{w}x{h}"
    date_human = time.strftime("%Y-%m-%d %H:%M")
    tag = f"[DOX-IMG:{filename} | {res_str} | {date_human}]"

    # Miniatura RLE de 64 colunas
    thumb_w = min(64, max(32, int(w / 20)))
    thumb_h = max(18, int(thumb_w * (h / max(1, w))))
    thumb = img.resize((thumb_w, thumb_h), Image.Resampling.BILINEAR).convert("RGB")

    lua_rows = []
    for py in range(thumb_h):
        spans = []
        x = 0
        while x < thumb_w:
            r, g, b = thumb.getpixel((x, py))
            span_len = 1
            while (x + span_len) < thumb_w:
                nr, ng, nb = thumb.getpixel((x + span_len, py))
                if abs(r - nr) + abs(g - ng) + abs(b - nb) < 26:
                    span_len += 1
                else:
                    break
            spans.append(f"{{{x}, {span_len}, {{{r}, {g}, {b}, 255}}}}")
            x += span_len
        lua_rows.append(f"    {{ {', '.join(spans)} }},")

    meta_lua_file = assets_dir / f"img_{img_hash}.meta.lua"
    meta_lua_content = (
        "-- auto-generated by dox_image_bridge.py\n"
        "return {\n"
        f"  width = {w},\n"
        f"  height = {h},\n"
        f"  thumb_w = {thumb_w},\n"
        f"  thumb_h = {thumb_h},\n"
        "  spans = {\n"
        + "\n".join(lua_rows) + "\n"
        "  }\n"
        "}\n"
    )
    meta_lua_file.write_text(meta_lua_content, encoding="utf-8")

    return {
        "status": "SUCCESS",
        "filename": filename,
        "path": str(target_file),
        "resolution": res_str,
        "date": date_human,
        "tag": tag,
    }


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--copy":
        res = copy_image_to_clipboard(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ".")
        print(json.dumps(res, ensure_ascii=False))
    else:
        root_arg = sys.argv[1] if len(sys.argv) > 1 else "."
        res = capture_and_store_image(root_arg)
        print(json.dumps(res, ensure_ascii=False))
