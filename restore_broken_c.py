#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""restore_broken_c.py — restaura os 3 arquivos C corrompidos pelo --apply."""
from pathlib import Path
import shutil
import subprocess
import sys

FILES = [
    'doxoade/tools/rev_eng/src/decoder_backend.c',
    'doxoade/tools/rev_eng/src/doctor.c',
    'doxoade/tools/rev_eng/src/functions.c',
]

restored = []
for path in FILES:
    p = Path(path)
    bak = p.with_suffix(p.suffix + '.bak')
    if not bak.exists():
        print(f'SKIP {path}: .bak não encontrado')
        continue
    shutil.copy2(bak, p)
    restored.append(path)
    print(f'✓ RESTAURADO {path} ← {bak.name}')

if not restored:
    sys.exit('ERROR: nada restaurado')

# Recompila
print('\n🔨 Validando compilação...')
result = subprocess.run(
    ['doxoade', 'metal', 'build', '--target', 'doxreveng', '--force'],
    capture_output=True, text=True,
)
if result.returncode == 0:
    print('✅ Compilação OK — arquivos restaurados e saudáveis.')
else:
    print('✘ Compilação ainda falha. Cole a saída abaixo:')
    print(result.stderr[-2000:])
    sys.exit(1)