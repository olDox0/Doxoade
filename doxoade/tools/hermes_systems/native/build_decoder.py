# doxoade/tools/hermes_systems/native/build_decoder.py

#!/usr/bin/env python3
"""
Build script para o Hermes Native Decoder
Usa o Metalcraft (w64devkit/GCC) para compilar o decoder C
"""
import os
import sys
import subprocess
from pathlib import Path

def find_python_include():
    """Encontra o caminho dos headers do Python"""
    import sysconfig
    return sysconfig.get_path('include')

def find_python_lib():
    """Encontra a biblioteca do Python"""
    import sysconfig
    lib_dir = sysconfig.get_config_var('LIBDIR')
    lib_name = sysconfig.get_config_var('LDLIBRARY')
    
    if lib_dir and lib_name:
        return Path(lib_dir) / lib_name
    return None

def find_lzma():
    """Encontra a biblioteca LZMA"""
    # No Windows com w64devkit, geralmente está em /lib ou /usr/lib
    search_paths = [
        Path("C:/w64devkit/lib"),
        Path("C:/w64devkit/x86_64-w64-mingw32/lib"),
        Path("/usr/lib"),
        Path("/usr/local/lib"),
    ]
    
    for path in search_paths:
        if path.exists():
            # Procura por liblzma.a ou lzma.lib
            for lib_file in path.glob("*lzma*"):
                if lib_file.suffix in ['.a', '.lib']:
                    return path
    return None

def build_decoder():
    """Compila o decoder C nativo"""
    project_root = Path(__file__).parent.parent.parent.parent.parent
    native_dir = Path(__file__).parent
    source_file = native_dir / "hermes_decoder.c"
    
    # Detecta sistema operacional
    if os.name == 'nt':
        output_file = native_dir / "hermes_decoder.pyd"
        compiler = "gcc"  # w64devkit
    else:
        output_file = native_dir / "hermes_decoder.so"
        compiler = "gcc"
    
    # Caminhos
    python_include = find_python_include()
    lzma_lib_dir = find_lzma()
    
    print(f"🔨 Compilando Hermes Native Decoder...")
    print(f"   Source: {source_file}")
    print(f"   Output: {output_file}")
    print(f"   Python include: {python_include}")
    
    # Monta comando de compilação
    cmd = [
        compiler,
        "-O3",                    # Otimização máxima
        "-shared",                # Biblioteca compartilhada
        "-fPIC",                  # Position-independent code
        f"-I{python_include}",    # Headers do Python
        str(source_file),
        "-o", str(output_file),
    ]
    
    # Adiciona LZMA
    if lzma_lib_dir:
        cmd.extend([f"-L{lzma_lib_dir}", "-llzma"])
    else:
        cmd.append("-llzma")  # Assume que está no PATH
    
    # Adiciona Python library (Windows)
    if os.name == 'nt':
        python_lib = find_python_lib()
        if python_lib:
            cmd.append(str(python_lib))
    
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Compilação bem-sucedida!")
        print(f"   Output: {output_file}")
        print(f"   Size: {output_file.stat().st_size / 1024:.1f} KB")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro na compilação:")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        return False

if __name__ == "__main__":
    success = build_decoder()
    sys.exit(0 if success else 1)