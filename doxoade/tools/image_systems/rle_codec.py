# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/rle_codec.py
"""
🖼️ RLE CODEC V1.0 — Codec binário de thumbnails (bordas contíguas / Zero-Seams).

Objetivo:
    Serializar runs de pixels (rects) consumidos pelos módulos 19a/19c do Lite XL,
    substituindo o parsing de texto linha-a-linha por leitura binária única
    (string.unpack no lado Lua).

Planos (ProDeNov 1.2.1):
    Plano A (principal): formato binário DOXRLE1 (little-endian, 9 bytes/rect).
    Plano B (fallback) : texto CSV legado "x,y,w,r,g,b" (compatível com 19a/19c atuais).
    Plano C (emergência): lista vazia de rects — a UI renderiza placeholder, nunca crasha.

Formato binário:
    Header : magic(7s) version(B) grid_w(H) grid_h(H) orig_w(H) orig_h(H) count(I) = 20B
    Registro: x(H) y(H) w(H) r(B) g(B) b(B) = 9B
"""
from __future__ import annotations

import struct
from typing import List, Sequence, Tuple

MAGIC = b"DOXRLE1"
VERSION = 1
_HEADER = struct.Struct("<7sBHHHHI")
_RECORD = struct.Struct("<HHHBBB")

Rect = Tuple[int, int, int, Tuple[int, int, int]]  # (x, y, largura, (r, g, b))


class RleCodec:
    """Codec estatal (sem estado) de RLE quantizado."""

    @staticmethod
    def quantize_color(color: Sequence[int], levels: int = 32) -> Tuple[int, int, int]:
        """Quantiza cor para o centro do bucket (levels por canal).

        Por quê: cores quase idênticas (gradientes, ruído de screenshot) fundem-se
        em blocos RLE maiores, reduzindo o nº de rects em ~40-60%.
        """
        step = 256 // levels
        out = []
        for c in color[:3]:
            bucket = min(levels - 1, int(c) // step)
            out.append(min(255, bucket * step + step // 2))
        return (out[0], out[1], out[2])

    @staticmethod
    def build_runs(flat_pixels: Sequence[Sequence[int]], width: int, height: int,
                   tolerance: int = 4, levels: int = 32) -> List[Rect]:
        """Plano A: RLE por linha sobre lista plana de pixels (w*h tuplas RGB).

        Fluxo: quantiza -> compara com tolerância -> fecha run por linha.
        """
        rects: List[Rect] = []
        for y in range(height):
            row = flat_pixels[y * width:(y + 1) * width]
            if not row:
                continue
            cur = RleCodec.quantize_color(row[0], levels)
            run_x, run_len = 0, 1
            for x in range(1, width):
                c = RleCodec.quantize_color(row[x], levels)
                if (abs(c[0] - cur[0]) <= tolerance and abs(c[1] - cur[1]) <= tolerance
                        and abs(c[2] - cur[2]) <= tolerance):
                    run_len += 1
                else:
                    rects.append((run_x, y, run_len, cur))
                    run_x, cur, run_len = x, c, 1
            rects.append((run_x, y, run_len, cur))
        return rects

    @staticmethod
    def encode_binary(grid_w: int, grid_h: int, orig_w: int, orig_h: int,
                      rects: Sequence[Rect]) -> bytes:
        """Plano A: empacota header + registros em bytes little-endian."""
        parts = [_HEADER.pack(MAGIC, VERSION,
                              min(grid_w, 65535), min(grid_h, 65535),
                              min(orig_w, 65535), min(orig_h, 65535),
                              len(rects))]
        for x, y, w, color in rects:
            parts.append(_RECORD.pack(min(x, 65535), min(y, 65535), min(w, 65535),
                                      color[0], color[1], color[2]))
        return b"".join(parts)

    @staticmethod
    def decode_binary(data: bytes):
        """Plano A: decodifica bytes -> (grid_w, grid_h, orig_w, orig_h, rects).

        Levanta ValueError se magic/versão inválidos (chamador cai no Plano B).
        """
        if len(data) < _HEADER.size:
            raise ValueError("RLE binário truncado")
        magic, ver, gw, gh, ow, oh, count = _HEADER.unpack_from(data, 0)
        if magic != MAGIC:
            raise ValueError(f"Magic inválido: {magic!r}")
        if ver != VERSION:
            raise ValueError(f"Versão não suportada: {ver}")
        if count > 200000:
            raise ValueError(f"Contagem absurda (corrupção?): {count}")
        rects: List[Rect] = []
        off = _HEADER.size
        for _ in range(count):
            x, y, w, r, g, b = _RECORD.unpack_from(data, off)
            off += _RECORD.size
            rects.append((x, y, w, (r, g, b)))
        return gw, gh, ow, oh, rects

    @staticmethod
    def encode_text(rects: Sequence[Rect]) -> str:
        """Plano B: serializa CSV legado (uma linha por rect)."""
        return "\n".join(f"{x},{y},{w},{c[0]},{c[1]},{c[2]}" for x, y, w, c in rects)

    @staticmethod
    def decode_text(text: str) -> List[Rect]:
        """Plano B: parseia CSV legado tolerando linhas corrompidas."""
        rects: List[Rect] = []
        for line in text.splitlines():
            p = line.split(",")
            if len(p) == 6:
                try:
                    rects.append((int(p[0]), int(p[1]), int(p[2]),
                                  (int(p[3]), int(p[4]), int(p[5]))))
                except ValueError:
                    continue
        return rects
