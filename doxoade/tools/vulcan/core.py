# -*- coding: utf-8 -*-
"""
Vulcan Core - Otimização Nativa Controlada.
Implementa o regime de 'Passe Livre' apenas após validação de estabilidade.
Compliance: MPoT-15 (Modos Degradados), PASC-3 (Progressividade).
"""
#import os
from pathlib import Path
#from ..logger import ExecutionLogger

class VulcanCore:
    def __init__(self):
        self.enabled = False # Opcional por padrão
        self.registry_path = Path(".doxoade/vulcan/registry.json")
        self.optimized_dir = Path(".doxoade/vulcan/bin")
        self.blacklist = set() # Funções que falharam na validação
        
    def should_optimize(self, func_name, hot_hits):
        """Decide se uma função merece o risco do Vulcano."""
        if not self.enabled or func_name in self.blacklist:
            return False
        # Só otimiza se for um gargalo real (identificado pelo Chronos)
        return hot_hits > 100 

    def revert(self, func_name, reason):
        """Protocolo de Reversibilidade Imediata."""
        self.blacklist.add(func_name)
        # Registra a falha no banco de incidentes para análise forense
        from ..db_utils import _log_execution
        _log_execution("VULCAN_REVERSION", func_name, {"reason": reason}, {})