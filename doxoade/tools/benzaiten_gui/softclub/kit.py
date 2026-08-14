# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/kit.py
"""SOFTCLUB KIT — primitivas de desenho sobre o DIB (GDI via DLL)."""
import os
import ctypes

_bound = False


def _bind(lib):
    global _bound
    if _bound:
        return
    lib.dxgui_fill_rect.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint
    ]
    lib.dxgui_fill_rect.restype = None
    lib.dxgui_draw_text.argtypes = [
        ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint, ctypes.c_int, ctypes.c_int,
    ]
    lib.dxgui_draw_text.restype = ctypes.c_int
    _bound = True


def _cref(rgb):
    """Converte (r, g, b) → COLORREF 0x00BBGGRR (ordem do GDI)."""
    r, g, b = rgb
    return (b << 16) | (g << 8) | r


def fill_rect(r, x, y, w, h, color):
    _bind(r.lib)
    r.lib.dxgui_fill_rect(x, y, w, h, _cref(color))


def draw_text(r, x, y, s, color, size=14, spacing=1):
    _bind(r.lib)
    return r.lib.dxgui_draw_text(
        str(s).encode('utf-8'), x, y, _cref(color), size, spacing
    )


def panel(r, x, y, w, h, fill, edge=None):
    """Painel com borda 1px na tinta @35% — estética Soft Club."""
    fill_rect(r, x, y, w, h, fill)
    if edge:
        fill_rect(r, x, y, w, 1, edge)
        fill_rect(r, x, y + h - 1, w, 1, edge)
        fill_rect(r, x, y, 1, h, edge)
        fill_rect(r, x + w - 1, y, 1, h, edge)
        
