# doxoade/doxoade/commands/run_systems/run_vulcan.py
import os
from doxoade.tools.vulcan.bridge import vulcan_bridge

def apply_vulcan_turbo(script_path: str, globs: dict):
    """Injeta binário nativo com Sincronia de Assinatura v84.2."""
    if vulcan_bridge.is_binary_stale(script_path):
        return
    v_mod = vulcan_bridge.get_optimized_module(script_path)
    if v_mod:
        from click import echo
        script_display = os.path.basename(script_path).replace('.py', '')
        echo(f"\x1b[93m🔥 [VULCAN-TURBO] Módulo '{script_display}' operando em modo nativo.\x1b[0m")
        for attr in dir(v_mod):
            if attr.endswith('_vulcan_optimized'):
                orig = attr.replace('_vulcan_optimized', '')
                globs[orig] = getattr(v_mod, attr)