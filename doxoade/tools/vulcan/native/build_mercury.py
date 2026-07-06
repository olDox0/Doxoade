#!/usr/bin/env python3
# doxoade/tools/vulcan/native/build_mercury.py
"""
Build script para Mercury Core Engine
Compila como .pyd, linkando contra o import lib do CPython
"""
import sys
import subprocess
import sysconfig
from pathlib import Path

def build_mercury():
    """Compila mercury_core.pyd linkando corretamente contra python3XX.dll."""
    print("🔨 Compilando Mercury Core Engine...")

    gcc = "C:/Users/olDox222/Documents/A20251122/DOSSIER/Altonomo/Projetos_E_Programas/Projeto OADE/doxoade/thirdparty/w64devkit/bin/gcc.exe"
    if not Path(gcc).exists():
        gcc = "gcc"
    print(f"GCC: {gcc}")

    python_include = sysconfig.get_path('include')
    python_libs_dir = Path(sys.base_prefix) / 'libs'
    python_version = f"{sys.version_info.major}{sys.version_info.minor}"

    source = Path(__file__).parent / 'mercury_core_v2.c'
    output = Path(__file__).parent / 'mercury_core.pyd'

    # ═══════════════════════════════════════════════════════════════════
    # COMPILAÇÃO DE EXTENSÃO PYTHON (.pyd)
    # Os símbolos da C-API (PyArg_ParseTuple, PyModule_Create2, PyExc_*...)
    # são __declspec(dllimport) — só PyInit_* é resolvido automaticamente
    # pelo loader. É preciso linkar contra o import lib (python312.lib)
    # para resolver o resto no link-time. Isso NÃO embute o interpretador:
    # em runtime o .pyd só chama de volta pro python312.dll já carregado
    # no processo.
    # ═══════════════════════════════════════════════════════════════════
    cmd = [
        gcc,
        '-O2',
        '-shared',
        '-static-libgcc',
        '-fPIC',
        '-march=westmere',
        '-msse4.2',
        f'-I{python_include}',
        str(source),
        '-o', str(output),
        f'-L{python_libs_dir}',
        f'-lpython{python_version}',
    ]

    print(f"Comando: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace'
        )
        if result.returncode != 0:
            print("✘ Erro na compilação:")
            print(result.stderr)
            return False
        if not output.exists():
            print("✘ Compilação concluída mas arquivo não gerado")
            return False
        size_kb = output.stat().st_size / 1024
        print("✔ Compilação bem-sucedida!")
        print(f"   Output: {output.name} ({size_kb:.1f} KB)")
        return True
    except subprocess.TimeoutExpired:
        print("✘ Timeout na compilação (>60s)")
        return False
    except Exception as e:
        print(f"✘ Erro: {e}")
        return False

if __name__ == '__main__':
    success = build_mercury()
    sys.exit(0 if success else 1)