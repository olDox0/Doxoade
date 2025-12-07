# doxoade/commands/search.py
"""
Sistema Sapiens Search - Busca Inteligente de Código
Versão 1.0 - MVP (Minimum Viable Product)

Filosofia MPoT:
- Funções < 60 linhas
- Uma responsabilidade por função
- Documentação clara
- Fail loudly (erros explícitos)
"""

import click
import ast
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
from colorama import Fore, Style
from difflib import SequenceMatcher

from ..shared_tools import _get_project_config, ExecutionLogger

# ============================================================================
# FASE 1: INDEXAÇÃO BÁSICA
# ============================================================================

class CodeIndexer:
    """
    Indexador de código Python.
    
    Responsabilidades:
    - Extrair funções, classes e docstrings
    - Mapear definições e usos
    - Construir grafo de chamadas
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.index = {
            'functions': {},      # {name: [locations]}
            'classes': {},        # {name: [locations]}
            'calls': defaultdict(set),  # {func: {callers}}
            'comments': {},       # {file: [(line, text)]}
            'docstrings': {}      # {func_name: docstring}
        }
    
    def index_project(self, ignore_dirs: Optional[Set[str]] = None) -> None:
        """Indexa todos os arquivos .py do projeto."""
        if ignore_dirs is None:
            ignore_dirs = {'venv', '.git', '__pycache__', 'build', 'dist'}
        
        py_files = self._collect_python_files(ignore_dirs)
        
        click.echo(Fore.CYAN + f"Indexando {len(py_files)} arquivos...")
        
        for file_path in py_files:
            self._index_file(file_path)
    
    def _collect_python_files(self, ignore_dirs: Set[str]) -> List[Path]:
        """Coleta todos os arquivos Python do projeto."""
        files = []
        
        for root, dirs, filenames in os.walk(self.project_root):
            # Remove diretórios ignorados
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for filename in filenames:
                if filename.endswith('.py'):
                    files.append(Path(root) / filename)
        
        return files
    
    def _index_file(self, file_path: Path) -> None:
        """Indexa um arquivo Python individual."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            # Parse AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Extrai informações
            self._extract_definitions(tree, file_path)
            self._extract_calls(tree, file_path)
            self._extract_comments(content, file_path)
            
        except SyntaxError:
            # Arquivo com erro de sintaxe - ignora silenciosamente
            pass
        except Exception as e:
            click.echo(Fore.YELLOW + f"⚠ Erro ao indexar {file_path.name}: {e}")
    
    def _extract_definitions(self, tree: ast.AST, file_path: Path) -> None:
        """Extrai funções e classes do AST."""
        rel_path = file_path.relative_to(self.project_root)
        
        for node in ast.walk(tree):
            # Funções
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
                
                # Guarda docstring
                if location['docstring']:
                    self.index['docstrings'][node.name] = location['docstring']
            
            # Classes
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
        rel_path = file_path.relative_to(self.project_root)
        
        # Primeiro, identifica todas as funções neste arquivo
        function_scopes = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_scopes[node.name] = node
        
        # Depois, encontra chamadas dentro de cada função
        for func_name, func_node in function_scopes.items():
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    # Tenta extrair o nome da função chamada
                    called_func = self._get_call_name(node.func)
                    
                    if called_func:
                        self.index['calls'][called_func].add(func_name)
    
    def _get_call_name(self, node: ast.AST) -> Optional[str]:
        """Extrai o nome de uma chamada de função."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # Ex: obj.method() -> retorna 'method'
            return node.attr
        return None
    
    def _extract_comments(self, content: str, file_path: Path) -> None:
        """Extrai comentários do código."""
        rel_path = str(file_path.relative_to(self.project_root))
        comments = []
        
        for i, line in enumerate(content.splitlines(), 1):
            if '#' in line:
                comment = line.split('#', 1)[1].strip()
                if comment:  # Ignora comentários vazios
                    comments.append((i, comment))
        
        if comments:
            self.index['comments'][rel_path] = comments


# ============================================================================
# FASE 2: BUSCA INTELIGENTE
# ============================================================================

class TextMatcher:
    """
    Matcher de texto com fuzzy matching e normalização.
    
    Funcionalidades:
    - Normalização de termos (plural/singular, typos comuns)
    - Fuzzy matching (similaridade de strings)
    - Sinônimos programáticos
    """
    
    # Mapa de normalizações comuns
    NORMALIZATIONS = {
        'postmortems': ['post-mortems', 'postmortem', 'post_mortems'],
        'database': ['db', 'banco', 'bd'],
        'function': ['func', 'funcao', 'função'],
        'class': ['classe'],
        'error': ['erro', 'exception'],
    }
    
    @staticmethod
    def normalize_term(term: str) -> Set[str]:
        """
        Gera variações normalizadas de um termo.
        
        Retorna:
            Set de strings com o termo original + variações
        """
        variations = {term.lower()}
        
        # Remove hífens e underscores
        variations.add(term.replace('-', '').replace('_', ''))
        
        # Adiciona versão com hífens/underscores substituídos por espaço
        variations.add(term.replace('-', ' ').replace('_', ' '))
        
        # Adiciona sinônimos conhecidos
        term_lower = term.lower()
        for canonical, aliases in TextMatcher.NORMALIZATIONS.items():
            if term_lower == canonical or term_lower in aliases:
                variations.add(canonical)
                variations.update(aliases)
        
        return variations
    
    @staticmethod
    def fuzzy_match(query: str, target: str, threshold: float = 0.6) -> bool:
        """
        Verifica se query é similar o suficiente a target.
        
        Args:
            query: Termo buscado
            target: Termo alvo
            threshold: Similaridade mínima (0.0 a 1.0)
        
        Retorna:
            True se similaridade >= threshold
        """
        ratio = SequenceMatcher(None, query.lower(), target.lower()).ratio()
        return ratio >= threshold
    
    @staticmethod
    def match_text(query: str, text: str, fuzzy: bool = False) -> bool:
        """
        Verifica se query está presente em text.
        
        Args:
            query: Termo buscado
            text: Texto onde buscar
            fuzzy: Se True, usa fuzzy matching
        
        Retorna:
            True se houver match
        """
        if not query or not text:
            return False
        
        # Normaliza ambos
        query_variations = TextMatcher.normalize_term(query)
        text_lower = text.lower()
        
        # Match exato (após normalização)
        for variation in query_variations:
            if variation in text_lower:
                return True
        
        # Fuzzy match (opcional)
        if fuzzy:
            words = text_lower.split()
            for word in words:
                if TextMatcher.fuzzy_match(query, word):
                    return True
        
        return False


# ============================================================================
# FASE 3: COMANDO CLI
# ============================================================================

@click.command('search')
@click.argument('query')
@click.option('--code', '-c', is_flag=True, help='Busca no código fonte')
@click.option('--function', '-f', is_flag=True, help='Busca funções relacionadas')
@click.option('--comment', is_flag=True, help='Busca em comentários')
@click.option('--fuzzy', is_flag=True, help='Ativa busca fuzzy (typos)')
@click.option('--callers', is_flag=True, help='Mostra quem chama a função')
@click.pass_context
def search(ctx, query, code, function, comment, fuzzy, callers):
    """
    Busca inteligente no código do projeto.
    
    Exemplos:
        doxoade search "output" --code
        doxoade search "logger" --function
        doxoade search "postmortems" --fuzzy
        doxoade search "_log_execution" --callers
    """
    # Configuração do projeto
    config = _get_project_config(None)
    project_root = config['root_path']
    
    with ExecutionLogger('search', project_root, ctx.params) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n╔═══ Busca: '{query}' ═══╗" + Style.RESET_ALL)
        
        # Indexa projeto
        indexer = CodeIndexer(project_root)
        ignore_dirs = set(config.get('ignore', []))
        ignore_dirs.update({'venv', '.git', '__pycache__'})
        
        indexer.index_project(ignore_dirs)
        
        # Executa busca
        results = _perform_search(indexer, query, code, function, comment, fuzzy, callers)
        
        # Exibe resultados
        _display_results(results, query)
        
        # Estatísticas
        total = sum(len(v) for v in results.values())
        if total == 0:
            click.echo(Fore.YELLOW + "\nNenhum resultado encontrado.")
            logger.add_finding('INFO', f"Busca por '{query}' não retornou resultados")
        else:
            click.echo(Fore.GREEN + f"\n{total} resultado(s) encontrado(s).")


def _perform_search(
    indexer: CodeIndexer, 
    query: str,
    search_code: bool,
    search_functions: bool,
    search_comments: bool,
    fuzzy: bool,
    show_callers: bool
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Executa a busca no índice.
    
    Retorna:
        Dicionário com categorias de resultados
    """
    results = {
        'functions': [],
        'classes': [],
        'code': [],
        'comments': [],
        'callers': []
    }
    
    # Busca em funções
    if search_functions or not any([search_code, search_functions, search_comments]):
        results['functions'] = _search_functions(indexer, query, fuzzy)
    
    # Busca em código (raw text)
    if search_code:
        results['code'] = _search_in_code(indexer.project_root, query, fuzzy)
    
    # Busca em comentários
    if search_comments:
        results['comments'] = _search_comments(indexer, query, fuzzy)
    
    # Mostra call graph
    if show_callers:
        results['callers'] = _find_callers(indexer, query)
    
    return results


