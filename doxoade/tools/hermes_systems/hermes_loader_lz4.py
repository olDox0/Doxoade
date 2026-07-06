# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_loader_lz4.py
"""
Hermes Loader v2.0 — LZ4 Accelerated Decoder
Otimizações:
1. LZ4 em vez de zlib (10x mais rápido)
2. Marshal em vez de pickle (5x mais rápido, 4x menor)
3. Cache em memória LRU otimizado
4. Decoder C nativo prioritário
"""
import hashlib
import marshal
import json
import types
from pathlib import Path
from typing import Optional

# Tenta importar LZ4, fallback para zlib se não disponível
try:
    import lz4.block
    LZ4_AVAILABLE = True
except ImportError:
    import zlib
    LZ4_AVAILABLE = False

from .hermes_format import parse_header, get_bitmap, string_needs_reverse, MAGIC_HBC3
from .hermes_format_hbc4 import parse_header_hbc4, get_bitmap_hbc4, MAGIC_HBC4

class HermesLoaderV2:
    """Loader v2.0 com LZ4 e cache otimizado."""
    
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
    # CACHE EM DISCO (Marshal em vez de Pickle)
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
                # Marshal é 5x mais rápido que pickle
                return marshal.load(f)
        except Exception:
            # Cache corrompido, remove
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
                # Marshal é 4x menor que pickle
                marshal.dump(code_obj, f)
        except Exception:
            pass  # Falha silenciosa
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DECOMPRESSÃO (LZ4 em vez de zlib)
    # ═══════════════════════════════════════════════════════════════════════════
    def _decompress_data(self, data: bytes, format_magic: bytes) -> bytes:
        """Descomprime dados usando LZ4 (ou zlib como fallback)."""
        if format_magic == MAGIC_HBC3:
            if LZ4_AVAILABLE:
                # LZ4 é 10x mais rápido que zlib
                return lz4.block.decompress(data)
            else:
                # Fallback para zlib
                return zlib.decompress(data)
        else:
            # HBC4 não tem compressão
            return data
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DECOMPRESSÃO PRINCIPAL (Com Decoder C Nativo)
    # ═══════════════════════════════════════════════════════════════════════════
    def decompress_to_code(self, hermes_path: Path):
        """
        Decodifica arquivo .hermes em code object.
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
            pass  # Fallback para Python
        
        # 3.2 Fallback: Decoder Python
        self.stats['python_decode'] += 1
        code_obj = self._decompress_python_fallback(hermes_path)
        
        self._code_cache[cache_key] = code_obj
        self._save_to_disk_cache(hermes_path, code_obj)
        
        return code_obj
    
    def _decompress_python_fallback(self, hermes_path: Path):
        """Decoder Python fallback (lento, mas funcional)."""
        data = hermes_path.read_bytes()
        
        # Detecta formato
        if data.startswith(MAGIC_HBC4):
            decoder_dict, marshalled_data, _ = parse_header_hbc4(data)
            # HBC4 não tem compressão
            code_obj = marshal.loads(marshalled_data)
        else:
            # HBC3 tem compressão
            decoder_dict, compressed_data, _ = parse_header(data)
            marshalled_data = self._decompress_data(compressed_data, MAGIC_HBC3)
            code_obj = marshal.loads(marshalled_data)
        
        # Reverte tokens dinâmicos se houver
        if decoder_dict:
            code_obj = self._reverse_dynamic_tokens(code_obj, decoder_dict)
        
        return code_obj
    
    def _reverse_dynamic_tokens(self, code_obj, decoder: dict):
        """Reverte tokens dinâmicos nas strings do code object."""
        # Esta função é chamada apenas no fallback Python
        # O decoder C faz isso internamente
        new_consts = []
        
        for const in code_obj.co_consts:
            if isinstance(const, str):
                # Substitui tokens de volta para strings
                result = const
                for token_id, pattern in decoder.items():
                    token_char = chr(token_id)
                    if token_char in result:
                        result = result.replace(token_char, pattern)
                new_consts.append(result)
            elif isinstance(const, types.CodeType):
                # Recursivamente processa code objects aninhados
                new_consts.append(self._reverse_dynamic_tokens(const, decoder))
            else:
                new_consts.append(const)
        
        # Cria novo code object com constantes revertidas
        return code_obj.replace(co_consts=tuple(new_consts))
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UTILITÁRIOS
    # ═══════════════════════════════════════════════════════════════════════════
    def find_hermes_for_module(self, module_name: str) -> Optional[Path]:
        """Encontra arquivo .hermes para um módulo."""
        hermes_file = self.hermes_base_dir / f"{module_name}.hermes"
        if hermes_file.exists():
            return hermes_file
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

# ═══════════════════════════════════════════════════════════════════════════════
# COMPATIBILIDADE COM API ANTIGA
# ═══════════════════════════════════════════════════════════════════════════════
class HermesLoader(HermesLoaderV2):
    """Alias para compatibilidade com código existente."""
    pass

def verify_lossless(original_py: Path, hermes_file: Path) -> bool:
    """Verifica se a compressão foi lossless."""
    try:
        # Carrega original
        with open(original_py, 'r', encoding='utf-8') as f:
            original_code = f.read()
        
        # Carrega hermes
        loader = HermesLoader(str(original_py.parent.parent))
        hermes_code_obj = loader.decompress_to_code(hermes_file)
        
        # Compara bytecode
        import dis
        import io
        
        orig_output = io.StringIO()
        hermes_output = io.StringIO()
        
        orig_bytecode = compile(original_code, str(original_py), 'exec')
        
        dis.dis(orig_bytecode, file=orig_output)
        dis.dis(hermes_code_obj, file=hermes_output)
        
        return orig_output.getvalue() == hermes_output.getvalue()
    except Exception:
        return False