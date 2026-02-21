# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_utils.py
import os
import re

TREE_BRANCH = "├── "
TREE_LAST   = "└── "
TREE_INDENT = "│   "

def get_tree_icon(is_dir: bool) -> str:
    """Ícones de alta visibilidade para terminais modernos."""
    return "📁 " if is_dir else "📄 "

def is_directory(path_name: str) -> bool:
    """Detecta se o alvo é diretório. Pastas terminam com / ou não possuem extensão."""
    clean_name = path_name.strip().replace('\\', '/')
    if clean_name.endswith('/'): return True
    # Se não tem ponto e não é um arquivo especial de config
    return '.' not in os.path.basename(clean_name)

def clean_path_and_content(line: str):
    """Extrai path e conteúdo de strings tipo 'file.txt[conteúdo]'."""
    line = line.strip().replace('\\', '/')
    match = re.search(r'^([^\\[]+)\[(.*)\](.*)$', line)
    if match:
        path = f"{match.group(1).strip()}{match.group(3).strip()}"
        content = match.group(2).replace('\\n', '\n').replace('/n', '\n')
        return path, content
    return line, ""

def expand_braces(text: str) -> list:
    """Expande sintaxe de chaves: folder/{a.py,b.py} -> [folder/a.py, folder/b.py]."""
    match = re.search(r'^(.*)\{(.*)\}(.*)$', text)
    if not match: return [text]
    prefix, content, suffix = match.groups()
    parts = [p.strip() for p in content.split(',')]
    return [f"{prefix}{p}{suffix}" for p in parts]

def get_indent_level(line: str) -> int:
    """Calcula o nível de indentação convertendo tabs em 4 espaços (PASC 6.3)."""
    expanded_line = line.replace('\t', '    ')
    return len(expanded_line) - len(expanded_line.lstrip())