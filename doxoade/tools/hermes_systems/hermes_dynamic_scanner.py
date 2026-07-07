# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_dynamic_scanner.py
"""
Hermes Dynamic Scanner v2.0 - Análise Local por Arquivo.
CORREÇÃO: Apenas padrões de linha única (sem \n).
"""
import re
from collections import Counter
from pathlib import Path
from typing import Dict

_STRING_PATTERN = re.compile(r'''(["'])((?:(?!\1).){10,80})\1''')

class HermesDynamicScanner:
    """Scanner que identifica padrões repetitivos DENTRO de um arquivo."""

    def __init__(self):
        self.local_patterns = Counter()

    def scan_file(self, file_path: Path) -> Dict[str, int]:
        """Analisa um arquivo e retorna padrões locais repetitivos."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return {}

        self._scan_individual_lines(content)
        self._scan_substrings(content)

        return dict(self.local_patterns)

    def _scan_individual_lines(self, content: str):
        """Identifica linhas que se repetem 3+ vezes."""
        lines = content.splitlines()
        line_counter = Counter()

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and len(stripped) >= 4:
                line_counter[stripped] += 1

        for line, count in line_counter.items():
            if count >= 3 and '\n' not in line and '\r' not in line:
                self.local_patterns[line] += count

    def _scan_substrings(self, content: str):
        """Identifica substrings repetitivas (mínimo 8 caracteres)."""
        # Padrões de caminho de módulo
        module_patterns = re.findall(
            r'[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\.',
            content
        )
        for pattern in module_patterns:
            if len(pattern) >= 8 and '\n' not in pattern:
                self.local_patterns[pattern] += 1

        # Strings literais longas (entre aspas, 10-80 caracteres)
#        string_pattern = re.compile(r'''(["'])((?:(?!\1).){10,80})\1''')
        for match in _STRING_PATTERN.finditer(content):
            string_content = match.group(2)
            if not string_content.isspace() and '\n' not in string_content:
                self.local_patterns[string_content] += 1

        # Padrões de decorator Click
        click_patterns = re.findall(r'@click\.\w+\([^)]*\)', content)
        for pattern in click_patterns:
            if len(pattern) >= 8 and '\n' not in pattern:
                self.local_patterns[pattern] += 1


def build_dynamic_dictionary(
    file_path: Path,
    existing_encoder: dict,
    max_new_tokens: int = 200,
    min_freq: int = 3
) -> Dict[str, int]:
    """
    Constrói dicionário dinâmico para um arquivo específico.
    Retorna APENAS padrões de linha única (sem \n).
    """
    scanner = HermesDynamicScanner()
    patterns = scanner.scan_file(file_path)

    # Filtra: não duplicar existentes, frequência mínima, sem \n
    new_patterns = {
        p: f for p, f in patterns.items()
        if p not in existing_encoder
        and f >= min_freq
        and '\n' not in p
        and '\r' not in p
    }

    sorted_patterns = sorted(new_patterns.items(), key=lambda x: x[1], reverse=True)

    dynamic_encoder = {}
    token_counter = 0x80

    for pattern, freq in sorted_patterns[:max_new_tokens]:
        if token_counter > 0xFF:
            break
        dynamic_encoder[pattern] = token_counter
        token_counter += 1

    return dynamic_encoder