# doxoade/commands/vulcan_module.py
from pathlib import Path

VULCAN_STUB = """\
# Vulcan Embedded Stub
# Gerado pelo doxoade — uso EXPLÍCITO apenas
# Importar manualmente no projeto se desejar

import sys
from pathlib import Path

class VulcanContext:
    def __init__(self):
        self.argv = sys.argv
        self.cwd = Path.cwd()

def call_safe(fn):
    try:
        return fn(VulcanContext())
    except TypeError:
        return fn()
"""

def generate_vulcan_module(path: str):
    root = Path(path).resolve()
    target = root / ".doxoade" / "vulcan.py"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        return False  # nunca sobrescreve

    target.write_text(VULCAN_STUB, encoding="utf-8")
    return True