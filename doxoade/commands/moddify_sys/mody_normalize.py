# -*- coding: utf-8 -*-
# doxoade\commands\moddify_sys\mody_normalize.py
"""Saneamento de diffs sujos. Rodar ANTES de qualquer parser."""
from __future__ import annotations
import re

ANSI_RE = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
BOM = '\ufeff'

# Mojibake: UTF-8 lido como cp1252/cp850
_MOJIBAKE = {
    '├º': 'ç', '├ú': 'ã', '├í': 'í', '├│': 'ó', '├⌐': 'é', '├á': 'à',
    '├¬': 'ê', '├ó': 'ô', '├╡': 'õ', '├╝': 'ü',
    '├ç': 'Ç', '├â': 'Ã', '├ì': 'Í', '├ë': 'É',
    'в”ң': '─', 'в”Җ': '─', 'в”Ӯ': '│', 'в”Ң': '┌', 'в”җ': '┐',
    'в”"': '└', 'в”ҳ': '┘', 'в”ң': '├', 'в”Ө': '┤', 'в”ҙ': '┴', 'в”¬': '┬',
    'в–': '█', 'вң': '✓', 'вңҳ': '✘', 'вҶі': '↳', 'вҖў': '•',
    'рҹ': ' ',  # emoji do bloco "©№" etc → espaço
}

def _fix_mojibake(t: str) -> str:
    for bad, good in _MOJIBAKE.items():
        if bad in t: t = t.replace(bad, good)
    return t

def normalize_diff_text(raw: str) -> str:
    t = raw.lstrip(BOM)
    t = ANSI_RE.sub('', t)
    t = _fix_mojibake(t)
    t = t.replace('\r\n', '\n').replace('\r', '\n')
    return t
