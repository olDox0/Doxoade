# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/forge.py (v96.5 Platinum)
import ast
# [DOX-UNUSED] import os

class VulcanForge(ast.NodeTransformer):
    """Transpilador Estrutural: Converte Python moderno em C-Style limpo."""
    def __init__(self, target_path: str = ""):
        super().__init__()
        self.original_imports = []
        # Bloqueio de libs que possuem extensões C complexas (evita conflitos de linkagem)
        self.blacklist = {'radon', 'click', 'psutil', 'sqlite3', 'progressbar', 'rich', 'pathspec'}

    def visit_Import(self, node):
        content = ast.unparse(node)
        if any(x in content for x in self.blacklist): return None
        self.original_imports.append(content)
        return node

    def visit_ImportFrom(self, node):
        if node.module and any(x in node.module for x in self.blacklist): return None
        self.original_imports.append(ast.unparse(node))
        return node

    def visit_arg(self, node):
        """Remove anotações de argumento (ex: path: Path -> path)."""
        node.annotation = None
        return node

    def visit_AnnAssign(self, node):
        """Converte 'var: type = val' para 'var = val' para o Cython."""
        if node.value is None: return None # Remove declarações puras sem valor
        return ast.Assign(targets=[node.target], value=node.value, lineno=node.lineno)

    def visit_FunctionDef(self, node):
        """Prepara funções para o Turbo Nativo."""
        node.returns = None # Remove '-> dict'
        node.decorator_list = [] # Limpa decoradores de UI
        if not node.name.endswith('_vulcan_optimized'):
            node.name = f"{node.name}_vulcan_optimized"
        self.generic_visit(node)
        return node

    def generate_source(self, file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read())
        
        # Transformação via Árvore (Imune a erros de Regex)
        transformed = self.visit(tree)
        ast.fix_missing_locations(transformed)
        
        header = "# cython: language_level=3, boundscheck=False, wraparound=False\n"
        header += "import sys, os, json\n"
        header += "try: from typing import *\nexcept: pass\n\n"
        
        return header + ast.unparse(transformed)