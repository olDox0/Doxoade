# doxoade/indexer/code_indexer.py
"""
Indexador de Código Python via AST.

Responsabilidades:
- Parsear arquivos Python
- Extrair definições (funções, classes) e docstrings
- Mapear chamadas de função (Call Graph)
- Extrair comentários

Filosofia MPoT:
- Classes coesas
- Métodos pequenos
- Tratamento explícito de erros
"""

import ast
import os
import click
from pathlib import Path
from typing import List, Set, Optional
from collections import defaultdict
from colorama import Fore


class CodeIndexer:
    """
    Indexador de código Python.
    """
    
    def __init__(self, project_root: str):
        assert project_root, "project_root não pode estar vazio"
        
        self.project_root = Path(project_root)
        self.index = {
            'functions': {},
            'classes': {},
            'calls': defaultdict(set),
            'comments': {},
            'docstrings': {}
        }
    
    def index_project(self, ignore_dirs: Optional[Set[str]] = None, use_cache: bool = True) -> None:
        """
        Indexa todos os arquivos .py do projeto.
        
        Args:
            ignore_dirs: Diretórios a ignorar
            use_cache: Se True, tenta usar cache (Lógica de cache delegada ao chamador ou integrada aqui se circular)
        """
        # Nota: A lógica de carregar/salvar cache foi movida para o comando search.py 
        # ou para uma camada superior para evitar dependência circular com a classe Cache.
        # Aqui focamos apenas na extração.
        
        if ignore_dirs is None:
            ignore_dirs = {'venv', '.git', '__pycache__', 'build', 'dist'}
        
        py_files = self._collect_python_files(ignore_dirs)
        
        # A lógica de verificar cache deve ser feita antes de chamar este método, 
        # ou injetada. Para manter simples e MPoT, este método faz o trabalho bruto.
        
        click.echo(Fore.CYAN + f"Indexando {len(py_files)} arquivos...")
        
        for file_path in py_files:
            self._index_file(file_path)
    
    def _collect_python_files(self, ignore_dirs: Set[str]) -> List[Path]:
        """Coleta todos os arquivos Python do projeto."""
        assert ignore_dirs is not None, "ignore_dirs não pode ser None"
        
        files = []
        for root, dirs, filenames in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for filename in filenames:
                if filename.endswith('.py'):
                    files.append(Path(root) / filename)
        
        return files
    
    def _index_file(self, file_path: Path) -> None:
        """Indexa um arquivo Python individual."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = ast.parse(content, filename=str(file_path))
            
            self._extract_definitions(tree, file_path)
            self._extract_calls(tree, file_path)
            self._extract_comments(content, file_path)
            
        except SyntaxError:
            pass  # Esperado - arquivo com erro de sintaxe
        except Exception as e:
            click.echo(Fore.YELLOW + f"⚠ Erro ao indexar {file_path.name}: {e}")
    
    def _extract_definitions(self, tree: ast.AST, file_path: Path) -> None:
        """Extrai funções e classes do AST."""
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path # Fallback se não for relativo
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                location = {
                    'file': str(rel_path),
                    'line': node.lineno,
                    'name': node.name,
                    'docstring': ast.get_docstring(node)
                }
                
                if node.name not in self.index['functions']:
                    self.index['functions'][node.name] = []
                
                self.index['functions'][node.name].append(location)
                
                if location['docstring']:
                    self.index['docstrings'][node.name] = location['docstring']
            
            elif isinstance(node, ast.ClassDef):
                location = {
                    'file': str(rel_path),
                    'line': node.lineno,
                    'name': node.name,
                    'docstring': ast.get_docstring(node)
                }
                
                if node.name not in self.index['classes']:
                    self.index['classes'][node.name] = []
                
                self.index['classes'][node.name].append(location)
    
    def _extract_calls(self, tree: ast.AST, file_path: Path) -> None:
        """Mapeia chamadas de função (grafo de dependências)."""
        function_scopes = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_scopes[node.name] = node
        
        for func_name, func_node in function_scopes.items():
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    called_func = self._get_call_name(node.func)
                    if called_func:
                        self.index['calls'][called_func].add(func_name)
    
    def _get_call_name(self, node: ast.AST) -> Optional[str]:
        """Extrai o nome de uma chamada de função."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None
    
    def _extract_comments(self, content: str, file_path: Path) -> None:
        """Extrai comentários do código."""
        try:
            rel_path = str(file_path.relative_to(self.project_root))
        except ValueError:
            rel_path = str(file_path)

        comments = []
        
        for i, line in enumerate(content.splitlines(), 1):
            if '#' in line:
                comment = line.split('#', 1)[1].strip()
                if comment:
                    comments.append((i, comment))
        
        if comments:
            self.index['comments'][rel_path] = comments