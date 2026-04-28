# -*- coding: utf-8 -*-
import sys
import os
import functools

# --- DETECÇÃO DE CONTEXTO ---
# Se 'doxoade' está no path, estamos no modo CORE. 
# Caso contrário, estamos no modo EMBEDDED.
try:
    from doxoade.tools import doxcolors as colors
    from doxoade.tools import error_info
    from doxoade.tools.telemetry_tools import logger
    IS_CORE = True
except ImportError:
    # Fallback para o modo Silo (Arquivos na mesma pasta utils/)
    import doxcolors as colors
    import error_info
    import telemetry as logger
    IS_CORE = False

def monitor(func):
    """
    Decorator Dual-Context: 
    1. Inicia Telemetria (Chronos Lite)
    2. Instala Escudo contra Crash (Rescue)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        project_name = os.path.basename(os.getcwd())
        
        # Inicia rastro de telemetria
        with logger.ExecutionLogger(project_name, os.getcwd(), sys.argv) as log:
            try:
                return func(*args, **kwargs)
            except Exception:
                # Dispara interface forense em caso de erro
                import traceback
                error_text = traceback.format_exc()
                
                if IS_CORE:
                    from doxoade.rescue import activate_protocol
                    activate_protocol(error_text)
                else:
                    import rescue
                    rescue.activate_protocol(error_text)
                sys.exit(1)
    return wrapper

def ignite():
    """Inicialização rápida de UI."""
    colors.init()
    return colors.Fore, colors.Style