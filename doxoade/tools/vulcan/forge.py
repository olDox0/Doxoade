# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/forge.py (v8.2 Sledgehammer)
import ast
# [DOX-UNUSED] import os

class VulcanForge(ast.NodeTransformer):
    def __init__(self, target_path: str):
        super().__init__()
        self.target_path = target_path

    def visit_ImportFrom(self, node):
        """Remove imports de tipagem (Fix: translator.py)."""
        if node.module in ['typing', 'abc']:
            return None # O C não precisa de Optional, Union ou ABC
        return node

    def visit_ClassDef(self, node):
        """Sanitiza bases de classe (Fix: ABC error)."""
        # Remove ABC das classes base para não confundir o compilador C
        node.bases = [b for b in node.bases if not (isinstance(b, ast.Name) and b.id == 'ABC')]
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node):
        """Remove decoradores e renomeia (Fix: lru_cache/abstractmethod)."""
        if node.name.startswith('__'): return node
        
        # Remove decoradores que travam a forja nativa
        ignored_decs = ['lru_cache', 'abstractmethod', 'classmethod', 'staticmethod']
        node.decorator_list = [
            d for d in node.decorator_list 
            if not (isinstance(d, ast.Name) and d.id in ignored_decs) and
               not (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id in ignored_decs)
        ]

        # Limpeza de tipos
        node.returns = None
        for arg in node.args.args: arg.annotation = None
        
        # Ponte Vulcan
        node.name = f"{node.name}_vulcan_optimized"
        
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node):
        """Remove anotações de variáveis."""
        return ast.Assign(targets=[node.target], value=node.value, lineno=node.lineno)

    def visit_Subscript(self, node):
        """Remove Subscripts de tipo (ex: list[str] -> list)."""
        typing_names = {'list', 'dict', 'set', 'Optional', 'Union', 'List', 'Dict', 'Iterable'}
        if isinstance(node.value, ast.Name) and node.value.id in typing_names:
            return node.value
        return self.generic_visit(node)

    def generate_source(self, file_path):
        """Gera .pyx limpo de qualquer metadado (v8.2)."""
        content = ""
        for enc in ['utf-8-sig', 'utf-8']:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                    break
            except Exception as e:
                print(f"\033[0;33m generate_source - Exception: {e}")
                continue
        
        tree = ast.parse(content, filename=file_path)
        
        # Preserva imports reais
        imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        
        # Aplica o Sledgehammer
        self.visit(tree)
        
        header = [
            "# cython: language_level=3",
            "# cython: boundscheck=False",
            "import sys, os",
            "\n".join(imports)
        ]
        
        return "\n".join(header) + "\n\n" + ast.unparse(tree)