# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_loader_hbc5.py
"""
Hermes Loader HBC5 — Zero-Compression Fast Path
================================================
Loader otimizado para o formato HBC5:
- Zero decompressão (sem zlib/LZ4)
- Reverse tokens em C (não em Python)
- Cache duplo (memória + disco)
- Fallback gracioso para Python

Performance esperada:
• 5-10x mais rápido que HBC3 (sem decompressão)
• 2-3x mais rápido que HBC4 (decoder C otimizado)
• Memory usage: similar ao HBC4
"""
import hashlib
import marshal
import json
import types
from pathlib import Path
from typing import Optional

from .hermes_format_hbc5 import parse_header_hbc5, get_bitmap_hbc5, MAGIC_HBC5

class HermesLoaderHBC5:
    """Loader otimizado para HBC5 (zero-compression)."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.dict_file = self.root / '.doxoade' / 'hermes' / 'master.dict'
        self.hermes_base_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.cache_dir = self.root / '.doxoade' / 'hermes' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.decoder = self._load_decoder()
        
        # Cache em memória (LRU simples)
        self._code_cache: dict = {}
        self._cache_max_size = 200
        
        # Cache em disco (persistente)
        self._disk_cache_enabled = True
        
        # Estatísticas
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'native_decode': 0,
            'python_decode': 0
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DICIONÁRIO
    # ═══════════════════════════════════════════════════════════════════════════
    def _load_decoder(self) -> dict:
        """Carrega dicionário master."""
        if not self.dict_file.exists():
            return {}
        
        try:
            with open(self.dict_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            decoder = {}
            for k, v in data.get('decoder', {}).items():
                if not k.startswith('['):
                    try:
                        decoder[int(k)] = v
                    except ValueError:
                        continue
            
            return decoder
        except Exception:
            return {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CACHE EM DISCO (Marshal otimizado)
    # ═══════════════════════════════════════════════════════════════════════════
    def _disk_cache_path(self, hermes_path: Path) -> Path:
        """Gera caminho do cache baseado no hash do .hermes."""
        try:
            hermes_hash = hashlib.sha256(hermes_path.read_bytes()).hexdigest()[:16]
        except Exception:
            hermes_hash = "0000000000000000"
        
        return self.cache_dir / f"{hermes_path.stem}_{hermes_hash}.cache"
    
    def _load_from_disk_cache(self, hermes_path: Path):
        """Carrega code object do cache em disco (marshal)."""
        if not self._disk_cache_enabled:
            return None
        
        cache_path = self._disk_cache_path(hermes_path)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                return marshal.load(f)
        except Exception:
            try:
                cache_path.unlink(missing_ok=True)
            except Exception:
                pass
            return None
    
    def _save_to_disk_cache(self, hermes_path: Path, code_obj):
        """Salva code object no cache em disco (marshal)."""
        if not self._disk_cache_enabled:
            return
        
        cache_path = self._disk_cache_path(hermes_path)
        try:
            with open(cache_path, 'wb') as f:
                marshal.dump(code_obj, f)
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DECOMPRESSÃO PRINCIPAL (Fast Path HBC5)
    # ═══════════════════════════════════════════════════════════════════════════
    def decompress_to_code(self, hermes_path: Path):
        """
        Decodifica arquivo .hermes HBC5 em code object.
        Prioridade: Cache RAM → Cache Disco → Decoder C → Python Fallback
        """
        hermes_path = Path(hermes_path)
        cache_key = str(hermes_path)
        
        # 1. Cache em memória (instantâneo)
        if cache_key in self._code_cache:
            self.stats['cache_hits'] += 1
            return self._code_cache[cache_key]
        
        self.stats['cache_misses'] += 1
        
        # 2. Cache em disco (persistente)
        cached = self._load_from_disk_cache(hermes_path)
        if cached is not None:
            self._code_cache[cache_key] = cached
            return cached
        
        # 3. Decompressão real
        if not hermes_path.exists():
            raise FileNotFoundError(f"Arquivo .hermes não encontrado: {hermes_path}")
        
        # 3.1 Tenta decoder C nativo PRIMEIRO (vôo supersônico)
        try:
            from doxoade.tools.hermes_systems.native import decode as native_decode
            code_obj = native_decode(str(hermes_path))
            
            if code_obj:
                self.stats['native_decode'] += 1
                self._code_cache[cache_key] = code_obj
                self._save_to_disk_cache(hermes_path, code_obj)
                
                # Limita tamanho do cache
                if len(self._code_cache) > self._cache_max_size:
                    oldest = next(iter(self._code_cache))
                    del self._code_cache[oldest]
                
                return code_obj
        except (ImportError, Exception):
            pass
        
        # 3.2 Fallback: Decoder Python
        self.stats['python_decode'] += 1
        code_obj = self._decompress_python_fallback(hermes_path)
        
        self._code_cache[cache_key] = code_obj
        self._save_to_disk_cache(hermes_path, code_obj)
        
        return code_obj
    
    def _decompress_python_fallback(self, hermes_path: Path):
        """Decoder Python fallback para HBC5."""
        data = hermes_path.read_bytes()
        
        # Valida formato
        if not data.startswith(MAGIC_HBC5):
            raise ValueError(f"Arquivo não é HBC5: {hermes_path}")
        
        # Parse do header
        decoder_dict, marshalled_data, flags, _ = parse_header_hbc5(data)
        
        if decoder_dict is None or marshalled_data is None:
            raise ValueError(f"Header HBC5 corrompido: {hermes_path}")
        
        # Deserializa (SEM decompressão - HBC5 é zero-compression)
        code_obj = marshal.loads(marshalled_data)
        
        # Reverte tokens dinâmicos se houver
        if decoder_dict:
            code_obj = self._reverse_dynamic_tokens(code_obj, decoder_dict)
        
        return code_obj
    
    def _reverse_dynamic_tokens(self, code_obj, decoder: dict):
        """Reverte tokens dinâmicos nas strings do code object."""
        new_consts = []
        
        for const in code_obj.co_consts:
            if isinstance(const, str):
                result = const
                for token_id, pattern in decoder.items():
                    token_char = chr(token_id)
                    if token_char in result:
                        result = result.replace(token_char, pattern)
                new_consts.append(result)
            elif isinstance(const, types.CodeType):
                new_consts.append(self._reverse_dynamic_tokens(const, decoder))
            else:
                new_consts.append(const)
        
        return code_obj.replace(co_consts=tuple(new_consts))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITÁRIOS
    # ═══════════════════════════════════════════════════════════════════════════
    def find_hermes_for_module(self, module_name: str) -> Optional[Path]:
        """Encontra arquivo .hermes HBC5 para um módulo."""
        hermes_file = self.hermes_base_dir / f"{module_name}.hermes"
        if hermes_file.exists():
            # Verifica se é HBC5
            try:
                with open(hermes_file, 'rb') as f:
                    magic = f.read(4)
                    if magic == MAGIC_HBC5:
                        return hermes_file
            except Exception:
                pass
        return None
    
    def get_stats(self) -> dict:
        """Retorna estatísticas de performance."""
        return self.stats.copy()
    
    def clear_cache(self):
        """Limpa todo o cache."""
        self._code_cache.clear()
        
        if self._disk_cache_enabled:
            for cache_file in self.cache_dir.glob('*.cache'):
                try:
                    cache_file.unlink()
                except Exception:
                    pass