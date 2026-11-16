#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_triangulation_generics.py — exclui headers genéricos ('}', '{', etc)
   de collect_headers para evitar ADD_ONLY_POST_HEADER falso."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_triangulation.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── STEP 1: adicionar _GENERIC_HEADERS após BODY_INDENT_THRESHOLD ──
anchor1 = 'BODY_INDENT_THRESHOLD = 2\n'
if '_GENERIC_HEADERS' in src:
    print('SKIP 1: _GENERIC_HEADERS já presente')
elif anchor1 not in src:
    sys.exit('ERROR 1: BODY_INDENT_THRESHOLD anchor não encontrado')
else:
    src = src.replace(anchor1, anchor1 + '''
# Tokens que não servem como âncora (aparecem em qualquer lugar do código)
_GENERIC_HEADERS = frozenset({
    '}', '{', '};', ');', ')', '(', ']', '[',
    'break;', 'break', 'continue;', 'continue',
    'return;', 'return', 'else', 'else {', 'do {',
    'default:', 'case',
})
''', 1)
    print('✓ 1: _GENERIC_HEADERS adicionado')

# ── STEP 2: filtrar em collect_headers ──────────────────────────────
old_ch = '''def collect_headers(hunk: "Hunk", indices: List[int], indent_unit: str = INDENT_UNIT) -> List[str]:
    headers = []
    for i in indices:
        expanded = desconcatenate_line(hunk.lines[i].text, indent_unit)
        for l in expanded:
            norm = normalize_line(l)
            if not norm: continue
            if not is_indented(l): headers.append(norm)
    return headers'''

new_ch = '''def collect_headers(hunk: "Hunk", indices: List[int], indent_unit: str = INDENT_UNIT) -> List[str]:
    headers = []
    for i in indices:
        expanded = desconcatenate_line(hunk.lines[i].text, indent_unit)
        for l in expanded:
            norm = normalize_line(l)
            if not norm: continue
            if norm in _GENERIC_HEADERS: continue  # ← NOVO: exclui }/{ etc
            if not is_indented(l): headers.append(norm)
    return headers'''

if old_ch in src:
    src = src.replace(old_ch, new_ch, 1)
    print('✓ 2: collect_headers filtra _GENERIC_HEADERS')
elif 'norm in _GENERIC_HEADERS' in src:
    print('SKIP 2: filtro já presente')
else:
    sys.exit('ERROR 2: collect_headers anchor não encontrado')

# ── STEP 3: exigir 2+ headers para Camadas 1 e 2 ────────────────────
old_post = '''    if post_headers:
        post_matches = []'''
new_post = '''    if post_headers and len(post_headers) >= 2:  # ← exige 2+
        post_matches = []'''

if old_post in src:
    src = src.replace(old_post, new_post, 1)
    print('✓ 3: Camada 2 exige 2+ post_headers')
elif 'len(post_headers) >= 2' in src:
    print('SKIP 3: já presente')
else:
    print('WARN 3: anchor Camada 2 não encontrado (não-bloqueante)')

old_pre = '''    if pre_headers:
        pre_matches = []'''
new_pre = '''    if pre_headers and len(pre_headers) >= 1:  # 1 header específico basta
        pre_matches = []'''

if old_pre in src:
    src = src.replace(old_pre, new_pre, 1)
    print('✓ 4: Camada 1 exige 1+ pre_headers (clarificado)')
else:
    print('SKIP 4: já presente ou anchor diferente')

# ── Validate ────────────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError L{e.lineno}: {e.msg}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_triangulation.py reparado ({len(src)} bytes)')
else:
    print('OK: nada a fazer')