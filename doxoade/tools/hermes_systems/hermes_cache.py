# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_cache.py
"""
Hermes Cache - Cache persistente de code objects descomprimidos.
Salva em disco para evitar decompressão LZMA em reloads.
"""
# [DOX-UNUSED] import marshal
import pickle
from pathlib import Path
from typing import Optional

class HermesCache:
    """Cache LRU persistente para code objects."""
    
    def __init__(self, project_root: str, max_size: int = 100):
        self.root = Path(project_root).resolve()
        self.cache_dir = self.root / '.doxoade' / 'hermes' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self._memory_cache = {}
        
    def _get_cache_path(self, hermes_path: Path) -> Path:
        """Gera caminho do cache baseado no hash do arquivo .hermes."""
        import hashlib
        hermes_hash = hashlib.sha256(hermes_path.read_bytes()).hexdigest()[:16]
        return self.cache_dir / f"{hermes_path.stem}_{hermes_hash}.cache"
    
    def get(self, hermes_path: Path) -> Optional[object]:
        """Recupera code object do cache (memória ou disco)."""
        cache_key = str(hermes_path)
        
        # 1. Cache em memória (mais rápido)
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # 2. Cache em disco
        cache_path = self._get_cache_path(hermes_path)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    code_obj = pickle.load(f)
                # Adiciona ao cache em memória
                self._memory_cache[cache_key] = code_obj
                return code_obj
            except Exception:
                # Cache corrompido, remove
                cache_path.unlink(missing_ok=True)
        
        return None
    
    def put(self, hermes_path: Path, code_obj: object):
        """Salva code object no cache (memória e disco)."""
        cache_key = str(hermes_path)
        
        # 1. Cache em memória
        self._memory_cache[cache_key] = code_obj
        
        # Limita tamanho do cache em memória
        if len(self._memory_cache) > self.max_size:
            oldest = next(iter(self._memory_cache))
            del self._memory_cache[oldest]
        
        # 2. Cache em disco
        cache_path = self._get_cache_path(hermes_path)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(code_obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass  # Falha silenciosa no cache em disco
    
    def clear(self):
        """Limpa todo o cache."""
        self._memory_cache.clear()
        for cache_file in self.cache_dir.glob('*.cache'):
            cache_file.unlink()
