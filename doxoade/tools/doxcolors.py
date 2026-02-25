# -*- coding: utf-8 -*-
# doxoade/tools/doxcolors.py
"""
Doxcolors – Colorama-Compatible ANSI Engine
Versão: 1.5

✔ 100% compatível com sintaxe Colorama
✔ Fore.RED + "texto" + Style.RESET_ALL
✔ f-strings
✔ print(Fore.RED, "texto")
✔ Zero vazamento ANSI
✔ Mais leve que Colorama
✔ Windows / Linux
✔ Zero dependências externas
"""

import os
import sys
import builtins

# ============================================================
# DETECÇÃO ANSI REAL (Windows + Unix)
# ============================================================

def _ansi_enabled():
    if os.name != "nt":
        return sys.stdout.isatty()

    return (
        sys.stdout.isatty()
        or "ANSICON" in os.environ
        or "WT_SESSION" in os.environ
        or os.environ.get("TERM_PROGRAM") == "vscode"
    )

ANSI_ENABLED = _ansi_enabled()

# ============================================================
# HABILITA ANSI NO WINDOWS
# ============================================================

if os.name == "nt" and ANSI_ENABLED:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass

# ============================================================
# ANSI STRING (COMPATÍVEL COM COLORAMA)
# ============================================================

class AnsiCode(str):
    __slots__ = ()

    def __new__(cls, code: str):
        if not ANSI_ENABLED:
            return str.__new__(cls, "")
        return str.__new__(cls, f"\033[{code}m")

# ============================================================
# PALETAS
# ============================================================

class Fore:
    BLACK   = AnsiCode("30")
    RED     = AnsiCode("31")
    GREEN   = AnsiCode("32")
    YELLOW  = AnsiCode("33")
    BLUE    = AnsiCode("34")
    MAGENTA = AnsiCode("35")
    CYAN    = AnsiCode("36")
    WHITE   = AnsiCode("37")
    RESET   = AnsiCode("0")

    LIGHTBLACK_EX   = AnsiCode("90")
    LIGHTRED_EX     = AnsiCode("91")
    LIGHTGREEN_EX   = AnsiCode("92")
    LIGHTYELLOW_EX  = AnsiCode("93")
    LIGHTBLUE_EX    = AnsiCode("94")
    LIGHTMAGENTA_EX = AnsiCode("95")
    LIGHTCYAN_EX    = AnsiCode("96")
    LIGHTWHITE_EX   = AnsiCode("97")


class Back:
    BLACK   = AnsiCode("40")
    RED     = AnsiCode("41")
    GREEN   = AnsiCode("42")
    YELLOW  = AnsiCode("43")
    BLUE    = AnsiCode("44")
    MAGENTA = AnsiCode("45")
    CYAN    = AnsiCode("46")
    WHITE   = AnsiCode("47")
    RESET   = AnsiCode("0")


class Style:
    DIM       = AnsiCode("2")
    NORMAL    = AnsiCode("22")
    BRIGHT    = AnsiCode("1")
    ITALIC    = AnsiCode("3")
    UNDERLINE = AnsiCode("4")
    RESET_ALL = AnsiCode("0")

# ============================================================
# RGB / HEX (igual Colorama, mas leve)
# ============================================================

def rgb(r, g, b):
    return AnsiCode(f"38;2;{r};{g};{b}")

def bg_rgb(r, g, b):
    return AnsiCode(f"48;2;{r};{g};{b}")

def hex(hex_code: str):
    hex_code = hex_code.lstrip("#")
    if len(hex_code) != 6:
        return AnsiCode("0")
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    return rgb(r, g, b)

# ============================================================
# PRINT SEGURO (RESET AUTOMÁTICO)
# ============================================================

_original_print = builtins.print

def safe_print(*args, **kwargs):
    _original_print(*args, **kwargs)
    if ANSI_ENABLED:
        _original_print("\033[0m", end="")

builtins.print = safe_print

# ============================================================
# API DE COMPATIBILIDADE
# ============================================================

class DoxColors:
    Fore = Fore
    Back = Back
    Style = Style
    rgb = staticmethod(rgb)
    bg_rgb = staticmethod(bg_rgb)
    hex = staticmethod(hex)

colors = DoxColors