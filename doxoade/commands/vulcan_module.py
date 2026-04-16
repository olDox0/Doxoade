# doxoade/doxoade/commands/vulcan_module.py
from pathlib import Path
VULCAN_STUB = '# Vulcan Embedded Stub\n# Gerado pelo doxoade — uso EXPLÍCITO apenas\n# Importar manualmente no projeto se desejar\n\nimport sys\nfrom pathlib import Path\n\nclass VulcanContext:\n    def __init__(self):\n        self.argv = sys.argv\n        self.cwd = Path.cwd()\n\ndef call_safe(fn):\n    try:\n        return fn(VulcanContext())\n    except TypeError:\n        return fn()\n'

def generate_vulcan_module(path: str):
    root = Path(path).resolve()
    target = root / '.doxoade' / 'vulcan.py'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return False
    target.write_text(VULCAN_STUB, encoding='utf-8')
    return True