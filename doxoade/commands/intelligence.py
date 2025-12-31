# -*- coding: utf-8 -*-
"""
Módulo de Inteligência Profunda (Deep Insight).
Varre o projeto para extrair metadados, estrutura de classes/funções,
dívida técnica (TODOs) e estado do Git.
Otimizado para Termux: removido chardet em favor de detecção heurística rápida.
"""

import os
import json
import ast
import re
import sys
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import click
from rich.console import Console

from ..shared_tools import ExecutionLogger
from ..tools.git import _run_git_command
from ..dnm import DNM

__version__ = "38.1 Alfa (Termux-Optimized)"

class InsightVisitor(ast.NodeVisitor):
    """Extrai inteligência profunda da Árvore Sintática Abstrata (AST)."""
    
    def __init__(self):
        self.classes = []
        self.functions = []
        self.imports = []
        
    def visit_ClassDef(self, node: ast.ClassDef):
        """Mapeia definições de classes e seus métodos."""
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "docstring": ast.get_docstring(node) or "",
            "methods": methods,
            "bases": [ast.unparse(b) for b in node.bases]
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Mapeia funções, argumentos e calcula complexidade básica."""
        args = [a.arg for a in node.args.args]
        decorators = [ast.unparse(d) for d in node.decorator_list]
        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "docstring": ast.get_docstring(node) or "",
            "args": args,
            "decorators": decorators,
            "complexity": self._estimate_complexity(node)
        })
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Registra imports globais."""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Registra imports de módulos específicos."""
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")
        self.generic_visit(node)

    def _estimate_complexity(self, node: ast.AST) -> int:
        """Estimativa rápida de complexidade ciclomática baseada em nós de desvio."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
                complexity += 1
        return complexity

def _extract_todos(content: str) -> List[Dict[str, Any]]:
    """Extrai comentários de dívida técnica utilizando Regex otimizado."""
    todos = []
    # Compila a regex para performance no loop
    todo_pattern = re.compile(r'\b(TODO|FIXME|HACK|XXX|BUG)\b[:\s]*(.*)', re.IGNORECASE)
    
    for i, line in enumerate(content.splitlines(), 1):
        if "#" in line:
            comment = line.split("#", 1)[1].strip()
            match = todo_pattern.match(comment)
            if match:
                tag, text = match.groups()
                todos.append({
                    "tag": tag.upper(),
                    "line": i,
                    "text": text.strip()
                })
    return todos

def _read_file_safely(file_path: str) -> str:
    """
    Lê o conteúdo do arquivo com fallback de encoding.
    MPoT-7: Retorna string vazia em vez de None para manter consistência de tipo.
    """
    if os.path.getsize(file_path) > 1024 * 1024:
        return ""

    for enc in ['utf-8', 'latin-1', 'cp1252']:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, PermissionError):
            continue
    return ""

def _get_git_info(file_path: str) -> Optional[Dict[str, str]]:
    """Obtém informações do último commit deste arquivo via Git."""
    try:
        fmt = "%h|%an|%ai|%s"
        cmd = ['log', '-n', '1', f'--format={fmt}', '--', file_path]
        output = _run_git_command(cmd, capture_output=True, silent_fail=True)
        
        if output:
            parts = output.strip().split('|')
            if len(parts) >= 4:
                return {
                    "last_commit_hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                }
    except Exception as e:
        logging.debug(f"Falha ao obter Git Info para {file_path}: {e}")
    return None

def _analyze_file_metadata(file_path_str: str, root_path: str, logger: ExecutionLogger) -> Optional[Dict[str, Any]]:
    """
    Coleta metadados ricos para um único arquivo.
    Retorna None apenas se o arquivo for irrelevante (binário/vazio).
    """
    try:
        content = _read_file_safely(file_path_str)
        if not content: # Se o conteúdo vier vazio do _read_file_safely
            return None 

        stats = os.stat(file_path_str)
        rel_path = os.path.relpath(file_path_str, root_path).replace('\\', '/')
        
        content = _read_file_safely(file_path_str)
        if content is None:
            return None # Arquivo binário ou ilegível

        file_info = {
            "path": rel_path,
            "size_bytes": stats.st_size,
            "modified_at_utc": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
            "language": "python" if file_path_str.endswith(".py") else "text",
            "git_status": _get_git_info(file_path_str)
        }

        if file_path_str.endswith('.py'):
            try:
                tree = ast.parse(content, filename=file_path_str)
                visitor = InsightVisitor()
                visitor.visit(tree)
                file_info.update({
                    "classes": visitor.classes,
                    "functions": visitor.functions,
                    "imports": sorted(list(set(visitor.imports))),
                    "todos": _extract_todos(content),
                    "loc": len(content.splitlines())
                })
            except SyntaxError as e:
                file_info["error"] = f"AST Parse Error: {str(e)}"
        else:
            file_info["loc"] = len(content.splitlines())

        return file_info
    except Exception as e:
        logger.add_finding('warning', f"Erro ao analisar: {file_path_str}", details=str(e))
        return None

@click.command('intelligence')
@click.pass_context
@click.option('--output', '-o', default='doxoade_report.json', help="Nome do arquivo de saída.")
def intelligence(ctx, output):
    """Gera um dossiê de Inteligência Profunda (Deep Insight) do projeto."""
    path = '.'
    arguments = ctx.params
    console = Console()
    
    with ExecutionLogger('intelligence', path, arguments) as logger:
        console.print("[bold cyan]--- [INTELLIGENCE] Gerando Dossiê de Conhecimento ---[/bold cyan]")
        
        dnm = DNM(path)
        files = dnm.scan()
        
        console.print(f"   > Analisando [bold]{len(files)}[/bold] arquivos (Estrutura, Semântica, Git)...")
        
        analyzed_files = []
        with click.progressbar(files, label='Processando') as bar:
            for file_path in bar:
                data = _analyze_file_metadata(file_path, path, logger)
                if data:
                    analyzed_files.append(data)

        # Sumário Executivo
        total_loc = sum(f.get('loc', 0) for f in analyzed_files)
        total_todos = sum(len(f.get('todos', [])) for f in analyzed_files if 'todos' in f)
        
        report_data = {
            "header": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "doxoade_version": __version__,
                "project_root": os.path.abspath(path),
                "metrics": {
                    "total_files": len(analyzed_files),
                    "total_loc": total_loc,
                    "technical_debt_items": total_todos
                }
            },
            "codebase": analyzed_files
        }
        
        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)
            console.print(f"\n[bold green][OK] Dossiê salvo em: {output}[/bold green]")
            console.print(f"   - LOC Total: {total_loc} | Dívida Técnica: {total_todos} itens")
        except IOError as e:
            console.print(f"[bold red]\n[ERRO] Falha ao salvar relatório: {e}[/bold red]")
            sys.exit(1)