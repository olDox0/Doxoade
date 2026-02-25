# -*- coding: utf-8 -*-
# doxoade/commands/diff.py
"""
Módulo de Diferenciação e Auditoria de Regressão (PASC-1).
Suporte a Diff Padrão e Auditoria de Funcionalidades Legadas (-l, -lc).
"""
import os
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _run_git_command, _present_diff_output
# [DOX-UNUSED] from .search import _search_in_code_stream
@click.command('diff')
@click.argument('path', type=click.Path(exists=True))
@click.option('-v', '--revision', 'revision_hash', help="Hash do commit para comparação.")
@click.option('--legacy', '-l', 'show_legacy', is_flag=True, help="Identifica regressões de funções no histórico.")
@click.option('--legacy-code', '-lc', 'show_legacy_code', is_flag=True, help="Exibe o código das funções removidas no passado.")
@click.option('--limit', '-lmt', default=5, help="Quantidade de commits para retroceder na análise.")
@click.option('--search', '-s', 'search_moved', is_flag=True, help="Rastreia se funções removidas foram movidas para outros arquivos.") # NOVO
def diff(path, revision_hash, show_legacy, limit, show_legacy_code, search_moved):
    """Analisa diferenças de código e regressões de funcionalidade."""
    params = {'revision': revision_hash, 'legacy': show_legacy, 'lc': show_legacy_code}
    with ExecutionLogger('diff', path, params):
        git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True, silent_fail=True)
        if not git_root:
            click.echo(Fore.RED + "[ERRO] Este diretório não é um repositório Git.")
            return
        # FIX: Sincronização do rel_path para uso nas funções internas
        rel_path = os.path.relpath(os.path.abspath(path), git_root.strip()).replace('\\', '/')
        
        # FIX: is_legacy_mode removido para evitar Dead Store
        if show_legacy or show_legacy_code or search_moved:
            _run_legacy_audit(rel_path, limit, show_legacy_code, search_moved)
        else:
            _run_standard_diff(rel_path, revision_hash)
def _run_standard_diff(rel_path: str, revision: str):
    """Executa o diff tradicional do Git."""
    target = revision if revision else "HEAD"
    cmd = ['diff', target, '--', rel_path]
    result = _run_git_command(cmd, capture_output=True)
    
    if not result:
        click.echo(Fore.GREEN + "✔ Nenhuma diferença detectada.")
    else:
        click.echo(Fore.CYAN + f"--- Diferenças em '{rel_path}' vs {target} ---")
        _present_diff_output(result)
def _run_legacy_audit(rel_path: str, limit: int, show_code: bool, search_moved: bool):
    """Analisa a evolução semântica (Fix v88.1)."""
    from ..tools.git import _get_file_history_metadata, _get_historical_content
    from ..tools.analysis import _extract_function_signatures, _get_function_source
    from .search import _search_in_code_stream 
#    from .search_systems.search_engine import _search_code_logic as _search_in_code_stream
    from ..shared_tools import _find_project_root
    current_content = ""
    project_root = Path(_find_project_root(os.getcwd()))
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [LEGACY AUDIT] Regressões em '{rel_path}' ---{Style.RESET_ALL}")
    
    # 1. Estado Atual
    try:
        with open(rel_path, 'r', encoding='utf-8', errors='ignore') as f:
            current_content = f.read()
            current_signatures = _extract_function_signatures(current_content)
#            current_signatures = _extract_function_signatures(f.read())
    except Exception as e:
        click.echo(f"{Fore.RED}[ERRO] Leitura falhou: {e}{Style.RESET_ALL}")
        return
    # 2. Varredura Temporal
    history = _get_file_history_metadata(rel_path, limit=limit)
    for commit in history:
        h_hash = commit['hash']
        click.echo(f"\n{Fore.WHITE}{Style.BRIGHT}Commit: {h_hash} ({commit['date']}) - {commit['subject']}{Style.RESET_ALL}")
        
        past_content = _get_historical_content(rel_path, h_hash)
        past_signatures = _extract_function_signatures(past_content)
        
        found_regression = False
        for name, info in past_signatures.items():
            # Caso A: Remoção
            if name not in current_signatures:
                click.echo(f"   {Fore.RED}✘ FUNÇÃO REMOVIDA: {Style.BRIGHT}{name}{Style.RESET_ALL}")
                if show_code:
                    code = _get_function_source(past_content, name)
                    if code:
                        click.echo(f"     {Style.DIM}--- CÓDIGO PERDIDO ---")
                        for line in code.splitlines():
                            click.echo(f"     {Fore.RED}| {line}")
                        click.echo(f"     ----------------------{Style.RESET_ALL}")
                else:
                    click.echo(f"     {Style.DIM}> Contrato: ({', '.join(info['args'])}){Style.RESET_ALL}")
                found_regression = True
                
                if search_moved:
                    click.echo(f"     {Fore.YELLOW}🔍 Rastreando migração...{Style.RESET_ALL}")
                    # TENTATIVA: Busca elástica por nome original e limpo
                    queries = [f"def {name}", f"{name}_vulcan_optimized", name.lstrip('_')]
                    
                    found_locations = []
                    for q in queries:
                        # Busca no projeto inteiro (sem limite de 1 para pegar duplicatas)
                        hits = _search_in_code_stream(project_root, q, limit=5)
                        if hits:
                            for h in hits:
                                # Normaliza para comparação de string
                                h_path = h['file'].replace('\\', '/')
                                loc_str = f"{h_path}:{h['line']}"
                                if loc_str not in found_locations:
                                    found_locations.append(loc_str)
                    if found_locations:
                        for loc in found_locations:
                            tag = "➔ RENOMEADA/REFERENCIADA EM:" if loc.startswith(rel_path) else "➔ MIGRADA PARA:"
                            color = Fore.GREEN if "MIGRADA" in tag else Fore.CYAN
                            click.echo(f"     {color}{tag} {loc}{Style.RESET_ALL}")
                    else:
                        # PASC-Omega: Sugestão de Refatoração Estrutural
                        click.echo(f"     {Fore.WHITE}{Style.DIM}Lógica não rastreada como função isolada.")
                        click.echo(f"     {Fore.YELLOW}{Style.DIM}   > Provável causa: Absorção por classe ou refatoração inline.{Style.RESET_ALL}")
            
            # Caso B: Mudança de Contrato
            elif current_signatures[name]['args'] != info['args']:
                click.echo(f"   {Fore.YELLOW}⚠ CONTRATO ALTERADO: {Style.BRIGHT}{name}{Style.RESET_ALL}")
                click.echo(f"     {Fore.RED}- Antigo: ({', '.join(info['args'])}){Style.RESET_ALL}")
                click.echo(f"     {Fore.GREEN}+ Novo:   ({', '.join(current_signatures[name]['args'])}){Style.RESET_ALL}")
                found_regression = True
        
        if not found_regression:
            click.echo(f"   {Fore.GREEN}✔ Estrutura preservada.{Style.RESET_ALL}")