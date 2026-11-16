#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_idem_v3.py — case 5 de _is_idempotent_hunk usa raw text + fuzzy.

Bug: _normalize_line() apaga linhas '#'-prefixadas (#include) e ignora
comentários C /* */, então ADD_ONLY com "#include <x>" nunca era detectado
como idempotente. Fix: comparar pl.text raw com normalização fuzzy local.
"""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── STEP 1: substituir case 5 por versão fuzzy ──────────────────────
old_case5 = '''        # 5) ADD_ONLY com TODAS as adições já presentes no arquivo
        #    (cobre "#include <x>" que já existe, "#define" duplicado, etc.)
        #    Exige pelo menos uma linha de contexto existente (evita falso
        #    positivo de "return 0;" em outra função — ali o bloco completo
        #    do caso 4 já teria pego, ou não há contexto).
        if plus_n and not minus and has_ctx:
            if all(p in file_set for p in plus_n):
                ctx_norms = [
                    cls._normalize_line(pl.text)
                    for pl in hunk.lines if pl.kind == ' '
                ]
                ctx_norms = [c for c in ctx_norms if c]
                if any(c in file_set for c in ctx_norms):
                    return True, (
                        f"ADD_ONLY: todas as {len(plus_n)} adição(ões) "
                        f"já existem no arquivo + âncora de contexto "
                        f"encontrada."
                    )'''

new_case5 = '''        # 5) ADD_ONLY com TODAS as adições já presentes no arquivo.
        #    Usa normalização FUZZY local (preserva #include, strip /* */)
        #    porque _normalize_line() remove linhas '#'-prefixadas.
        _adds_raw = [pl.text for pl in hunk.lines if pl.kind == '+']
        _minus_raw = [pl.text for pl in hunk.lines if pl.kind == '-']
        if _adds_raw and not _minus_raw and has_ctx:
            def _fuzzy_idem(s: str) -> str:
                s = re.sub(r'/\\*.*?\\*/', '', s).rstrip()
                if s.lstrip().startswith('#'):
                    return re.sub(r'\\s+', ' ', s).strip()
                s = re.sub(r'\\s+(?://|#).*$', '', s)
                return re.sub(r'\\s+', ' ', s).strip()
            _adds_f = [_fuzzy_idem(a) for a in _adds_raw]
            _adds_f = [a for a in _adds_f if a]
            _file_f = {_fuzzy_idem(l) for l in file_lines}
            if _adds_f and all(a in _file_f for a in _adds_f):
                _ctx_raw = [pl.text for pl in hunk.lines if pl.kind == ' ']
                _ctx_f = [_fuzzy_idem(c) for c in _ctx_raw if _fuzzy_idem(c)]
                if _ctx_f and any(c in _file_f for c in _ctx_f):
                    return True, (
                        f"ADD_ONLY: {len(_adds_f)} adição(ões) já "
                        f"presente(s) no arquivo (fuzzy) + âncora de "
                        f"contexto encontrada."
                    )'''

if new_case5 in src:
    print('SKIP STEP 1: caso 5 v3 já presente')
elif old_case5 in src:
    src = src.replace(old_case5, new_case5, 1)
    print('✓ STEP 1: caso 5 substituído por versão fuzzy')
else:
    sys.exit('ERROR STEP 1: bloco caso 5 não encontrado')

# ── STEP 2: STEP 3 (partial dup reject) também usa raw + fuzzy ─────
old_step3 = '''            # ─── v6.16: ADD_ONLY com adições parcialmente duplicadas ──
            if match_type.startswith("ADD_ONLY"):
                _adds = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == "+"]
                _adds_n = [a for a in _adds if a]'''

new_step3 = '''            # ─── v6.16: ADD_ONLY com adições parcialmente duplicadas ──
            if match_type.startswith("ADD_ONLY"):
                def _fuzzy_dup(s: str) -> str:
                    s = re.sub(r'/\\*.*?\\*/', '', s).rstrip()
                    if s.lstrip().startswith('#'):
                        return re.sub(r'\\s+', ' ', s).strip()
                    s = re.sub(r'\\s+(?://|#).*$', '', s)
                    return re.sub(r'\\s+', ' ', s).strip()
                _adds = [pl.text for pl in hunk.lines if pl.kind == "+"]
                _adds_n = [_fuzzy_dup(a) for a in _adds if _fuzzy_dup(a)]'''

if new_step3 in src:
    print('SKIP STEP 2: STEP 3 v3 já presente')
elif old_step3 in src:
    src = src.replace(old_step3, new_step3, 1)
    print('✓ STEP 2: STEP 3 usa fuzzy raw')
else:
    print('SKIP STEP 2: STEP 3 anchor não encontrado (não-bloqueante)')

# ── STEP 3: comparação do STEP 3 também precisa ser fuzzy ──────────
old_cmp = '                    _file_set = {cls._normalize_line(l) for l in modified_lines}'
new_cmp = '                    _file_set = {_fuzzy_dup(l) for l in modified_lines}'

if new_cmp in src:
    print('SKIP STEP 3: comparação fuzzy já presente')
elif old_cmp in src:
    src = src.replace(old_cmp, new_cmp, 1)
    print('✓ STEP 3: comparação fuzzy no STEP 3')
else:
    print('SKIP STEP 3: comparação anchor não encontrado (não-bloqueante)')

# ── Validação ────────────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError L{e.lineno}: {e.msg}\n  {e.text!r}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py patcheado ({len(src)} bytes)')
else:
    print('OK: nenhuma alteração')
