#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_reconcile_v4.py — reconcilia mody_patch.py que perdeu correções."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src
changes = []

# ═══════════════════════════════════════════════════════════════
# A. Remover semantic mal posicionado do SyntaxError branch
# ═══════════════════════════════════════════════════════════════
lines = src.split('\n')
out = []
i = 0
while i < len(lines):
    line = lines[i]
    if (line == ' ' * 24 + "if match_type == 'NONE':"
        and i + 1 < len(lines)
        and 'classify_rejection' in lines[i+1]
        and 'semantic_verdict' in '\n'.join(lines[i:i+12])):
        j = i + 1
        while j < len(lines) and lines[j] != ' ' * 24 + 'report["hunks_failed"] += 1':
            j += 1
        if j < len(lines):
            out.append(lines[j])
            i = j + 1
            changes.append('A (removed misplaced semantic)')
            continue
    out.append(line)
    i += 1
src = '\n'.join(out)

# ═══════════════════════════════════════════════════════════════
# B. Fix all_views + serialize position
# ═══════════════════════════════════════════════════════════════
if '    all_views = []' in src:
    changes.append('B (skipped — all_views already present)')
else:
    lines = src.split('\n')
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (line == '    if report and all_views:'
            and i + 1 < len(lines)
            and 'mody_code_view' in lines[i+1]):
            j = i + 1
            while j < len(lines) and j - i < 40 and lines[j] != '    for p in patches:':
                j += 1
            if j < len(lines) and lines[j] == '    for p in patches:':
                out.append('    all_views = []')
                out.append('')
                out.append(lines[j])
                i = j + 1
                changes.append('B (replaced misplaced serialize with all_views = [])')
                continue
        out.append(line)
        i += 1
    src = '\n'.join(out)
    if '    all_views = []' not in src:
        lines = src.split('\n')
        for i, line in enumerate(lines):
            if line == '    for p in patches:':
                lines.insert(i, '    all_views = []')
                lines.insert(i + 1, '')
                break
        src = '\n'.join(lines)
        changes.append('B-alt (inserted all_views = [])')

# ═══════════════════════════════════════════════════════════════
# C. Re-adicionar case 5 (fuzzy ADD_ONLY) em _is_idempotent_hunk
# ═══════════════════════════════════════════════════════════════
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

        # 5) ADD_ONLY com todas as adições já presentes (fuzzy, preserva #include)
        _adds_raw = [pl.text for pl in hunk.lines if pl.kind == '+']
        _minus_raw = [pl.text for pl in hunk.lines if pl.kind == '-']
        if _adds_raw and not _minus_raw and has_ctx:
            def _fuzzy_idem(s):
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
                    )

        return False, ""'''

if '_fuzzy_idem' in src:
    changes.append('C (skipped — case 5 already present)')
elif old_tail in src:
    src = src.replace(old_tail, new_tail, 1)
    changes.append('C (added case 5 fuzzy ADD_ONLY)')
else:
    changes.append('C (WARN — anchor not found)')

# ═══════════════════════════════════════════════════════════════
# D. Adicionar semantic ao bloco REJEITADO
# ═══════════════════════════════════════════════════════════════
old_rej = '''                report["details"].append({
                    "hunk": idx, "status": "REJEITADO",
                    "reason": reason_msg,
                    "match_type": "NONE", "loc": hunk.old_start,
                })
                report["hunks_failed"] += 1'''

new_rej = '''                # v6.17: classificação semântica
                try:
                    from doxoade.commands.moddify_sys.mody_semantic import classify_rejection
                    _verdict, _vconf, _vhint = classify_rejection(hunk, working_lines)
                except Exception:
                    _verdict, _vconf, _vhint = "UNKNOWN", 0.0, ""
                if _verdict != "UNKNOWN":
                    reason_msg += (
                        f"\\n      🧠 Semântica: {_verdict} "
                        f"(conf {_vconf:.2f}) — {_vhint}"
                    )
                report["details"].append({
                    "hunk": idx, "status": "REJEITADO",
                    "reason": reason_msg,
                    "match_type": "NONE", "loc": hunk.old_start,
                    "semantic_verdict": _verdict,
                    "semantic_confidence": _vconf,
                    "semantic_hint": _vhint,
                })
                report["hunks_failed"] += 1'''

if 'semantic_verdict": _verdict' in src:
    changes.append('D (skipped — already present)')
elif old_rej in src:
    src = src.replace(old_rej, new_rej, 1)
    changes.append('D (semantic added to REJEITADO)')
else:
    changes.append('D (WARN — anchor not found)')

# ═══════════════════════════════════════════════════════════════
# E. Adicionar serialize block antes do resumo
# ═══════════════════════════════════════════════════════════════
if 'CodeView.serialize_report' in src:
    changes.append('E (skipped — serialize already present)')
else:
    lines = src.split('\n')
    out = []
    i = 0
    inserted = False
    while i < len(lines):
        line = lines[i]
        if (line == '    click.echo("─" * 75)'
            and i + 1 < len(lines)
            and lines[i+1] == '    click.echo('
            and i + 2 < len(lines)
            and '📊 Resumo' in lines[i+2]):
            out.append(line)
            out.append('')
            out.append('    if report and all_views:')
            out.append('        from doxoade.commands.moddify_sys.mody_code_view import CodeView')
            out.append('        try:')
            out.append('            CodeView.serialize_report(')
            out.append('                all_views, Path(report), str(target_diff),')
            out.append('                chosen_parser, confidence)')
            out.append('            click.secho(f"\\n📊 Relatório estruturado: {report}",')
            out.append('                        fg="green", bold=True)')
            out.append('        except Exception as _e:')
            out.append('            click.secho(f"⚠ Falha ao gravar --report: {_e}", fg="red")')
            out.append('')
            i += 1
            inserted = True
            continue
        out.append(line)
        i += 1
    src = '\n'.join(out)
    if inserted:
        changes.append('E (serialize added before resumo)')
    else:
        changes.append('E (WARN — resumo anchor not found)')

# ═══════════════════════════════════════════════════════════════
# Validate
# ═══════════════════════════════════════════════════════════════
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError L{e.lineno}: {e.msg}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py reparado ({len(src)} bytes)')
    for c in changes:
        print(f'  ✓ {c}')
else:
    print('OK: nada a fazer')