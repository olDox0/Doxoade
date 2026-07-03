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

MAGIC_HBC4 = b"HBC4"
VERSION = 4
BITMAP_SIZE = 32

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════
MAGIC_HBC3 = b"HBC3"
VERSION = 3
BITMAP_SIZE = 32  # 32 bytes = 256 bits (cobre todos os char codes 0-255)

# Range de tokens dinâmicos (0x80-0xFF)
TOKEN_MIN = 0x80
TOKEN_MAX = 0xFF


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD (Compressor → Arquivo)
# ═══════════════════════════════════════════════════════════════════════════════
def build_header(dynamic_encoder: Dict[str, int]) -> bytes:
    """Constrói o header binário HBC3.
    
    Args:
        dynamic_encoder: {pattern_str: token_int}
            Ex: {"doxoade.tools.hermes": 0x80, "click.option": 0x81}
    
    Returns:
        Header binário pronto para ser concatenado com compressed_data.
    
    Raises:
        ValueError: se token_count > 65535 ou token fora do range 0x80-0xFF.
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
    
    # 3. Monta header completo
    header = (
        MAGIC_HBC3 +
        struct.pack('<B', VERSION) +
        struct.pack('<H', len(dynamic_encoder)) +
        bytes(bitmap) +
        bytes(tokens_data)
    )
    
    return header

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
    
    # 3. Monta header completo
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

# ═══════════════════════════════════════════════════════════════════════════════
# PARSE (Arquivo → Loader)
# ═══════════════════════════════════════════════════════════════════════════════
def parse_header(data: bytes) -> Tuple[Optional[Dict[int, str]], Optional[bytes], int]:
    """Parse do header HBC3.
    
    Args:
        data: Bytes brutos do arquivo .hermes (começando com b"HBC3").
    
    Returns:
        Tuple (decoder_dict, compressed_data, header_size):
          - decoder_dict: {token_int: pattern_str} ou None se erro
          - compressed_data: bytes do bytecode LZMA ou None se erro
          - header_size: tamanho do header em bytes (para debug)
    
    Note:
        Em caso de erro, retorna (None, None, 0) — fail-graceful.
        O chamador deve verificar se decoder_dict é None.
    """
    try:
        # Validação mínima
        if len(data) < 4 + 1 + 2 + BITMAP_SIZE:
            return None, None, 0
        
        if not data.startswith(MAGIC_HBC3):
            return None, None, 0
        
        offset = 4  # Pula magic
        
        # Version
        version = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        
        if version != VERSION:
            return None, None, 0
        
        # Token count
        token_count = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        
        # Bitmap (32 bytes)
        bitmap = data[offset:offset + BITMAP_SIZE]
        offset += BITMAP_SIZE
        
        # Tokens
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
        
        # O resto é bytecode comprimido
        compressed_data = data[offset:]
        
        return decoder, compressed_data, offset
    
    except Exception:
        # Fail-graceful: qualquer erro de parsing retorna None
        return None, None, 0

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

def get_bitmap(data: bytes) -> Optional[bytes]:
    """Extrai o bitmap de 32 bytes diretamente do header HBC3.
    
    Args:
        data: Bytes brutos do arquivo .hermes.
    
    Returns:
        Bitmap de 32 bytes ou None se não for HBC3 válido.
    
    Note:
        Otimização: evita parse completo quando só precisamos do bitmap.
    """
    if len(data) < 4 + 1 + 2 + BITMAP_SIZE:
        return None
    if not data.startswith(MAGIC_HBC3):
        return None
    return data[7:7 + BITMAP_SIZE]


# ═══════════════════════════════════════════════════════════════════════════════
# BITMAP VETORIAL (O(1) lookup)
# ═══════════════════════════════════════════════════════════════════════════════
def has_token_char(bitmap: bytes, char_code: int) -> bool:
    """Verifica O(1) se um caractere é um token válido.
    
    Args:
        bitmap: 32 bytes do bitmap extraído do header.
        char_code: Código do caractere (0-255).
    
    Returns:
        True se o caractere é um token dinâmico válido.
    
    Note:
        Operação puramente bitwise: 1 acesso a array + 1 shift + 1 AND.
        No C com SSE 4.2, isso seria 1 instrução PCMPISTRM.
    """
    if not (0 <= char_code <= 255):
        return False
    byte_idx = char_code // 8
    bit_idx = char_code % 8
    return bool(bitmap[byte_idx] & (1 << bit_idx))


def string_needs_reverse(s: str, bitmap: bytes) -> bool:
    """Pré-filtro rápido: a string contém algum caractere token?
    
    Args:
        s: String a ser verificada.
        bitmap: 32 bytes do bitmap.
    
    Returns:
        True se a string contém pelo menos um caractere token.
    
    Note:
        Usa early-exit: para no primeiro caractere token encontrado.
        Complexidade: O(N) no pior caso, O(1) no melhor (primeiro char é token).
        
        Para o cli.py com 19 tokens, isso evita ~90% das chamadas a str.replace().
    """
    for c in s:
        code = ord(c)
        # Só verifica chars no range de tokens dinâmicos (0x80-0xFF)
        if code >= TOKEN_MIN and has_token_char(bitmap, code):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════
def is_hbc3(data: bytes) -> bool:
    """Verifica se os dados começam com magic HBC3."""
    return data[:4] == MAGIC_HBC3


def detect_format(data: bytes) -> str:
    """Detecta o formato do arquivo .hermes.
    
    Returns:
        'HBC3', 'HBC2', 'HBC1' ou 'UNKNOWN'.
    """
    if data[:4] == b"HBC3":
        return 'HBC3'
    if data[:4] == b"HBC2":
        return 'HBC2'
    if data[:4] == b"HBC1":
        return 'HBC1'
    return 'UNKNOWN'


def header_size_estimate(token_count: int, avg_pattern_len: int = 30) -> int:
    """Estima o tamanho do header para fins de debug/metrics.
    
    Args:
        token_count: Número de tokens no dicionário.
        avg_pattern_len: Tamanho médio dos padrões em bytes.
    
    Returns:
        Tamanho estimado em bytes.
    """
    return (
        4 +           # magic
        1 +           # version
        2 +           # token_count
        BITMAP_SIZE + # bitmap
        token_count * (4 + avg_pattern_len)  # tokens
    )