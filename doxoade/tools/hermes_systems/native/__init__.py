# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/native/__init__.py
"""
Hermes Native Decoder
Decodificador C nativo para arquivos .hermes HBC3
"""

try:
    from .hermes_decoder import decode
    __all__ = ['decode']
except ImportError:
    # Decoder C não disponível, usa fallback Python
    pass