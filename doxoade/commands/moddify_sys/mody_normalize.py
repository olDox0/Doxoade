# -*- coding: utf-8 -*-
"""mody_normalize.py — saneamento de diffs sujos (mojibake, ANSI, CRLF)."""
from __future__ import annotations
import re

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
BOM = '\ufeff'

# Mapa literal de mojibake → UTF-8 correto
_MOJIBAKE = {
    # cp437/cp850 → UTF-8
    '\u251c\u00ba': '\u00e7',   # ├º → ç
    '\u251c\u00fa': '\u00e3',   # ├ú → ã
    '\u251c\u00ed': '\u00ed',   # ├í → í
    '\u251c\u00b7': '\u00f3',   # ├· → ó
    '\u251c\u2310': '\u00e9',   # ├⌐ → é
    '\u251c\u00e0': '\u00e0',   # ├à → à
    '\u251c\u00ea': '\u00ea',   # ├ê → ê
    '\u251c\u00f4': '\u00f4',   # ├Ô → ô
    '\u251c\u00f5': '\u00f5',   # ├Õ → õ
    '\u251c\u00fc': '\u00fc',   # ├Ü → ü
    # cp1251 → UTF-8 (Cyrillic as mojibake)
    '\u0413\u00a7': '\u00e7',   # Г§ → ç
    '\u0413\u0403': '\u00e3',   # ГЃ → ã
    '\u0413\u00a9': '\u00e9',   # Г© → é
    '\u0413\u0406': '\u00ed',   # ГІ → í
    '\u0413\u0407': '\u00f3',   # Г· → ó
    # cp1252 → UTF-8
    '\u00c3\u00a7': '\u00e7',   # Ã§ → ç
    '\u00c3\u00a3': '\u00e3',   # Ã£ → ã
    '\u00c3\u00a9': '\u00e9',   # Ã© → é
    # box drawing cp1251 → ASCII box
    '\u0432\u201d\u2013': '\u2500',   # в”— → ─
    '\u0432\u201d\u2014': '\u2500',   # в”— → ─
    '\u0432\u2013': '\u2502',         # в–  → │
    # emojis colapsados → espaço
    '\u0440\u04b9': ' ',
}

# Marcadores suspeitos (indicam mojibake residual)
_BAD_MARKERS = (
    '\u251c', '\u2510', '\u250c', '\u2514', '\u2518',
    '\u252c', '\u2534', '\u253c',
    '\u0413', '\u0496',
    '\u0432\u201d',
)


def _fix_mojibake(t: str) -> str:
    """Mojibake fix: literal map + round-trip por encoding."""
    if not t:
        return t

    # 1) Literal map
    for bad in sorted(_MOJIBAKE, key=len, reverse=True):
        if bad in t:
            t = t.replace(bad, _MOJIBAKE[bad])

    # Se não há marcadores suspeitos restantes, pronto
    if not any(m in t for m in _BAD_MARKERS):
        return t

    # 2) Round-trip por encoding (aceita só se reduz marcadores)
    for enc in ('cp1251', 'cp437', 'cp850', 'cp1252', 'latin-1'):
        try:
            cand = t.encode(enc).decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        cand_bad = sum(1 for m in _BAD_MARKERS if m in cand)
        t_bad = sum(1 for m in _BAD_MARKERS if m in t)
        if cand_bad < t_bad:
            return cand

    return t


def normalize_diff_text(raw: str) -> str:
    """Normalização canônica antes de qualquer parser."""
    t = raw.lstrip(BOM)
    t = ANSI_RE.sub('', t)
    t = _fix_mojibake(t)
    t = t.replace('\r\n', '\n').replace('\r', '\n')
    return t
