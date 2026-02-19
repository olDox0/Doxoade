# -*- coding: utf-8 -*-
# doxoade/commands/save.py

"""
Comando Save - v80.1 Gold.
Gatekeeper Ma'at (Produção) & Anúbis (Infraestrutura).
"""

import sys
import sqlite3 # noqa
import re
import os
import click
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Set
from rich.console import Console
from colorama import Fore
import subprocess

from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger, 
    _run_git_command, 
    _present_results
)
from .check import run_check_logic

__version__ = "63.3 Alfa (Gold Standard)"

def _get_staged_python_files(git_root):
    """Filtra o Stage contra lixo e arquivos deletados (PASC 3.0)."""
    # AMR: Added, Modified, Renamed. Ignora Deletados.
    res = _run_git_command(['diff', '--name-only', '--cached', '--diff-filter=AMR', '--', '*.py'], capture_output=True)
    if not res: return []
    
    from ..dnm import DNM
    dnm = DNM(git_root)
    valid = []
    for f in res.splitlines():
        p = os.path.normpath(os.path.join(git_root, f.strip())).replace('\\', '/')
        # Só envia para o tribunal se o arquivo EXISTIR fisicamente
        if os.path.isfile(p) and not dnm.is_ignored(p):
            valid.append(p)
    return valid

