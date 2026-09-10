# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/dox_image_bridge.py
"""
🖼️ Ponte Autônoma de Captura e Indexação de Imagens CAS para o Doxoade.
Captura do clipboard do SO, grava em .doxoade/assets/images e retorna JSON com tag [DOX-IMG].
"""

import os
import sys
import time
import json
import hashlib
import platform
import datetime
from pathlib import Path
from io import BytesIO


def get_clipboard_image():
    # 1. Tenta Pillow ImageGrab
    try:
        from PIL import ImageGrab, Image
        for _ in range(3):
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return img
            elif isinstance(img, list) and len(img) > 0:
                p = Path(img[0])
                if p.is_file():
                    return Image.open(p)
            time.sleep(0.05)
    except Exception:
        pass

    # 2. Fallback ctypes Windows nativo
    if platform.system() == "Windows":
        try:
            import ctypes
            from PIL import Image
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            for _ in range(3):
                if user32.OpenClipboard(None):
                    CF_DIB = 8
                    CF_DIBV5 = 17
                    h_data = user32.GetClipboardData(CF_DIB) or user32.GetClipboardData(CF_DIBV5)
                    if h_data:
                        p_data = kernel32.GlobalLock(h_data)
                        size = kernel32.GlobalSize(h_data)
                        if p_data and size > 0:
                            import struct
                            raw_bytes = ctypes.string_at(p_data, size)
                            kernel32.GlobalUnlock(h_data)
                            user32.CloseClipboard()
                            header_size = struct.unpack("<I", raw_bytes[0:4])[0]
                            file_header = struct.pack("<2sIHHI", b"BM", 14 + size, 0, 0, 14 + header_size)
                            return Image.open(BytesIO(file_header + raw_bytes))
                    user32.CloseClipboard()
                time.sleep(0.05)
        except Exception:
            pass
    return None


def main():
    proj_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    assets_dir = Path(proj_dir) / ".doxoade" / "assets" / "images"
    assets_dir.mkdir(parents=True, exist_ok=True)

    img = get_clipboard_image()
    if not img:
        print(json.dumps({"status": "EMPTY", "error": "Área de transferência vazia."}))
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"img_{ts}.png"
    dest_png = assets_dir / filename
    dest_meta = assets_dir / f"img_{ts}.meta.json"

    # Salva imagem PNG
    img.save(str(dest_png), format="PNG")

    # Gera metadados forenses CAS
    meta = {
        "filename": filename,
        "width": img.size[0],
        "height": img.size[1],
        "resolution": f"{img.size[0]}x{img.size[1]}",
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.system()
    }

    with open(dest_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    tag = f"[DOX-IMG:{filename} | {meta['resolution']} | {ts}]"
    print(json.dumps({
        "status": "SUCCESS",
        "filename": filename,
        "resolution": meta["resolution"],
        "tag": tag
    }))


if __name__ == "__main__":
    main()
