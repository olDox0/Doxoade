# -*- coding: utf-8 -*-
# doxoade/tools/emulator_systems/__init__.py
"""
[HEFESTO/ANÚBIS/HÓRUS] Subsistema de Emulação e Suporte a Bare-Metal.
Exporta as estruturas de detecção, execução, telemetria, forja e matriz de simulação.
"""

from .qemu_detector import QemuDetector, QemuInfo, OvmfInfo
from .qemu_runner import QemuRunner, QemuRunConfig, RunResult
from .disk_forge import DiskForge, DiskForgeConfig, DiskForgeResult
from .sim_profiles import SimulationProfile, ProfileCatalog
from .sim_matrix import SimulationMatrix

__all__ = [
    "QemuDetector",
    "QemuInfo",
    "OvmfInfo",
    "QemuRunner",
    "QemuRunConfig",
    "RunResult",
    "DiskForge",
    "DiskForgeConfig",
    "DiskForgeResult",
    "SimulationProfile",
    "ProfileCatalog",
    "SimulationMatrix",
]
