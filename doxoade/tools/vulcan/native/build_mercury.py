# doxoade/tools/vulcan/native/build_mercury.py
import os, sys, subprocess, sysconfig
from pathlib import Path

def build_mercury():
    root = Path(__file__).resolve().parent
    src = root / 'mercury_core.c'
    out_ext = '.pyd' if os.name == 'nt' else '.so'
    out = root / f'mercury_core{out_ext}'
    
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
        return

    cmd = [
        gcc, '-O3', '-shared', '-fPIC', '-static-libgcc',
        f'-I{inc}', str(src), '-o', str(out),
        f'-L{libs}', f'-lpython{version}'
    ]
    
    print(f"🔨 Compilando Mercury Core Engine...\nGCC: {gcc}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✔ Sucesso! Motor nativo gerado: {out.name}")
    else:
        print(f"✘ Erro na compilação:\n{res.stderr}")

if __name__ == '__main__':
    build_mercury()