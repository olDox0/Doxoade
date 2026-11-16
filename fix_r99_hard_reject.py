#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_r99_hard_reject.py — promove R99 de WARN para FAIL no simulate_or_apply."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── Anchor: logo após o bloco v6.12 (OVERSHOOT_CORRECTED), antes do if match_type == 'NONE'
anchor = '            # ─── v6.3: reportar ambiguidade explicitamente ────────────────\n'
if anchor not in src:
    sys.exit('ERROR: ambiguity anchor not found')

if 'R99_SUSPICIOUS_INDENTED_ADD' in src:
    print('SKIP: R99 hard reject already present')
else:
    block = (
        '            # ─── v6.15: R99 hard reject (ADD_ONLY em linha indentada + duplicata) ──\n'
        '            if match_type.startswith("ADD_ONLY") and loc is not None and loc < len(modified_lines):\n'
        '                _target = modified_lines[loc] if loc < len(modified_lines) else ""\n'
        '                if _target and _target[:1] in (" ", "\\t"):\n'
        '                    _adds = [cls._normalize_line(pl.text) for pl in hunk.lines if pl.kind == "+"]\n'
        '                    _adds_n = [a for a in _adds if a]\n'
        '                    _file_norms = {cls._normalize_line(l) for l in working_lines}\n'
        '                    _dups = [a for a in _adds_n if a in _file_norms]\n'
        '                    if _dups:\n'
        '                        report["details"].append({\n'
        '                            "hunk": idx,\n'
        '                            "status": "REJEITADO (R99)",\n'
        '                            "reason": (\n'
        '                                f"R99_SUSPICIOUS_INDENTED_ADD: inserção em L{loc+1} "\n'
        '                                f"({_target.strip()[:50]!r}) e "\n'
        '                                f"{len(_dups)}/{len(_adds_n)} linhas de adição já "\n'
        '                                f"existem no arquivo (provável duplicação)."\n'
        '                            ),\n'
        '                            "match_type": "SUSPICIOUS_REJECT",\n'
        '                            "loc": loc + 1,\n'
        '                            "duplicate_additions": _dups[:3],\n'
        '                        })\n'
        '                        report["hunks_failed"] += 1\n'
        '                        continue\n'
        '\n'
    )
    src = src.replace(anchor, block + anchor, 1)
    print('✓ R99 hard reject block inserted')

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
    print('OK: nenhuma alteração')
