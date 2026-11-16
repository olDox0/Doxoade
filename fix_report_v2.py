#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_report_v2.py — move o bloco de serialize para DEPOIS do loop
   e adiciona all_views = [] antes do loop."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── STEP 1: substituir bloco deslocado por "all_views = []" ─────────
old_pattern = '    click.echo("─" * 75)\n\n    if report and all_views:'
new_pattern = '    click.echo("─" * 75)\n\n    all_views = []'

if old_pattern in src:
    start_idx = src.find(old_pattern)
    end_idx = src.find('    for p in patches:', start_idx)
    if end_idx < 0:
        print("ERROR: end of misplaced block not found")
        sys.exit(1)
    src = src[:start_idx] + new_pattern + '\n    for p in patches:' + src[end_idx + len('    for p in patches:'):]
    print("✓ STEP 1: removed misplaced block, added all_views = []")
else:
    print("SKIP: misplaced block pattern not found (may already be fixed)")

# ── STEP 2: adicionar serialize DEPOIS do loop, ANTES do resumo ─────
resumo_marker = '    click.echo("─" * 75)\n    click.echo(\n        f"📊 Resumo:'

if resumo_marker not in src:
    print("ERROR: resumo marker not found")
    sys.exit(1)

resumo_idx = src.find(resumo_marker)
before_resumo = src[max(0, resumo_idx - 3000):resumo_idx]

if 'CodeView.serialize_report' in before_resumo:
    print("SKIP: serialize already present before resumo")
else:
    # Nota: "\\n" no source vira "\n" no arquivo (escape de newline válido)
    block = (
        '    if report and all_views:\n'
        '        from doxoade.commands.moddify_sys.mody_code_view import CodeView\n'
        '        try:\n'
        '            CodeView.serialize_report(\n'
        '                all_views, Path(report), str(target_diff),\n'
        '                chosen_parser, confidence)\n'
        '            click.secho(f"\\n📊 Relatório estruturado: {report}",\n'
        '                        fg="green", bold=True)\n'
        '        except Exception as _e:\n'
        '            click.secho(f"⚠ Falha ao gravar --report: {_e}", fg="red")\n'
        '\n'
    )
    src = src[:resumo_idx] + block + src[resumo_idx:]
    print("✓ STEP 2: serialize block inserted after loop")

# ── Validação ────────────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    raise SystemExit(f'SyntaxError L{e.lineno}: {e.msg}\n  {e.text!r}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py reparado ({len(src)} bytes)')
else:
    print('OK: nenhuma alteração necessária')
