# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/bridge.py (v83.9 Omega Gold)
import os
import sys
import importlib.util
from pathlib import Path

class VulcanBridge:
    def __init__(self, project_root):
        self.root = Path(project_root)
        self.bin_dir = self.root / ".doxoade" / "vulcan" / "bin"

    def is_binary_stale(self, script_path: str) -> bool:
        script_name = os.path.basename(script_path).replace('.py', '')
        ext = ".pyd" if os.name == 'nt' else ".so"
        bin_path = self.bin_dir / f"v_{script_name}{ext}"
        if not bin_path.exists(): return True
        return os.path.getmtime(script_path) > os.path.getmtime(bin_path)

    def get_optimized_module(self, original_module_name, script_path=None):
        """Carrega o módulo injetando o Venv do Alvo (Fix: Requests error)."""
        if script_path and self.is_binary_stale(script_path): return None

        v_name = f"v_{original_module_name}"
        ext = ".pyd" if os.name == 'nt' else ".so"
        bin_path = self.bin_dir / f"{v_name}{ext}"

        if not bin_path.exists(): return None

        # --- PROTOCOLO DE FUSÃO DE AMBIENTES ---
        old_path = sys.path.copy()
        try:
            # 1. Injeta Raiz do Projeto
            target_dir = str(self.root.resolve())
            if target_dir not in sys.path:
                sys.path.insert(0, target_dir)

            # 2. Injeta Venv do Projeto Alvo (VITAL para binários nativos)
            # Busca recursiva simples pelo site-packages do alvo
            venv_path = self.root / "venv"
            if venv_path.exists():
                sp = venv_path / "Lib" / "site-packages" if os.name == 'nt' else \
                     venv_path / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
                if sp.exists() and str(sp) not in sys.path:
                    sys.path.insert(1, str(sp))

            spec = importlib.util.spec_from_file_location(v_name, str(bin_path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[v_name] = mod
                spec.loader.exec_module(mod)
                return mod
# [DOX-UNUSED]         except Exception as e:
            # Fallback silencioso
            return None
        finally:
            sys.path = old_path
        return None

vulcan_bridge = VulcanBridge(os.getcwd())