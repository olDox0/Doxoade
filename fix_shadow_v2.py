#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_shadow_v2.py — move shadow block pós-loop + adiciona hash/compile/diff detalhado."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── 1. Remover bloco shadow existente (por marker) ─────────────────
marker = '    # v6.21 — Mostra diff real vs shadow'
mp = src.find(marker)
if mp >= 0:
    ends = []
    for em in ('\n    for p in patches:', '\n    click.echo(\n        f"📊 Resumo:'):
        idx = src.find(em, mp + len(marker))
        if idx >= 0:
            ends.append(idx)
    if not ends:
        sys.exit('ERROR 1: end do bloco não encontrado')
    end_pos = min(ends)
    src = src[:mp] + src[end_pos:]
    print(f'✓ 1: bloco antigo removido ({end_pos - mp} chars)')
else:
    print('SKIP 1: bloco antigo não encontrado')

# ── 2. Inserir versão enriquecida ANTES do resumo (última ocorrência) ──
rp = src.rfind('    click.echo(\n        f"📊 Resumo:')
if rp < 0:
    sys.exit('ERROR 2: resumo anchor não encontrado')

if 'SHADOW DIFF v2' in src:
    print('SKIP 2: bloco v2 já presente')
else:
    enhanced = '''    # v6.22 — SHADOW DIFF detalhado (real vs shadow)
    if shadow_path:
        from difflib import unified_diff
        import hashlib
        import subprocess as _sp
        import shutil as _sh_util
        
        def _hash_file(p):
            h = hashlib.sha256()
            h.update(p.read_bytes())
            return h.hexdigest()[:16]
        
        def _count_lines_file(p):
            try:
                return len(p.read_text(encoding='utf-8', errors='ignore').splitlines())
            except Exception:
                return 0
        
        def _try_compile_shadow(path, ext):
            if ext == '.py':
                try:
                    import py_compile, tempfile
                    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w', encoding='utf-8') as tf:
                        tf.write(path.read_text(encoding='utf-8', errors='ignore'))
                        tf_p = tf.name
                    py_compile.compile(tf_p, doraise=True, cfile=None)
                    Path(tf_p).unlink(missing_ok=True)
                    return True, "py_compile OK"
                except Exception as e:
                    return False, "py_compile: " + str(e)[:100]
            elif ext in ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx'):
                try:
                    cands = [
                        _sh_util.which('gcc'), _sh_util.which('gcc.exe'),
                        _sh_util.which('clang'), _sh_util.which('clang.exe'),
                        _sh_util.which('cc'), _sh_util.which('cc.exe'),
                    ]
                    try:
                        _wk = root / "thirdparty" / "w64devkit" / "bin" / "gcc.exe"
                        if _wk.exists():
                            cands.insert(0, str(_wk))
                    except Exception:
                        pass
                    gcc = next((g for g in cands if g), None)
                    if not gcc:
                        return True, "compiler indisponivel (skip)"
                    r = _sp.run(
                        [gcc, '-fsyntax-only', str(path)],
                        capture_output=True, text=True, timeout=20,
                    )
                    compiler = Path(gcc).stem
                    if r.returncode == 0:
                        return True, compiler + " -fsyntax-only OK"
                    return False, compiler + ": " + (r.stderr or '')[:200]
                except Exception as e:
                    return True, "compile skip: " + str(e)[:80]
            return True, "skip"
        
        click.echo()
        click.echo(Fore.MAGENTA + "=" * 75 + Style.RESET_ALL)
        click.echo(Fore.MAGENTA + "[SHADOW] DIFF v2 (real -> shadow)" + Style.RESET_ALL)
        click.echo(Fore.DIM + "   Sandbox: " + str(shadow_path) + Style.RESET_ALL)
        click.echo(Fore.MAGENTA + "=" * 75 + Style.RESET_ALL)
        
        _shadow_summary = []
        for p in patches:
            try:
                _rel = p.target_path.relative_to(root)
            except (ValueError, AttributeError):
                _rel = Path(p.target_path.name)
            _sf = shadow_path / _rel
            
            if not _sf.exists():
                click.echo("  " + Fore.RED + "[FAIL] " + str(_rel) + Style.RESET_ALL + " -- shadow NAO escrito")
                _shadow_summary.append((str(_rel), "BLOQUEADO", ""))
                continue
            
            _real_exists = p.target_path.exists()
            _real_size = p.target_path.stat().st_size if _real_exists else 0
            _sh_size = _sf.stat().st_size
            _real_hash = _hash_file(p.target_path) if _real_exists else "MISSING"
            _sh_hash = _hash_file(_sf)
            _real_lines = _count_lines_file(p.target_path) if _real_exists else 0
            _sh_lines = _count_lines_file(_sf)
            _identical = (_real_hash == _sh_hash)
            
            click.echo()
            click.echo("  " + Fore.CYAN + "[FILE] " + str(_rel) + Style.RESET_ALL)
            click.echo("     real  : hash=" + Fore.DIM + _real_hash + Style.RESET_ALL + "  size=" + str(_real_size) + "B  lines=" + str(_real_lines))
            click.echo("     shadow: hash=" + Fore.DIM + _sh_hash + Style.RESET_ALL + "  size=" + str(_sh_size) + "B  lines=" + str(_sh_lines))
            
            if _identical:
                click.echo("     " + Fore.GREEN + "[OK] IDENTICO (idempotente)" + Style.RESET_ALL)
                _shadow_summary.append((str(_rel), "IDENTICO", ""))
                continue
            
            _ok, _msg = _try_compile_shadow(_sf, p.target_path.suffix.lower())
            _cc_color = Fore.GREEN if _ok else Fore.RED
            _cc_icon = "[OK]" if _ok else "[FAIL]"
            click.echo("     " + _cc_color + _cc_icon + " compile: " + _msg + Style.RESET_ALL)
            
            try:
                _real_text = p.target_path.read_text(encoding='utf-8', errors='ignore') if _real_exists else ""
                _sh_text = _sf.read_text(encoding='utf-8', errors='ignore')
            except Exception as _e:
                click.echo("     " + Fore.RED + "erro de leitura: " + str(_e) + Style.RESET_ALL)
                _shadow_summary.append((str(_rel), "ERRO_LEITURA", ""))
                continue
            
            _diff = list(unified_diff(
                _real_text.splitlines(keepends=True),
                _sh_text.splitlines(keepends=True),
                fromfile="real/" + str(_rel), tofile="shadow/" + str(_rel), n=3,
            ))
            _added = sum(1 for l in _diff if l.startswith('+') and not l.startswith('+++'))
            _removed = sum(1 for l in _diff if l.startswith('-') and not l.startswith('---'))
            click.echo("     " + Fore.GREEN + "+" + str(_added) + Style.RESET_ALL + " " + Fore.RED + "-" + str(_removed) + Style.RESET_ALL + " linha(s)")
            click.echo("     " + Fore.DIM + "-" * 60 + Style.RESET_ALL)
            for _ln in _diff:
                _ln = _ln.rstrip('\\n')
                if _ln.startswith('+++') or _ln.startswith('---') or _ln.startswith('@@'):
                    click.echo("     " + Fore.CYAN + _ln + Style.RESET_ALL)
                elif _ln.startswith('+'):
                    click.echo("     " + Fore.GREEN + _ln + Style.RESET_ALL)
                elif _ln.startswith('-'):
                    click.echo("     " + Fore.RED + _ln + Style.RESET_ALL)
                else:
                    click.echo("     " + _ln)
            
            _status = "COMPILA" if _ok else "FALHA_COMPILE"
            _shadow_summary.append((str(_rel), _status, ""))
        
        click.echo()
        click.echo(Fore.MAGENTA + "=" * 75 + Style.RESET_ALL)
        click.echo(Fore.MAGENTA + "[SUMMARY] SHADOW" + Style.RESET_ALL)
        click.echo(Fore.MAGENTA + "=" * 75 + Style.RESET_ALL)
        for _rel, _st, _ in _shadow_summary:
            _c = {"IDENTICO": Fore.GREEN, "COMPILA": Fore.CYAN, "BLOQUEADO": Fore.RED}.get(_st, Fore.YELLOW)
            click.echo("  " + _c + _st.ljust(15) + Style.RESET_ALL + "  " + str(_rel))
        click.echo()
    
'''
    src = src[:rp] + enhanced + src[rp:]
    print('✓ 2: bloco v2 inserido antes do resumo')

# ── Validate ──────────────────────────────────────────────────────
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
    print('OK: nada a fazer')