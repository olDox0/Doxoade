# doxoade/commands/search.py
"""
Sistema Sapiens Search - Busca Inteligente de Código e Contexto
Versão 3.1 - Nexus com Limite Dinâmico (Relatórios)
"""

import subprocess
import sqlite3
import os
import click
from typing import List, Dict, Any
from pathlib import Path
from difflib import SequenceMatcher
from colorama import Fore, Style

from ..shared_tools import _get_project_config, ExecutionLogger
from ..indexer import CodeIndexer, TextMatcher
from ..database import get_db_connection

# ============================================================================
# FASE 1: BUSCA GIT E ESTATÍSTICAS
# ============================================================================

def _search_in_commits(query: str, fuzzy: bool, limit: int) -> List[Dict]:
    """Busca em mensagens de commit do Git com limite dinâmico."""
    assert query, "Query não pode estar vazia"
    try:
        # Usa o limite passado pelo usuário
        cmd = ['git', 'log', f'--grep={query}', '--oneline', '--no-merges', f'-n{limit}']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode != 0: return []
        
        matches = []
        for line in result.stdout.splitlines():
            if not line.strip(): continue
            parts = line.split(' ', 1)
            if len(parts) == 2:
                commit_hash, message = parts
                if TextMatcher.match_text(query, message, fuzzy):
                    matches.append({'type': 'commit', 'hash': commit_hash, 'message': message})
        return matches
    except Exception: return []

def _generate_usage_stats(indexer: CodeIndexer, func_name: str) -> Dict[str, Any]:
    """Gera estatísticas de uso de uma função."""
    stats = {
        'function': func_name, 'definitions': [], 'total_callers': 0,
        'callers_by_file': {}, 'call_frequency': {}
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
                    if file_path not in stats['callers_by_file']: stats['callers_by_file'][file_path] = []
                    stats['callers_by_file'][file_path].append(caller)
        stats['call_frequency'] = {file: len(funcs) for file, funcs in stats['callers_by_file'].items()}
    return stats

def _display_stats(stats: Dict[str, Any]) -> None:
    func_name = stats['function']
    click.echo(Fore.CYAN + Style.BRIGHT + f"\n╔═══ Estatísticas: '{func_name}' ═══╗" + Style.RESET_ALL)
    if stats['definitions']:
        click.echo(Fore.GREEN + "\n[Definição]")
        for loc in stats['definitions']:
            click.echo(f"  {Fore.YELLOW}{loc['file']}:{loc['line']}")
    else: click.echo(Fore.YELLOW + "\n[Definição] Não encontrada.")
    
    total = stats['total_callers']
    if total > 0:
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n[Uso] {total} lugares")
        for file_path, count in sorted(stats['call_frequency'].items(), key=lambda x: x[1], reverse=True)[:5]:
            click.echo(f"    • {Fore.BLUE}{file_path}{Fore.WHITE}: {count}x")

def _suggest_similar_functions(indexer: CodeIndexer, query: str, threshold: float = 0.7) -> List[str]:
    suggestions = []
    for func_name in indexer.index['functions'].keys():
        ratio = SequenceMatcher(None, query.lower(), func_name.lower()).ratio()
        if ratio >= threshold: suggestions.append((func_name, ratio))
    suggestions.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in suggestions[:5]]

# ============================================================================
# FASE 2: BUSCA CRUZADA NO BANCO DE DADOS (NEXUS)
# ============================================================================

def _search_in_database(query: str, fuzzy: bool, limit: int) -> Dict[str, List[Dict]]:
    """Busca cruzada em incidentes e soluções (History) com limite."""
    results = {'incidents': [], 'solutions': []}
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    sql_wildcard = f"%{query}%"
    
    try:
        # Busca Estendida: Mensagem + Caminho do Arquivo
        cursor.execute("""
            SELECT * FROM open_incidents 
            WHERE message LIKE ? OR file_path LIKE ? OR category LIKE ?
            ORDER BY timestamp DESC LIMIT ?
        """, (sql_wildcard, sql_wildcard, sql_wildcard, limit))
        
        for row in cursor.fetchall():
            results['incidents'].append({
                'file': row['file_path'],
                'line': row['line'],
                'message': row['message'],
                'category': row['category'],
                'hash': row['finding_hash']
            })
            
        cursor.execute("""
            SELECT * FROM solutions 
            WHERE message LIKE ? OR file_path LIKE ? 
            ORDER BY timestamp DESC LIMIT ?
        """, (sql_wildcard, sql_wildcard, limit))
        
        for row in cursor.fetchall():
            results['solutions'].append({
                'file': row['file_path'],
                'line': row['error_line'],
                'message': row['message'],
                'hash': row['finding_hash'],
                'timestamp': row['timestamp']
            })
    except Exception: pass
    finally: conn.close()
    return results

