# doxoade/commands/search.py
"""
Sistema Sapiens Search - Busca Inteligente de Código
Versão 2.1 - Refatorado para usar módulo indexer

Filosofia MPoT:
- Funções < 60 linhas
- Uma responsabilidade por função
- Documentação clara
- Fail loudly (erros explícitos)
- Contratos com assertions
"""

import click
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Set
from difflib import SequenceMatcher
from colorama import Fore, Style

from ..shared_tools import _get_project_config, ExecutionLogger
# IMPORTAÇÃO DA NOVA ARQUITETURA
from ..indexer import CodeIndexer, TextMatcher, IndexCache

# ============================================================================
# FASE 3: ESTATÍSTICAS E INTEGRAÇÃO GIT
# ============================================================================

def _search_in_commits(query: str, fuzzy: bool, limit: int = 20) -> List[Dict]:
    """
    Busca em mensagens de commit do Git.
    """
    assert query, "Query não pode estar vazia"
    
    try:
        cmd = [
            'git', 'log', 
            f'--grep={query}',
            '--oneline',
            '--no-merges',
            f'-n{limit}'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode != 0:
            return []
        
        matches = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            
            parts = line.split(' ', 1)
            if len(parts) == 2:
                commit_hash, message = parts
                
                if TextMatcher.match_text(query, message, fuzzy):
                    matches.append({
                        'type': 'commit',
                        'hash': commit_hash,
                        'message': message
                    })
        
        return matches
        
    except FileNotFoundError:
        return []
    except Exception:
        return []

def _generate_usage_stats(indexer: CodeIndexer, func_name: str) -> Dict[str, Any]:
    """
    Gera estatísticas de uso de uma função.
    """
    assert indexer and func_name, "Parâmetros não podem estar vazios"
    
    stats = {
        'function': func_name,
        'definitions': [],
        'total_callers': 0,
        'callers_by_file': {},
        'call_frequency': {}
    }
    
    if func_name in indexer.index['functions']:
        stats['definitions'] = indexer.index['functions'][func_name]
    
    if func_name in indexer.index['calls']:
        callers = list(indexer.index['calls'][func_name])
        stats['total_callers'] = len(callers)
        
        for caller in callers:
            if caller in indexer.index['functions']:
                for loc in indexer.index['functions'][caller]:
                    file_path = loc['file']
                    if file_path not in stats['callers_by_file']:
                        stats['callers_by_file'][file_path] = []
                    stats['callers_by_file'][file_path].append(caller)
        
        stats['call_frequency'] = {
            file: len(funcs) 
            for file, funcs in stats['callers_by_file'].items()
        }
    
    return stats

def _display_stats(stats: Dict[str, Any]) -> None:
    """Exibe estatísticas formatadas."""
    func_name = stats['function']
    
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n╔═══ Estatísticas: '{func_name}' ═══╗" + Style.RESET_ALL)
    
    if stats['definitions']:
        click.echo(Fore.GREEN + "\n[Definição]")
        for loc in stats['definitions']:
            click.echo(f"  {Fore.YELLOW}{loc['file']}:{loc['line']}")
            if loc['docstring']:
                first_line = loc['docstring'].split('\n')[0].strip()
                click.echo(f"  {Style.DIM}{first_line}{Style.RESET_ALL}")
    else:
        click.echo(Fore.YELLOW + "\n[Definição]")
        click.echo("  Não encontrada (pode ser importada de lib externa)")
    
    total = stats['total_callers']
    if total > 0:
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n[Uso]")
        click.echo(f"  Usada em {Fore.YELLOW}{total}{Fore.WHITE} lugares")
        
        top_files = sorted(
            stats['call_frequency'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        if top_files:
            click.echo(Fore.WHITE + "\n  Top arquivos:")
            for file_path, count in top_files:
                click.echo(f"    • {Fore.BLUE}{file_path}{Fore.WHITE}: {count}x")
                
                callers = stats['callers_by_file'][file_path]
                for caller in callers[:3]:
                    click.echo(f"      {Style.DIM}→ {caller}{Style.RESET_ALL}")
                
                if len(callers) > 3:
                    click.echo(f"      {Style.DIM}... e mais {len(callers) - 3}{Style.RESET_ALL}")
    else:
        click.echo(Fore.YELLOW + "\n[Uso]")
        click.echo("  Não usada em nenhum lugar (função morta?)")

def _suggest_similar_functions(indexer: CodeIndexer, query: str, threshold: float = 0.7) -> List[str]:
    """Sugere funções similares."""
    assert indexer and query, "Parâmetros não podem estar vazios"
    
    suggestions = []
    for func_name in indexer.index['functions'].keys():
        ratio = SequenceMatcher(None, query.lower(), func_name.lower()).ratio()
        if ratio >= threshold:
            suggestions.append((func_name, ratio))
    
    suggestions.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in suggestions[:5]]

# ============================================================================
# FUNÇÕES DE BUSCA (Delega para o Indexer/Matcher mas formata aqui)
# ============================================================================

def _perform_search(
    indexer: CodeIndexer, 
    query: str,
    search_code: bool,
    search_functions: bool,
    search_comments: bool,
    search_commits: bool,
    fuzzy: bool,
    show_callers: bool
) -> Dict[str, List[Dict[str, Any]]]:
    """Executa a busca unificada."""
    assert indexer, "Indexer não pode ser None"
    assert query, "Query não pode estar vazia"
    
    results = {
        'functions': [],
        'code': [],
        'comments': [],
        'commits': [],
        'callers': []
    }
    
    # 1. Busca Funções (Default ou Explícito)
    if search_functions or not any([search_code, search_functions, search_comments, search_commits]):
        results['functions'] = _search_functions(indexer, query, fuzzy)
    
    # 2. Busca Código Raw (Opcional)
    if search_code:
        # A busca raw ainda é feita aqui pois depende de varredura de texto,
        # não do índice estruturado. Poderíamos mover para um módulo 'scanner'.
        results['code'] = _search_in_code_raw(indexer.project_root, query, fuzzy)
    
    # 3. Busca Comentários (Do Índice)
    if search_comments:
        results['comments'] = _search_comments(indexer, query, fuzzy)
    
    # 4. Busca Commits (Git)
    if search_commits:
        results['commits'] = _search_in_commits(query, fuzzy)
    
    # 5. Call Graph
    if show_callers:
        results['callers'] = _find_callers(indexer, query)
    
    return results

def _search_functions(indexer: CodeIndexer, query: str, fuzzy: bool) -> List[Dict]:
    matches = []
    for func_name, locations in indexer.index['functions'].items():
        if TextMatcher.match_text(query, func_name, fuzzy):
            for loc in locations:
                matches.append({
                    'name': func_name,
                    'file': loc['file'],
                    'line': loc['line'],
                    'docstring': loc['docstring']
                })
        elif func_name in indexer.index['docstrings']:
            docstring = indexer.index['docstrings'][func_name]
            if TextMatcher.match_text(query, docstring, fuzzy):
                for loc in locations:
                    matches.append({
                        'name': func_name,
                        'file': loc['file'],
                        'line': loc['line'],
                        'docstring': docstring
                    })
    return matches

def _search_comments(indexer: CodeIndexer, query: str, fuzzy: bool) -> List[Dict]:
    matches = []
    for file_path, comments in indexer.index['comments'].items():
        for line_num, comment_text in comments:
            if TextMatcher.match_text(query, comment_text, fuzzy):
                matches.append({
                    'file': file_path,
                    'line': line_num,
                    'text': comment_text
                })
    return matches

def _find_callers(indexer: CodeIndexer, func_name: str) -> List[Dict]:
    callers = []
    if func_name in indexer.index['calls']:
        for caller in indexer.index['calls'][func_name]:
            if caller in indexer.index['functions']:
                for loc in indexer.index['functions'][caller]:
                    callers.append({
                        'name': caller,
                        'file': loc['file'],
                        'line': loc['line']
                    })
    return callers

def _search_in_code_raw(project_root: Path, query: str, fuzzy: bool) -> List[Dict]:
    """Busca textual direta (fallback/complemento)."""
    matches = []
    for root, dirs, filenames in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in {'venv', '.git', '__pycache__', 'build', 'dist'}]
        for filename in filenames:
            if not filename.endswith('.py'): continue
            file_path = Path(root) / filename
            try:
                lines = file_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                for i, line in enumerate(lines, 1):
                    if TextMatcher.match_text(query, line, fuzzy):
                        # Extrai snippet simples
                        snippet_start = max(0, i-2)
                        snippet_lines = [(j+1, lines[j]) for j in range(snippet_start, min(len(lines), i+1))]
                        
                        matches.append({
                            'file': str(file_path.relative_to(project_root)),
                            'line': i,
                            'text': line.strip(),
                            'snippet': snippet_lines
                        })
            except Exception: pass
    return matches

def _display_results(results: Dict[str, List[Dict]], query: str) -> None:
    # Exibe funções
    if results['functions']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Funções]")
        for match in results['functions'][:10]:
            click.echo(f"{Fore.YELLOW}{match['name']:<30}{Fore.WHITE} {match['file']}:{match['line']}")
            if match['docstring']:
                first_line = match['docstring'].split('\n')[0].strip()
                click.echo(f"  {Style.DIM}{first_line}{Style.RESET_ALL}")
    
    # Exibe código
    if results['code']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Código]")
        for match in results['code'][:15]:
            click.echo(f"{Fore.BLUE}{match['file']}:{match['line']}")
            for lnum, ltext in match['snippet']:
                prefix = "  > " if lnum == match['line'] else "    "
                color = Style.BRIGHT if lnum == match['line'] else Style.DIM
                click.echo(f"{Fore.WHITE}{color}{prefix}{lnum:4}: {ltext}{Style.RESET_ALL}")
    
    # Exibe comentários e commits (simplificado para brevidade, mas deve existir)
    if results['comments']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Comentários]")
        for match in results['comments'][:10]:
            click.echo(f"{Fore.BLUE}{match['file']}:{match['line']}{Fore.WHITE} # {match['text']}")

    if results['commits']:
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Commits]")
        for match in results['commits'][:10]:
            click.echo(f"{Fore.MAGENTA}{match['hash']}{Fore.WHITE}: {match['message']}")

