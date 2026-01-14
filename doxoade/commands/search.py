# -*- coding: utf-8 -*-
"""
Nexus Search v4.1 - Chief Gold Edition.
Otimizado para busca linear em stream e filtragem de ruído.
Conformidade: MPoT-7, PASC-6.
"""
from os import walk
from pathlib import Path
from click import command, argument, option, echo, pass_context
from colorama import Fore, Style

from ..shared_tools import _get_project_config, ExecutionLogger

# ============================================================================
# FASE 1: MOTORES DE BUSCA (LÓGICA PURA)
# ============================================================================

def _search_in_commits(query: str, limit: int) -> list:
    """Busca em mensagens de commit via Git (Aegis Protocol)."""
    if not query:
        return []
    
    from subprocess import run # PASC-6.1: Lazy Import
    try:
        cmd = ['git', 'log', f'--grep={query}', '--oneline', '--no-merges', f'-n{limit}']
        # shell=False garante segurança; # nosec silencia o Bandit revisado
        result = run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=False) # nosec
        
        if result.returncode != 0: 
            return []
        
        matches = []
        for line in result.stdout.splitlines():
            if not line.strip(): continue
            parts = line.split(' ', 1)
            if len(parts) == 2:
                matches.append({'hash': parts[0], 'message': parts[1]})
        return matches
    except Exception: 
        return []

def _is_searchable(file_path: Path) -> bool:
    """Filtro de integridade para arquivos de busca (MPoT-17)."""
    SKIP_EXTS = {'.lock', '.bin', '.db', '.pyc', '.log'}
    ALLOWED_EXTS = {'.py', '.md', '.txt', '.json', '.dox', '.toml'}
    
    if file_path.suffix in SKIP_EXTS or file_path.name == "arvore.txt":
        return False
    return file_path.suffix in ALLOWED_EXTS

def _search_in_code_stream(project_root: Path, query: str, limit: int) -> list:
    """
    Motor de Busca Linear via Stream (Gargalo 4 Fix).
    MPoT-5: Contrato de validação de entrada implementado.
    """
    if not project_root.exists() or not query:
        return []
        
    matches = []
    query_lower = query.lower()

    for root, dirs, filenames in walk(project_root):
        # Filtro de Pastas (Isolamento de Processamento)
        dirs[:] = [d for d in dirs if d not in {
            'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade_cache'
        }]
        
        for filename in filenames:
            file_path = Path(root) / filename
            if not _is_searchable(file_path):
                continue

            try:
                # Busca via Stream para RAM constante (PASC-6.4)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if query_lower in line.lower():
                            matches.append({
                                'file': str(file_path.relative_to(project_root)),
                                'line': i,
                                'text': line.strip(),
                                'type': file_path.suffix
                            })
                            if len(matches) >= limit:
                                return matches
            except (OSError, UnicodeDecodeError):
                continue
    return matches

# ============================================================================
# FASE 2: RENDERIZADORES ESPECIALISTAS (MPoT-4)
# ============================================================================

def _render_timeline(results: list):
    """Renderiza histórico Chronos (MPoT-4)."""
    if not results: return
    echo(f"{Fore.MAGENTA}{Style.BRIGHT}\n╔═══ Timeline (Chronos) ═══╗")
    for t in results:
        status = f"{Fore.GREEN}✔" if t['exit_code'] == 0 else f"{Fore.RED}✘"
        echo(f" {status} {Fore.WHITE}{t['timestamp'][:19]} | {Fore.CYAN}{t['full_line']}")
        echo(f"    {Style.DIM}Em: {t['dir']}{Style.RESET_ALL}")

def _render_database(db: dict):
    """Renderiza Dívida Técnica e Gênese (MPoT-4)."""
    if db.get('incidents'):
        echo(f"{Fore.RED}{Style.BRIGHT}\n╔═══ Incidentes Ativos (Dívida Técnica) ═══╗")
        for inc in db['incidents']:
            echo(f"{Fore.YELLOW}[{inc['category']}] {Fore.WHITE}{inc['message']}")
            echo(f"  Em: {inc['file']}:{inc['line']}")
            
    if db.get('solutions'):
        echo(f"{Fore.GREEN}{Style.BRIGHT}\n╔═══ Soluções Históricas (Gênese) ═══╗")
        for sol in db['solutions']:
            echo(f"{Fore.WHITE}{sol['message']}")
            echo(f"  {Fore.CYAN}Arquivo:{Style.RESET_ALL} {sol['file']}")