def _search_in_timeline(query: str, limit: int) -> List[Dict]:
    """[NOVO] Busca no histórico de execução (Chronos) com limite."""
    results = []
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    sql_wildcard = f"%{query}%"

    try:
        # Verifica se a tabela existe (v15+)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'")
        if not cursor.fetchone(): return []

        # Busca por comando, linha completa ou diretório de execução
        cursor.execute("""
            SELECT * FROM command_history 
            WHERE full_command_line LIKE ? OR working_dir LIKE ?
            ORDER BY timestamp DESC LIMIT ?
        """, (sql_wildcard, sql_wildcard, limit))
        
        for row in cursor.fetchall():
            results.append({
                'command': row['command_name'],
                'full_line': row['full_command_line'],
                'dir': row['working_dir'],
                'timestamp': row['timestamp'],
                'exit_code': row['exit_code']
            })
    except Exception: pass
    finally: conn.close()
    return results

def _display_db_results(db_results: Dict[str, List[Dict]], timeline_results: List[Dict]):
    """Exibe o painel de inteligência cruzada."""
    
    if timeline_results:
        click.echo(Fore.MAGENTA + Style.BRIGHT + "\n╔═══ Timeline (Chronos) ═══╗")
        for t in timeline_results:
            status = Fore.GREEN + "✔" if t['exit_code'] == 0 else Fore.RED + "✘"
            click.echo(f" {status} {Fore.WHITE}{t['timestamp'][:19]} | {Fore.CYAN}{t['full_line']}")
            click.echo(f"    {Style.DIM}Em: {t['dir']}{Style.RESET_ALL}")

    if db_results['incidents']:
        click.echo(Fore.RED + Style.BRIGHT + "\n╔═══ Incidentes Ativos (Não Resolvidos) ═══╗")
        for inc in db_results['incidents']:
            click.echo(f"{Fore.YELLOW}[{inc['category']}] {Fore.WHITE}{inc['message']}")
            click.echo(f"  Em: {inc['file']}:{inc['line']}")
            
    if db_results['solutions']:
        click.echo(Fore.GREEN + Style.BRIGHT + "\n╔═══ Soluções Históricas (Base de Conhecimento) ═══╗")
        for sol in db_results['solutions']:
            click.echo(f"{Fore.WHITE}{sol['message']}")
            click.echo(f"  {Fore.CYAN}Arquivo:{Style.RESET_ALL} {sol['file']}")

# ============================================================================
# FASE 3: BUSCA DE CÓDIGO E DOCUMENTAÇÃO
# ============================================================================

def _search_in_code_raw(project_root: Path, query: str, fuzzy: bool, limit: int) -> List[Dict]:
    """Busca textual em .py e DOCS com limite."""
    matches = []
    ALLOWED_EXTS = {'.py', '.md', '.txt', '.json', '.dox', '.yaml', '.yml', '.ini', '.toml'}
    count = 0
    
    for root, dirs, filenames in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in {'venv', '.git', '__pycache__', 'build', 'dist', 'site-packages', '.doxoade_cache'}]
        
        for filename in filenames:
            if count >= limit: return matches

            file_path = Path(root) / filename
            if file_path.suffix not in ALLOWED_EXTS: continue
            if filename.endswith('.lock'): continue

            try:
                content = ""
                try: content = file_path.read_text(encoding='utf-8')
                except: content = file_path.read_text(encoding='latin-1', errors='ignore')
                
                lines = content.splitlines()
                for i, line in enumerate(lines, 1):
                    if TextMatcher.match_text(query, line, fuzzy):
                        snippet_start = max(0, i-2)
                        snippet_lines = [(j+1, lines[j]) for j in range(snippet_start, min(len(lines), i+1))]
                        
                        matches.append({
                            'file': str(file_path.relative_to(project_root)),
                            'line': i,
                            'text': line.strip(),
                            'snippet': snippet_lines,
                            'type': file_path.suffix
                        })
                        count += 1
                        if count >= limit: return matches
            except Exception: pass
    return matches

def _perform_search(indexer: CodeIndexer, query: str, code: bool, func: bool, comment: bool, commits: bool, incidents: bool, timeline: bool, fuzzy: bool, callers: bool, limit: int) -> Dict[str, Any]:
    """Orquestrador da Busca com Limitador."""
    results = {
        'functions': [], 'code': [], 'comments': [], 'commits': [], 'callers': [],
        'database': {'incidents': [], 'solutions': []},
        'timeline': []
    }
    
    all_flags = any([code, func, comment, commits, incidents, timeline, callers])
    if not all_flags:
        func = code = incidents = timeline = True

    # Aplica o limite individualmente para cada fonte para garantir dados ricos
    if func: results['functions'] = _search_functions(indexer, query, fuzzy)[:limit]
    if code: results['code'] = _search_in_code_raw(indexer.project_root, query, fuzzy, limit)
    if comment: results['comments'] = _search_comments(indexer, query, fuzzy)[:limit]
    if commits: results['commits'] = _search_in_commits(query, fuzzy, limit)
    if callers: results['callers'] = _find_callers(indexer, query)[:limit]
    
    if incidents: results['database'] = _search_in_database(query, fuzzy, limit)
    if timeline: results['timeline'] = _search_in_timeline(query, limit)
    
    return results

