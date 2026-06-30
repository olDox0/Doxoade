# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_dict/hermes_builder.py
import json
from pathlib import Path


class HermesDictionaryBuilder:
    def __init__(self, project_root: str):
        self.dict_dir = Path(project_root) / '.doxoade' / 'hermes'
        self.dict_dir.mkdir(parents=True, exist_ok=True)
        self.dict_file = self.dict_dir / 'master.dict'

    def build_from_scan(self, top_patterns: list, mapping: dict, max_tokens: int = 5000):
        """
        Constrói o dicionário binário v3.0 com suporte a 5.000 tokens.
        - Tokens 1-25: 1 byte (0x01-0x1F)
        - Tokens 26-5000: 2 bytes (0x80 0x01 a 0xFF 0xFF)
        """
        encoder = {}
        decoder = {}

        for i, (pattern_data) in enumerate(top_patterns[:max_tokens]):
            # pattern_data pode ser (pattern, freq, type) ou (pattern, freq)
            if len(pattern_data) == 3:
                source_string, freq, pattern_type = pattern_data
            else:
                source_string, freq = pattern_data
                pattern_type = 'LINE'
            
            if i < 25:
                # Token de 1 byte
                token_byte = i + 1
                encoder[source_string] = token_byte
                decoder[str(token_byte)] = source_string
            else:
                # Token de 2 bytes
                high_byte = 0x80 + ((i - 25) // 256)
                low_byte = ((i - 25) % 256) + 1
                token_bytes = [high_byte, low_byte]
                encoder[source_string] = token_bytes
                decoder[str(token_bytes)] = source_string

        with open(self.dict_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "3.0",
                "token_count": len(encoder),
                "encoder": encoder,
                "decoder": decoder
            }, f, indent=2, ensure_ascii=False)

        return len(encoder), self.dict_file

    def load_dictionary(self):
        if not self.dict_file.exists():
            return None
        with open(self.dict_file, 'r', encoding='utf-8') as f:
            return json.load(f)