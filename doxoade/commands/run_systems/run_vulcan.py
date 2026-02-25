# -*- coding: utf-8 -*-
# doxoade/commands/run_systems/run_vulcan.py (v84.2 Gold Fix)
import os
from ...tools.vulcan.bridge import vulcan_bridge
def apply_vulcan_turbo(script_path: str, globs: dict):
    """Injeta binário nativo com Sincronia de Assinatura v84.2."""
    
    # 1. Verifica integridade temporal (Staleness)
    if vulcan_bridge.is_binary_stale(script_path):
        return
    # 2. FIX: Chamada sincronizada com a assinatura (self + 1 arg)
    v_mod = vulcan_bridge.get_optimized_module(script_path)
    
    if v_mod:
        from click import echo
        script_display = os.path.basename(script_path).replace('.py', '')
        echo(f"\033[93m🔥 [VULCAN-TURBO] Módulo '{script_display}' operando em modo nativo.\033[0m")
        
        for attr in dir(v_mod):
            if attr.endswith('_vulcan_optimized'):
                orig = attr.replace('_vulcan_optimized', '')
                globs[orig] = getattr(v_mod, attr)