#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/native/build_logger.py
"""
Build script para Hermes Async Logger
======================================
Compila o logger assíncrono como DLL/SO independente.
"""
import os
import sys
import subprocess
from pathlib import Path

def find_gcc() -> str:
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

def build_logger() -> bool:
    """Compila hermes_async_log.dll/so."""
    root = Path(__file__).resolve().parent
    src = root / 'hermes_async_log.c'
    
    # No Windows gera .dll, no Linux .so
    if os.name == 'nt':
        out = root / 'hermes_async_log.dll'
    else:
        out = root / 'hermes_async_log.so'
    
    gcc = find_gcc()
    if not gcc:
        print("✘ GCC não encontrado. Instale w64devkit ou adicione gcc ao PATH.")
        return False
    
    if not src.exists():
        print(f"✘ Arquivo fonte não encontrado: {src}")
        return False
    
    # Flags otimizados
    cmd = [
        gcc,
        '-O2',                    # Otimização balanceada
        '-shared',                # Biblioteca compartilhada
        '-static-libgcc',         # Linka libgcc estaticamente
        '-fPIC',                  # Position-independent code
        '-pthread',               # Suporte a threads (Linux)
        str(src),
        '-o', str(out),
    ]
    
    print(f"🔨 Compilando Hermes Async Logger...")
    print(f"   GCC: {gcc}")
    print(f"   Source: {src.name}")
    print(f"   Output: {out.name}")
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        size_kb = out.stat().st_size / 1024
        print(f"✔ Sucesso! Logger assíncrono gerado: {out.name}")
        print(f"   Tamanho: {size_kb:.1f} KB")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✘ Erro na compilação:")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False

if __name__ == '__main__':
    success = build_logger()
    sys.exit(0 if success else 1)