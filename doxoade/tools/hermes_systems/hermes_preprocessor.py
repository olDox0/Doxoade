# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_preprocessor.py
"""
Hermes Preprocessor - Pipeline de Otimização Pré-Compressão.
Remove imports não utilizados, comentários e docstrings não atribuídos.
Compliance: OSL-4 (responsabilidade única), OSL-5 (nunca levanta exceção).
"""
import ast
# [DOX-UNUSED] import re
from pathlib import Path
from typing import Tuple


class HermesPreprocessor:
    """Otimiza código Python antes da compressão Hermes.

    Pipeline:
    1. Remove docstrings não atribuídos (via AST)
    2. Remove imports não utilizados (via AST + análise de nomes)
    3. Remove comentários inline (via regex)
    4. Remove linhas vazias excessivas (via regex)

    Todas as métricas são contagens reais de remoções, não diffs de string.
    """

    def __init__(self, project_root: str = None):
        self.root = Path(project_root).resolve() if project_root else None
        self.metrics = {
            'docstrings_removed': 0,
            'imports_removed': 0,
            'comments_removed': 0,
            'blank_lines_removed': 0,
        }

    def optimize_file(self, file_path: Path) -> Tuple[str, dict]:
        self.metrics = {
            'docstrings_removed': 0,
            'imports_removed': 0,
            'comments_removed': 0,
            'blank_lines_removed': 0,
        }

        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception:
            return '', self.metrics

        original_lines = len(content.splitlines())

        # Fase 1: Docstrings (via AST)
        content = self._remove_unassigned_docstrings(content)

        # Fase 2: Imports não utilizados (via AST)
        content = self._remove_unused_imports(content)

        # Fase 3: Comentários inline (via regex)
        content = self._remove_inline_comments(content)

        # Fase 4: Linhas vazias excessivas (via regex)
        content = self._remove_excessive_blank_lines(content)

        final_lines = len(content.splitlines())
        self.metrics['blank_lines_removed'] = max(0, original_lines - final_lines - 
                                                   self.metrics['docstrings_removed'] - 
                                                   self.metrics['comments_removed'])

        return content, self.metrics

    # ─────────────────────────────────────────────────────────────────
    # Fase 1: Docstrings via AST
    # ─────────────────────────────────────────────────────────────────
    def _remove_unassigned_docstrings(self, content: str) -> str:
        """Remove docstrings, mas preserva pelo menos um 'pass' se o corpo ficar vazio."""
        try:
            tree = ast.parse(content)
            lines = content.splitlines()
            lines_to_remove = set()
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if (node.body and isinstance(node.body[0], ast.Expr) and 
                        isinstance(node.body[0].value, ast.Constant) and 
                        isinstance(node.body[0].value.value, str)):
                        
                        # PROTEÇÃO: Se é o ÚNICO statement do corpo, não remove
                        if len(node.body) == 1:
                            continue
                        
                        doc_node = node.body[0]
                        for line_no in range(doc_node.lineno, doc_node.end_lineno + 1):
                            lines_to_remove.add(line_no)
            
            optimized_lines = [line for i, line in enumerate(lines, 1) if i not in lines_to_remove]
            return '\n'.join(optimized_lines)
        
        except SyntaxError:
            return content

    # ─────────────────────────────────────────────────────────────────
    # Fase 2: Imports não utilizados via AST
    # ─────────────────────────────────────────────────────────────────
    def _remove_unused_imports(self, source: str) -> str:
        """Remove imports não utilizados."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        # Coleta nomes usados
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        lines = source.splitlines()
        lines_to_remove = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Verifica se algum nome do import é usado
                has_used = False
                for alias in node.names:
                    name = alias.asname or alias.name.split('.')[0]
                    if name in used_names or name == '*':
                        has_used = True
                        break

                if not has_used:
                    for line_no in range(node.lineno, getattr(node, 'end_lineno', node.lineno) + 1):
                        lines_to_remove.add(line_no)
                    self.metrics['imports_removed'] += 1

        if lines_to_remove:
            new_lines = [line for i, line in enumerate(lines, 1) if i not in lines_to_remove]
            return '\n'.join(new_lines)

        return source

    # ─────────────────────────────────────────────────────────────────
    # Fase 3: Comentários inline via regex
    # ─────────────────────────────────────────────────────────────────
    def _remove_inline_comments(self, source: str) -> str:
        """Remove comentários inline."""
        lines = source.splitlines()
        new_lines = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Preserva shebang e coding
            if i == 0 and stripped.startswith('#!'):
                new_lines.append(line)
                continue
            if i <= 1 and 'coding' in stripped and stripped.startswith('#'):
                new_lines.append(line)
                continue

            # Linha que é apenas comentário
            if stripped.startswith('#'):
                # Preserva TODO, FIXME, etc
                if any(tag in stripped.upper() for tag in ['TODO', 'FIXME', 'NOTE', 'HACK', 'XXX', 'NOQA']):
                    new_lines.append(line)
                    continue
                self.metrics['comments_removed'] += 1
                continue

            # Comentário inline após código
            if '#' in line:
                new_line = self._remove_trailing_comment(line)
                if new_line != line:
                    self.metrics['comments_removed'] += 1
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        return '\n'.join(new_lines)

    def _remove_trailing_comment(self, line: str) -> str:
        """Remove comentário trailing preservando strings."""
        in_single = False
        in_double = False
        in_triple_single = False
        in_triple_double = False
        i = 0

        while i < len(line):
            if line[i:i+3] in ('"""', "'''"):
                if line[i:i+3] == '"""':
                    in_triple_double = not in_triple_double
                else:
                    in_triple_single = not in_triple_single
                i += 3
                continue

            if in_triple_single or in_triple_double:
                i += 1
                continue

            if line[i] == '"' and not in_single:
                in_double = not in_double
            elif line[i] == "'" and not in_double:
                in_single = not in_single
            elif line[i] == '#' and not in_single and not in_double:
                return line[:i].rstrip()

            i += 1

        return line

    # ─────────────────────────────────────────────────────────────────
    # Fase 4: Linhas vazias excessivas
    # ─────────────────────────────────────────────────────────────────
    def _remove_excessive_blank_lines(self, source: str) -> str:
        """Reduz blocos de 3+ linhas vazias para no máximo 2."""
        lines = source.splitlines()
        new_lines = []
        blank_count = 0

        for line in lines:
            if line.strip() == '':
                blank_count += 1
                if blank_count <= 2:
                    new_lines.append(line)
            else:
                blank_count = 0
                new_lines.append(line)

        return '\n'.join(new_lines)

def preprocess_for_hermes(file_path: Path, project_root: str = None) -> Tuple[str, dict]:
    preprocessor = HermesPreprocessor(project_root)
    return preprocessor.optimize_file(file_path)