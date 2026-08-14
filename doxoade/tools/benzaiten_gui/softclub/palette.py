# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/palette.py
"""SOFTCLUB PALETTE — Gen X Soft Club.
Dicotomia Ma'at: day = pastéis frios claros | night = quentes + fortes.
Nada de branco puro nem preto puro: contraste por temperatura."""
from __future__ import annotations
from dataclasses import dataclass

def _hx(h: str):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

# ── Terreno p/ temas derivados de foto (SOFTCLUB_BG) ──────────────
def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

_DARK  = (22, 24, 28)      # quase-preto  (doutrina: nunca puro)
_LIGHT = (236, 240, 246)   # quase-branco (doutrina: nunca puro)

def _darken(c, t):  return _lerp(c, _DARK, t)
def _lighten(c, t): return _lerp(c, _LIGHT, t)
def _sat(c, t):
    """Empurra p/ longe do cinza: cor + saturada/+ forte sem estourar."""
    m = (c[0] + c[1] + c[2]) / 3.0
    return tuple(max(0, min(255, int(m + (ch - m) * (1.0 + t)))) for ch in c)


def build_photo_theme(pal, base_name='day'):
    """Theme harmonizado com a foto.
    Passo 1: night usa a mesma paleta (escurecida).
    Passo 2 (futuro): night usará paleta da imagem NEGATIVA."""
    avg = tuple(pal.get('avg', (128, 128, 128)))
    dom = [tuple(c) for c in pal.get('dominant', [])] or [avg]
    vib = tuple(pal.get('vibrant', dom[0]))
    d2  = dom[1] if len(dom) > 1 else dom[0]

    if base_name == 'night':
        panel = (24, 28, 40)
        # tinta bem clara c/ tint da vibrante ("saturada clara"); muted ainda clara
        ink       = (226, 232, 242)            # neutro frio claro (corpo)
        ink_muted = (148, 158, 176)
        accent    = _sat(_lerp(vib, _LIGHT, 0.30), 0.5)   # vibrant só p/ títulos
        accent2   = _sat(_lerp(d2,  _LIGHT, 0.45), 0.45)
        return Theme(
            name='night-foto',
            top=_darken(dom[0], 0.65),  bottom=_darken(dom[-1], 0.75),
            ink=ink, ink_muted=ink_muted,
            accent=accent, accent2=accent2,
            haze=_darken(avg, 0.80),
            panel=panel, panel_edge=_darken(panel, 0.35),
            horizon_light=_darken(avg, 0.60), horizon_dark=_darken(avg, 0.72),
            tubes=False,
        )
    panel = (206, 218, 234)
    # tinta bem escura c/ tint da vibrante; muted ainda escura
    ink       = (16, 24, 38)                   # neutro frio bem escuro (corpo)
    ink_muted = (44, 58, 78)
    accent    = _sat(_lerp(vib, _DARK, 0.45), 0.45)   # vibrant só p/ títulos
    accent2   = _sat(_lerp(d2,  _DARK, 0.55), 0.35)
    return Theme(
        name='day-foto',
        top=_sat(_lighten(dom[0], 0.28), 0.35),  bottom=_sat(_lighten(dom[-1], 0.14), 0.45),
        ink=ink, ink_muted=ink_muted,
        accent=accent, accent2=accent2,
        haze=_darken(avg, 0.70),
        panel=panel, panel_edge=_darken(panel, 0.22),
        horizon_light=_darken(avg, 0.30), horizon_dark=_darken(avg, 0.50),
        tubes=False,
    )


_PHOTO_CACHE = {}

def photo_theme_for(base_name, pal):
    key = (base_name, tuple(pal.get('avg', ())), tuple(pal.get('vibrant', ())))
    hit = _PHOTO_CACHE.get(key)
    if hit is None:
        hit = build_photo_theme(pal, base_name)
        _PHOTO_CACHE[key] = hit
    return hit

@dataclass(frozen=True)
class Theme:
    name: str
    top: tuple; bottom: tuple
    ink: tuple; ink_muted: tuple
    accent: tuple; accent2: tuple
    haze: tuple; panel: tuple; panel_edge: tuple
    horizon_light: tuple; horizon_dark: tuple
    tubes: bool = False

DAY = Theme(
    name='day',
    top=_hx('b9d4f0'), bottom=_hx('72a3d6'),          # X: mist blue → Y: lilás névoa
    ink=_hx('2a4f75'), ink_muted=_hx('202e3d'),
    accent=_hx('092542'), accent2=_hx('0c5b6b'),
    haze=_hx('000000'), panel=_hx('92b3d6'), panel_edge=_hx('7e9dbd'),
    horizon_light=_hx('677c91'), horizon_dark=_hx('21374f'),
    tubes=False,
)
NIGHT = Theme(
    name='night',
    top=_hx('1b1c24'), bottom=_hx('0b0c17'),         # A: plum quente → B: terracota
    ink=_hx('a8aabd'), ink_muted=_hx('888dbd'),
    accent=_hx('D9975F'), accent2=_hx('9CCFAF'),     # âmbar + verde-tubo
    haze=_hx('000000'), panel=_hx('414c57'), panel_edge=_hx('34404d'),
    horizon_light=_hx('262730'), horizon_dark=_hx('3a3b47'),
    tubes=True,
)
THEMES = {'day': DAY, 'night': NIGHT}