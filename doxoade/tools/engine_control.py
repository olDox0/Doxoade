# doxoade/tools/engine_control.py
import sys
import os
from dataclasses import dataclass
from doxoade.tools.doxcolors import Fore

@dataclass
class EngineStatus:
    name: str
    active: bool
    mode: str  # 'TOML', 'ENV', or 'AUTO'
    integrity: str # 'OK', 'CORRUPT', 'DISABLED'

class NexusEngineGuard:
    """Autoridade central de despacho de motores de background."""
    
    @staticmethod
    def get_engine_states(project_root):
        from doxoade.tools.filesystem import _get_project_config
        config = _get_project_config(start_path=project_root)
        
        states = []
        
        # 1. Verificação do Shadow Runtime
        shadow_enabled = os.environ.get('DOXOADE_SHADOW') != '0' and config.get('shadow_runtime', True)
        shadow_present = any("ShadowFinder" in str(f) for f in sys.meta_path)
        states.append(EngineStatus(
            "SHADOW", shadow_present, 
            "ACTIVE" if shadow_enabled else "OFF",
            "OK" if (shadow_present == shadow_enabled) else "DIVERGENT"
        ))

        # 2. Verificação da Sotéria (Hook de Exceção)
        soteria_enabled = os.environ.get('DOXOADE_RESCUE') != '0' and config.get('soteria_active', True)
        # Verifica se o sys.excepthook foi sequestrado pelo lazarus_hook
        is_hooked = "lazarus_crash_handler" in str(sys.excepthook)
        states.append(EngineStatus(
            "SOTERIA", is_hooked,
            "ACTIVE" if soteria_enabled else "OFF",
            "OK" if (is_hooked == soteria_enabled) else "BYPASSED"
        ))

        # 3. Verificação do Vulcan (Tier 1 Redirection)
        vulcan_present = any("Vulcan" in str(f) for f in sys.meta_path)
        states.append(EngineStatus(
            "VULCAN", vulcan_present, "AUTO", "OK"
        ))
        
        return states