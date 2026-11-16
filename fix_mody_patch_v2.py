#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_mody_patch_v2.py — repara mody_patch.py (indentação, signature, imports)."""
from pathlib import Path

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── FIX 1: re-indent module-level _is_idempotent_hunk into class ─
lines = src.split('\n')
def_idx = next(
    (i for i, ln in enumerate(lines)
     if ln == 'def _is_idempotent_hunk(cls, file_lines, hunk) -> Tuple[bool, str]:'),
    None,
)
if def_idx is not None:
    start = def_idx - 1 if def_idx > 0 and lines[def_idx - 1] == '@classmethod' else def_idx
    end = next(
        (i + 1 for i in range(def_idx + 1, min(def_idx + 200, len(lines)))
         if lines[i] == '    return False, ""'),
        None,
    )
    if end is None:
        raise SystemExit('ERROR FIX1: end of _is_idempotent_hunk not found')
    for i in range(start, end):
        if lines[i].strip():
            lines[i] = '    ' + lines[i]
    src = '\n'.join(lines)
    print(f'FIX1: indented L{start+1}-L{end} by +4')
else:
    print('FIX1: skipped (already inside class)')

# ── FIX 2: _checkshot_args placeholder ───────────────────────────
if '_checkshot_args = ...' in src:
    src = src.replace(
        '_checkshot_args = ...',
        '_checkshot_args: Optional[List[str]] = None',
        1,
    )
    print('FIX2: _checkshot_args fixed')
else:
    print('FIX2: skipped')

# ── FIX 3: mod_patch signature ───────────────────────────────────
old_sig = (
    '              checkshot_arg, keep_snapshot, report_pre_broken, force,\n'
    '              freestyle):'
)
new_sig = (
    '              checkshot_arg, keep_snapshot, report_pre_broken, force,\n'
    '              freestyle, verbose, report, parser_name):'
)
if old_sig in src:
    src = src.replace(old_sig, new_sig, 1)
    print('FIX3: signature updated')
elif 'freestyle, verbose, report, parser_name' in src:
    print('FIX3: skipped (already fixed)')
else:
    raise SystemExit('ERROR FIX3: signature pattern not found')

# ── FIX 4: import _REGISTRY ──────────────────────────────────────
old_imp = 'from doxoade.commands.moddify_sys.mody_parsers import detect_and_parse'
new_imp = 'from doxoade.commands.moddify_sys.mody_parsers import detect_and_parse, _REGISTRY'
if old_imp in src and '_REGISTRY' not in old_imp:
    src = src.replace(old_imp, new_imp, 1)
    print('FIX4: _REGISTRY import added')
elif new_imp in src:
    print('FIX4: skipped (already imported)')

# ── Validate ─────────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    debug = FP.with_suffix('.py.broken')
    debug.write_text(src, encoding='utf-8')
    raise SystemExit(
        f'SyntaxError after fix: L{e.lineno}: {e.msg}\n'
        f'  Line: {e.text!r}\n'
        f'  Saved: {debug}'
    )

if src == orig:
    print('OK: no changes (already valid)')
else:
    FP.write_text(src, encoding='utf-8')
    print(f'OK: {FP.name} repaired ({len(src)} bytes)')