def _search_functions(indexer: CodeIndexer, query: str, fuzzy: bool) -> List[Dict]:
    """Busca funções por nome ou docstring."""
    matches = []
    
    for func_name, locations in indexer.index['functions'].items():
        # Match no nome da função
        if TextMatcher.match_text(query, func_name, fuzzy):
            for loc in locations:
                matches.append({
                    'type': 'function',
                    'name': func_name,
                    'file': loc['file'],
                    'line': loc['line'],
                    'docstring': loc['docstring'],
                    'match_type': 'name'
                })
        
        # Match na docstring
        elif func_name in indexer.index['docstrings']:
            docstring = indexer.index['docstrings'][func_name]
            if TextMatcher.match_text(query, docstring, fuzzy):
                for loc in locations:
                    matches.append({
                        'type': 'function',
                        'name': func_name,
                        'file': loc['file'],
                        'line': loc['line'],
                        'docstring': docstring,
                        'match_type': 'docstring'
                    })
    
    return matches


def _search_in_code(project_root: Path, query: str, fuzzy: bool) -> List[Dict]:
    """Busca raw no código fonte."""
    matches = []
    
    # TODO: Implementar busca linha por linha
    # Por enquanto, retorna vazio (Fase 2)
    
    return matches


def _search_comments(indexer: CodeIndexer, query: str, fuzzy: bool) -> List[Dict]:
    """Busca em comentários."""
    matches = []
    
    for file_path, comments in indexer.index['comments'].items():
        for line_num, comment_text in comments:
            if TextMatcher.match_text(query, comment_text, fuzzy):
                matches.append({
                    'type': 'comment',
                    'file': file_path,
                    'line': line_num,
                    'text': comment_text
                })
    
    return matches


