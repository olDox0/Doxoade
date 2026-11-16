# -*- coding: utf-8 -*-
"""Registry de parsers com confidence. Adicionar formato = @register.

NOTA: NÃO importa mody_patch no topo (evita circular import).
      Cada parser faz import lazy dentro do método parse().
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional, Protocol, Tuple, Type, runtime_checkable


@runtime_checkable
class Parser(Protocol):
    name: str
    def confidence(self, text: str) -> float: ...
    def parse(self, text: str, root: Path) -> list: ...


_REGISTRY: List[Type] = []


def register(cls):
    _REGISTRY.append(cls)
    return cls


# ── Parser 1: unified diff canônico ──────────────────────────────────
@register
class UnifiedParser:
    name = "unified"
    def confidence(self, text: str) -> float:
        if re.search(r'^diff --git ', text, re.M): return 1.0
        if re.search(r'^--- [ab]/', text, re.M) and \
           re.search(r'^\+\+\+ [ab]/', text, re.M):
            return 0.95
        if re.search(r'^--- \S', text, re.M) and \
           re.search(r'^\+\+\+ \S', text, re.M):
            return 0.8
        return 0.0
    def parse(self, text: str, root: Path):
        from doxoade.commands.moddify_sys.mody_patch import UnifiedDiffParser
        return UnifiedDiffParser.parse(text, root)


# ── Parser 2: decorado com pipe ──────────────────────────────────────
@register
class DecoratedPipeParser:
    name = "decorated-pipe"
    def confidence(self, text: str) -> float:
        pipes = len(re.findall(r'^\s*[-+]\s*\|\s', text, re.M))
        if pipes >= 2: return 0.85
        hints = len(re.findall(r'Mudan[çc]as perto da linha', text, re.I))
        if hints >= 1: return 0.75
        return 0.0
    def parse(self, text: str, root: Path):
        from doxoade.commands.moddify_sys.mody_freestyle import (
            FreestyleDiffParser,
        )
        return FreestyleDiffParser.parse(text, root)


# ── Parser 3: bloco markdown ```diff ────────────────────────────────
@register
class MarkdownFenceParser:
    name = "markdown-fence"
    def confidence(self, text: str) -> float:
        return 0.7 if re.search(r'```(?:diff|patch)\n', text) else 0.0
    def parse(self, text: str, root: Path):
        out = []
        for block in re.findall(r'```(?:diff|patch)\n(.*?)```', text, re.S):
            out.extend(UnifiedParser().parse(block, root))
        return out


# ── Parser 4: diff com padding de número ────────────────────────────
@register
class NumberedPaddingParser:
    name = "numbered-padding"
    def confidence(self, text: str) -> float:
        hits = len(re.findall(r'^\s*\d+\s*[|:]\s*[-+ ]', text, re.M))
        return 0.7 if hits >= 2 else 0.0
    def parse(self, text: str, root: Path):
        stripped = re.sub(r'^\s*\d+\s*[|:]\s?', '', text, flags=re.M)
        return UnifiedParser().parse(stripped, root)


# ── Parser 5: pares DE/PARA sem hunk ────────────────────────────────
@register
class LoosePairsParser:
    name = "loose-pairs"
    def confidence(self, text: str) -> float:
        hits = len(re.findall(r'^\s*(?:DE|PARA|OLD|NEW):', text, re.M))
        return 0.5 if hits >= 2 else 0.0
    def parse(self, text: str, root: Path):
        return []  # TODO quando aparecer caso real


# ── Dispatcher ──────────────────────────────────────────────────────
def detect_and_parse(
    raw: str, root: Path, force: Optional[str] = None
) -> Tuple[list, str, float]:
    from doxoade.commands.moddify_sys.mody_normalize import normalize_diff_text
    text = normalize_diff_text(raw)
    cands = []
    for cls in _REGISTRY:
        p = cls()
        if force and p.name != force:
            continue
        c = p.confidence(text)
        if c > 0:
            cands.append((c, p))
    cands.sort(key=lambda t: -t[0])
    for conf, parser in cands:
        try:
            patches = parser.parse(text, root)
        except Exception:
            continue
        if any(getattr(p, "hunks", None) for p in patches):
            return patches, parser.name, conf
    for conf, parser in cands:
        try:
            patches = parser.parse(text, root)
        except Exception:
            continue
        if patches:
            return patches, parser.name, conf
    return [], "none", 0.0
