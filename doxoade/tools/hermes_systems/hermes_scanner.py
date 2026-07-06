# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_scanner.py
"""
Hermes Scanner v2.1 - Motor de Reconhecimento por Linhas Inteiras.
CORREÇÃO: Desabilitado scanner de substrings para evitar corrupção.
Foco em linhas inteiras que se repetem 3+ vezes no projeto.
"""
import re
# [DOX-UNUSED] import hashlib
from collections import Counter
from pathlib import Path


def run_hermes_reconnaissance(project_root: str, max_tokens: int = 5000, min_freq: int = 2):
    """
    Varre todos os .py do projeto e retorna as linhas mais repetitivas.
    APENAS linhas inteiras (sem substrings para evitar corrupção).
    """
    line_frequencies = Counter()
    mapping = {}
    root = Path(project_root).resolve()
    
    ignore_dirs = {"venv", ".venv", ".doxoade", "__pycache__", "build", "dist", "node_modules", "tests", ".git"}

    for py_file in root.rglob("*.py"):
        if any(part in ignore_dirs for part in py_file.parts):
            continue
            
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()
            
            # APENAS linhas inteiras
            for line in lines:
                stripped = line.strip()
                # Ignora linhas vazias, comentários e linhas muito curtas
                if stripped and not stripped.startswith('#') and len(stripped) >= 4:
                    if stripped not in line_frequencies:
                        mapping[stripped] = stripped
                    line_frequencies[stripped] += 1
                
        except (SyntaxError, UnicodeDecodeError):
            continue

    # Ordena por frequência e limita
    combined_patterns = []
    for pattern, freq in line_frequencies.most_common():
        if freq >= min_freq:
            combined_patterns.append((pattern, freq, 'LINE'))

    return combined_patterns[:max_tokens], mapping

def _extract_substrings(content: str, frequencies: Counter, mapping: dict):
    """
    Extrai substrings repetitivas do conteúdo.
    Foca em padrões que aparecem dentro de strings e código.
    """
    # Padrões de prefixo de módulo (ex: "doxoade.commands.", "doxoade.tools.")
    module_patterns = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\.', content)
    for pattern in module_patterns:
        if len(pattern) >= 8:  # Mínimo 8 caracteres para ser útil
            if pattern not in frequencies:
                mapping[pattern] = pattern
            frequencies[pattern] += 1
    
    # Padrões de string com aspas (ex: ": '", "': '")
    string_patterns = re.findall(r'["\'][^"\']{3,}["\']', content)
    for pattern in string_patterns:
        if len(pattern) >= 6 and len(pattern) <= 50:  # Tamanho razoável
            if pattern not in frequencies:
                mapping[pattern] = pattern
            frequencies[pattern] += 1
    
    # Padrões de controle parcial (ex: "if not", "else:", "except Exception")
    control_patterns = [
        r'\bif not\b',
        r'\bif \w+ in\b',
        r'\bfor \w+ in\b',
        r'\bexcept \w+',
        r'\breturn \w+',
        r':\s*\'[^\']+\'',  # ': 'value''
        r'=\s*\'[^\']+\'',  # = 'value'
    ]
    for pattern_regex in control_patterns:
        matches = re.findall(pattern_regex, content)
        for pattern in matches:
            if len(pattern) >= 5 and len(pattern) <= 40:
                if pattern not in frequencies:
                    mapping[pattern] = pattern
                frequencies[pattern] += 1
    
    # Padrões de indentação (ex: "    ", "        ")
    indent_patterns = re.findall(r'^(\s+)', content, re.MULTILINE)
    for pattern in indent_patterns:
        if len(pattern) >= 4 and len(pattern) <= 16:
            if pattern not in frequencies:
                mapping[pattern] = pattern
            frequencies[pattern] += 1