def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def row_gradient(r, x, y, w, h, c1, c2, slices=8):
    """Degrade horizontal fatiado — hook p/ estilos futuros (Frutiger Aero etc.)."""
    sw = max(1, w // slices)
    for i in range(slices):
        t = i / max(1, slices - 1)
        fill_rect(r, x + i * sw, y, sw + 1, h, lerp_color(c1, c2, t))

def measure_text(r, s, size=13, spacing=1):
    _bind(r.lib)
    try:
        fn = r.lib.dxgui_measure_text
        fn.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        fn.restype = ctypes.c_int
        return fn(str(s).encode('utf-8'), size, spacing)
    except AttributeError:
        s = str(s)
        n = len(s)
        if n == 0:
            return 0
        base = int(size * 0.60)
        return n * base + max(0, n - 1) * spacing

FX_ENABLED = os.environ.get("SOFTCLUB_FX", "1") != "0"


def _border(r, x, y, w, h, edge):
    if not edge:
        return
    fill_rect(r, x, y, w, 1, edge)
    fill_rect(r, x, y + h - 1, w, 1, edge)
    fill_rect(r, x, y, 1, h, edge)
    fill_rect(r, x + w - 1, y, 1, h, edge)


def vgradient(r, x, y, w, h, c1, c2, steps=8):
    """Degrade vertical simples, fatiado."""
    if w <= 0 or h <= 0:
        return

    steps = max(2, min(steps, h))
    band = max(1, h // steps)

    for i in range(steps):
        yy = y + i * band
        hh = band if i < steps - 1 else (y + h - yy)

        if hh <= 0:
            continue

        t = i / max(1, steps - 1)
        fill_rect(r, x, yy, w, hh, lerp_color(c1, c2, t))


GLASS_PAL = None
GLASS_BORDERS_ONLY = False
EDGE_TINT = None  # corpo transparente: só bordas

def panel_gradient(r, x, y, w, h, th, steps=8, edge=None, solid=False):
    """Painel c/ degradê | vidro fosco c/ GLASS_PAL | só bordas c/ GLASS_BORDERS_ONLY
    (solid=True força preenchimento — overlay de ajuda)."""
    if not FX_ENABLED:
        panel(r, x, y, w, h, th.panel, th.panel_edge)
        return
    if not (GLASS_BORDERS_ONLY and not solid):
        if GLASS_PAL:
            avg = tuple(GLASS_PAL.get('avg', (128, 128, 128)))
            dom = GLASS_PAL.get('dominant') or [avg]
            lig = tuple(dom[0])
            c1 = lerp_color(avg, th.panel, 0.42)
            c2 = lerp_color(avg, th.panel, 0.80)
            vgradient(r, x, y, w, h, c1, c2, steps=steps)
            spec = lerp_color(lig, (236, 240, 246), 0.55)
            fill_rect(r, x, y, w, 1, spec)
            fill_rect(r, x, y + 1, w, 1, lerp_color(spec, c1, 0.5))
        else:
            c1 = lerp_color(th.panel, th.ink_muted, 0.14)
            c2 = lerp_color(th.panel, th.bottom, 0.38)
            vgradient(r, x, y, w, h, c1, c2, steps=steps)
    if edge:
        _border(r, x, y, w, h, edge)
        double_bevel(r, x + 1, y + 1, w - 2, h - 2, th, t=1)
    else:
        double_bevel(r, x, y, w, h, th, t=2)


def line_gradient(r, x, y, w, h, th, mode="normal"):
    """
    Degrade horizontal para linhas do editor.
    mode:
      normal   -> linha comum
      selected -> linha selecionada
      active   -> linha atual/cursor
    """
    if w <= 0 or h <= 0:
        return

    if not FX_ENABLED:
        if mode == "active":
            fill_rect(r, x, y, w, h, lerp_color(th.panel, th.accent, 0.20))
        elif mode == "selected":
            fill_rect(r, x, y, w, h, lerp_color(th.panel, th.accent2, 0.12))
        else:
            fill_rect(r, x, y, w, h, th.panel)
        return

    if mode == "active":
        c1 = lerp_color(th.panel, th.accent, 0.22)
        c2 = lerp_color(th.panel, th.accent2, 0.14)
    elif mode == "selected":
        c1 = lerp_color(th.panel, th.accent2, 0.14)
        c2 = lerp_color(th.panel, th.accent, 0.07)
    else:
#        c1 = lerp_color(th.panel, th.panel_edge, 0.08)
#        c2 = lerp_color(th.panel, th.panel_edge, 0.16)
        c1 = lerp_color(th.panel, th.ink_muted, 0.14)
        c2 = lerp_color(th.panel, th.bottom, 0.38)

    steps = 6
    sw = max(1, w // steps)

    for i in range(steps):
        t = i / max(1, steps - 1)
        xx = x + i * sw

        if i == steps - 1:
            ww = x + w - xx
        else:
            ww = sw + 1

        if ww <= 0:
            continue

        fill_rect(r, xx, y, ww, h, lerp_color(c1, c2, t))

def ring(r, x, y, w, h, c_top, c_bottom, c_side=None):
    """Anel 1px com degradê vertical (top/bottom diferentes, lados no meio)."""
    if w <= 0 or h <= 0:
        return
    c_side = c_side or lerp_color(c_top, c_bottom, 0.5)
    fill_rect(r, x, y, w, 1, c_top)
    fill_rect(r, x, y + h - 1, w, 1, c_bottom)
    if h > 2:
        fill_rect(r, x, y + 1, 1, h - 2, c_side)
        fill_rect(r, x + w - 1, y + 1, 1, h - 2, c_side)


def double_bevel(r, x, y, w, h, th, t=2):
    """Borda dupla Gen-X; com EDGE_TINT usa a dominante da foto:
    escura -> degradê branco (sheen) | clara -> claro topo / escuro base."""
    if EDGE_TINT:
        lum = (EDGE_TINT[0] * 299 + EDGE_TINT[1] * 587 + EDGE_TINT[2] * 114) // 1000
        if lum < 96:
            light = lerp_color(EDGE_TINT, (250, 252, 255), 0.78)
            mid   = lerp_color(EDGE_TINT, (250, 252, 255), 0.42)
            dark  = lerp_color(EDGE_TINT, (250, 252, 255), 0.18)
        else:
            light = lerp_color(EDGE_TINT, (255, 255, 255), 0.40)
            mid   = tuple(EDGE_TINT)
            dark  = lerp_color(EDGE_TINT, (18, 20, 26), 0.38)
    else:
        light = lerp_color(th.panel, th.ink_muted, 0.32)
        mid   = light
        dark  = lerp_color(th.panel_edge, th.bottom, 0.50)
    ring(r, x, y, w, h, light, mid)
    if t >= 2:
        ring(r, x + 1, y + 1, w - 2, h - 2,
             mid, lerp_color(mid, th.panel, 0.45))
    ring(r, x + t, y + t, w - 2 * t, h - 2 * t,
         lerp_color(dark, th.panel, 0.25),
         dark)
    if t >= 2:
        ring(r, x + t + 1, y + t + 1, w - 2 * (t + 1), h - 2 * (t + 1),
             dark,
             lerp_color(dark, th.bottom, 0.30))
