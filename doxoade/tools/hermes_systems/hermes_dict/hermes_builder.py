# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_dict/hermes_builder.py
import json
from pathlib import Path

class HermesDictionaryBuilder:
    def __init__(self, project_root: str):
        self.dict_dir = Path(project_root) / '.doxoade' / 'hermes'
        self.dict_dir.mkdir(parents=True, exist_ok=True)
        self.dict_file = self.dict_dir / 'master.dict'
    
    def build_from_scan(self, top_patterns: list, mapping: dict, max_tokens: int = 200):
        """
        NOVA ESTRATÉGIA: Apenas tokens ultra-frequentes no dicionário global.
        Tokens específicos ficam embutidos nos arquivos .hermes.
        
        Critérios para token global:
        - Frequência mínima: 50 ocorrências no projeto
        - Tamanho máximo: 30 caracteres (tokens longos vão para específico)
        - Aparece em 80%+ dos arquivos
        """
        encoder = {}
        decoder = {}
        
        # Filtra apenas tokens ultra-frequentes
        global_patterns = []
        for pattern_data in top_patterns:
            if len(pattern_data) == 3:
                source_string, freq, pattern_type = pattern_data
            else:
                source_string, freq = pattern_data
            
            # CRITÉRIOS PARA TOKEN GLOBAL:
            if freq >= 50 and len(source_string) <= 30:
                global_patterns.append((source_string, freq))
            
            # Limita a 200 tokens globais
            if len(global_patterns) >= max_tokens:
                break
        
        # Atribui tokens
        for i, (pattern, freq) in enumerate(global_patterns):
            token_int = 0xE000 + i  # Private Use Area
            encoder[pattern] = token_int
            decoder[str(token_int)] = pattern
        
        with open(self.dict_file, 'w', encoding='utf-8') as f:
            json.dump({
                "version": "5.0",
                "strategy": "global_specific_split",
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