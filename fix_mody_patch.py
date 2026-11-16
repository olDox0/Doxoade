# fix_mody_patch.py — rodar da raiz do projeto
# -*- coding: utf-8 -*-
from pathlib import Path

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8')
src = src.replace('\r\n', '\n')   # normaliza
orig = src

# ─── Fix 1: restaurar _checkshot_args como atributo tipado ──────────
src = src.replace(
    '    _checkshot_args = ...\n    _checkshot_keep = False',
    '    _checkshot_args: Optional[List[str]] = None\n    _checkshot_keep: bool = False',
    1,
)

# ─── Fix 2: remover bloco de placeholders quebrados ─────────────────
anchor = '    @classmethod\n    def _is_idempotent_hunk(cls, file_lines, hunk): ...'
apos = src.find(anchor)
if apos < 0:
    raise SystemExit('ERROR: placeholder block not found '
                     '(file state differs from expected)')
end_marker = 'def simulate_or_apply(...): ...'
epos = src.find(end_marker, apos)
if epos < 0:
    raise SystemExit('ERROR: placeholder end not found')
i = epos + len(end_marker)
while i < len(src) and src[i] in ' \t\n':
    i += 1
src = src[:apos] + '\n' + src[i:]

# ─── Fix 3: mover _is_idempotent_hunk (module-level) p/ dentro da classe
wrapper = ('@classmethod\n'
           'def _is_idempotent_hunk(cls, file_lines, hunk) '
           '-> Tuple[bool, str]:')
wpos = src.find(wrapper)
if wpos < 0:
    raise SystemExit('ERROR: module-level _is_idempotent_hunk not found')
end_marker = '    return False, ""\n'
epos = src.find(end_marker, wpos)
if epos < 0:
    raise SystemExit('ERROR: _is_idempotent_hunk end not found')
epos += len(end_marker)
block = src[wpos:epos]
indented = '\n'.join(
    '    ' + ln if ln.strip() else ln
    for ln in block.split('\n')
)
src = src[:wpos] + indented + src[epos:]

# ─── Validação final ────────────────────────────────────────────────
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    raise SystemExit(
        f'ERROR: fix incompleto — ainda há SyntaxError em L{e.lineno}: {e.msg}\n'
        f'       Linha: {e.text!r}'
    )

if src == orig:
    print('OK: arquivo já estava válido, nada a fazer.')
else:
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py reparado ({len(src)} bytes).')