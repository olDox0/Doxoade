# vulcan_safe_loader.py
import importlib.machinery
import importlib.util
import sys
import os

class SafeExtensionLoader(importlib.machinery.ExtensionFileLoader):
    def __init__(self, fullname, path, py_fallback):
        super().__init__(fullname, path)
        self._py_fallback = py_fallback

    def exec_module(self, module):
        try:
            return super().exec_module(module)

        except Exception as e:
            # 🔥 FALHOU → REMOVE O .pyd E CAI PARA .py
            sys.modules.pop(module.__name__, None)

            if self._py_fallback and os.path.exists(self._py_fallback):
                spec = importlib.util.spec_from_file_location(
                    module.__name__,
                    self._py_fallback
                )
                py_mod = importlib.util.module_from_spec(spec)
                sys.modules[module.__name__] = py_mod
                spec.loader.exec_module(py_mod)
                return

            raise  # se não houver .py, erro real