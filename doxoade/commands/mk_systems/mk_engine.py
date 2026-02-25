# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_engine.py (v94.9 Platinum)
import os
# [DOX-UNUSED] from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
# [DOX-UNUSED] from ...tools.filesystem import is_ignored
from .mk_utils import (
    get_indent_level, is_directory, clean_path_and_content, 
    expand_braces, TREE_BRANCH, TREE_LAST, TREE_INDENT, get_tree_icon
)
# [DOX-UNUSED] from ...dnm import DNM
# [DOX-UNUSED] from ...tools.filesystem import _get_project_config
class MkEngine:
    """Motor de Construção de Topologia (Nexus Edition)."""
    def __init__(self, base_path="."):
        self.base_path = os.path.abspath(base_path)
        self.stack = [(-1, self.base_path)]
    def _process_single_item(self, indent, raw_name):
        """Gerencia a pilha de diretórios com proteção de escopo (OSL-1)."""
        # Remove da pilha qualquer diretório que tenha indentação maior ou igual à atual
        while len(self.stack) > 1 and self.stack[-1][0] >= indent:
            self.stack.pop()
        name, content = clean_path_and_content(raw_name)
        parent_path = self.stack[-1][1]
        full_path = os.path.normpath(os.path.join(parent_path, name))
        if is_directory(raw_name):
            os.makedirs(full_path, exist_ok=True)
            # Só adiciona na pilha se for um diretório para servir de pai para os próximos
            self.stack.append((indent, full_path))
            return full_path, "Diretório"
        else:
            # Garante que a pasta pai do arquivo exista
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return full_path, "Arquivo"
    def parse_architecture_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip() or line.strip().startswith('#'): continue
                indent = get_indent_level(line)
                for expanded in expand_braces(line.strip()):
                    yield self._process_single_item(indent, expanded)
    def _expand_and_create(self, indent, item):
        """[FIX] Método solicitado pela mk_commands para expansão de chaves."""
        for expanded in expand_braces(item):
            path, kind = self._process_single_item(indent, expanded)
            yield f"{kind:<10}: {path}"
            
    def render_tree(self, path: str, project_root: str, prefix: str = ""):
        """Visualização recursiva blindada pelo DNM e TOML."""
        from ...dnm import DNM
        
        if not os.path.exists(path): return
        
        # Instancia a autoridade de navegação para a raiz do projeto
        dnm = DNM(project_root)
        try:
            # PASC-8.17: Só processa itens que NÃO estão no ignore do TOML ou Git
            raw_items = os.listdir(path)
            items = []
            for i in sorted(raw_items):
                full_item_path = os.path.join(path, i)
                # Verifica contra .gitignore e pyproject.toml
                if not dnm.is_ignored(full_item_path):
                    items.append(i)
        except PermissionError: return
        count = len(items)
        for i, item in enumerate(items):
            is_last = (i == count - 1)
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            
            connector = TREE_LAST if is_last else TREE_BRANCH
            icon = get_tree_icon(is_dir)
            color = Fore.CYAN if is_dir else Fore.WHITE
            
            yield f"{prefix}{connector}{icon}{color}{item}{Style.RESET_ALL}"
            
            if is_dir:
                new_prefix = prefix + ("    " if is_last else TREE_INDENT)
                yield from self.render_tree(full_path, project_root, new_prefix)