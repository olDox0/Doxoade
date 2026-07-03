# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_format_hbc4.py
"""
Hermes Binary Format v4 — Formato sem LZMA para módulos críticos.
Troca compressão por velocidade de carregamento.

Layout do arquivo HBC4:
┌─────────────────────────────────────────────────────────┐
│ [4B] Magic: b"HBC4"                                     │
│ [1B] Version: 0x04                                      │
│ [2B] token_count (uint16, little-endian)                │
│ [32B] bitmap_chars (256 bits)                           │
│ [N×] tokens:                                            │
│      [2B] token_int (uint16)                            │
│      [2B] pattern_len (uint16)                          │
│      [pattern_len B] pattern (UTF-8)                    │
├─────────────────────────────────────────────────────────┤
│ [4B] marshalled_size (uint32, little-endian)            │
│ [marshalled_size B] marshalled_bytecode (SEM LZMA)      │
└─────────────────────────────────────────────────────────┘

Vantagens vs HBC3:
• Zero decompressão LZMA (250ms → 0ms)
• Carregamento 3x mais rápido
• Desvantagem: arquivo 2-3x maior

Use para módulos críticos onde velocidade > tamanho.
"""
import struct
from typing import Dict, Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
MAGIC_HBC4 = b"HBC4"
VERSION = 4
BITMAP_SIZE = 32
TOKEN_MIN = 0x80
TOKEN_MAX = 0xFF

# ═══════════════════════════════════════════════════════════════════════
# BUILD (Compressor → Arquivo)
# ═══════════════════════════════════════════════════════════════════════
def build_header_hbc4(dynamic_encoder: Dict[str, int], marshalled_data: bytes) -> bytes:
    """Constrói header HBC4 + dados marshalled sem compressão."""
    if len(dynamic_encoder) > 65535:
        raise ValueError(f"token_count excede limite uint16: {len(dynamic_encoder)}")
    
    # 1. Constrói bitmap
    bitmap = bytearray(BITMAP_SIZE)
    for token_int in dynamic_encoder.values():
        if not (0x80 <= token_int <= 0xFF):
            raise ValueError(f"Token fora do range 0x80-0xFF: {token_int}")
        byte_idx = token_int // 8
        bit_idx = token_int % 8
        bitmap[byte_idx] |= (1 << bit_idx)
    
    # 2. Serializa tokens
    tokens_data = bytearray()
    for pattern, token_int in sorted(dynamic_encoder.items(), key=lambda x: x[1]):
        pattern_bytes = pattern.encode('utf-8')
        if len(pattern_bytes) > 65535:
            raise ValueError(f"Pattern muito longo: {len(pattern_bytes)} bytes")
        tokens_data += struct.pack('<HH', token_int, len(pattern_bytes))
        tokens_data += pattern_bytes
    
    # 3. Monta header completo + marshalled (SEM LZMA)
    header = (
        MAGIC_HBC4 +
        struct.pack('<B', VERSION) +
        struct.pack('<H', len(dynamic_encoder)) +
        bytes(bitmap) +
        bytes(tokens_data) +
        struct.pack('<I', len(marshalled_data)) +  # Tamanho do marshalled
        marshalled_data  # SEM compressão LZMA
    )
    
    return header

# ═══════════════════════════════════════════════════════════════════════
# PARSE (Arquivo → Loader)
# ═══════════════════════════════════════════════════════════════════════
def parse_header_hbc4(data: bytes) -> Tuple[Optional[Dict[int, str]], Optional[bytes], int]:
    """Parse do header HBC4."""
    try:
        if len(data) < 4 + 1 + 2 + BITMAP_SIZE + 4:
            return None, None, 0
        
        if not data.startswith(MAGIC_HBC4):
            return None, None, 0
        
        offset = 4
        version = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        
        if version != VERSION:
            return None, None, 0
        
        token_count = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        bitmap = data[offset:offset + BITMAP_SIZE]
        offset += BITMAP_SIZE
        
        decoder = {}
        for _ in range(token_count):
            if offset + 4 > len(data):
                return None, None, 0
            token_int, pattern_len = struct.unpack_from('<HH', data, offset)
            offset += 4
            if offset + pattern_len > len(data):
                return None, None, 0
            pattern = data[offset:offset + pattern_len].decode('utf-8')
            offset += pattern_len
            decoder[token_int] = pattern
        
        # Tamanho do marshalled
        if offset + 4 > len(data):
            return None, None, 0
        marshalled_size = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        # Marshalled data (SEM decompressão)
        marshalled_data = data[offset:offset + marshalled_size]
        
        return decoder, marshalled_data, offset
    
    except Exception:
        return None, None, 0

def get_bitmap_hbc4(data: bytes) -> Optional[bytes]:
    """Extrai o bitmap de 32 bytes diretamente do header HBC4."""
    if len(data) < 4 + 1 + 2 + BITMAP_SIZE:
        return None
    if not data.startswith(MAGIC_HBC4):
        return None
    return data[7:7 + BITMAP_SIZE]

def is_hbc4(data: bytes) -> bool:
    """Verifica se os dados começam com magic HBC4."""
    return data[:4] == MAGIC_HBC4