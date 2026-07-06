# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_compress_tiered.py
"""
Hermes Compressor Tiered — Dicionário Hierárquico por Frequência
================================================================
Estratégia:
  Tier 1 (Hot):  0x80-0x9F  (32 tokens)   → 1000+ ocorrências
  Tier 2 (Warm): 0xA0-0xBF  (32 tokens)   → 100-999 ocorrências  
  Tier 3 (Cold): 0xC0-0xFF  (64 tokens)   → 10-99 ocorrências
  
Vantagens:
  - Decoder pode parar cedo (Tier 1 cobre 80% dos casos)
  - Arquivos pequenos carregam só Tier 1
  - Lookup vetorizado (array em vez de dict)
"""

import os
import marshal
import struct
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple

MAGIC_HBC6 = b"HBC6"
VERSION = 6

# Tier boundaries
TIER1_MIN, TIER1_MAX = 0x80, 0x9F  # 32 tokens (hot)
TIER2_MIN, TIER2_MAX = 0xA0, 0xBF  # 32 tokens (warm)
TIER3_MIN, TIER3_MAX = 0xC0, 0xFF  # 64 tokens (cold)

class TieredDictionary:
    """Dicionário hierárquico baseado em frequência."""
    
    def __init__(self):
        self.tier1: Dict[str, int] = {}  # Hot (32 tokens)
        self.tier2: Dict[str, int] = {}  # Warm (32 tokens)
        self.tier3: Dict[str, int] = {}  # Cold (64 tokens)
        self.vector: List[str] = [None] * 256  # Lookup vetorizado O(1)
    
    def build_from_patterns(self, patterns: Dict[str, int]):
        """Constrói dicionário tierizado a partir de padrões com frequência."""
        # Ordena por frequência (mais frequente primeiro)
        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
        
        tier1_count = 0
        tier2_count = 0
        tier3_count = 0
        
        for pattern, freq in sorted_patterns:
            if tier1_count < 32 and freq >= 1000:
                token = TIER1_MIN + tier1_count
                self.tier1[pattern] = token
                self.vector[token] = pattern
                tier1_count += 1
            elif tier2_count < 32 and freq >= 100:
                token = TIER2_MIN + tier2_count
                self.tier2[pattern] = token
                self.vector[token] = pattern
                tier2_count += 1
            elif tier3_count < 64 and freq >= 10:
                token = TIER3_MIN + tier3_count
                self.tier3[pattern] = token
                self.vector[token] = pattern
                tier3_count += 1
            else:
                break  # Não cabe mais tokens
        
        return {
            'tier1': tier1_count,
            'tier2': tier2_count,
            'tier3': tier3_count,
            'total': tier1_count + tier2_count + tier3_count
        }
    
    def get_encoder(self) -> Dict[str, int]:
        """Retorna encoder completo (pattern → token)."""
        encoder = {}
        encoder.update(self.tier1)
        encoder.update(self.tier2)
        encoder.update(self.tier3)
        return encoder
    
    def get_decoder_vector(self) -> List[str]:
        """Retorna decoder vetorizado (token → pattern)."""
        return self.vector
    
    def save(self, path: Path):
        """Salva dicionário tierizado em formato binário."""
        with open(path, 'wb') as f:
            # Header: magic + version + tier counts
            f.write(MAGIC_HBC6)
            f.write(struct.pack('<B', VERSION))
            f.write(struct.pack('<BBB', len(self.tier1), len(self.tier2), len(self.tier3)))
            
            # Tier 1 tokens
            for pattern, token in sorted(self.tier1.items(), key=lambda x: x[1]):
                pattern_bytes = pattern.encode('utf-8')
                f.write(struct.pack('<BH', token, len(pattern_bytes)))
                f.write(pattern_bytes)
            
            # Tier 2 tokens
            for pattern, token in sorted(self.tier2.items(), key=lambda x: x[1]):
                pattern_bytes = pattern.encode('utf-8')
                f.write(struct.pack('<BH', token, len(pattern_bytes)))
                f.write(pattern_bytes)
            
            # Tier 3 tokens
            for pattern, token in sorted(self.tier3.items(), key=lambda x: x[1]):
                pattern_bytes = pattern.encode('utf-8')
                f.write(struct.pack('<BH', token, len(pattern_bytes)))
                f.write(pattern_bytes)
    
    @classmethod
    def load(cls, path: Path) -> 'TieredDictionary':
        """Carrega dicionário tierizado de arquivo binário."""
        obj = cls()
        
        with open(path, 'rb') as f:
            magic = f.read(4)
            if magic != MAGIC_HBC6:
                raise ValueError(f"Magic inválido: {magic}")
            
            version = struct.unpack('<B', f.read(1))[0]
            if version != VERSION:
                raise ValueError(f"Version inválido: {version}")
            
            tier1_count, tier2_count, tier3_count = struct.unpack('<BBB', f.read(3))
            
            # Lê Tier 1
            for _ in range(tier1_count):
                token, pattern_len = struct.unpack('<BH', f.read(3))
                pattern = f.read(pattern_len).decode('utf-8')
                obj.tier1[pattern] = token
                obj.vector[token] = pattern
            
            # Lê Tier 2
            for _ in range(tier2_count):
                token, pattern_len = struct.unpack('<BH', f.read(3))
                pattern = f.read(pattern_len).decode('utf-8')
                obj.tier2[pattern] = token
                obj.vector[token] = pattern
            
            # Lê Tier 3
            for _ in range(tier3_count):
                token, pattern_len = struct.unpack('<BH', f.read(3))
                pattern = f.read(pattern_len).decode('utf-8')
                obj.tier3[pattern] = token
                obj.vector[token] = pattern
        
        return obj


