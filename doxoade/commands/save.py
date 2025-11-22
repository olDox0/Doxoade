# doxoade/commands/save.py
# Versão Gênese V2 - Simplificado: foca apenas em aprender soluções
import sys
import sqlite3
import re
import os
import click
from datetime import datetime, timezone
from colorama import Fore, Style
from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger, 
    _run_git_command, 
    _present_results
)
from .check import run_check_logic

def _get_staged_python_files(git_root):
    """Retorna uma lista de caminhos absolutos de arquivos .py no staging area."""
    staged_files_str = _run_git_command(
        ['diff', '--name-only', '--cached', '--diff-filter=AMR', '--', '*.py'], 
        capture_output=True
    )
    if not staged_files_str:
        return []
    return [os.path.join(git_root, f.strip()) for f in staged_files_str.splitlines()]

def _learn_solutions_from_commit(new_commit_hash, logger, project_path):
    """
    (Gênese V2) Aprende soluções a partir dos incidentes que foram resolvidos.
    O check já gerencia os incidentes - aqui apenas consultamos quais foram resolvidos
    e aprendemos as soluções.
    """
    click.echo(Fore.CYAN + "\n--- [LEARN] Buscando soluções para aprender... ---")
    
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # Obtém arquivos modificados neste commit
        modified_files_str = _run_git_command(
            ['diff-tree', '--no-commit-id', '--name-only', '-r', new_commit_hash],
            capture_output=True, silent_fail=True
        ) or ""
        modified_files = set(f.strip().replace('\\', '/') for f in modified_files_str.splitlines())
        
        if not modified_files:
            click.echo(Fore.WHITE + "   > Nenhum arquivo modificado neste commit.")
            return
        
        # Busca incidentes que EXISTIAM para os arquivos modificados
        # mas que agora foram resolvidos (o check já os removeu da tabela open_incidents)
        # Precisamos consultar o histórico de eventos/findings para saber o que foi corrigido
        
        # Abordagem alternativa: buscar na tabela solutions os hashes que ainda não têm solução
        # mas cujos arquivos foram modificados
        
        # Por enquanto, vamos usar uma abordagem mais simples:
        # Se o commit passou sem erros nos arquivos modificados, assume que correções foram feitas
        
        learned_solutions = 0
        learned_templates = 0
        
        # Busca findings recentes (últimas 24h) para os arquivos modificados que não têm solução ainda
        cursor.execute("""
            SELECT DISTINCT f.finding_hash, f.file, f.line, f.message, f.category
            FROM findings f
            JOIN events e ON f.event_id = e.id
            WHERE e.project_path = ?
            AND f.severity IN ('CRITICAL', 'ERROR')
            AND datetime(e.timestamp) > datetime('now', '-1 day')
            AND f.finding_hash NOT IN (SELECT finding_hash FROM solutions WHERE project_path = ?)
        """, (project_path, project_path))
        
        recent_findings = cursor.fetchall()
        
        for finding in recent_findings:
            file_path = finding['file']
            if not file_path:
                continue
                
            # Normaliza o caminho
            normalized_path = file_path.replace('\\', '/')
            
            # Verifica se este arquivo foi modificado no commit
            if normalized_path not in modified_files:
                continue
            
            # Obtém o conteúdo corrigido
            corrected_content = _run_git_command(
                ['show', f"{new_commit_hash}:{normalized_path}"],
                capture_output=True, silent_fail=True
            )
            
            if not corrected_content:
                continue
            
            # Salva a solução
            cursor.execute(
                """INSERT OR REPLACE INTO solutions 
                   (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (finding['finding_hash'], 
                 corrected_content, 
                 new_commit_hash, 
                 project_path, 
                 datetime.now(timezone.utc).isoformat(), 
                 file_path, 
                 finding['message'], 
                 finding['line'])
            )
            learned_solutions += 1
            click.echo(Fore.GREEN + f"   > Solução aprendida: {finding['message'][:60]}...")

            # Tenta aprender template
            incident_data = {
                'message': finding['message'],
                'category': finding['category'] or 'UNCATEGORIZED'
            }
            if _abstract_and_learn_template(cursor, incident_data):
                learned_templates += 1

        conn.commit()
        
        if learned_solutions > 0:
            click.echo(Fore.GREEN + f"[OK] {learned_solutions} solução(ões) aprendida(s).")
        if learned_templates > 0:
            click.echo(Fore.GREEN + f"[GÊNESE] {learned_templates} template(s) aprendido(s)/reforçado(s).")
        if learned_solutions == 0:
            click.echo(Fore.WHITE + "   > Nenhuma solução nova para aprender.")

    except Exception as e:
        conn.rollback()
        logger.add_finding("ERROR", "Falha ao aprender soluções.", details=str(e))
        import traceback
        click.echo(Fore.RED + f"   > [DEBUG] {traceback.format_exc()}")
    finally:
        if conn: conn.close()

def _abstract_and_learn_template(cursor, concrete_finding):
    """
    (Gênese V2 - Expandido) Analisa um 'finding' e tenta criar/atualizar um template de solução.
    
    Templates suportados:
    - DEADCODE: imports não usados, redefinições
    - STYLE: f-strings sem placeholders, variáveis não usadas
    - RUNTIME-RISK: nomes indefinidos
    """
    message = concrete_finding.get('message', '')
    category = concrete_finding.get('category', '')
    
    # Inferência de categoria se não fornecida
    if not category:
        if 'imported but unused' in message or 'redefinition of unused' in message:
            category = 'DEADCODE'
        elif 'undefined name' in message:
            category = 'RUNTIME-RISK'
        elif 'f-string' in message or 'assigned to but never used' in message:
            category = 'STYLE'
        else:
            category = 'UNCATEGORIZED'
    
    problem_pattern = None
    solution_template = None
    
    # REGRAS DE ABSTRAÇÃO - DEADCODE
    
    # Regra 1: Import não usado
    # Exemplo: "'os' imported but unused"
    if re.match(r"'(.+?)' imported but unused", message):
        problem_pattern = "'<MODULE>' imported but unused"
        solution_template = "REMOVE_LINE"
    
    # Regra 2: Redefinição de variável/import não usado
    # Exemplo: "redefinition of unused 'conn' from line 42"
    elif re.match(r"redefinition of unused '(.+?)' from line \d+", message):
        problem_pattern = "redefinition of unused '<VAR>' from line <LINE>"
        solution_template = "REMOVE_LINE"
    
    # REGRAS DE ABSTRAÇÃO - STYLE
    
    # Regra 3: f-string sem placeholders
    # Exemplo: "f-string is missing placeholders"
    elif message == "f-string is missing placeholders":
        problem_pattern = "f-string is missing placeholders"
        solution_template = "REMOVE_F_PREFIX"
    
    # Regra 4: Variável local atribuída mas nunca usada
    # Exemplo: "local variable 'e' is assigned to but never used"
    elif re.match(r"local variable '(.+?)' is assigned to but never used", message):
        problem_pattern = "local variable '<VAR>' is assigned to but never used"
        solution_template = "REPLACE_WITH_UNDERSCORE"
    
    # REGRAS DE ABSTRAÇÃO - RUNTIME-RISK

    # Regra 5: Nome indefinido
    # Exemplo: "undefined name 'foo'"
    elif re.match(r"undefined name '(.+?)'", message):
        problem_pattern = "undefined name '<VAR>'"
        solution_template = "ADD_IMPORT_OR_DEFINE"  # Sugestão: precisa de ação manual
    
    # REGRAS DE ABSTRAÇÃO - SYNTAX (informativo)

    # Regra 6: Erro de indentação
    elif 'unexpected indent' in message.lower() or 'expected an indented block' in message.lower():
        problem_pattern = "indentation error"
        solution_template = "FIX_INDENTATION"
    
    if not problem_pattern:
        return False

    # Verifica se o template já existe
    cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (problem_pattern,))
    existing = cursor.fetchone()

    if existing:
        new_confidence = existing['confidence'] + 1
        cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_confidence, existing['id']))
        click.echo(Fore.CYAN + f"   > [GÊNESE] Confiança de '{problem_pattern}' → {new_confidence}")
    else:
        cursor.execute(
            "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
            (problem_pattern, solution_template, category, datetime.now(timezone.utc).isoformat())
        )
        click.echo(Fore.CYAN + f"   > [GÊNESE] Novo template: '{problem_pattern}' ({solution_template})")
    
    return True

@click.command('save')
@click.pass_context
@click.argument('message')
@click.option('--force', is_flag=True, help="Força o commit mesmo se o 'check' encontrar erros.")
def save(ctx, message, force):
    """Executa um 'commit seguro', verificando qualidade e aprendendo com correções."""
    project_path = os.getcwd()
    with ExecutionLogger('save', project_path, ctx.params) as logger:
        click.echo(Fore.CYAN + "--- [SAVE] Iniciando processo de salvamento seguro ---")

        # Passo 1: Preparar arquivos
        click.echo(Fore.YELLOW + "\nPasso 1: Preparando arquivos (git add .)...")
        _run_git_command(['add', '.'])
        click.echo(Fore.GREEN + "[OK] Arquivos preparados.")
        
        status_output = _run_git_command(['status', '--porcelain'], capture_output=True) or ""
        if not status_output.strip():
            click.echo(Fore.YELLOW + "[AVISO] Nenhuma alteração para commitar.")
            return

        # Passo 2: Verificação de qualidade (o check agora gerencia incidentes automaticamente)
        click.echo(Fore.YELLOW + "\nPasso 2: Verificando qualidade...")
        
        git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True)
        files_to_check = _get_staged_python_files(git_root)
        
        if not files_to_check:
            click.echo(Fore.GREEN + "[OK] Nenhum arquivo Python modificado.")
            check_results = {'summary': {}, 'findings': []}
        else:
            click.echo(f"   > Analisando {len(files_to_check)} arquivo(s)...")
            check_results = run_check_logic(
                '.', [], False, False, 
                no_cache=True, 
                target_files=files_to_check
            )
        
        summary = check_results.get('summary', {})
        has_errors = summary.get('critical', 0) > 0 or summary.get('errors', 0) > 0

        if has_errors and not force:
            click.echo(Fore.RED + "\n[ERRO] Erros encontrados. Commit abortado.")
            click.echo(Fore.WHITE + "   Use --force para forçar o commit, ou corrija os erros.")
            _present_results('text', check_results)
            _run_git_command(['reset'])
            sys.exit(1)
        
        # Passo 3: Criar commit
        click.echo(Fore.YELLOW + "\nPasso 3: Criando commit...")
        _run_git_command(['commit', '-m', message])
        
        new_commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True)
        
        # Passo 4: Aprender soluções
        if new_commit_hash:
            _learn_solutions_from_commit(new_commit_hash, logger, project_path)

        click.echo(Fore.GREEN + Style.BRIGHT + "\n[SAVE] Alterações salvas com sucesso!")