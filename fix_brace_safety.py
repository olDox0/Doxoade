#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fix_brace_safety.py — adiciona validação de brace balance para .c/.h
   e bloqueia offset grande sem --force."""
from pathlib import Path
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ═══════════════════════════════════════════════════════════════
# PARTE 1 — método _validate_brace_balance na classe PatchSurgeon
# ═══════════════════════════════════════════════════════════════
if '_validate_brace_balance' in src:
    print('SKIP 1: _validate_brace_balance já presente')
else:
    anchor = '    @classmethod\n    def _validate_module_compile('
    block = '''    @classmethod
    def _validate_brace_balance(cls, content: str, target_path: Path) -> Optional[str]:
        """v6.18 — Checa balanceamento de chaves em C/C++ (pré-save)."""
        if not target_path:
            return None
        if target_path.suffix.lower() not in ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx'):
            return None
        import re as _re
        s = _re.sub(r'/\\*.*?\\*/', '', content, flags=_re.DOTALL)
        s = _re.sub(r'//[^\\n]*', '', s)
        s = _re.sub(r'"(?:\\\\.|[^"\\\\])*"', '""', s)
        s = _re.sub(r"'(?:\\\\.|[^'\\\\])*'", "''", s)
        opens = s.count('{')
        closes = s.count('}')
        if opens != closes:
            return f"Brace mismatch: {opens} '{{' vs {closes} '}}' (delta {opens - closes:+d})"
        return None

'''
    if anchor not in src:
        sys.exit('ERROR 1: anchor _validate_module_compile não encontrado')
    src = src.replace(anchor, block + anchor, 1)
    print('✓ 1: método _validate_brace_balance adicionado')

# ═══════════════════════════════════════════════════════════════
# PARTE 2 — rejeitar offset grande sem --force (antes do apply)
# ═══════════════════════════════════════════════════════════════
if 'LARGE_OFFSET_BLOCK' in src:
    print('SKIP 2: large offset check já presente')
else:
    anchor = '''            # ─── v6.3: reportar ambiguidade explicitamente ────────────────
'''
    if anchor not in src:
        sys.exit('ERROR 2: anchor ambiguidade não encontrado')
    block = '''            # ─── v6.18: bloquear offset absurdo sem --force ────────
            if abs(offset) > 20 and not force:
                report["details"].append({
                    "hunk": idx,
                    "status": "BLOQUEADO (offset grande)",
                    "reason": (
                        f"Offset {offset} > 20; aplicação insegura. "
                        f"Revise com --code ou use --force para ignorar."
                    ),
                    "match_type": "LARGE_OFFSET_BLOCK",
                    "offset": offset,
                })
                report["hunks_failed"] += 1
                continue

'''
    src = src.replace(anchor, block + anchor, 1)
    print('✓ 2: bloqueio de offset > 20 adicionado (com --force para bypass)')

# ═══════════════════════════════════════════════════════════════
# PARTE 3 — validar brace balance após aplicar (por arquivo)
# ═══════════════════════════════════════════════════════════════
if '_validate_brace_balance(new_content' in src:
    print('SKIP 3: brace check no apply já presente')
else:
    anchor = '''        if apply:
            if report["hunks_failed"] > 0:'''
    block = '''        # v6.18 — validar brace balance para C antes de gravar
        if patch.target_path and patch.target_path.suffix.lower() in (
                '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx'):
            _orig_bal = cls._validate_brace_balance(original_content, patch.target_path)
            _new_bal = cls._validate_brace_balance(new_content, patch.target_path)
            if _orig_bal is None and _new_bal is not None:
                report["syntax_ok"] = False
                report["errors"].append(
                    f"Violação Ma'at (braces C): {_new_bal}\\n"
                    f"  O patch desbalancearia {{ }} — abortando gravação.\\n"
                    f"  Sugestão: revisar com --code e usar `mody replace`."
                )

        if apply:
            if report["hunks_failed"] > 0:'''
    if anchor not in src:
        sys.exit('ERROR 3: anchor "if apply:" não encontrado')
    src = src.replace(anchor, block, 1)
    print('✓ 3: validação de brace balance no apply adicionada')

# ── Validação ────────────────────────────────────────────────────
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
    print('OK: nada a fazer')