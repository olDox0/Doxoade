#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_case4_idem.py — case 4 exige '+' (adições), senão falso positivo
   em remoções puras com contexto."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# Case 4 atual
old = '''        # 4) Bloco de contexto + '+' presente em ordem
        block = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '+')]
        if len(block) >= 2:
            n = len(block)
            for cand in range(len(norm_file) - n + 1):
                if norm_file[cand:cand + n] == block:
                    return True, "Bloco completo já presente no arquivo."

        return False, ""'''

new = '''        # 4) Bloco de contexto + '+' presente em ordem
        # v6.19 — SÓ quando há '+' (adições). Para remoção pura com contexto,
        # o bloco 'break; } } return; }' existe em qualquer função C e
        # dispararia falso positivo.
        if plus_n:
            block = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '+')]
            if len(block) >= 2:
                n = len(block)
                for cand in range(len(norm_file) - n + 1):
                    if norm_file[cand:cand + n] == block:
                        return True, "Bloco completo já presente no arquivo."

        # 4b) Remoção pura com contexto: removals AUSENTES + contexto PRESENTE
        if minus_n and not plus_n and has_ctx:
            if all(m not in file_set for m in minus_n if m):
                ctx_norms = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == ' ']
                ctx_norms = [c for c in ctx_norms if c]
                if ctx_norms and any(c in file_set for c in ctx_norms):
                    return True, "Remoção pura com contexto: removals ausentes do arquivo."

        return False, ""'''

if '_is_idempotent_hunk' not in src:
    sys.exit('ERROR: _is_idempotent_hunk não encontrado')
if 'v6.19' in src:
    print('SKIP: case 4 já corrigido (v6.19)')
elif old in src:
    src = src.replace(old, new, 1)
    print('✓ case 4 requer plus_n; case 4b adicionado')
else:
    sys.exit('ERROR: anchor case 4 não encontrado')

try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError L{e.lineno}: {e.msg}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py patcheado ({len(src)} bytes)')
else:
    print('OK: nada a fazer')