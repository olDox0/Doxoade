# -*- coding: utf-8 -*-
"""
Vulcan Environment Manager - Isolation v1.0.
Cria a 'Sandbox' de compilação fora da árvore de execução principal.
Compliance: MPoT-19 (Quarantine), PASC-3.
"""
# [DOX-UNUSED] import os
import shutil
from pathlib import Path

class VulcanEnvironment:
    def __init__(self, project_root):
        self.root = Path(project_root)
        # Quarentena: Fora da pasta 'doxoade/'
        self.work_dir = self.root / ".doxoade" / "vulcan"
        self.foundry = self.work_dir / "foundry" # Onde o C nasce
        self.bin_dir = self.work_dir / "bin"         # Onde o .so/.pyd vive
        self.logs = self.work_dir / "audit.log"
        
        self._setup_structure()

    def _setup_structure(self):
        """Cria os silos de isolamento."""
        for folder in [self.foundry, self.bin_dir]:
            folder.mkdir(parents=True, exist_ok=True)
            
        # PASC-19.1: Cria arquivo de bloqueio para o Doxoade não importar nada daqui sem autorização
        init_file = self.work_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# VULCAN QUARANTINE ZONE\nraise ImportError('Direct import blocked by Aegis Rule 19.')")

    def purge_unstable(self):
        """Limpa binários não validados em caso de instabilidade (Reversibilidade)."""
        if self.foundry.exists():
            shutil.rmtree(self.foundry)
        self._setup_structure()

vulcan_env = None # Inicializado pelo CLI