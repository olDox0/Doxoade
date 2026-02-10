# -*- coding: utf-8 -*-
# doxoade/commands/run_systems/run_vulcan.py (v83.6 Gold Fix)
import os
# Importamos a instância em minúsculo 'vulcan_bridge' (PASC 8.12)
from ...tools.vulcan.bridge import vulcan_bridge

def apply_vulcan_turbo(script_path: str, globs: dict):
    """Injeta binário nativo apenas se estiver sincronizado (v83.6)."""
    script_name = os.path.basename(script_path).replace('.py', '')
    
    # FIX: Chamar na instância 'vulcan_bridge', não na classe 'VulcanBridge'
    if vulcan_bridge.is_binary_stale(script_path):
        # O código mudou, ignoramos o binário silenciosamente
        return

    # Tenta carregar o módulo
    v_mod = vulcan_bridge.get_optimized_module(script_name, script_path)
    if v_mod:
        from click import echo
        echo(f"\033[93m🔥 [VULCAN-TURBO] Acelerando lógica de '{script_name}'\033[0m")
        for attr in dir(v_mod):
            if attr.endswith('_vulcan_optimized'):
                orig = attr.replace('_vulcan_optimized', '')
                globs[orig] = getattr(v_mod, attr)