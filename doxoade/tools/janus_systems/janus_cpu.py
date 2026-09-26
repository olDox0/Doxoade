# -*- coding: utf-8 -*-
# doxoade/tools/janus_systems/janus_cpu.py
"""
🏛️ JANUS CPU & SIMD PROFILER — Identificador de Hardware e Otimização Vetorial.
Detecta CPU e instruções reais no Windows (winreg/kernel32), Linux e Android/Termux,
entregando as flags de compilação exatas para N2808, Alder Lake ou ARM64.
"""
from __future__ import annotations

import os
import sys
import platform
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class CPUProfile:
    """Perfil de hardware e capacidades SIMD da estação atual."""
    model_name: str
    arch: str
    simd_tier: str  # 'SCALAR', 'SSE2', 'SSE4.2', 'AVX2', 'NEON'
    has_sse2: bool
    has_sse4_2: bool
    has_avx: bool
    has_avx2: bool
    has_neon: bool
    optimal_cflags: List[str]


class JanusCPU:
    """Motor de inspeção de hardware de baixo nível (Zero-Overhead)."""

    @classmethod
    def profile(cls) -> CPUProfile:
        if os.name == 'nt':
            return cls._profile_windows()
        elif bool(os.environ.get("TERMUX_VERSION") or os.path.exists("/data/data/com.termux")):
            return cls._profile_termux()
        else:
            return cls._profile_linux()

    @classmethod
    def _profile_windows(cls) -> CPUProfile:
        """Probe atômico via WinReg e Kernel32 no Windows."""
        model_name = "x86_64 Processor"
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            model_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            winreg.CloseKey(key)
        except Exception:
            model_name = platform.processor() or "Generic Windows x64"

        # Probes de instruções via kernel32 (custo: <0.01ms)
        import ctypes
        k32 = ctypes.windll.kernel32
        # Windows Feature IDs: PF_XMMI64(SSE2)=10, PF_AVX=25, PF_AVX2=40
        has_sse2 = bool(k32.IsProcessorFeaturePresent(10))
        has_avx = bool(k32.IsProcessorFeaturePresent(25))
        has_avx2 = bool(k32.IsProcessorFeaturePresent(40))

        # Heurística para SSE4.2 no N2808/Atom
        has_sse4_2 = has_sse2  # Silvermont/N2808 suporta SSE4.2

        tier = "SSE2"
        flags = ["-O2", "-msse2"]

        # Se for Bluebaby (i5-1235U / Alder Lake / AVX2):
        if has_avx2 and has_avx:
            tier = "AVX2"
            flags = ["-O3", "-mavx2", "-mfma", "-mbmi2", "-funroll-loops"]
        # Se for Amaranth (N2808 / Celeron / Silvermont / SSE4.2):
        elif "n2808" in model_name.lower() or "celeron" in model_name.lower():
            tier = "SSE4.2"
            flags = ["-O2", "-msse4.2", "-mpopcnt"]
        elif has_sse4_2:
            tier = "SSE4.2"
            flags = ["-O2", "-msse4.2", "-mpopcnt"]

        return CPUProfile(
            model_name=model_name,
            arch="x86_64",
            simd_tier=tier,
            has_sse2=has_sse2,
            has_sse4_2=has_sse4_2,
            has_avx=has_avx,
            has_avx2=has_avx2,
            has_neon=False,
            optimal_cflags=flags
        )

    @classmethod
    def _profile_termux(cls) -> CPUProfile:
        """Probe de arquitetura ARM64 no Android/Termux."""
        model_name = "ARM64 Processor"
        has_neon = False
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for line in content.splitlines():
                    if "Hardware" in line or "model name" in line:
                        model_name = line.split(":", 1)[1].strip()
                        break
                if "asimd" in content or "neon" in content or "fp" in content:
                    has_neon = True
        except Exception:
            pass

        return CPUProfile(
            model_name=model_name,
            arch="aarch64",
            simd_tier="NEON",
            has_sse2=False,
            has_sse4_2=False,
            has_avx=False,
            has_avx2=False,
            has_neon=has_neon,
            optimal_cflags=["-O3", "-march=armv8-a"]
        )

    @classmethod
    def _profile_linux(cls) -> CPUProfile:
        """Probe via /proc/cpuinfo no Linux/WSL."""
        model_name = platform.processor() or "Linux Processor"
        flags_set = set()
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("flags"):
                        flags_set.update(line.split(":", 1)[1].strip().split())
                    elif line.startswith("model name") and model_name == "Linux Processor":
                        model_name = line.split(":", 1)[1].strip()
        except Exception:
            pass

        has_avx2 = "avx2" in flags_set
        has_avx = "avx" in flags_set
        has_sse4_2 = "sse4_2" in flags_set

        tier = "AVX2" if has_avx2 else ("SSE4.2" if has_sse4_2 else "SSE2")
        flags = ["-O3", "-mavx2", "-mfma"] if has_avx2 else ["-O2", "-msse4.2", "-mpopcnt"]

        return CPUProfile(
            model_name=model_name,
            arch=platform.machine(),
            simd_tier=tier,
            has_sse2="sse2" in flags_set,
            has_sse4_2=has_sse4_2,
            has_avx=has_avx,
            has_avx2=has_avx2,
            has_neon=False,
            optimal_cflags=flags
        )
