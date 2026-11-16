#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_code_view_v1.py — move R12 do corpo de RuleTrace para infer_rule_trace."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_code_view.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── STEP 1: remover o R12 mal posicionado dentro de RuleTrace ──────
bad_block = '''    if status == "REJECTED" and detail.get("semantic_verdict"):
        v = detail["semantic_verdict"]
        traces.append(RuleTrace(
            "R12_SEMANTIC_CLASSIFY", "validate",
            {"verdict": v, "confidence": detail["semantic_confidence"]},
            "WARN" if v in ("REFACTORED", "SUPERSEDED") else "FAIL",
            detail["semantic_hint"],
        ))
'''

if bad_block in src:
    src = src.replace(bad_block, '', 1)
    print('✓ STEP 1: R12 mal posicionado removido de RuleTrace')
else:
    print('SKIP STEP 1: bloco mal posicionado não encontrado (talvez já corrigido)')

# ── STEP 2: re-inserir R12 corretamente em infer_rule_trace ────────
old_anchor = '''        if abs(detail.get("offset", 0)) > 5:
            traces.append(RuleTrace(
                "R99_LARGE_OFFSET", "validate",
                {"offset": detail.get("offset")}, "WARN",
                "large offset — verify anchor"))
        return traces'''

new_anchor = '''        if abs(detail.get("offset", 0)) > 5:
            traces.append(RuleTrace(
                "R99_LARGE_OFFSET", "validate",
                {"offset": detail.get("offset")}, "WARN",
                "large offset — verify anchor"))

        # R12 — classificação semântica (se presente)
        _sv = detail.get("semantic_verdict")
        if _sv and _sv != "UNKNOWN":
            _vconf = detail.get("semantic_confidence", 0.0)
            _vhint = detail.get("semantic_hint", "")
            _vout = "WARN" if _sv in (
                "REFACTORED", "SUPERSEDED", "RELOCATED"
            ) else "FAIL"
            traces.append(RuleTrace(
                "R12_SEMANTIC_CLASSIFY", "validate",
                {"verdict": _sv, "confidence": _vconf},
                _vout, _vhint,
            ))
        return traces'''

if old_anchor in src:
    src = src.replace(old_anchor, new_anchor, 1)
    print('✓ STEP 2: R12 re-inserido em infer_rule_trace')
elif '_sv = detail.get("semantic_verdict")' in src:
    print('SKIP STEP 2: R12 já presente corretamente')
else:
    sys.exit('ERROR STEP 2: anchor do R99/return traces não encontrado')

# ── Validate ────────────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError L{e.lineno}: {e.msg}\n  {e.text!r}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_code_view.py reparado ({len(src)} bytes)')
else:
    print('OK: nada a fazer')