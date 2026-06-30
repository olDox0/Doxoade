# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_loader.py
"""
Hermes Loader v4.1 - Motor de Descompressão Lossless.
CORREÇÃO: Descompressão linha-a-linha (sem substrings).
"""
import json
from pathlib import Path


class HermesLoader:
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.dict_file = self.root / '.doxoade' / 'hermes' / 'master.dict'
        self.hermes_base_dir = self.root / '.doxoade' / 'hermes' / 'build'
        self.decoder = self._load_decoder()

    def _load_decoder(self) -> dict:
        if not self.dict_file.exists():
            raise FileNotFoundError(f"Dicionário não encontrado: {self.dict_file}")
        
        with open(self.dict_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        decoder = {}
        for k, v in data['decoder'].items():
            if k.startswith('['):
                token_bytes = tuple(json.loads(k))
                decoder[token_bytes] = v
            else:
                decoder[int(k)] = v
        
        return decoder

    def decompress_bytes(self, hermes_bytes: bytes) -> str:
        """Descompressão linha-a-linha (sem substituição de substrings)."""
        text = hermes_bytes.decode('utf-8')
        
        # Processa LINHA A LINHA
        lines = text.split('\n')
        decompressed_lines = []
        
        for line in lines:
            decompressed_line = line
            
            # Tenta tokens de 2 bytes primeiro
            for token, original in self.decoder.items():
                if isinstance(token, tuple) and len(token) == 2:
                    token_str = chr(token[0]) + chr(token[1])
                    # APENAS substitui se a linha inteira (stripped) for o token
                    if decompressed_line.strip() == token_str:
                        indent = decompressed_line[:len(decompressed_line) - len(decompressed_line.lstrip())]
                        decompressed_line = indent + original
                        break
            
            # Tenta tokens de 1 byte
            for token, original in self.decoder.items():
                if isinstance(token, int):
                    token_str = chr(token)
                    # APENAS substitui se a linha inteira (stripped) for o token
                    if decompressed_line.strip() == token_str:
                        indent = decompressed_line[:len(decompressed_line) - len(decompressed_line.lstrip())]
                        decompressed_line = indent + original
                        break
            
            decompressed_lines.append(decompressed_line)
        
        return '\n'.join(decompressed_lines)

    def decompress_file(self, hermes_path: Path) -> str:
        hermes_path = Path(hermes_path)
        if not hermes_path.exists():
            raise FileNotFoundError(f"Arquivo .hermes não encontrado: {hermes_path}")
        
        hermes_bytes = hermes_path.read_bytes()
        return self.decompress_bytes(hermes_bytes)

    def find_hermes_for_module(self, module_name: str) -> Path:
        hermes_file = self.hermes_base_dir / f"{module_name}.hermes"
        return hermes_file if hermes_file.exists() else None


def verify_lossless(original_path: Path, hermes_path: Path, loader: 'HermesLoader') -> bool:
    """Prova de conceito lossless."""
    original = Path(original_path).read_text(encoding='utf-8')
    reconstructed = loader.decompress_file(hermes_path)
    
    original_norm = original.replace('\r\n', '\n').rstrip('\n')
    reconstructed_norm = reconstructed.replace('\r\n', '\n').rstrip('\n')
    
    return original_norm == reconstructed_norm