class HermesCompressorTiered:
    """Compressor que usa dicionário tierizado."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.hermes_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.hermes_dir.mkdir(parents=True, exist_ok=True)
    
    def compress_file(self, py_file: Path, dictionary: TieredDictionary = None) -> dict:
        """Comprime arquivo usando dicionário tierizado."""
        source = py_file.read_text(encoding='utf-8')
        original_size = len(source.encode('utf-8'))
        
        # Compila para bytecode
        code_obj = compile(source, str(py_file), 'exec', optimize=2)
        
        # Se não tem dicionário, cria um baseado no arquivo
        if dictionary is None:
            patterns = self._extract_patterns(source)
            dictionary = TieredDictionary()
            dictionary.build_from_patterns(patterns)
        
        # Tokeniza os co_consts
        encoder = dictionary.get_encoder()
        tokenized_code = self._tokenize_code(code_obj, encoder)
        
        # Serializa
        marshalled = marshal.dumps(tokenized_code)
        
        # Salva arquivo HBC6
        module_name = py_file.stem
        hermes_path = self.hermes_dir / f"{module_name}.hermes"
        
        with open(hermes_path, 'wb') as f:
            f.write(MAGIC_HBC6)
            f.write(struct.pack('<B', VERSION))
            f.write(struct.pack('<I', len(marshalled)))
            f.write(marshalled)
        
        final_size = hermes_path.stat().st_size
        
        return {
            'original_size': original_size,
            'final_size': final_size,
            'reduction_pct': (1 - final_size / original_size) * 100 if original_size > 0 else 0,
            'hermes_path': hermes_path,
            'dictionary': dictionary
        }
    
    def _extract_patterns(self, source: str) -> Dict[str, int]:
        """Extrai padrões repetitivos do código fonte."""
        patterns = Counter()
        lines = source.splitlines()
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and len(stripped) >= 4:
                patterns[stripped] += 1
        
        return dict(patterns)
    
    def _tokenize_code(self, code_obj, encoder: Dict[str, int]):
        """Tokeniza co_consts recursivamente."""
        import types
        
        new_consts = []
        for const in code_obj.co_consts:
            if isinstance(const, str):
                # Substitui padrões na string
                result = const
                for pattern, token in sorted(encoder.items(), key=lambda x: len(x[0]), reverse=True):
                    if pattern in result:
                        result = result.replace(pattern, chr(token))
                new_consts.append(result)
            elif isinstance(const, types.CodeType):
                # Recursivamente processa code objects aninhados
                new_consts.append(self._tokenize_code(const, encoder))
            else:
                new_consts.append(const)
        
        return code_obj.replace(co_consts=tuple(new_consts))