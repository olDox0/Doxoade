# -*- coding: utf-8 -*-
# engine/tools/vulcan/_thermal.py
"""
ORN — Vulcan Thermal Engine (Hórus)
Calcula a Assinatura de Calor e Fever Score de um módulo vulcanizado.

PASC 8.19: Feedback visual contra o efeito Black-Box.
OSL-12: Telemetria de custo de tradução.
"""

from __future__ import annotations
# [DOX-UNUSED] from typing import Any

class ThermalMapper:
    """Mapeia a dor do Vulcan através de calor e febre."""

    @staticmethod
    def calculate_temperature(hot_score: int, line_count: int) -> float:
        """
        Calcula a temperatura (0-100°C).
        Fricção = (Hot_Score / (Line_Count / 100))
        """
        if line_count == 0: return 0.0
        # Normalização: densidade de chamadas pesadas por bloco de código
        friction = (hot_score * 10) / (line_count / 10)
        return min(100.0, round(friction, 2))

    @staticmethod
    def get_fever_status(elapsed_ms: float, baseline_ms: float) -> str:
        """Determina o estado de Febre baseado no tempo de processamento."""
        if elapsed_ms <= (baseline_ms * 1.2):
            return "NORMAL (Cold)"
        if elapsed_ms <= (baseline_ms * 2.0):
            return "FEBRIL (Warm)"
        return "CRÍTICO (IGNITION)"

    @staticmethod
    def get_recommendation(temp: float) -> str:
        """Atena: Estratégia de correção baseada no calor."""
        if temp < 30:
            return "Saudável. Código operando próximo ao metal."
        if temp < 70:
            return "Inflamação moderada. Revise tipagem estática (cdef)."
        return "IGNIÇÃO: Fricção C-API extrema. Substitua por C puro ou .s (ASM)."

def format_heat_bar(temp: float, width: int = 20) -> str:
    """Gera uma barra de calor visual para o terminal."""
    filled = int((temp / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {temp}°C"