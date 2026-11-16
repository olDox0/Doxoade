# add_code_view.py — patcheia mody_patch.py de forma idempotente
from pathlib import Path

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src
applied = []

# ── FIX 1: signature (adiciona verbose/report/parser_name/code) ─────
old_sig = ('def mod_patch(ctx, patch_file, apply, archive, generate, checkshot,\n'
           '              checkshot_arg, keep_snapshot, report_pre_broken, force,\n'
           '              freestyle):')
new_sig = ('def mod_patch(ctx, patch_file, apply, archive, generate, checkshot,\n'
           '              checkshot_arg, keep_snapshot, report_pre_broken, force,\n'
           '              freestyle, verbose, report, parser_name, code):')
if old_sig in src:
    src = src.replace(old_sig, new_sig, 1); applied.append('signature')
elif 'freestyle, verbose, report, parser_name, code):' in src:
    applied.append('signature (already fixed)')
else:
    raise SystemExit('ABORT: signature anchor not found')

# ── FIX 2: import _REGISTRY ─────────────────────────────────────────
if 'import detect_and_parse\n' in src and '_REGISTRY' not in src.split('\n\n')[0]:
    src = src.replace(
        'from doxoade.commands.moddify_sys.mody_parsers import detect_and_parse\n',
        'from doxoade.commands.moddify_sys.mody_parsers import detect_and_parse, _REGISTRY\n',
        1)
    applied.append('_REGISTRY import')

# ── FIX 3: decorator --code ─────────────────────────────────────────
if "@click.option('--code'" not in src:
    anchor = "@click.pass_context\ndef mod_patch("
    if anchor not in src:
        raise SystemExit('ABORT: @click.pass_context anchor not found')
    src = src.replace(
        anchor,
        "@click.option('--code', is_flag=True,\n"
        "              help='Mostra o código original vs. o patch por hunk (console).')\n"
        + anchor, 1)
    applied.append('--code decorator')

# ── FIX 4: all_views = [] antes do loop ─────────────────────────────
if '    all_views = []' not in src:
    anchor = '    click.echo("─" * 75)\n    for p in patches:'
    if anchor not in src:
        raise SystemExit('ABORT: for-patches anchor not found')
    src = src.replace(
        anchor,
        '    all_views = []\n' + anchor, 1)
    applied.append('all_views init')

# ── FIX 5: bloco de render/serialize antes de check_analysis ────────
if 'CodeView.build_hunk_view' not in src:
    anchor = ('        if res.get("check_analysis"):\n'
              '            click.echo(f"   {Fore.CYAN}🔬 Análise do Doxoade Check:'
              '{Style.RESET_ALL}")')
    if anchor not in src:
        raise SystemExit('ABORT: check_analysis anchor not found')
    view_block = (
        '        if code or report:\n'
        '            from doxoade.commands.moddify_sys.mody_code_view import CodeView\n'
        '            _file_lines = []\n'
        '            try:\n'
        '                with open(p.target_path, "r", encoding="utf-8", errors="ignore") as _f:\n'
        '                    _file_lines = _f.readlines()\n'
        '            except Exception:\n'
        '                _file_lines = []\n'
        '            for _det in res["details"]:\n'
        '                _idx = _det.get("hunk", 0) - 1\n'
        '                if not (0 <= _idx < len(p.hunks)):\n'
        '                    continue\n'
        '                _st = "APPLICABLE"\n'
        '                _s = _det.get("status", "")\n'
        '                if "IDEMPOTENT" in _s or "JÁ APLICADO" in _s:\n'
        '                    _st = "IDEMPOTENT"\n'
        '                elif "REJEITADO" in _s or "CONFLITO" in _s:\n'
        '                    _st = "REJECTED"\n'
        '                elif "AMBÍGUO" in _s:\n'
        '                    _st = "AMBIGUOUS"\n'
        '                _v = CodeView.build_hunk_view(\n'
        '                    p.target_path, _file_lines, p.hunks[_idx], _det, _st)\n'
        '                if code:\n'
        '                    click.echo(CodeView.render_console(_v))\n'
        '                if report:\n'
        '                    all_views.append(_v)\n'
        '\n'
    )
    src = src.replace(anchor, view_block + anchor, 1)
    applied.append('view-building block')

# ── FIX 6: serialize após loop (antes do resumo) ────────────────────
if 'CodeView.serialize_report' not in src:
    anchor = '    click.echo("─" * 75)\n    click.echo(\n        f"📊 Resumo:'
    if anchor not in src:
        raise SystemExit('ABORT: resumo anchor not found')
    serialize_block = (
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
    src = src.replace(anchor, serialize_block + anchor, 1)
    applied.append('serialize block')

# ── Validação ───────────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    (FP.with_suffix('.py.broken')).write_text(src, encoding='utf-8')
    raise SystemExit(f'SyntaxError L{e.lineno}: {e.msg}\n  {e.text!r}')

if src == orig:
    print('OK: já estava tudo aplicado, nada a fazer.')
else:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py patcheado ({len(src)} bytes)')
    for a in applied:
        print(f'  ✓ {a}')