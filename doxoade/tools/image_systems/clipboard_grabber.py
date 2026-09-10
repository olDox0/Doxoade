# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/clipboard_grabber.py
"""
🖼️ DOXOADE CLIPBOARD GRABBER — Captura Híbrida com Win32 DIB Fallback.
Captura PrintScreens (Win+Shift+S), Bitmaps da memória e arquivos do Explorer.
"""
import io
import sys
import time
import platform
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from PIL import ImageGrab, Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _grab_win32_dib() -> Optional[Any]:
    """Captura DIB direto da memória do Windows quando ImageGrab falha."""
    if platform.system() != "Windows" or not PIL_AVAILABLE:
        return None
    try:
        import ctypes
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32

        for _ in range(3):
            if u32.OpenClipboard(None):
                try:
                    # CF_DIB = 8, CF_DIBV5 = 17
                    h_data = u32.GetClipboardData(8) or u32.GetClipboardData(17)
                    if h_data:
                        p_data = k32.GlobalLock(h_data)
                        size = k32.GlobalSize(h_data)
                        if p_data and size > 0:
                            raw_dib = ctypes.string_at(p_data, size)
                            k32.GlobalUnlock(h_data)
                            # Constrói cabeçalho BMP (14 bytes) para o Pillow ler
                            header = b"BM" + (len(raw_dib) + 14).to_bytes(4, "little") + b"\x00\x00\x00\x00\x36\x00\x00\x00"
                            return Image.open(io.BytesIO(header + raw_dib))
                finally:
                    u32.CloseClipboard()
            time.sleep(0.05)
    except Exception:
        pass
    return None


def grab_image_hybrid() -> Dict[str, Any]:
    """
    Captura imagem da área de transferência com 3 camadas de resgate:
    1. Pillow ImageGrab padrão
    2. Win32 API DIB Memory Grab
    3. Lista de arquivos copiados do Explorer
    """
    if not PIL_AVAILABLE:
        return {"status": "ERROR", "error": "Pillow não instalado."}

    # Camada 1: ImageGrab
    try:
        data = ImageGrab.grabclipboard()
        if isinstance(data, Image.Image):
            return {"status": "SUCCESS", "type": "bitmap", "image": data}
        elif isinstance(data, list):
            valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}
            for item in data:
                p = Path(item)
                if p.suffix.lower() in valid_exts and p.exists():
                    img = Image.open(p)
                    return {"status": "SUCCESS", "type": "file", "image": img, "orig_path": str(p)}
    except Exception:
        pass

    # Camada 2: Win32 API DIB
    dib_img = _grab_win32_dib()
    if dib_img:
        return {"status": "SUCCESS", "type": "win32_dib", "image": dib_img}

    return {"status": "EMPTY", "error": "Nenhuma imagem na área de transferência. Tire um print com Win+Shift+S."}

def copy_image_to_clipboard_win32(image_path: str | Path) -> tuple[bool, str]:
    """
    Injeta uma imagem PNG como bitmap DIB na área de transferência do Windows x64.
    Totalmente blindado com wintypes para evitar truncamento de ponteiros de 64-bits.
    """
    img_p = Path(image_path).resolve()
    if not img_p.exists():
        return False, f"Arquivo não encontrado: {img_p}"

    if platform.system() != "Windows":
        return False, "Cópia direta para clipboard suportada nativamente no Windows."

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 🛡️ Tipagem estrita de 64 bits
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

        user32.OpenClipboard.restype = wintypes.BOOL
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        user32.EmptyClipboard.argtypes = []
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

        with Image.open(img_p) as img:
            output = io.BytesIO()
            img.convert("RGB").save(output, "BMP")
            # Remove o cabeçalho BMP de 14 bytes para obter o formato CF_DIB padrão
            dib_data = output.getvalue()[14:]

        for _ in range(5):
            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    h_glob = kernel32.GlobalAlloc(0x0002, len(dib_data))  # GMEM_MOVEABLE = 0x0002
                    if not h_glob:
                        return False, "Falha ao alocar memória global (GlobalAlloc)"
                    
                    p_glob = kernel32.GlobalLock(h_glob)
                    if not p_glob:
                        return False, "Falha ao travar memória (GlobalLock)"

                    ctypes.memmove(p_glob, dib_data, len(dib_data))
                    kernel32.GlobalUnlock(h_glob)

                    if not user32.SetClipboardData(8, h_glob):  # CF_DIB = 8
                        return False, "Falha ao definir dados no Clipboard (SetClipboardData)"

                    return True, f"Imagem copiada com sucesso: {img_p.name}"
                finally:
                    user32.CloseClipboard()
            time.sleep(0.04)

        return False, "Não foi possível abrir a área de transferência (OpenClipboard ocupado)"

    except Exception as e:
        return False, f"Exceção ao copiar para clipboard: {e}"

