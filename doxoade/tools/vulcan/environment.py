# doxoade/doxoade/tools/vulcan/environment.py
"""
Vulcan Environment Manager - Isolation v1.2.
Cria a 'Sandbox' de compilação fora da árvore de execução principal.
Compliance: MPoT-19 (Quarantine), PASC-3.
"""
import shutil
import os
import stat
import time
from pathlib import Path

class VulcanEnvironment:

    def __init__(self, project_root):
        self.root = Path(project_root)
        self.work_dir = self.root / '.doxoade' / 'vulcan'
        self.foundry = self.work_dir / 'foundry'
        self.bin_dir = self.work_dir / 'bin'
        self.opt_dir = self.work_dir / 'opt_py'
        self.lib_dir = self.work_dir / 'lib_bin'
        self.logs = self.work_dir / 'audit.log'
        self.staging = self.work_dir / 'staging'
        self._setup_structure()

    def _setup_structure(self):
        """Cria os silos de isolamento."""
        for folder in [self.foundry, self.bin_dir, self.staging, self.lib_dir, self.opt_dir]:
            folder.mkdir(parents=True, exist_ok=True)
        init_file = self.work_dir / '__init__.py'
        if not init_file.exists():
            init_file.write_text("# VULCAN QUARANTINE ZONE\nraise ImportError('Direct import blocked by Aegis Rule 19.')")

    def purge_unstable(self):
        """
        Limpeza completa: foundry (fontes .pyx/.c) + bin (todos os .pyd/.so).

        MUDANÇA v1.2: Antes só limpava a foundry/, deixando os .pyd legados
        (sem hash, ex: autopilot.pyd, compiler.pyd) no bin/ após um purge.
        Agora ambos são limpos, alinhando o comportamento com 'vulcan purge'.
        """
        for target in [self.foundry, self.bin_dir, self.lib_dir, self.opt_dir]:
            if target.exists():
                self._safe_rmtree(target)
        self._setup_structure()

    @staticmethod
    def _safe_rmtree(target: Path) -> None:
        """Remove diretório com fallback robusto para travas no Windows (.pyd em uso)."""

        def _onerror(func, path, _exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                return
        try:
            shutil.rmtree(target, onerror=_onerror)
            return
        except Exception:
            pass
        try:
            suffix = int(time.time())
            parked = target.with_name(f'{target.name}.purge_pending_{suffix}')
            if parked.exists():
                shutil.rmtree(parked, ignore_errors=True)
            target.rename(parked)
        except Exception:
            return
    purge_all = purge_unstable
vulcan_env = None