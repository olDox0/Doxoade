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
        encoder = {}
        decoder = {}

        for i, pattern_data in enumerate(top_patterns[:max_tokens]):
            if len(pattern_data) == 3:
                source_string, freq, pattern_type = pattern_data
            else:
                source_string, freq = pattern_data
            
            # Utiliza a Private Use Area do Unicode (U+E000 até U+F8FF)
            # Dessa forma os tokens são 100% seguros contra strip() e bugs de codificação.
            token_int = 0xE000 + i
            encoder[source_string] = token_int
            decoder[str(token_int)] = source_string

        with open(self.dict_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "4.2",
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