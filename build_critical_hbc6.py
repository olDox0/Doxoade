# build_critical_hbc6.py
from pathlib import Path
from doxoade.tools.hermes_systems.hermes_compress_hbc6 import HBC6Compressor

project_root = Path(__file__).resolve().parent
build_dir = project_root / '.doxoade' / 'hermes' / 'build'
build_dir.mkdir(parents=True, exist_ok=True)

# Módulos que queremos testar no Hook V2
targets = [
    'doxoade/tools/filesystem.py',
    'doxoade/tools/doxcolors.py',
    'doxoade/tools/error_info.py'
]

# Dicionário Global (usando os tokens de alta frequência que o scan caçou)
GLOBAL_MACROS = {
    'hash_import_1': ['LOAD_CONST', 'LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME'],
    'hash_import_2': ['LOAD_CONST', 'IMPORT_NAME', 'STORE_NAME'],
    'hash_try_1': ['SETUP_FINALLY', 'POP_BLOCK'],
}
TOKEN_MAP = {h: i for i, h in enumerate(GLOBAL_MACROS.keys())}

compressor = HBC6Compressor(project_root, GLOBAL_MACROS, TOKEN_MAP)

for target in targets:
    py_file = project_root / target
    if py_file.exists():
        out_file = build_dir / f"{target.replace('/', '.').replace('.py', '')}.hbc6"
        stats = compressor.compress_file(py_file, out_file)
        print(f"✔ {py_file.name} -> {out_file.name} ({stats['patches_applied']} patches mapeados)")