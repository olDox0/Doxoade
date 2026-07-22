# doxoade\tools\metalcraft\__init__.py
"""
Metalcraft - Sistema de Compilação Nativa do Doxoade.

Auto-build é ativado automaticamente via boot.py.
Para verbose, use: export METALCRAFT_VERBOSE=1
"""

# Lazy initialization: não faz nada na importação
# O auto-build real acontece no boot.py

__all__ = ['NexusMetalEngine', 'NexusToolchain']

def __getattr__(name):
    """Lazy import dos componentes principais."""
    if name == 'NexusMetalEngine':
        from .metal_engine import NexusMetalEngine
        return NexusMetalEngine
    elif name == 'NexusToolchain':
        from .metal_toolchain import NexusToolchain
        return NexusToolchain
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")