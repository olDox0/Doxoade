# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/benzaiten_gui/softclub/bg_gen.py
"""
SOFTCLUB BG_GEN v2 — fundos procedurais Gen X Soft Club (máquina modesta friendly).
Estratégia: receita pesada (gradiente+haze+spill) em ¼ de resolução →
upscale nearest + dither Bayer (anti-banding/anti-upscale) →
detalhes finos (horizonte, tubos, grain) em resolução cheia.
Saída: RGB (3B/px) p/ PNG | BGRA (4B/px) p/ DIB GDI.
"""
from __future__ import annotations
import struct
import zlib
from pathlib import Path

_BAYER = (
    ( 0, 32,  8, 40,  2, 34, 10, 42), (48, 16, 56, 24, 50, 18, 58, 26),
    (12, 44,  4, 36, 14, 46,  6, 38), (60, 28, 52, 20, 62, 30, 54, 22),
    ( 3, 35, 11, 43,  1, 33,  9, 41), (51, 19, 59, 27, 49, 17, 57, 25),
    (15, 47,  7, 39, 13, 45,  5, 37), (63, 31, 55, 23, 61, 29, 53, 21),
)
_BAYER_ROW = tuple(tuple((v / 63.0 - 0.5) * 4.0 for v in row) for row in _BAYER)  # ±2


def _clamp(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def _lerp3(c1, c2, t):
    return (c1[0] + (c2[0] - c1[0]) * t,
            c1[1] + (c2[1] - c1[1]) * t,
            c1[2] + (c2[2] - c1[2]) * t)


def _noise_grid(seed, gw, gh):
    grid = []
    for y in range(gh):
        row = []
        for x in range(gw):
            h = (x * 73856093) ^ (y * 19349663) ^ (seed * 668265263)
            h = (h ^ (h >> 13)) * 1274126177
            row.append(((h ^ (h >> 16)) & 0xFFFF) / 65535.0)
        grid.append(row)
    return grid


def _value_noise(grid, x, y, cell):
    gw, gh = len(grid[0]), len(grid)
    gx, gy = x / cell, y / cell
    x0, y0 = int(gx) % gw, int(gy) % gh
    fx, fy = gx - int(gx), gy - int(gy)
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    r0, r1 = grid[y0], grid[(y0 + 1) % gh]
    a = r0[x0] + (r0[(x0 + 1) % gw] - r0[x0]) * fx
    b = r1[x0] + (r1[(x0 + 1) % gw] - r1[x0]) * fx
    return a + (b - a) * fy


def render_background(theme, width=800, height=600, seed=7, bgra=False):
    sw, sh = max(8, width // 4), max(8, height // 4)
    top, bottom, hz = theme.top, theme.bottom, theme.haze
    spill_on = bool(theme.tubes)
    g1 = _noise_grid(seed, 24, 18)
    g2 = _noise_grid(seed + 1, 64, 48)

    # ── 1) receita pesada em ¼ de resolução ──
    small = bytearray(sw * sh * 3)
    si = 0
    for sy in range(sh):
        ty0 = sy / (sh - 1)
        spill = 0.10 * ty0 if spill_on else 0.0
        for sx in range(sw):
            t = ty0 + (sx / (sw - 1) - 0.5) * 0.04
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
            r, g, b = _lerp3(top, bottom, t)
            xf, yf = sx * 4, sy * 4
            n = 0.65 * _value_noise(g1, xf, yf, 96) + 0.35 * _value_noise(g2, xf, yf, 32)
            ha = 0.06 * n
            r += (hz[0] - r) * ha; g += (hz[1] - g) * ha; b += (hz[2] - b) * ha
            if spill > 0.0:
                ac = theme.accent
                r += (ac[0] - r) * spill; g += (ac[1] - g) * spill; b += (ac[2] - b) * spill
            small[si] = _clamp(r); small[si + 1] = _clamp(g); small[si + 2] = _clamp(b)
            si += 3

    # ── 2) upscale nearest + dither Bayer ──
    stride = 4 if bgra else 3
    buf = bytearray(width * height * stride)
    colmap = tuple((x * sw) // width for x in range(width))
    rowmap = tuple((y * sh) // height for y in range(height))
    bi = 0
    for y in range(height):
        srow = rowmap[y] * sw * 3
        brow = _BAYER_ROW[y & 7]
        for x in range(width):
            s = srow + colmap[x] * 3
            d = brow[x & 7]
            r = _clamp(small[s] + d)
            g = _clamp(small[s + 1] + d)
            b = _clamp(small[s + 2] + d)
            if bgra:
                buf[bi] = b; buf[bi + 1] = g; buf[bi + 2] = r; buf[bi + 3] = 255
            else:
                buf[bi] = r; buf[bi + 1] = g; buf[bi + 2] = b
            bi += stride

    # ── 3) detalhes finos em resolução cheia (canon-safe p/ RGB e BGRA) ──
    def _mix(j, target, k):
        if bgra:
            B, G, R = buf[j], buf[j + 1], buf[j + 2]
        else:
            R, G, B = buf[j], buf[j + 1], buf[j + 2]
        R = _clamp(R + (target[0] - R) * k)
        G = _clamp(G + (target[1] - G) * k)
        B = _clamp(B + (target[2] - B) * k)
        if bgra:
            buf[j], buf[j + 1], buf[j + 2] = B, G, R
        else:
            buf[j], buf[j + 1], buf[j + 2] = R, G, B

    hy = int(height * 0.58)
    hl, hd = theme.horizon_light, theme.horizon_dark
    for y in (hy, hy + 1):
        base = y * width * stride
        for x in range(width):
            _mix(base + x * stride, hl, 0.55)
    for y in range(hy + 2, min(height, hy + 6)):
        base = y * width * stride
        for x in range(width):
            _mix(base + x * stride, hd, 0.10)
    if theme.tubes:
        a2 = theme.accent2
        for y in range(height):
            ty = y / (height - 1)
            tf = 0.0
            for tfy in (0.86, 0.93):
                dy = abs(ty - tfy)
                if dy <= 0.004: tf = max(tf, 0.30)
                elif dy < 0.03: tf = max(tf, 0.12 * (1 - dy / 0.03))
            if tf <= 0.0:
                continue
            base = y * width * stride
            for x in range(width):
                _mix(base + x * stride, a2, tf)
    # grain esparso (~1%)
    for i in range(0, width * height, 13):
        h = (i * 2654435761) ^ (seed * 40503)
        if (h & 0xFF) < 32:
            j = i * stride
            s = 3 if (h & 0x100) else -3
            buf[j] = _clamp(buf[j] + s)
            buf[j + 1] = _clamp(buf[j + 1] + s)
            buf[j + 2] = _clamp(buf[j + 2] + s)
    return bytes(buf)


def save_png(path, buf, width, height):
    """PNG truecolor puro-stdlib (zlib+struct)."""
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b''.join(b'\x00' + buf[y * width * 3:(y + 1) * width * 3] for y in range(height))
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6))
    png += chunk(b'IEND', b'')
    Path(path).write_bytes(png)