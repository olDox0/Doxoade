#!/usr/bin/env python3
# remove_vulcan_bootstrap.py
# [DOX-UNUSED] import sys
from pathlib import Path
import re

ROOT = Path.cwd()
PATTERN = re.compile(
    r"# --- DOXOADE_VULCAN_BOOTSTRAP:START ---.*?# --- DOXOADE_VULCAN_BOOTSTRAP:END ---\n?",
    re.DOTALL
)

changed = []
for p in ROOT.rglob("__main__.py"):
    text = p.read_text(encoding="utf-8", errors="replace")
    new = PATTERN.sub("", text)
    if new != text:
        p.write_text(new, encoding="utf-8")
        changed.append(p)

if changed:
    print("Removido bootstrap nestes arquivos:")
    for c in changed:
        print(" -", c)
else:
    print("Nenhum bootstrap encontrado em __main__.py a partir da raiz:", ROOT)