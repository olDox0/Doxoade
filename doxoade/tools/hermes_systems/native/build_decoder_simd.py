#!/usr/bin/env python3
# doxoade/tools/hermes_systems/native/build_decoder_simd.py
"""
Build script para Hermes SIMD Decoder (SSE 4.2)
Otimizações:
- SSE 4.2 STTNI (PCMPISTRM/PCMPISTRI)
- Branchless expansion
- Zero-allocation no loop crítico
"""
import os
import sys
import subprocess
import sysconfig
from pathlib import Path

def build_decoder_simd():
    root = Path(__file__).resolve().parent
    src = root / 'hermes_decoder_simd.c'
    out_ext = '.pyd' if os.name == 'nt' else '.so'
    out = root / f'hermes_decoder_simd{out_ext}'
    
    inc = sysconfig.get_path('include')
    libs = Path(sys.prefix) / 'libs'
    version = f"{sys.version_info.major}{sys.version_info.minor}"
    
    # Caça o w64devkit no PATH
    gcc = None
    for p in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(p.strip('"')) / 'gcc.exe'
        if candidate.exists():
            gcc = str(candidate)
            break
    
    if not gcc:
        print("✘ GCC não encontrado no PATH.")
        return False
    
    # Flags otimizados para SSE 4.2
    cmd = [
        gcc,
        '-O3',                      # Otimização máxima
        '-shared',                   # Biblioteca compartilhada
        '-fPIC',                     # Position-independent code
        '-static-libgcc',            # Linka libgcc estaticamente
        '-msse4.2',                  # Habilita SSE 4.2
        '-mpopcnt',                  # Population count (para bitmaps)
        '-funroll-loops',            # Desrola loops
        '-march=native',             # Usa instruções da CPU atual
        f'-I{inc}',
        str(src),
        '-o', str(out),
    ]
    
    # No Windows, NÃO linkar com libpython
    if os.name != 'nt':
        cmd.extend([f'-L{libs}', f'-lpython{version}'])
    
    print(f"🔨 Compilando Hermes SIMD Decoder (SSE 4.2)...")
    print(f"   GCC: {gcc}")
    print(f"   Source: {src.name}")
    print(f"   Output: {out.name}")
    print(f"   Otimizações: SSE 4.2, Branchless, Zero-Allocation")
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✔ Sucesso! Decoder SIMD gerado: {out.name}")
        print(f"   Tamanho: {out.stat().st_size / 1024:.1f} KB")
        
        # Verifica se SSE 4.2 foi habilitado
        if '-msse4.2' in cmd:
            print(f"   ✓ SSE 4.2 habilitado")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"✘ Erro na compilação:")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False

if __name__ == '__main__':
    success = build_decoder_simd()
    sys.exit(0 if success else 1)