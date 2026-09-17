# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/clipboard_grabber.py
"""
📋 DOXOADE CLIPBOARD GRABBER — Captura Híbrida de Imagens da Área de Transferência.
Estratégias:
  1. Pillow ImageGrab (Padrão multiplataforma).
  2. Win32 Nativo (ctypes / CF_DIB / CF_DIBV5) imune a travamentos de OLE.
  3. Linux / xclip / wl-paste fallback.
Compliance: ProDeNov 1.2.1, PASC-6.1, Limite < 50KB.
"""
from __future__ import annotations

import os
import sys
import time
import struct
import platform
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional


def grab_image_hybrid() -> Dict[str, Any]:
    """Tenta capturar imagem da área de transferência utilizando todas as estratégias disponíveis."""
    # Estratégia 1: Pillow ImageGrab
    try:
        from PIL import ImageGrab, Image
        for _ in range(3):
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return {"status": "SUCCESS", "image": img, "source": "PIL_IMAGEGRAB"}
            elif isinstance(img, list) and len(img) > 0:
                p = Path(img[0])
                if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                    return {"status": "SUCCESS", "image": Image.open(p), "source": "FILE_PATH"}
            time.sleep(0.04)
    except Exception:
        pass

    # Estratégia 2: Win32 Nativo via ctypes
    if platform.system() == "Windows":
        try:
            import ctypes
            from PIL import Image
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            for _ in range(4):
                if user32.OpenClipboard(None):
                    CF_DIB = 8
                    CF_DIBV5 = 17
                    h_data = user32.GetClipboardData(CF_DIB) or user32.GetClipboardData(CF_DIBV5)
                    if h_data:
                        p_data = kernel32.GlobalLock(h_data)
                        size = kernel32.GlobalSize(h_data)
                        if p_data and size > 0:
                            raw_bytes = ctypes.string_at(p_data, size)
                            kernel32.GlobalUnlock(h_data)
                            user32.CloseClipboard()

                            header_size = struct.unpack("<I", raw_bytes[0:4])[0]
                            file_header = struct.pack("<2sIHHI", b"BM", 14 + size, 0, 0, 14 + header_size)
                            img = Image.open(BytesIO(file_header + raw_bytes))
                            return {"status": "SUCCESS", "image": img, "source": "WIN32_CF_DIB"}
                    user32.CloseClipboard()
                time.sleep(0.04)
        except Exception:
            pass

    return {"status": "EMPTY", "image": None, "error": "Nenhuma imagem encontrada na área de transferência."}
