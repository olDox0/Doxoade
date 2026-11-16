# -*- coding: utf-8 -*-
# doxoade/commands/moddify_sys/mody_freestyle.py
"""
[MODY FREESTYLE] Parser tolerante a diffs decorados.

Reconhece formatos de exibição como:

     - | linha removida
     + | linha adicionada
       | linha de contexto
Mudanças perto da linha N

Converte para FilePatch/Hunk compatíveis com PatchSurgeon, que já
possui triangulação, idempotência e validação de sintaxe.
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List, Optional, Tuple

from doxoade.commands.moddify_sys.mody_patch import (
    PatchLine, Hunk, FilePatch,
)

# Hunk hint: "Mudanças perto da linha N"
# Tolerante a mojibake (├º, Г§) caso o arquivo tenha sido salvo em cp850/cp1252
RE_HUNK_HINT = re.compile(
    r'^\s*Mudan(?:[çc]|├º|Г§|Ã§)as\s+perto\s+da\s+linha\s+(\d+)\s*$',
    re.IGNORECASE,
)

# Linhas decoradas:
#   "     - | conteúdo"   → remoção
#   "     + | conteúdo"   → adição
#   "       | contexto"   → contexto
RE_CHANGE  = re.compile(r'^\s*([-+])\s*\|\s?(.*)$')
RE_CONTEXT = re.compile(r'^\s+\|\s?(.*)$')

# Cabeçalhos de arquivo (tolerantes): captura "a/path" ou "b/path"
RE_FILE_A = re.compile(r'(?:^|\s)a/(\S+)')
RE_FILE_B = re.compile(r'(?:^|\s)b/(\S+)')


def looks_like_freestyle(text: str) -> bool:
    """Heurística: tem hint de hunk + várias linhas com pipe decorado?"""
    if not RE_HUNK_HINT.search(text):
        return False
    n_pipe = 0
    for ln in text.splitlines():
        if RE_CHANGE.match(ln) or RE_CONTEXT.match(ln):
            n_pipe += 1
            if n_pipe >= 3:
                return True
    return False


class FreestyleDiffParser:
    """Parser de diffs decorados → FilePatch[] consumível por PatchSurgeon."""

    @classmethod
    def parse(cls, text: str, project_root: Path) -> List[FilePatch]:
        patches: List[FilePatch] = []
        current_patch: Optional[FilePatch] = None
        # Buffer do hunk atual: (linha_hint, [PatchLine, ...])
        hunk_raw: List[Tuple[Optional[int], List[PatchLine]]] = []
        last_hint: Optional[int] = None

        def _flush_hunk_buffer():
            nonlocal hunk_raw
            if current_patch is None:
                hunk_raw = []
                return
            for hint, lines in hunk_raw:
                if not lines:
                    continue
                old_count = sum(1 for pl in lines if pl.kind in (' ', '-'))
                new_count = sum(1 for pl in lines if pl.kind in (' ', '+'))
                base = hint if hint else 1
                current_patch.hunks.append(Hunk(
                    old_start=base,
                    old_count=old_count,
                    new_start=base,
                    new_count=new_count,
                    header_ctx=(f"freestyle hint L{hint}"
                                if hint else "freestyle"),
                    lines=list(lines),
                ))
            hunk_raw = []

        def _flush_patch():
            nonlocal current_patch
            if current_patch is None:
                return
            _flush_hunk_buffer()
            patches.append(current_patch)
            current_patch = None

        for raw in text.splitlines():
            # 1) Hint de hunk
            hm = RE_HUNK_HINT.match(raw)
            if hm:
                last_hint = int(hm.group(1))
                hunk_raw.append((last_hint, []))
                continue

            # 2) Linha de remoção/adição (possível cabeçalho de arquivo)
            cm = RE_CHANGE.match(raw)
            if cm:
                marker, content = cm.group(1), cm.group(2)

                # Cabeçalho de arquivo: "--- a/..." ou "+++ b/..."
                # (aqui toleramos 1+ '-', 1+ '+')
                if marker == '-':
                    fm = RE_FILE_A.search(content)
                    if fm:
                        _flush_patch()
                        rel = fm.group(1)
                        current_patch = FilePatch(
                            raw_old_path=f"a/{rel}",
                            raw_new_path=f"b/{rel}",
                            target_path=(project_root / rel).resolve(),
                            is_new_file=False,
                        )
                        last_hint = None
                        continue
                elif marker == '+':
                    fm = RE_FILE_B.search(content)
                    if fm:
                        # Se ainda não temos patch, abre um aqui
                        if current_patch is None:
                            rel = fm.group(1)
                            current_patch = FilePatch(
                                raw_old_path=f"a/{rel}",
                                raw_new_path=f"b/{rel}",
                                target_path=(project_root / rel).resolve(),
                                is_new_file=False,
                            )
                        last_hint = None
                        continue

                # Linha normal de conteúdo
                if current_patch is not None:
                    if not hunk_raw:
                        hunk_raw.append((last_hint, []))
                    hunk_raw[-1][1].append(
                        PatchLine(kind=marker, text=content)
                    )
                continue

            # 3) Linha de contexto
            ctxm = RE_CONTEXT.match(raw)
            if ctxm and current_patch is not None:
                if not hunk_raw:
                    hunk_raw.append((last_hint, []))
                hunk_raw[-1][1].append(
                    PatchLine(kind=' ', text=ctxm.group(1))
                )
                continue

            # 4) Linhas em branco / decorativas → apenas ignoradas

        _flush_patch()
        return patches