# ============================================================================
# COMANDO CLI
# ============================================================================

@click.command('search')
@click.argument('query')
@click.option('--code', '-c', is_flag=True, help='Busca no código fonte')
@click.option('--function', '-f', is_flag=True, help='Busca funções relacionadas')
@click.option('--comment', is_flag=True, help='Busca em comentários')
@click.option('--commits', is_flag=True, help='Busca em mensagens de commit')
@click.option('--fuzzy', is_flag=True, help='Ativa busca fuzzy (typos)')
@click.option('--callers', is_flag=True, help='Mostra quem chama a função')
@click.option('--stats', is_flag=True, help='Estatísticas de uso da função')
@click.option('--no-cache', is_flag=True, help='Força re-indexação (ignora cache)')
@click.pass_context
def search(ctx, query, code, function, comment, commits, fuzzy, callers, stats, no_cache):
    """Busca inteligente no código do projeto."""
    config = _get_project_config(None)
    project_root = config['root_path']
    
    with ExecutionLogger('search', project_root, ctx.params) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n╔═══ Busca: '{query}' ═══╗" + Style.RESET_ALL)
        
        # Usa o novo Indexer modular
        indexer = CodeIndexer(project_root)
        ignore_dirs = set(config.get('ignore', []))
        ignore_dirs.update({'venv', '.git', '__pycache__'})
        
        # Indexa (usa cache automaticamente se possível)
        indexer.index_project(ignore_dirs, use_cache=not no_cache)
        
        if stats:
            usage_stats = _generate_usage_stats(indexer, query)
            _display_stats(usage_stats)
            return
            
        results = _perform_search(indexer, query, code, function, comment, commits, fuzzy, callers)
        _display_results(results, query)
        
        total = sum(len(v) for v in results.values())
        if total == 0:
            click.echo(Fore.YELLOW + "\nNenhum resultado encontrado.")
            if function or not any([code, comment, commits]):
                suggestions = _suggest_similar_functions(indexer, query)
                if suggestions:
                    click.echo(Fore.CYAN + "\nVocê quis dizer:")
                    for s in suggestions: click.echo(f"  • {Fore.YELLOW}{s}")