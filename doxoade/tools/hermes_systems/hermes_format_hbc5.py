# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_format_hbc5.py
"""
Hermes Binary Format v5 — Zero-Compression Optimized Format
Filosofia: Velocidade > Tamanho
Zero compressão (sem zlib/LZ4)
Header otimizado para parsing rápido
Tokens embutidos para reverse em C
Compatível com decoder C nativo

Layout do arquivo HBC5:
┌─────────────────────────────────────────────────────────┐
│ [4B] Magic: b"HBC5"                                     │
│ [1B] Version: 0x05                                      │
│ [1B] Flags (otimizações aplicadas)                      │
│ [2B] token_count (uint16, little-endian)                │
│ [32B] bitmap_chars (256 bits)                           │
│ [N×] tokens:                                            │
│      [2B] token_int (uint16)                            │
│      [2B] pattern_len (uint16)                          │
│      [pattern_len B] pattern (UTF-8)                    │
├─────────────────────────────────────────────────────────┤
│ [4B] marshalled_size (uint32, little-endian)            │
│ [marshalled_size B] marshalled_bytecode (SEM compressão)│
└─────────────────────────────────────────────────────────┘

Vantagens vs HBC4:
• Header mais simples (1 byte a menos)
• Flags para otimizações futuras
• Parsing mais rápido (menos branches)
• Melhor alinhamento para SIMD

Uso:
• Módulos críticos onde velocidade > tamanho
• Cold start optimization
• Cache de code objects
"""
import struct
from typing import Dict, Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
MAGIC_HBC5 = b"HBC5"
VERSION = 5
BITMAP_SIZE = 32
TOKEN_MIN = 0x80
TOKEN_MAX = 0xFF

# Flags de otimização
FLAG_TOKENIZED_CONSTS = 0x01  # co_consts foi tokenizado
FLAG_TOKENIZED_NAMES = 0x02   # co_names foi tokenizado
FLAG_OPTIMIZED_BYTECODE = 0x04  # Bytecode otimizado

# ═══════════════════════════════════════════════════════════════════════
# BUILD (Compressor → Arquivo)
# ═══════════════════════════════════════════════════════════════════════
def build_header_hbc5(
    dynamic_encoder: Dict[str, int],
    marshalled_data: bytes,
    flags: int = FLAG_TOKENIZED_CONSTS
) -> bytes:
    """
    Constrói header HBC5 + dados marshalled sem compressão.
    
    Args:
        dynamic_encoder: {pattern_str: token_int}
        marshalled_data: Bytecode serializado (sem compressão)
        flags: Flags de otimização aplicadas
    
    Returns:
        Header binário completo pronto para escrita
    """
    if len(dynamic_encoder) > 65535:
        raise ValueError(f"token_count excede limite uint16: {len(dynamic_encoder)}")
    
    # 1. Constrói bitmap de 256 bits (32 bytes)
    bitmap = bytearray(BITMAP_SIZE)
    for token_int in dynamic_encoder.values():
        if not (TOKEN_MIN <= token_int <= TOKEN_MAX):
            raise ValueError(f"Token fora do range 0x80-0xFF: {token_int}")
        byte_idx = token_int // 8
        bit_idx = token_int % 8
        bitmap[byte_idx] |= (1 << bit_idx)
    
    # 2. Serializa tokens (ordenação por token_int para deterministicidade)
    tokens_data = bytearray()
    for pattern, token_int in sorted(dynamic_encoder.items(), key=lambda x: x[1]):
        pattern_bytes = pattern.encode('utf-8')
        if len(pattern_bytes) > 65535:
            raise ValueError(f"Pattern muito longo: {len(pattern_bytes)} bytes")
        tokens_data += struct.pack('<HH', token_int, len(pattern_bytes))
        tokens_data += pattern_bytes
    
    # 3. Monta header completo + marshalled (SEM compressão)
    header = (
        MAGIC_HBC5 +
        struct.pack('<B', VERSION) +
        struct.pack('<B', flags) +  # Flags de otimização
        struct.pack('<H', len(dynamic_encoder)) +
        bytes(bitmap) +
        bytes(tokens_data) +
        struct.pack('<I', len(marshalled_data)) +  # Tamanho do marshalled
        marshalled_data  # SEM compressão
    )
    
    return header

# ═══════════════════════════════════════════════════════════════════════
# PARSE (Arquivo → Loader)
# ═══════════════════════════════════════════════════════════════════════
def parse_header_hbc5(data: bytes) -> Tuple[Optional[Dict[int, str]], Optional[bytes], int, int]:
    """
    Parse do header HBC5.
    
    Returns:
        (decoder_dict, marshalled_data, flags, header_size)
        ou (None, None, 0, 0) se falhar
    """
    try:
        # Validação mínima
        if len(data) < 4 + 1 + 1 + 2 + BITMAP_SIZE + 4:
            return None, None, 0, 0
        
        if not data.startswith(MAGIC_HBC5):
            return None, None, 0, 0
        
        offset = 4  # Pula magic
        
        # Version
        version = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        
        if version != VERSION:
            return None, None, 0, 0
        
        # Flags
        flags = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        
        # Token count
        token_count = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # Bitmap
        bitmap = data[offset:offset + BITMAP_SIZE]
        offset += BITMAP_SIZE
        
        # Lê tokens
        decoder = {}
        for _ in range(token_count):
            if offset + 4 > len(data):
                return None, None, 0, 0
            token_int, pattern_len = struct.unpack_from('<HH', data, offset)
            offset += 4
            if offset + pattern_len > len(data):
                return None, None, 0, 0
            pattern = data[offset:offset + pattern_len].decode('utf-8')
            offset += pattern_len
            decoder[token_int] = pattern
        
        # Tamanho do marshalled
        if offset + 4 > len(data):
            return None, None, 0, 0
        marshalled_size = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        
        # Marshalled data (SEM decompressão)
        if offset + marshalled_size > len(data):
            return None, None, 0, 0
        marshalled_data = data[offset:offset + marshalled_size]
        
        return decoder, marshalled_data, flags, offset
    
    except Exception:
        return None, None, 0, 0

def get_bitmap_hbc5(data: bytes) -> Optional[bytes]:
    """Extrai o bitmap de 32 bytes diretamente do header HBC5."""
    if len(data) < 4 + 1 + 1 + 2 + BITMAP_SIZE:
        return None
    if not data.startswith(MAGIC_HBC5):
        return None
    # Bitmap está em offset fixo: 4 (magic) + 1 (version) + 1 (flags) + 2 (count) = 8
    return data[8:8 + BITMAP_SIZE]

def get_flags_hbc5(data: bytes) -> int:
    """Extrai as flags de otimização do header HBC5."""
    if len(data) < 4 + 1 + 1:
        return 0
    if not data.startswith(MAGIC_HBC5):
        return 0
    return struct.unpack_from('<B', data, 5)[0]

def is_hbc5(data: bytes) -> bool:
    """Verifica se os dados são um arquivo HBC5."""
    return data.startswith(MAGIC_HBC5)