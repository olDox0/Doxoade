#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_idem_add_only.py — ADD_ONLY com todas as adições já presentes = idempotente.

Substitui o R99 hard reject (que tinha condição errada) por regra semântica
baseada em conteúdo, não em indentação.

Idempotente: pode rodar várias vezes.
"""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── STEP 1: remover bloco R99 hard reject antigo (condição errada) ──
old_r99_anchor = '            # ─── v6.15: R99 hard reject'
if old_r99_anchor in src:
    start = src.find(old_r99_anchor)
    # Remover até o próximo marcador de v6.3 (ambiguidade) ou linha em branco dupla
    end_marker = '            # ─── v6.3: reportar ambiguidade explicitamente'
    end = src.find(end_marker, start)
    if end < 0:
        # fallback: remover até a linha 'continue\n\n' seguinte
        end = src.find('                        continue\n\n', start)
        if end > 0:
            end += len('                        continue\n\n')
    if end > start:
        src = src[:start] + src[end:]
        print('✓ STEP 1: bloco R99 hard reject removido')
else:
    print('SKIP STEP 1: R99 hard reject já removido')

# ── STEP 2: adicionar caso 5 em _is_idempotent_hunk ─────────────────
old_tail = '''        # 4) Bloco de contexto + '+' presente em ordem
        block = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '+')]
        if len(block) >= 2:
            n = len(block)
            for cand in range(len(norm_file) - n + 1):
                if norm_file[cand:cand + n] == block:
                    return True, "Bloco completo já presente no arquivo."

        return False, ""'''

new_tail = '''        # 4) Bloco de contexto + '+' presente em ordem
        block = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind in (' ', '+')]
        if len(block) >= 2:
            n = len(block)
            for cand in range(len(norm_file) - n + 1):
                if norm_file[cand:cand + n] == block:
                    return True, "Bloco completo já presente no arquivo."

        # 5) ADD_ONLY com TODAS as adições já presentes no arquivo
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
                    )

        # 6) ADD_ONLY com adições parcialmente presentes → suspeito,
        #    retorna motivo mas NÃO idempotente (o caller decide rejeitar).
        #    A decisão de rejeitar fica em simulate_or_apply para permitir
        #    --force em casos extremos.
        return False, ""'''

if new_tail in src:
    print('SKIP STEP 2: caso 5 já presente em _is_idempotent_hunk')
elif old_tail in src:
    src = src.replace(old_tail, new_tail, 1)
    print('✓ STEP 2: caso 5 (ADD_ONLY duplicado) adicionado')
else:
    sys.exit('ERROR STEP 2: bloco _is_idempotent_hunk não encontrado')

# ── STEP 3: rejeitar ADD_ONLY com adições PARCIALMENTE duplicadas ───
# (algumas existem, outras não → ambíguo, rejeitar por segurança)
anchor = '            # ─── v6.3: reportar ambiguidade explicitamente ────────────────\n'
if anchor not in src:
    sys.exit('ERROR STEP 3: anchor ambiguidade não encontrado')

if 'SUSPICIOUS_PARTIAL_DUP_ADD' in src:
    print('SKIP STEP 3: partial dup reject já presente')
else:
    block = (
        '            # ─── v6.16: ADD_ONLY com adições parcialmente duplicadas ──\n'
        '            if match_type.startswith("ADD_ONLY"):\n'
        '                _adds = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == "+"]\n'
        '                _adds_n = [a for a in _adds if a]\n'
        '                if _adds_n:\n'
        '                    _file_set = {cls._normalize_line(l) for l in modified_lines}\n'
        '                    _dups = [a for a in _adds_n if a in _file_set]\n'
        '                    if _dups and len(_dups) < len(_adds_n):\n'
        '                        report["details"].append({\n'
        '                            "hunk": idx,\n'
        '                            "status": "REJEITADO (duplicata parcial)",\n'
        '                            "reason": (\n'
        '                                f"{len(_dups)}/{len(_adds_n)} adição(ões) "\n'
        '                                f"já existem no arquivo. Não é idempotente "\n'
        '                                f"(algumas faltam) nem seguro "\n'
        '                                f"(algumas duplicariam)."\n'
        '                            ),\n'
        '                            "match_type": "SUSPICIOUS_PARTIAL_DUP_ADD",\n'
        '                            "duplicate_additions": _dups[:3],\n'
        '                        })\n'
        '                        report["hunks_failed"] += 1\n'
        '                        continue\n'
        '\n'
    )
    src = src.replace(anchor, block + anchor, 1)
    print('✓ STEP 3: rejeição de duplicata parcial adicionada')

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
