# -*- coding: utf-8 -*-
"""
Módulo de Salvamento Seguro e Aprendizado (Gênese V2).
Responsável por garantir que correções de bugs sejam transformadas em 
conhecimento persistente no banco de dados.
"""

import sys
import sqlite3
import re
import os
import click
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Set
from rich.console import Console
from colorama import Fore 

from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger, 
    _run_git_command, 
    _present_results
)
from .check import run_check_logic

__version__ = "63.3 Alfa (Gold Standard)"

def _get_staged_python_files(git_root: str) -> List[str]:
    """Retorna uma lista de caminhos absolutos de arquivos .py no staging area."""
    staged_files_str = _run_git_command(
        ['diff', '--name-only', '--cached', '--diff-filter=AMR', '--', '*.py'], 
        capture_output=True
    )
    if not staged_files_str:
        return []
    return [os.path.join(git_root, f.strip()) for f in staged_files_str.splitlines()]

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
@click.pass_context
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit ignorando erros de qualidade.")
def save(ctx, message: str, force: bool):
    """Executa commit seguro com aprendizado automatizado."""
    console = Console()
    project_path = os.getcwd()
    
    # MPoT-5: Inicialização explícita de estado para evitar NameError
    fix_applied = False 
    
    with ExecutionLogger('save', project_path, ctx.params):
        console.print("[bold cyan]--- [SAVE] Salvamento Seguro e Inteligente ---[/bold cyan]")

        # 1. Preparação Git
        _run_git_command(['add', '.'])
        status = (_run_git_command(['status', '--porcelain'], capture_output=True) or "").strip()
        if not status:
            console.print("[yellow][AVISO] Nada para salvar: working tree limpa.[/yellow]")
            return

        # 2. Portão de Qualidade
        git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True)
        staged_py = _get_staged_python_files(git_root)
        
        if staged_py:
            console.print(f"   > Auditando {len(staged_py)} arquivo(s) Python...")
            
            # Executa o check (Ouro v38.8)
            results = run_check_logic(
                path='.', fix=False, fast=True, no_cache=True, 
                clones=False, continue_on_error=True,
                target_files=staged_py
            )
            
            # Protocolo Lázaro Preventivo: Se tivéssemos aplicado fix, 
            # verificaríamos 'fix_applied' aqui.
            if fix_applied:
                # [Lógica futura para auto-reversão de sintaxe]
                pass

            summary = results.get('summary', {})
            # O commit só é bloqueado por erros reais (Code Breaking)
            blocking = [f for f in results.get('findings', []) if f['severity'] in ['CRITICAL', 'ERROR']]
            
            if blocking and not force:
                console.print("[bold red]\n[ERRO] Bloqueio de Qualidade: Falhas críticas detectadas.[/bold red]")
                results['findings'] = blocking 
                _present_results('text', results)
                console.print(Fore.YELLOW + "\n(Use --force se desejar ignorar estes erros)")
                sys.exit(1)
            elif results.get('findings'):
                 console.print(Fore.GREEN + f"[OK] {len(results['findings'])} avisos detectados (não bloqueantes).")

        # 3. Finalização do Commit
        _run_git_command(['commit', '-m', message])
        new_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        
        if new_hash:
            _learn_solutions_from_commit(new_hash, project_path)

        console.print("[bold green]\n[OK] Alfa 71.10: Commit finalizado e Gênese atualizada.[/bold green]")