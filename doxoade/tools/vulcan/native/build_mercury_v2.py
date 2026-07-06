#!/usr/bin/env python3
# doxoade/tools/vulcan/native/build_mercury.py
"""
Build script para Mercury Core Engine v3.0
===========================================
Compila como DLL pura (NÃO como .pyd).
Carregamento via ctypes — zero dependência de Python.h.

Vantagens:
  - Funciona com w64devkit (MinGW) sem precisar do python312.lib
  - Compatível com qualquer compilador C
  - Performance máxima (sem overhead PyObject)
"""
import os
import sys
import subprocess
import sysconfig
from pathlib import Path


def find_gcc() -> str | None:
    """Detecta GCC via w64devkit no PATH ou thirdparty."""
    # 1. Procura no thirdparty do projeto
    project_root = Path(__file__).resolve().parents[4]
    candidate = project_root / 'thirdparty' / 'w64devkit' / 'bin' / 'gcc.exe'
    if candidate.exists():
        return str(candidate)

    # 2. Procura no PATH
    for p in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(p.strip('"')) / 'gcc.exe'
        if candidate.exists():
            return str(candidate)

    return None


def build_mercury() -> bool:
    root = Path(__file__).resolve().parent
    src = root / 'mercury_core.c'

    # No Windows gera .dll, no Linux .so
    if os.name == 'nt':
        out = root / 'mercury_core.dll'
    else:
        out = root / 'mercury_core.so'

    gcc = find_gcc()
    if not gcc:
        print("✘ GCC não encontrado. Instale w64devkit ou adicione gcc ao PATH.")
        return False

    if not src.exists():
        print(f"✘ Arquivo fonte não encontrado: {src}")
        return False

    # ═══════════════════════════════════════════════════════════════════
    # Flags otimizados para Celeron N2808 / Westmere baseline
    # NÃO linka com libpython (DLL pura, carregada via ctypes)
    # ═══════════════════════════════════════════════════════════════════
    cmd = [
        gcc,
        '-O3',                    # Otimização máxima
        '-shared',                # Biblioteca compartilhada
        '-static-libgcc',         # Linka libgcc estaticamente
        '-fPIC',                  # Position-independent code
        '-march=westmere',        # Baseline: SSE4.2 (N2808 suporta)
        '-msse4.2',               # Habilita SSE 4.2 explicitamente
        '-funroll-loops',         # Desrola loops para performance
        str(src),
        '-o', str(out),
    ]

    print(f"🔨 Compilando Mercury Core Engine v3.0...")
    print(f"   GCC: {gcc}")
    print(f"   Source: {src.name}")
    print(f"   Output: {out.name}")
    print(f"   Otimizações: Zero-Allocation, Branchless, SSE4.2")
    print(f"   Modo: DLL pura (ctypes) — zero Python.h")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        size_kb = out.stat().st_size / 1024
        print(f"✔ Sucesso! Motor nativo v3.0 gerado: {out.name}")
        print(f"   Tamanho: {size_kb:.1f} KB")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✘ Erro na compilação:")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False


if __name__ == '__main__':
    success = build_mercury()
    sys.exit(0 if success else 1)