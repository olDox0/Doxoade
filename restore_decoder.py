#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""restore_decoder.py — reverte decoder_backend.c (fallback em lugar errado)."""
from pathlib import Path
import shutil
import subprocess

FP = Path('doxoade/tools/rev_eng/src/decoder_backend.c')
BAK = FP.with_suffix('.c.bak')

if not BAK.exists():
    raise SystemExit(f'ERROR: {BAK} não encontrado')

shutil.copy2(BAK, FP)
print(f'✓ RESTAURADO {FP.name} ← {BAK.name}')

result = subprocess.run(
    ['doxoade', 'metal', 'build', '--target', 'doxreveng', '--force'],
    capture_output=True, text=True,
)
print('✅ Compilação OK' if result.returncode == 0 else f'✘ Falha:\n{result.stderr[-1500:]}')