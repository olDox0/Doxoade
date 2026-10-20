# -*- coding: utf-8 -*-
# doxoade/commands/consult_systems/converters/__init__.py
"""
Catálogo e Registro de Conversores Canônicos (Thoth Registry).
"""
from __future__ import annotations
from typing import Dict, Type
from .base_converter import BaseCanonicalConverter
from .thirty_days_converter import ThirtyDaysConverter
from .byte_of_python_converter import ByteOfPythonConverter
from .py4e_converter import Py4eConverter

CONVERTER_REGISTRY: Dict[str, Type[BaseCanonicalConverter]] = {
    "30days": ThirtyDaysConverter,
    "byte_of_python": ByteOfPythonConverter,
    "py4e": Py4eConverter,
}

__all__ = [
    "BaseCanonicalConverter",
    "ThirtyDaysConverter",
    "ByteOfPythonConverter",
    "Py4eConverter",
    "CONVERTER_REGISTRY",
]
