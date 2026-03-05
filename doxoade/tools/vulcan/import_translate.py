# vulcan/import_translate.py
# [DOX-UNUSED] import sys
import importlib.util
from pathlib import Path

class ImportTranslator:
    def __init__(self, base_dir: Path, mapping: dict[str, str]):
        self.base_dir = base_dir
        self.mapping = mapping

    def find_spec(self, fullname, path, target=None):
        for src, dst in self.mapping.items():
            if fullname == src or fullname.startswith(src + "."):
                rel = fullname[len(src):].lstrip(".")
                real_mod = f"{dst}.{rel}" if rel else dst

                try:
                    return importlib.util.find_spec(real_mod)
                except ModuleNotFoundError:
                    return None
        return None