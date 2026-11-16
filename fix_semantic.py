#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_semantic.py — integra mody_semantic em mody_patch + mody_code_view.

Idempotente. Valida com compile() antes de gravar. Backups em *.bak.
"""
from pathlib import Path
import sys

FP_PATCH = Path('doxoade/commands/moddify_sys/mody_patch.py')
FP_VIEW  = Path('doxoade/commands/moddify_sys/mody_code_view.py')
changed = []


# ════════════════════════════════════════════════════════════════
# PARTE A — mody_patch.py: semantic classify em simulate_or_apply
# ════════════════════════════════════════════════════════════════
src = FP_PATCH.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

old_anchor = (
    '                report["details"].append({\n'
    '                    "hunk": idx, "status": "REJEITADO",\n'
    '                    "reason": reason_msg,\n'
    '                    "match_type": "NONE", "loc": hunk.old_start,\n'
    '                })\n'
    '                report["hunks_failed"] += 1'
)

new_anchor = (
    '                # v6.17: classificação semântica do motivo real\n'
    '                try:\n'
    '                    from doxoade.commands.moddify_sys.mody_semantic import classify_rejection\n'
    '                    _verdict, _vconf, _vhint = classify_rejection(hunk, working_lines)\n'
    '                except Exception:\n'
    '                    _verdict, _vconf, _vhint = "UNKNOWN", 0.0, ""\n'
    '                if _verdict != "UNKNOWN":\n'
    '                    reason_msg += (\n'
    '                        f"\\n      🧠 Semântica: {_verdict} "\n'
    '                        f"(conf {_vconf:.2f}) — {_vhint}"\n'
    '                    )\n'
    '                report["details"].append({\n'
    '                    "hunk": idx, "status": "REJEITADO",\n'
    '                    "reason": reason_msg,\n'
    '                    "match_type": "NONE", "loc": hunk.old_start,\n'
    '                    "semantic_verdict": _verdict,\n'
    '                    "semantic_confidence": _vconf,\n'
    '                    "semantic_hint": _vhint,\n'
    '                })\n'
    '                report["hunks_failed"] += 1'
)

if 'semantic_verdict' in src and 'classify_rejection' in src:
    print('SKIP A: simulate_or_apply já tem semantic')
elif old_anchor in src:
    src = src.replace(old_anchor, new_anchor, 1)
    print('✓ A: simulate_or_apply inclui classify_rejection')
else:
    sys.exit('ERROR A: anchor do append REJEITADO não encontrado')

# Console: colorir 🧠 Semântica em magenta
old_console = (
    '                    if \'🔍 Linhas suspeitas\' in ln or \'🔶 Linhas com divergência\' in ln:\n'
    '                        click.echo(f"     {Fore.YELLOW}{ln}{Style.RESET_ALL}")\n'
    '                    elif ln.strip().startswith(\'L\') and (\':\' in ln or \'|\' in ln):'
)
new_console = (
    '                    if \'🔍 Linhas suspeitas\' in ln or \'🔶 Linhas com divergência\' in ln:\n'
    '                        click.echo(f"     {Fore.YELLOW}{ln}{Style.RESET_ALL}")\n'
    '                    elif \'🧠 Semântica\' in ln:\n'
    '                        click.echo(f"     {Fore.MAGENTA}{ln}{Style.RESET_ALL}")\n'
    '                    elif ln.strip().startswith(\'L\') and (\':\' in ln or \'|\' in ln):'
)
if '🧠 Semântica\' in ln' in src:
    print('SKIP A2: coloração 🧠 já presente')
elif old_console in src:
    src = src.replace(old_console, new_console, 1)
    print('✓ A2: console coloriza 🧠 Semântica em magenta')
else:
    print('WARN A2: console anchor não encontrado (não-bloqueante)')

try:
    compile(src, str(FP_PATCH), 'exec')
except SyntaxError as e:
    FP_PATCH.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError A L{e.lineno}: {e.msg}')

if src != orig:
    FP_PATCH.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP_PATCH.write_text(src, encoding='utf-8')
    changed.append('mody_patch.py')


# ════════════════════════════════════════════════════════════════
# PARTE B — mody_code_view.py: HunkView + build + R12 + serialize
# ════════════════════════════════════════════════════════════════
src = FP_VIEW.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# B1) HunkView dataclass — 3 campos novos
old_b1 = (
    '    rejection_reason: str = ""\n'
    '    suggestions: List[str] = field(default_factory=list)'
)
new_b1 = (
    '    rejection_reason: str = ""\n'
    '    suggestions: List[str] = field(default_factory=list)\n'
    '    semantic_verdict: str = "UNKNOWN"\n'
    '    semantic_confidence: float = 0.0\n'
    '    semantic_hint: str = ""'
)
if 'semantic_verdict: str' in src:
    print('SKIP B1: HunkView já tem campos semânticos')
elif old_b1 in src:
    src = src.replace(old_b1, new_b1, 1)
    print('✓ B1: HunkView + 3 campos semânticos')
else:
    sys.exit('ERROR B1: HunkView anchor não encontrado')

# B2) build_hunk_view — preenche os 3 campos
old_b2 = (
    '            rejection_reason=detail.get("reason", ""),\n'
    '            suggestions=detail.get("suggestions", []),\n'
    '        )'
)
new_b2 = (
    '            rejection_reason=detail.get("reason", ""),\n'
    '            suggestions=detail.get("suggestions", []),\n'
    '            semantic_verdict=detail.get("semantic_verdict", "UNKNOWN"),\n'
    '            semantic_confidence=detail.get("semantic_confidence", 0.0),\n'
    '            semantic_hint=detail.get("semantic_hint", ""),\n'
    '        )'
)
if 'semantic_verdict=detail.get' in src:
    print('SKIP B2: build_hunk_view já preenche semântica')
elif old_b2 in src:
    src = src.replace(old_b2, new_b2, 1)
    print('✓ B2: build_hunk_view propaga campos semânticos')
else:
    sys.exit('ERROR B2: build_hunk_view anchor não encontrado')

# B3) infer_rule_trace — adiciona R12
old_b3 = (
    '        if abs(detail.get("offset", 0)) > 5:\n'
    '            traces.append(RuleTrace(\n'
    '                "R99_LARGE_OFFSET", "validate",\n'
    '                {"offset": detail.get("offset")}, "WARN",\n'
    '                "large offset — verify anchor"))\n'
    '        return traces'
)
new_b3 = (
    '        if abs(detail.get("offset", 0)) > 5:\n'
    '            traces.append(RuleTrace(\n'
    '                "R99_LARGE_OFFSET", "validate",\n'
    '                {"offset": detail.get("offset")}, "WARN",\n'
    '                "large offset — verify anchor"))\n'
    '\n'
    '        # R12 — classificação semântica (se presente)\n'
    '        _sv = detail.get("semantic_verdict")\n'
    '        if _sv and _sv != "UNKNOWN":\n'
    '            _vconf = detail.get("semantic_confidence", 0.0)\n'
    '            _vhint = detail.get("semantic_hint", "")\n'
    '            _vout = "WARN" if _sv in (\n'
    '                "REFACTORED", "SUPERSEDED", "RELOCATED"\n'
    '            ) else "FAIL"\n'
    '            traces.append(RuleTrace(\n'
    '                "R12_SEMANTIC_CLASSIFY", "validate",\n'
    '                {"verdict": _sv, "confidence": _vconf},\n'
    '                _vout, _vhint,\n'
    '            ))\n'
    '        return traces'
)
if 'R12_SEMANTIC_CLASSIFY' in src:
    print('SKIP B3: R12 já presente')
elif old_b3 in src:
    src = src.replace(old_b3, new_b3, 1)
    print('✓ B3: R12_SEMANTIC_CLASSIFY adicionado')
else:
    sys.exit('ERROR B3: R99/return traces anchor não encontrado')

# B4) serialize_report — propaga campos no JSON
old_b4 = (
    '                    "rejection_reason": v.rejection_reason,\n'
    '                    "suggestions": v.suggestions,\n'
    '                } for v in hv]'
)
new_b4 = (
    '                    "rejection_reason": v.rejection_reason,\n'
    '                    "suggestions": v.suggestions,\n'
    '                    "semantic_verdict": v.semantic_verdict,\n'
    '                    "semantic_confidence": v.semantic_confidence,\n'
    '                    "semantic_hint": v.semantic_hint,\n'
    '                } for v in hv]'
)
if '"semantic_verdict": v.semantic_verdict' in src:
    print('SKIP B4: serialize_report já propaga semântica')
elif old_b4 in src:
    src = src.replace(old_b4, new_b4, 1)
    print('✓ B4: serialize_report inclui campos semânticos')
else:
    sys.exit('ERROR B4: serialize anchor não encontrado')

try:
    compile(src, str(FP_VIEW), 'exec')
except SyntaxError as e:
    FP_VIEW.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError B L{e.lineno}: {e.msg}')

if src != orig:
    FP_VIEW.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP_VIEW.write_text(src, encoding='utf-8')
    changed.append('mody_code_view.py')


# ════════════════════════════════════════════════════════════════
# Smoke test
# ════════════════════════════════════════════════════════════════
try:
    from doxoade.commands.moddify_sys.mody_semantic import (
        classify_rejection, parse_c_functions,
    )
    from doxoade.commands.moddify_sys.mody_patch import PatchLine, Hunk

    # parse_c_functions
    test_c = [
        'static int foo(void) {\n',
        '    return 0;\n',
        '}\n',
        '\n',
        'static int bar(int x) {\n',
        '    if (x > 0) return 1;\n',
        '    return 0;\n',
        '}\n',
    ]
    fs = parse_c_functions(test_c)
    assert len(fs) == 2, f"parse: esperado 2, obtido {len(fs)}"
    assert {f.name for f in fs} == {'foo', 'bar'}, \
        f"parse: nomes {[f.name for f in fs]}"

    # classify_rejection — SUPERSEDED
    h_sup = Hunk(old_start=1, old_count=1, new_start=1, new_count=1,
                 header_ctx='t',
                 lines=[
                     PatchLine('-', 'rc = old_call(a, b, c);'),
                     PatchLine('+', 'rc = new_call(a, b, decode_mode, c);'),
                 ])
    test_file = [
        '#include "x.h"\n',
        'void f(void) {\n',
        '    DecodeMode decode_mode = DECODE_MODE_64;\n',
        '    rc = new_call(a, b, decode_mode, c);\n',
        '}\n',
    ]
    v, c, h = classify_rejection(h_sup, test_file)
    assert v == 'SUPERSEDED', f"superseded: obtido {v}"
    print(f'✓ smoke: SUPERSEDED detectado (conf {c:.2f})')

    # classify_rejection — OBSOLETE
    h_obs = Hunk(old_start=1, old_count=1, new_start=1, new_count=1,
                 header_ctx='t',
                 lines=[PatchLine('-', 'antiga_funcao(x, y);')])
    v, c, h = classify_rejection(h_obs, ['int main(void) { return 0; }\n'])
    assert v in ('OBSOLETE', 'UNKNOWN'), f"obsolete: obtido {v}"
    print(f'✓ smoke: OBSOLETE detectado (conf {c:.2f})')

except AssertionError as e:
    print(f'✘ smoke test FALHOU: {e}')
    sys.exit(2)
except Exception as e:
    print(f'⚠ smoke test pulado: {e}')


# ════════════════════════════════════════════════════════════════
# Relatório final
# ════════════════════════════════════════════════════════════════
if changed:
    print(f'\nOK: arquivos patcheados: {", ".join(changed)}')
else:
    print('\nOK: nada a fazer (tudo já aplicado)')
