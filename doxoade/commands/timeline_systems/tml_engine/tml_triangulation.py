# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_engine/tml_triangulation.py
""" Timeline Nexus - Ma'at (Triangulação Visual).
Traduz números em linguagem visual: intensidade (0-4), glifo e chave de cor.
NÃO conhece ANSI/Rich: emite chaves semânticas — o display (Apolo) pinta. """

from dataclasses import dataclass, field
from typing import List

GLYPHS = ('░', '▒', '▓', '█', '█', '■')  # idle, low, mid, high, peak, alert


@dataclass
class HeatmapCell:
    y: int
    x: int
    count: int = 0
    errors: int = 0
    commands: List[str] = field(default_factory=list)
    intensity: int = 0

    @property
    def error_ratio(self) -> float:
        return self.errors / self.count if self.count else 0.0

    @property
    def is_alert(self) -> bool:
        """Triangulação: célula com volume e >30% de erros vira alerta."""
        return self.count >= 3 and self.error_ratio > 0.3

    @property
    def glyph(self) -> str:
        if self.is_alert:
            return GLYPHS[5]
        return GLYPHS[self.intensity]

    @property
    def color_key(self) -> str:
        if self.count == 0:
            return 'idle'
        if self.is_alert:
            return 'alert'
        return ('low', 'mid', 'high', 'peak')[max(0, self.intensity - 1)]


def assign_intensities(cells: List[HeatmapCell]) -> None:
    """Níveis 1-4 por quartis dinâmicos dos valores não-zero (distribuição real)."""
    nz = sorted(c.count for c in cells if c.count > 0)
    if not nz:
        return
    n = len(nz)
    if n < 4:
        top = nz[-1]
        for c in cells:
            if c.count > 0:
                c.intensity = 4 if c.count == top else 1
        return
    q1, q2, q3 = nz[n // 4], nz[n // 2], nz[(3 * n) // 4]
    for c in cells:
        if c.count == 0:
            continue
        if c.count <= q1:
            c.intensity = 1
        elif c.count <= q2:
            c.intensity = 2
        elif c.count <= q3:
            c.intensity = 3
        else:
            c.intensity = 4