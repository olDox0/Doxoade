#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""clean_shadow_dupes.py — remove blocos shadow duplicados de mody_patch.py.

Estratégia:
1. Localiza todos os `if shadow_path:` (4-space indent) no corpo de mod_patch.
2. Localiza o último `click.echo(f"📊 Resumo:` (fim do escopo).
3. Mantém apenas o ÚLTIMO bloco shadow (o mais próximo do resumo).
4. Remove os anteriores, preservando o resto do arquivo intacto.
"""
from pathlib import Path
import re
import sys

FP = Path('doxoade/commands/moddify_sys/mody_patch.py')
src = FP.read_text(encoding='utf-8').replace('\r\n', '\n')
orig = src

# ── 1. Encontra todas as ocorrências de "if shadow_path:" no nível 4-space
anchors = [m.start() for m in re.finditer(r'\n    if shadow_path:\n', src)]
print(f'found {len(anchors)} `if shadow_path:` anchor(s)')

if len(anchors) < 2:
    print('SKIP: sem duplicação (anchor count < 2)')
    sys.exit(0)

# ── 2. Encontra o resumo (fim do escopo)
rp = src.rfind('    click.echo(\n        f"📊 Resumo:')
if rp < 0:
    sys.exit('ERROR: resumo anchor não encontrado')

# ── 3. Para cada bloco, encontra o range [início_comentário, fim_bloco)
# Início: procura para trás o último "# v6.2X" ou comentário similar
# Fim: procura o próximo `\n    if shadow_path:` ou `\n    click.echo(\n        f"📊 Resumo:`
blocks = []
for i, pos in enumerate(anchors):
    # Begin of block: scan back for a comment line "# v6.2X"
    begin = pos
    for lookback in range(pos - 1, max(pos - 3000, 0), -1):
        if src[lookback:lookback + 1] == '\n' and lookback + 1 < pos:
            line_start = lookback + 1
            line_end = src.find('\n', line_start)
            line_text = src[line_start:line_end] if line_end > 0 else ''
            if line_text.startswith('    # v6.') and 'shadow' in line_text.lower():
                begin = line_start
                break
            # Parar se encontrar linha não-comentário (evita voltar demais)
            if (line_text.strip() and
                not line_text.strip().startswith('#') and
                not line_text.strip().startswith('"""') and
                not line_text.strip().startswith("'''")):
                break
    
    # End of block: next anchor OR resumo
    if i + 1 < len(anchors):
        end = anchors[i + 1]
        # Reajustar: o "end" é o começo do próximo bloco, MAS precisamos
        # cortar até o fim do bloco atual (que é antes do próximo comentário)
        # Procurar para trás do próximo anchor até o comentário "# v6.2X"
        for lookback in range(anchors[i + 1] - 1, max(anchors[i + 1] - 3000, begin), -1):
            if src[lookback:lookback + 1] == '\n' and lookback + 1 < anchors[i + 1]:
                line_start = lookback + 1
                line_end = src.find('\n', line_start)
                line_text = src[line_start:line_end] if line_end > 0 else ''
                if line_text.startswith('    # v6.') and 'shadow' in line_text.lower():
                    end = line_start
                    break
        blocks.append((begin, end))
    else:
        # Último bloco termina no resumo
        blocks.append((begin, rp))

print(f'mapped {len(blocks)} block(s):')
for b, e in blocks:
    print(f'  [{b}:{e}] ({e-b} chars)')

# ── 4. Manter o último, remover os anteriores (de trás pra frente)
# Remove em ordem reversa para não invalidar índices
to_remove = blocks[:-1]  # tudo excepto o último
if not to_remove:
    print('SKIP: only one block after mapping')
    sys.exit(0)

# Remove em reverse order
for begin, end in reversed(to_remove):
    removed = src[begin:end]
    src = src[:begin] + src[end:]
    print(f'✓ removed {len(removed)} chars from [{begin}:{end}]')

# ── 5. Valida
try:
    compile(src, str(FP), 'exec')
except SyntaxError as e:
    FP.with_suffix('.py.broken').write_text(src, encoding='utf-8')
    sys.exit(f'SyntaxError L{e.lineno}: {e.msg}\n  {e.text!r}')

if src != orig:
    FP.with_suffix('.py.bak').write_text(orig, encoding='utf-8')
    FP.write_text(src, encoding='utf-8')
    print(f'OK: mody_patch.py cleanup ({len(src)} bytes)')
else:
    print('OK: nada a fazer')