# doxoade/doxoade/tools/vulcan/core.py
"""
Vulcan Core - Otimização Nativa Controlada.
Implementa o regime de 'Passe Livre' apenas após validação de estabilidade.
Compliance: MPoT-15 (Modos Degradados), PASC-3 (Progressividade).
"""
from pathlib import Path

class VulcanCore:

    def __init__(self):
        self.enabled = False
        self.registry_path = Path('.doxoade/vulcan/registry.json')
        self.optimized_dir = Path('.doxoade/vulcan/bin')
        self.blacklist = set()

    def should_optimize(self, func_name, hot_hits):
        """Decide se uma função merece o risco do Vulcano."""
        if not self.enabled or func_name in self.blacklist:
            return False
        return hot_hits > 100

    def revert(self, func_name, reason):
        """Protocolo de Reversibilidade Imediata."""
        self.blacklist.add(func_name)
        from ..db_utils import _log_execution
        _log_execution('VULCAN_REVERSION', func_name, {'reason': reason}, {})