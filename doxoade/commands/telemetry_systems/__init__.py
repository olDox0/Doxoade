# -*- coding: utf-8 -*-
# doxoade/commands/telemetry_systems/__init__.py
"""
Subsistema Integrado de Telemetria e Análise de Desempenho Nexus.
Exporta o comando telemetry e o motor de Shadow Profiling (ShadowMatrix).
"""
from doxoade.commands.telemetry_systems.telemetry import telemetry
from doxoade.commands.telemetry_systems.shadow_matrix import ShadowMatrix

__all__ = ["telemetry", "ShadowMatrix"]