def _process_finding_for_learning(cursor: sqlite3.Cursor, finding: sqlite3.Row, 
                                 modified_files: Set[str], new_commit_hash: str, 
                                 project_path: str) -> bool:
    """
    Analisa um finding individual e, se resolvido no commit, registra a solução.
    MPoT-5: Contratos de validação de entrada implementados.
    """
    if cursor is None or finding is None or modified_files is None:
        raise ValueError("Parâmetros de banco ou dados de commit inválidos.")

    file_path = finding['file']
    if not file_path:
        return False
        
    normalized_path = file_path.replace('\\', '/')
    if normalized_path not in modified_files:
        return False
    
    # Obtém o conteúdo corrigido (Estado Desejado)
    corrected_content = _run_git_command(
        ['show', f"{new_commit_hash}:{normalized_path}"],
        capture_output=True, silent_fail=True
    )
    
    if not corrected_content:
        return False
    
    cursor.execute(
        """INSERT OR REPLACE INTO solutions 
           (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (finding['finding_hash'], corrected_content, new_commit_hash, project_path, 
         datetime.now(timezone.utc).isoformat(), file_path, finding['message'], finding['line'])
    )
    return True

def _learn_solutions_from_commit(new_commit_hash: str, project_path: str):
    """
    Orquestra o aprendizado de soluções a partir de um commit recém-criado.
    Removido parâmetro 'logger' não utilizado (Fix Deepcheck).
    """
    console = Console()
    console.print("\n[bold cyan]--- [LEARN] Buscando soluções para aprender... ---[/bold cyan]")
    
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        modified_files_str = _run_git_command(
            ['diff-tree', '--no-commit-id', '--name-only', '-r', new_commit_hash],
            capture_output=True, silent_fail=True
        ) or ""
        modified_files = set(f.strip().replace('\\', '/') for f in modified_files_str.splitlines())
        
        if not modified_files:
            return

        # Busca findings recentes (24h) ativos antes deste commit
        cursor.execute("""
            SELECT DISTINCT f.finding_hash, f.file, f.line, f.message, f.category
            FROM findings f
            JOIN events e ON f.event_id = e.id
            WHERE e.project_path = ?
            AND f.severity IN ('CRITICAL', 'ERROR')
            AND datetime(e.timestamp) > datetime('now', '-1 day')
            AND f.finding_hash NOT IN (SELECT finding_hash FROM solutions WHERE project_path = ?)
        """, (project_path, project_path))
        
        findings = cursor.fetchall()
        learned_count = 0
        
        for f in findings:
            if _process_finding_for_learning(cursor, f, modified_files, new_commit_hash, project_path):
                learned_count += 1
                console.print(f"   [green]> Solução aprendida:[/green] {f['message'][:50]}...")
                _abstract_and_learn_template(cursor, {'message': f['message'], 'category': f['category']})

        conn.commit()
        if learned_count > 0:
            console.print(f"[bold green][GÊNESE] {learned_count} nova(s) solução(ões) integrada(s).[/bold green]")
    finally:
        if conn: conn.close()

def _get_template_for_message(message: str) -> Tuple[str, str, str]:
    """
    Mapeia mensagens de erro para padrões de templates.
    MPoT-7: Retorna tupla de strings vazias em vez de None para consistência.
    """
    if not message:
        return ("", "", "")

    rules = [
        (r"'(.+?)' imported but unused", "'<MODULE>' imported but unused", "FIX_UNUSED_IMPORT", "DEADCODE"),
        (r"redefinition of unused '(.+?)' from line \d+", "redefinition of unused '<VAR>' from line <LINE>", "REMOVE_LINE", "DEADCODE"),
        (r"f-string is missing placeholders", "f-string is missing placeholders", "REMOVE_F_PREFIX", "STYLE"),
        (r"undefined name '(.+?)'", "undefined name '<VAR>'", "ADD_IMPORT_OR_DEFINE", "RUNTIME-RISK"),
        (r"Uso de 'except:' genérico", "Uso de 'except:' genérico detectado", "FIX_BARE_EXCEPT", "SECURITY")
    ]
    
    for regex, pattern, template, category in rules:
        if re.search(regex, message):
            return (pattern, template, category)
            
    return ("", "", "") # Retorno consistente

def _abstract_and_learn_template(cursor: sqlite3.Cursor, concrete_finding: Dict[str, Any]) -> bool:
    """Extrai e persiste padrões abstratos de solução no banco de dados."""
    if cursor is None:
        raise ValueError("Cursor do banco de dados é obrigatório.")

    pattern, template, category = _get_template_for_message(concrete_finding.get('message', ''))
    
    if not pattern: # Se o retorno for a tupla vazia
        return False

    cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (pattern,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", 
                       (existing['confidence'] + 1, existing['id']))
    else:
        cursor.execute(
            "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
            (pattern, template, category, datetime.now(timezone.utc).isoformat())
        )
    return True

@click.command('save')
@click.argument('message', required=False)
@click.option('--archives', '-a', help="Lista arquivos de um commit.")
@click.option('--remove-commit', '-rc', help="Apaga o último commit.")
@click.option('--force', is_flag=True, help="Força o commit ignorando erros de qualidade.")
@click.pass_context
def save(ctx, message, archives, remove_commit, force):
    """Executa commit seguro com aprendizado automatizado."""
    console = Console()
    project_path = os.getcwd()
    
    # MPoT-5: Inicialização explícita de estado para evitar NameError
# [DOX-UNUSED]     fix_applied = False 

    # --- A. OPERAÇÕES DE HISTÓRICO (OSIRIS) ---
    if remove_commit or archives:
        from .git_systems.git_archivist import GitArchivist
        archivist = GitArchivist(project_path)
        if remove_commit:
            if click.confirm(f"{Fore.RED}⚠️ APAGAR commit {remove_commit}?"):
                success, err = archivist.delete_commit(remove_commit)
                click.echo(Fore.GREEN + "✔ OK" if success else Fore.RED + f"✘ {err}")
            return
        if archives:
            success, data = archivist.list_commit_assets(archives)
            if success:
                for item in sorted(data, key=lambda x: x['size'], reverse=True):
                    click.echo(f"  {item['size']:>7.1f} KB │ {item['path']}")
            return

    if not message:
        click.echo(Fore.RED + "Erro: Mensagem obrigatória para save."); return

    with ExecutionLogger('save', project_path, ctx.params):
        _run_git_command(['add', '.'])
        git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True)
        
        # --- REFRESH DE SINCRO (Ação de Zeus) ---
        # Usamos a função auxiliar que já filtra arquivos DELETADOS (AMR)
        staged_prod = _get_staged_python_files(git_root)
        
        from ..dnm import DNM
        dnm = DNM(project_path)
        
        # Filtro de Leaks (Anúbis)
        leaks = [os.path.relpath(f, git_root) for f in staged_prod if dnm.is_ignored(f)]
        
        if leaks and not force:
            console.print("\n[bold yellow]⚖  [ANÚBIS] Vazamento de Infra detectado![/bold yellow]")
            for l in leaks: console.print(f"   {Fore.RED}✘ {l}")
            if click.confirm("\nPurificar stage automaticamente?"):
                for l in leaks: 
                    subprocess.run(['git', 'rm', '--cached', os.path.join(git_root, l)], capture_output=True)
                # RE-SINCRONIZA: Atualiza a lista após a limpeza
                staged_prod = _get_staged_python_files(git_root)

        # --- TRIBUNAL DE MA'AT ---
        if staged_prod and not force:
            console.print("   > [MA'AT] Julgando integridade da produção...")
            # Check Logic agora só vê o que existe no disco
            results = run_check_logic(path='.', fix=False, fast=True, target_files=staged_prod)
            
            from .audit_systems.maat_engine import MaatEngine
            maat = MaatEngine(project_path)
            is_stable, maat_findings = maat.run_full_audit(staged_prod)
            
            blocking = [f for f in results.get('findings', []) if f['severity'] in ['CRITICAL', 'ERROR']]
            if blocking or not is_stable:
                console.print("\n[bold red]🛑 BLOQUEIO: Regressões detectadas![/bold red]")
                # FEEDBACK DETALHADO (Solicitado pelo Chefe)
                if blocking:
                    _present_results('text', {'summary': results['summary'], 'findings': blocking})
                
                if maat_findings:
                    console.print(f"\n[bold yellow]⚖  ACHADOS DE MA'AT:[/bold yellow]")
                    for mf in maat_findings:
                        console.print(f"   [red]✘[/red] {mf['message']} ({os.path.basename(mf['file'])})")
                sys.exit(1)

        # --- D. SEPULTAMENTO (COMMIT) ---
        if _run_git_command(['commit', '-m', message]):
            console.print("[bold green]✔ Alfa 80.1: Conhecimento sepultado com sucesso.[/bold green]")
        new_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        
        if new_hash:
            _learn_solutions_from_commit(new_hash, project_path)

        console.print("[bold green]\n[OK] Alfa 71.10: Commit finalizado e Gênese atualizada.[/bold green]")
        
def _verify_succession_integrity():
    """Garante que as tecnologias citadas no save v94 existam de fato."""
# [DOX-UNUSED]     from ..tools.vulcan.bridge import vulcan_bridge
    # 1. Verifica se o Vulcan está operando no Core
    if not any(f.endswith('.pyd') for f in os.listdir('.doxoade/vulcan/bin')):
        return False, "Regressão detectada: Binários Vulcan ausentes."
    
    # 2. Verifica se o Tribunal de Ma'at está no ar
    if not os.path.exists('doxoade/commands/audit_systems/maat_engine.py'):
        return False, "Regressão detectada: Ma'at Engine perdido."
        
    return True, "Integridade de Sucessão confirmada."