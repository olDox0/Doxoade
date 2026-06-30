# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_preprocessor.py
"""
Hermes Preprocessor - Pipeline de Otimização Pré-Compressão.
Remove imports não utilizados, comentários e docstrings não atribuídos.
"""
import ast
import re
from pathlib import Path
from typing import Tuple


class HermesPreprocessor:
    """Otimiza código Python antes da compressão Hermes."""

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()

    def optimize_file(self, py_file: Path) -> Tuple[str, dict]:
        """
        Aplica otimizações no arquivo e retorna o código otimizado + métricas.
        """
        original_content = py_file.read_text(encoding='utf-8', errors='ignore')
        metrics = {
            'original_size': len(original_content),
            'original_lines': len(original_content.splitlines()),
            'imports_removed': 0,
            'comments_removed': 0,
            'docstrings_removed': 0,
            'blank_lines_removed': 0,
        }

        # 1. Remove docstrings não atribuídos (apenas comentários de módulo/função)
        optimized_content = self._remove_unassigned_docstrings(original_content)
        metrics['docstrings_removed'] = original_content.count('"""') - optimized_content.count('"""')

        # 2. Remove imports não utilizados (via AST)
        optimized_content = self._remove_unused_imports(optimized_content)
        metrics['imports_removed'] = original_content.count('\nimport') - optimized_content.count('\nimport')

        # 3. Remove comentários de linha única
        optimized_content = self._remove_inline_comments(optimized_content)
        metrics['comments_removed'] = original_content.count('#') - optimized_content.count('#')

        # 4. Remove linhas vazias consecutivas (mantém no máximo 1)
        optimized_content = self._remove_excessive_blank_lines(optimized_content)
        metrics['blank_lines_removed'] = metrics['original_lines'] - len(optimized_content.splitlines())

        return optimized_content, metrics

    def _remove_unassigned_docstrings(self, content: str) -> str:
        """
        Remove docstrings que não estão atribuídos a variáveis.
        Preserva: xyz = \"\"\" ... \"\"\"
        Remove: \"\"\" ... \"\"\" (no início de módulo/função/classe)
        """
        try:
            tree = ast.parse(content)
            
            # Coleta linhas de docstrings não atribuídos
            docstring_lines = set()
            
            for node in ast.walk(tree):
                # Docstrings de módulo
                if isinstance(node, ast.Module):
                    if (node.body and isinstance(node.body[0], ast.Expr) and 
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)):
                        doc_node = node.body[0]
                        for line_no in range(doc_node.lineno, doc_node.end_lineno + 1):
                            docstring_lines.add(line_no)
                
                # Docstrings de funções/classes
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if (node.body and isinstance(node.body[0], ast.Expr) and 
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)):
                        doc_node = node.body[0]
                        for line_no in range(doc_node.lineno, doc_node.end_lineno + 1):
                            docstring_lines.add(line_no)
            
            # Remove as linhas marcadas
            lines = content.splitlines()
            optimized_lines = [line for i, line in enumerate(lines, 1) if i not in docstring_lines]
            
            return '\n'.join(optimized_lines)
        
        except SyntaxError:
            return content

    def _remove_unused_imports(self, content: str) -> str:
        """Remove imports que não são usados no código (análise AST simples)."""
        try:
            tree = ast.parse(content)
            
            # Coleta todos os nomes usados no código
            used_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        used_names.add(node.value.id)
            
            # Remove imports não utilizados
            lines = content.splitlines()
            optimized_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    # Extrai o nome do módulo importado
                    if ' import ' in stripped:
                        module_name = stripped.split(' import ')[0].replace('from ', '').strip()
                        if module_name not in used_names and module_name.split('.')[0] not in used_names:
                            continue  # Pula este import
                optimized_lines.append(line)
            
            return '\n'.join(optimized_lines)
        except SyntaxError:
            return content

    def _remove_inline_comments(self, content: str) -> str:
        """Remove comentários de linha única (# comentário)."""
        lines = content.splitlines()
        optimized_lines = []
        for line in lines:
            # Remove comentários que não estão dentro de strings
            if '#' in line and not line.strip().startswith('#'):
                # Verifica se o # não está dentro de uma string
                parts = line.split('#', 1)
                if len(parts) == 2:
                    before_hash = parts[0]
                    # Conta aspas antes do #
                    single_quotes = before_hash.count("'")
                    double_quotes = before_hash.count('"')
                    # Se o número de aspas é par, o # não está em string
                    if single_quotes % 2 == 0 and double_quotes % 2 == 0:
                        line = before_hash.rstrip()
            optimized_lines.append(line)
        return '\n'.join(optimized_lines)

    def _remove_excessive_blank_lines(self, content: str) -> str:
        """Remove linhas vazias consecutivas (mantém no máximo 1)."""
        lines = content.splitlines()
        optimized_lines = []
        prev_blank = False
        for line in lines:
            if not line.strip():
                if not prev_blank:
                    optimized_lines.append(line)
                prev_blank = True
            else:
                optimized_lines.append(line)
                prev_blank = False
        return '\n'.join(optimized_lines)


def preprocess_for_hermes(py_file: Path, project_root: str) -> Tuple[str, dict]:
    """
    Função helper para pré-processar um arquivo antes da compressão.
    """
    preprocessor = HermesPreprocessor(project_root)
    return preprocessor.optimize_file(py_file)