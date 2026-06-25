# doxoade/tools/vulcan/db_refactorer.py
import ast
import os
import shutil
import click
from pathlib import Path

from doxoade.tools.vulcan.refactor_exec import apply_refactor

class AlexandriaRefactorer(ast.NodeTransformer):
    def __init__(self):
        self.changes_made = False

    def visit_Call(self, node):
        # Transforma qualquer .execute(q, p) em alexandria_write(q, p)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
            self.changes_made = True
            return ast.Call(
                func=ast.Name(id='alexandria_write', ctx=ast.Load()),
                args=node.args,
                keywords=node.keywords
            )
        return self.generic_visit(node)

class DBRefactorer(ast.NodeTransformer):
    def __init__(self):
        self.changes_made = False

    def visit_Call(self, node):
        # Detecta chamadas de .execute() em qualquer objeto (conn, cursor, etc)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
            self.changes_made = True
            # Substitui por: alexandria_write(query, params)
            return ast.Call(
                func=ast.Name(id='alexandria_write', ctx=ast.Load()),
                args=node.args,
                keywords=[]
            )
        return self.generic_visit(node)

def apply_refactor_with_import(file_path: Path, dry_run: bool = True) -> tuple[bool, str]:
    """
    Mantém a assinatura original exigida pelo CLI `doxoade db refactor`.
    Repassa o arquivo para o novo motor que:
      1. Ignora comandos SELECT/PRAGMA.
      2. Injeta o import do Alexandria automaticamente.
      3. Faz a cirurgia via manipulação de string para preservar comentários.
    """
    return apply_refactor(file_path, dry_run=dry_run)