def _search_functions(indexer: CodeIndexer, query: str, fuzzy: bool) -> List[Dict]:
    matches = []
    if not indexer: return []
    for func_name, locations in indexer.index['functions'].items():
        if TextMatcher.match_text(query, func_name, fuzzy):
            for loc in locations:
                matches.append({'name': func_name, 'file': loc['file'], 'line': loc['line'], 'docstring': loc['docstring']})
    return matches

def _search_comments(indexer: CodeIndexer, query: str, fuzzy: bool) -> List[Dict]:
    matches = []
    if not indexer: return []
    for file_path, comments in indexer.index['comments'].items():
        for line_num, comment_text in comments:
            if TextMatcher.match_text(query, comment_text, fuzzy):
                matches.append({'file': file_path, 'line': line_num, 'text': comment_text})
    return matches

def _find_callers(indexer: CodeIndexer, func_name: str) -> List[Dict]:
    callers = []
    if not indexer: return []
    if func_name in indexer.index['calls']:
        for caller in indexer.index['calls'][func_name]:
            if caller in indexer.index['functions']:
                for loc in indexer.index['functions'][caller]:
                    callers.append({'name': caller, 'file': loc['file'], 'line': loc['line']})
    return callers

def _display_results(results: Dict[str, Any], query: str) -> None:
    # Exibe Timeline
    if results.get('timeline'):
        _display_db_results({'incidents':[], 'solutions':[]}, results['timeline'])

    # Exibe DB
    if results.get('database') and (results['database']['incidents'] or results['database']['solutions']):
        _display_db_results(results['database'], [])

    # Exibe Funções
    if results.get('functions'):
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Funções]")
        for match in results['functions']:
            click.echo(f"{Fore.YELLOW}{match['name']:<30}{Fore.WHITE} {match['file']}:{match['line']}")
    
    # Exibe Código
    if results.get('code'):
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Código & Docs]")
        for match in results['code']:
            ftype = "DOC" if match['type'] in ['.md', '.txt', '.dox'] else "CODE"
            color = Fore.BLUE if ftype == "CODE" else Fore.MAGENTA
            click.echo(f"{color}[{ftype}] {match['file']}:{match['line']}")
            for lnum, ltext in match['snippet']:
                prefix = "  > " if lnum == match['line'] else "    "
                s_color = Style.BRIGHT if lnum == match['line'] else Style.DIM
                click.echo(f"{Fore.WHITE}{s_color}{prefix}{lnum:4}: {ltext.strip()}{Style.RESET_ALL}")

    # Exibe Commits
    if results.get('commits'):
        click.echo(Fore.CYAN + Style.BRIGHT + "\n[Commits]")
        for match in results['commits']:
            click.echo(f"{Fore.MAGENTA}{match['hash']}{Fore.WHITE}: {match['message']}")

@click.command('search')
@click.argument('query')
@click.option('--code', '-c', is_flag=True, help='Busca no código e documentação')
@click.option('--function', '-f', is_flag=True, help='Busca funções')
@click.option('--comment', is_flag=True, help='Busca em comentários')
@click.option('--commits', is_flag=True, help='Busca em mensagens de commit')
@click.option('--incidents', '-i', is_flag=True, help='Busca na Base de Conhecimento')
@click.option('--timeline', '-t', is_flag=True, help='Busca no Histórico de Execução')
@click.option('--limit', '-n', default=20, help='Limite de resultados (Padrão: 20)')
@click.option('--fuzzy', is_flag=True, help='Ativa busca fuzzy (typos)')
@click.option('--callers', is_flag=True, help='Mostra quem chama a função')
@click.option('--stats', is_flag=True, help='Estatísticas de uso da função')
@click.option('--no-cache', is_flag=True, help='Força re-indexação')
@click.pass_context
def search(ctx, query, code, function, comment, commits, incidents, timeline, limit, fuzzy, callers, stats, no_cache):
    """
    Busca Nexus: Código, Docs, Histórico e Timeline unificados.
    """
    config = _get_project_config(None)
    project_root = config['root_path']
    
    with ExecutionLogger('search', project_root, ctx.params) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n╔═══ Nexus Search: '{query}' (Limit: {limit}) ═══╗" + Style.RESET_ALL)
        
        indexer = CodeIndexer(project_root)
        ignore_dirs = set(config.get('ignore', []))
        ignore_dirs.update({'venv', '.git', '__pycache__'})
        indexer.index_project(ignore_dirs, use_cache=not no_cache)
        
        if stats:
            usage_stats = _generate_usage_stats(indexer, query)
            _display_stats(usage_stats)
            return
            
        results = _perform_search(indexer, query, code, function, comment, commits, incidents, timeline, fuzzy, callers, limit)
        
        _display_results(results, query)
        
        total = 0
        for k, v in results.items():
            if isinstance(v, list): total += len(v)
            elif isinstance(v, dict): total += sum(len(x) for x in v.values())
        
        if total == 0:
            click.echo(Fore.YELLOW + "\nNenhum resultado encontrado.")