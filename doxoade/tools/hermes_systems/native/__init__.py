# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/native/__init__.py
"""
Hermes Native Decoder — Auto-Build System com SIMD
Integra com w64devkit (MinGW-w64) via NexusToolchain.
Suporta múltiplos decoders:
- hermes_decoder.pyd: Decoder base (sem SIMD)
- hermes_decoder_simd.pyd: Decoder SIMD (SSE 4.2)
"""
import os
import sys
from pathlib import Path

# Tenta carregar o decoder SIMD primeiro (mais rápido)
_decoder_module = None
_decoder_type = None

try:
    from . import hermes_decoder_simd as _decoder_module
    _decoder_type = 'simd'
except ImportError:
    try:
        from . import hermes_decoder as _decoder_module
        _decoder_type = 'base'
    except ImportError:
        pass

def decode(hermes_path: str):
    """
    Decodifica arquivo .hermes usando o melhor decoder disponível.
    Prioridade: SIMD > Base > Python fallback
    """
    if _decoder_module is None:
        return None
    
    try:
        return _decoder_module.decode(hermes_path)
    except Exception:
        return None

def get_decoder_type() -> str:
    """Retorna o tipo de decoder carregado ('simd', 'base', ou None)."""
    return _decoder_type

def is_simd_available() -> bool:
    """Verifica se o decoder SIMD está disponível."""
    return _decoder_type == 'simd'