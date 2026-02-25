# -*- coding: utf-8 -*-
# tests/vulcan_sandbox/heavy_core.py
import math
def compute_chunk(iterations):
    """Função alvo para otimização nativa."""
    res = 0.0
    for i in range(iterations):
        # Operações que forçam o uso de registradores
        res += (math.sqrt(i) * 1.5) / (math.sin(i) + 2.0)
    return res