def _find_callers(indexer: CodeIndexer, func_name: str) -> List[Dict]:
    """Encontra quem chama uma função."""
    callers = []
    
    if func_name in indexer.index['calls']:
        for caller in indexer.index['calls'][func_name]:
            # Encontra localização do caller
            if caller in indexer.index['functions']:
                for loc in indexer.index['functions'][caller]:
                    callers.append({
                        'type': 'caller',
                        'name': caller,
                        'file': loc['file'],
                        'line': loc['line']
                    })
    
    return callers


def _display_results(results: Dict[str, List[Dict]], query: str) -> None:
    """Exibe resultados formatados."""
    
    # Funções
    if results['functions']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Funções]")
        for match in results['functions'][:10]:  # Limita a 10
            click.echo(
                f"{Fore.YELLOW}{match['name']:<30}{Fore.WHITE} "
                f"{match['file']}:{match['line']}"
            )
            
            if match['docstring']:
                # Primeira linha da docstring
                first_line = match['docstring'].split('\n')[0].strip()
                click.echo(f"  {Style.DIM}{first_line}{Style.RESET_ALL}")
    
    # Comentários
    if results['comments']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Comentários]")
        for match in results['comments'][:10]:
            click.echo(
                f"{Fore.BLUE}{match['file']}:{match['line']}{Fore.WHITE} "
                f"# {match['text']}"
            )
    
    # Call graph
    if results['callers']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Quem Chama Esta Função]")
        for match in results['callers']:
            click.echo(
                f"{Fore.GREEN}  ← {match['name']:<30}{Fore.WHITE} "
                f"{match['file']}:{match['line']}"
            )