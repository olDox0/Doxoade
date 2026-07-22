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
    
    # Caça o w64devkit no PATH ou thirdparty
    gcc = None
    project_root = Path(__file__).resolve().parents[4]
    candidate = project_root / 'thirdparty' / 'w64devkit' / 'bin' / 'gcc.exe'
    if candidate.exists():
        gcc = str(candidate)
    else:
        for p in os.environ.get('PATH', '').split(os.pathsep):
            candidate = Path(p.strip('"')) / 'gcc.exe'
            if candidate.exists():
                gcc = str(candidate)
                break
                
    if not gcc:
        print("✘ GCC não encontrado.")
        return False

    # 🚀 CORREÇÃO DEFINITIVA PARA MINGW: Linkagem direta contra a DLL
    version = f"{sys.version_info.major}{sys.version_info.minor}"
    dll_name = f"python{version}.dll"
    dll_path = Path(sys.base_prefix) / dll_name
    if not dll_path.exists():
        dll_path = Path(sys.executable).parent / dll_name

    cmd = [
        gcc,
        '-O3',
        '-shared',
        '-fPIC',
        '-static-libgcc',
        '-msse4.2',
        '-mpopcnt',
        '-funroll-loops',
        '-march=native',
        f'-I{inc}',
        str(src),
        '-o', str(out),
    ]
    
    # No Windows, linka diretamente contra a DLL (MinGW não lê .lib da MSVC)
    if os.name == 'nt':
        if dll_path.exists():
            cmd.append(str(dll_path)) # <--- 🚀 LINKAGEM DIRETA CONTRA A DLL
        else:
            print(f"✘ Não foi possível localizar {dll_name} para linkagem.")
            return False
    else:
        # Linux/macOS usa a lib padrão
        libs = Path(sys.prefix) / 'libs'
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
        return True
    except subprocess.CalledProcessError as e:
        print(f"✘ Erro na compilação:")
        print(f"   stderr: {e.stderr}")
        return False

if __name__ == '__main__':
    success = build_decoder_simd()
    sys.exit(0 if success else 1)