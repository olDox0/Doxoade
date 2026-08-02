# -*- coding: utf-8 -*-
# doxoade/tools/compression/hybrid_codec.py
"""
Hybrid Codec — Motor de Compressão de Domínio (Ma'at Stack).
Aplica transformações semânticas específicas por tipo de arquivo antes do Zstd.
"""
import re
from collections import OrderedDict

# ==============================================================================
# ESCAPE E TOKENIZAÇÃO
# ==============================================================================
# Usamos a faixa \x01\x10 a \x01\xFF para tokens (240 tokens disponíveis).
# Se o byte \x01 aparecer no código original, ele é escapado como \x01\x00.
TOKEN_PREFIX = b'\x01'
ESCAPE_BYTE = b'\x01\x00'

def _escape_raw(data: bytes) -> bytes:
    """Escapa o byte de controle \x01 para não colidir com os tokens."""
    return data.replace(TOKEN_PREFIX, ESCAPE_BYTE)

def _unescape_raw(data: bytes) -> bytes:
    """Reverte o escape."""
    return data.replace(ESCAPE_BYTE, TOKEN_PREFIX)

# ==============================================================================
# PERFIS DE DOMÍNIO (DICTIONÁRIOS ESTÁTICOS DE ALTA FREQUÊNCIA)
# ==============================================================================
# Extraídos do probe_patterns.py e do conhecimento do código Doxoade.
# Ordem importa: padrões maiores devem ser substituídos primeiro.

PYTHON_PATTERNS = [
    b'from doxoade.tools.doxcolors import Fore, Style',
    b'from doxoade.tools.doxcolors import ',
    b'from doxoade.',
    b'import doxoade.',
    b'click.echo(f"{Fore.',
    b'click.echo(f"',
    b'click.echo(',
    b'Style.RESET_ALL',
    b'Fore.RESET',
    b'@click.option(',
    b'@click.command(',
    b'def ',
    b'class ',
    b'import ',
    b'    ',  # 4 espaços (Indentação)
    b'\r\n',  # Canonicalização CRLF -> LF
]

XML_JSON_PATTERNS = [
    b'<file path="',
    b'">',
    b'</',
    b'role="',
    b'complexity="',
    b'status="',
    b'<![CDATA[',
    b']]>',
    b'    ',  # Indentação
    b'\r\n',  # Canonicalização
]

GENERIC_TEXT_PATTERNS = [
    b'    ',  # Indentação
    b'\r\n',  # Canonicalização
]

def _build_token_map(patterns: list) -> dict:
    """Mapeia padrões para tokens de 2 bytes."""
    token_map = OrderedDict()
    for idx, pattern in enumerate(patterns):
        if idx >= 240: break # Limite da nossa faixa de tokens
        token = bytes([0x01, 0x10 + idx])
        token_map[pattern] = token
    return token_map

# Compila os mapas uma vez na inicialização do módulo
PYTHON_MAP = _build_token_map(PYTHON_PATTERNS)
XML_JSON_MAP = _build_token_map(XML_JSON_PATTERNS)
GENERIC_MAP = _build_token_map(GENERIC_TEXT_PATTERNS)

# Mapas reversos para descompressão
PYTHON_REV = {v: k for k, v in PYTHON_MAP.items()}
XML_JSON_REV = {v: k for k, v in XML_JSON_MAP.items()}
GENERIC_REV = {v: k for k, v in GENERIC_MAP.items()}

# ==============================================================================
# API PÚBLICA
# ==============================================================================

def get_profile_for_ext(ext: str) -> str:
    """Retorna o nome do perfil baseado na extensão."""
    ext = ext.lower()
    if ext in ('.py', '.pyw', '.pyx', '.pxd', '.c', '.h', '.cpp', '.hpp'):
        return 'python'
    if ext in ('.xml', '.json', '.html', '.xhtml', '.svg'):
        return 'xml_json'
    if ext in ('.md', '.txt', '.toml', '.yaml', '.yml', '.ini', '.cfg', '.rst'):
        return 'generic'
    return 'none'

def encode(data: bytes, profile_name: str) -> tuple[bytes, dict]:
    """
    Aplica o pipeline de Ma'at (Escape -> Tokenização -> RLE).
    Retorna (dados_transformados, metadados_do_perfil).
    """
    if profile_name == 'none' or not data:
        return data, {'profile': 'none'}

    # 1. Escape de segurança
    escaped = _escape_raw(data)
    
    # 2. Tokenização de Domínio
    if profile_name == 'python':
        token_map = PYTHON_MAP
        rev_map_id = 'py'
    elif profile_name == 'xml_json':
        token_map = XML_JSON_MAP
        rev_map_id = 'xm'
    elif profile_name == 'generic':
        token_map = GENERIC_MAP
        rev_map_id = 'gn'
    else:
        return data, {'profile': 'none'}

    tokenized = escaped
    for pattern, token in token_map.items():
        if pattern in tokenized:
            tokenized = tokenized.replace(pattern, token)

    # 3. RLE Adaptativo (Opcional, focado em runs de tokens de indentação)
    # Para código, o RLE é menos eficaz que em dados binários, mas vamos aplicar
    # apenas para runs do token de indentação (4 espaços) para ganhar those extra bytes.
    # (Nota: O Zstd Nível 9 já é muito bom em RLE, então aqui mantemos simples para não perder velocidade).
    
    return tokenized, {'profile': rev_map_id}

def decode(data: bytes, meta: dict) -> bytes:
    """
    Reverte o pipeline de Ma'at.
    """
    profile_id = meta.get('profile', 'none')
    if profile_id == 'none' or not data:
        return data

    if profile_id == 'py':
        rev_map = PYTHON_REV
    elif profile_id == 'xm':
        rev_map = XML_JSON_REV
    elif profile_id == 'gn':
        rev_map = GENERIC_REV
    else:
        return data

    # 1. Reverte Tokenização
    detokenized = data
    for token, pattern in rev_map.items():
        if token in detokenized:
            detokenized = detokenized.replace(token, pattern)

    # 2. Reverte Escape
    raw = _unescape_raw(detokenized)
    
    return raw