def _render_code_matches(matches: list):
    """Renderiza resultados de código (MPoT-4)."""
    if not matches: return
    echo(f"{Fore.CYAN}{Style.BRIGHT}\n[Código & Docs]")
    for m in matches:
        is_doc = m['type'] in ['.md', '.txt', '.dox']
        color = Fore.MAGENTA if is_doc else Fore.BLUE
        label = "DOC" if is_doc else "CODE"
        echo(f"{color}[{label}] {m['file']}:{m['line']}{Style.RESET_ALL}")
        echo(f"    > {Style.BRIGHT}{m['text']}{Style.RESET_ALL}")

# ============================================================================
# FASE 3: ORQUESTRADOR E SQL
# ============================================================================

@command('search')
@argument('query')
@option('--code', '-c', is_flag=True, help='Busca no código/docs')
@option('--commits', is_flag=True, help='Busca em commits')
@option('--incidents', '-i', is_flag=True, help='Busca incidentes')
@option('--timeline', '-t', is_flag=True, help='Busca na timeline')
@option('--limit', '-n', default=20, help='Limite (Padrão: 20)')
@pass_context
def search(ctx, query, code, commits, incidents, timeline, limit):
    """Busca Nexus: Código, Docs, Histórico e Timeline unificados."""
    if not query:
        raise ValueError("Contrato Violado: Query de busca é obrigatória.")

    config = _get_project_config(None)
    root = Path(config['root_path'])
    
    with ExecutionLogger('search', str(root), ctx.params):
        echo(f"{Fore.CYAN}{Style.BRIGHT}\n╔═══ Nexus Search: '{query}' (Limit: {limit}) ═══╗{Style.RESET_ALL}")
        
        # 1. Fontes de Dados (Busca Lógica)
        all_off = not any([code, commits, incidents, timeline])

        if incidents or all_off:
            _render_database(_search_in_database(query, limit))

        if timeline or all_off:
            _render_timeline(_search_in_timeline(query, limit))

        if code or all_off:
            matches = _search_in_code_stream(root, query, limit)
            _render_code_matches(matches)

        if commits:
            commit_matches = _search_in_commits(query, limit)
            if commit_matches:
                echo(f"{Fore.CYAN}{Style.BRIGHT}\n[Commits]")
                for m in commit_matches:
                    echo(f"{Fore.MAGENTA}{m['hash']}{Fore.WHITE}: {m['message']}")

def _search_in_database(query: str, limit: int) -> dict:
    """Busca SQL com contrato de segurança (MPoT-5)."""
    from ..database import get_db_connection
    from sqlite3 import Row
    
    results = {'incidents': [], 'solutions': []}
    conn = get_db_connection()
    conn.row_factory = Row
    sql_wildcard = f"%{query}%"
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM open_incidents WHERE message LIKE ? OR file_path LIKE ? LIMIT ?", (sql_wildcard, sql_wildcard, limit))
        for row in cursor.fetchall():
            results['incidents'].append({'file': row['file_path'], 'line': row['line'], 'message': row['message'], 'category': row['category']})
        
        cursor.execute("SELECT * FROM solutions WHERE message LIKE ? OR file_path LIKE ? LIMIT ?", (sql_wildcard, sql_wildcard, limit))
        for row in cursor.fetchall():
            results['solutions'].append({'file': row['file_path'], 'message': row['message']})
    finally:
        conn.close()
    return results

def _search_in_timeline(query: str, limit: int) -> list:
    """Busca Timeline com contrato de segurança (MPoT-5)."""
    from ..database import get_db_connection
    from sqlite3 import Row

    results = []
    conn = get_db_connection()
    conn.row_factory = Row
    sql_wildcard = f"%{query}%"
    try:
        cursor = conn.cursor()
        # Validação de integridade de esquema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='command_history'")
        if not cursor.fetchone(): return []
        
        cursor.execute("SELECT * FROM command_history WHERE full_command_line LIKE ? ORDER BY id DESC LIMIT ?", (sql_wildcard, limit))
        for row in cursor.fetchall():
            results.append({'full_line': row['full_command_line'], 'dir': row['working_dir'], 'timestamp': row['timestamp'], 'exit_code': row['exit_code']})
    finally:
        conn.close()
    return results