# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_utils.py
# [DOX-UNUSED] import os
import re

TREE_BRANCH = "├── "
TREE_LAST   = "└── "
TREE_INDENT = "│   "

def get_tree_icon(is_dir: bool) -> str:
    """Ícones de alta visibilidade para terminais modernos."""
    return "📁 " if is_dir else "📄 "

def is_directory(path_name: str) -> bool:
    """Detecta se o alvo é diretório pela sintaxe (termina em / ou sem ponto)."""
    if '[' in path_name: return False
    return path_name.endswith(('/', '\\')) or '.' not in path_name

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
    """Calcula o nível de indentação (espaços ou tabs)."""
    return len(line) - len(line.lstrip())