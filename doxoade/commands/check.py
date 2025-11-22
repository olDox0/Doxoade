# doxoade/commands/check.py
import sys
import subprocess
import sqlite3 
import shutil
import re
import os
import json
import hashlib
import click
import ast
from pyflakes import api as pyflakes_api
from pathlib import Path
from io import StringIO
from importlib import resources
from colorama import Fore

# Linha corrigida, que não causa o ciclo
from .._version import __version__ as DOXOADE_VERSION

#from datetime import datetime, timezone
from ..database import get_db_connection
from ..shared_tools import (
    ExecutionLogger, 
    _present_results,
    _get_code_snippet,
    _get_venv_python_executable,
    _get_project_config,
    collect_files_to_analyze,
    analyze_file_structure,
 #   _run_git_command,
    _update_open_incidents
)

def _get_probe_path(probe_name):
    """Encontra o caminho para um arquivo de sonda de forma segura."""
    try:
        # Python 3.9+
        with resources.path('doxoade.probes', probe_name) as probe_path:
            return str(probe_path)
    except (AttributeError, ModuleNotFoundError):
        # Fallback para Python < 3.9
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

def _run_syntax_probe(file_path, python_executable, debug=False):
    findings = []
    # ALTERADO: Chama o arquivo da sonda em vez da string
    probe_path = _get_probe_path('syntax_probe.py')
    syntax_cmd = [python_executable, probe_path, file_path]
    try:
        result = subprocess.run(syntax_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        # ... (o resto da função continua igual) ...
        if debug:
            click.echo(Fore.CYAN + "\n--- [DEBUG-SYNTAX PROBE] ---")
            click.echo(f"  > Alvo: {file_path}")
            click.echo(f"  > RC Sonda Sintaxe: {result.returncode}")
            click.echo(f"  > STDERR Sintaxe:\n---\n{result.stderr.strip()}\n---")
            click.echo("--- [FIM DEBUG-SYNTAX PROBE] ---\n")

        if result.returncode != 0:
            line_match = re.search(r':(\d+):', result.stderr)
            line_num = int(line_match.group(1)) if line_match else 1
            findings.append({'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Erro de sintaxe impede a análise: {result.stderr.strip()}", 'file': file_path, 'line': line_num})
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Falha catastrófica ao invocar a sonda de sintaxe: {e}", 'file': file_path, 'line': line_num})
    return findings

def _run_pyflakes_probe(file_path, python_executable, debug=False):
    findings = []
    # ALTERADO: Chama o arquivo da sonda em vez da string
    probe_path = _get_probe_path('static_probe.py')
    pyflakes_cmd = [python_executable, probe_path, file_path]
    try:
        result = subprocess.run(pyflakes_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        # ... (o resto da função continua igual) ...
        if debug:
            click.echo(Fore.CYAN + "\n--- [DEBUG-CHECK] ---")
            click.echo(f"  > Alvo: {file_path}")
            click.echo(f"  > RC Sonda: {result.returncode}")
            click.echo(f"  > STDOUT Sonda:\n---\n{result.stdout.strip()}\n---")
            click.echo(f"  > STDERR Sonda:\n---\n{result.stderr.strip()}\n---")
            click.echo("--- [FIM DEBUG] ---\n")

        if result.stderr:
            if 'invalid syntax' in result.stderr.lower() or 'indentation' in result.stderr.lower():
                line_match = re.search(r':(\d+):', result.stderr)
                line_num = int(line_match.group(1)) if line_match else 1
                findings.append({'severity': 'CRITICAL', 'message': f"Erro de sintaxe impede a análise: {result.stderr.strip()}", 'file': file_path, 'line': line_num})
            else:
                findings.append({'severity': 'WARNING', 'message': "Sonda de análise estática reportou um erro.", 'file': file_path, 'line': 1, 'details': result.stderr})

        for line_error in result.stdout.strip().splitlines():
            match = re.match(r'(.+?):(\d+):(\d+):\s(.+)', line_error)
            if match:
                _, line_num, _, message_text = match.groups()
    
                # --- LÓGICA DE CLASSIFICAÇÃO APRIMORADA ---
                if 'imported but unused' in message_text or 'redefinition' in message_text:
                    severity = 'ERROR'
                    category = 'DEADCODE'
                elif 'undefined name' in message_text:
                    severity = 'CRITICAL'
                    category = 'RUNTIME-RISK'
                # Adicione mais regras aqui se necessário, como para f-strings
                elif "f-string is missing placeholders" in message_text:
                    severity = 'WARNING'
                    category = 'STYLE'
                else:
                    severity = 'WARNING'
                    category = 'STYLE' # Padrão para outros avisos do Pyflakes
    
                findings.append({
                    'severity': severity,
                    'category': category,
                    'message': message_text,
                    'file': file_path,
                    'line': int(line_num)
                })
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'message': f"Falha catastrófica ao invocar a sonda Pyflakes: {e}", 'file': file_path})
    return findings

def _run_import_probe(all_imports, venv_python, logger, search_path):
    unique_module_names = sorted(list({imp['module'] for imp in all_imports}))
    if not unique_module_names: return []
    try:
        # ALTERADO: Chama o arquivo da sonda em vez da string
        probe_path = _get_probe_path('import_probe.py')
        process = subprocess.run([venv_python, probe_path], input=json.dumps(unique_module_names), capture_output=True, text=True, check=True, encoding='utf-8')
        missing_from_venv = set(json.loads(process.stdout))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.add_finding('CRITICAL', "A Sonda de Ambiente falhou.", details=str(e))
        return []
    # ... (o resto da função continua igual) ...
    if not missing_from_venv: return []
    truly_missing_modules = set()
    for module_name in missing_from_venv:
        potential_file = os.path.join(search_path, f"{module_name}.py")
        potential_package = os.path.join(search_path, module_name)
        if not os.path.exists(potential_file) and not os.path.isdir(potential_package):
            truly_missing_modules.add(module_name)
    if not truly_missing_modules: return []
    import_findings = []
    IGNORE_MODULES = {'setuptools', 'kivy', 'ia_core'}
    for imp in all_imports:
        if imp['module'] in truly_missing_modules and imp['module'] not in IGNORE_MODULES:
            import_findings.append({'severity': 'CRITICAL', 'category': 'DEPENDENCY', 'message': f"Import não resolvido: Módulo '{imp['module']}' não foi encontrado.", 'file': imp['file'], 'line': imp['line'], 'snippet': _get_code_snippet(imp['file'], imp['line'])})
    return import_findings

def _extract_imports(file_path):
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        if content.strip():
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: imports.append({'module': alias.name.split('.')[0], 'line': node.lineno, 'file': file_path})
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module: imports.append({'module': node.module.split('.')[0], 'line': node.lineno, 'file': file_path})
    except (SyntaxError, IOError):
        pass
    return imports
    
def _analyze_single_file_statically(file_path, python_executable, debug=False):
    syntax_findings = _run_syntax_probe(file_path, python_executable, debug)
    if syntax_findings:
        return syntax_findings, []
    pyflakes_findings = _run_pyflakes_probe(file_path, python_executable, debug)
    imports = _extract_imports(file_path)
    return pyflakes_findings, imports
    
def _fix_unused_imports(file_path, logger):
    """Comenta linhas com imports não utilizados em um arquivo."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        output_stream = StringIO()
        reporter = pyflakes_api.modReporter.Reporter(output_stream, output_stream)
        pyflakes_api.check(content, file_path, reporter)
        
        unused_import_lines = {
            int(line.split(':', 2)[1]) for line in output_stream.getvalue().strip().splitlines()
            if "' is unused" in line and 'redefinition' not in line
        }

        if not unused_import_lines: return 0

        shutil.copy(file_path, f"{file_path}.bak")
        lines = content.splitlines()
        fix_count = 0
        new_lines = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if line_num in unused_import_lines and not line.strip().startswith("#dox-fix#"):
                new_lines.append(f"#dox-fix# {line}")
                fix_count += 1
            else:
                new_lines.append(line)
        
        if fix_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(new_lines))
        
        return fix_count
    except Exception as e:
        logger.add_finding('WARNING', f"Não foi possível processar ou corrigir o arquivo {file_path}", details=str(e))
        return 0

# =============================================================================
# ETAPAS DO PIPELINE DE ANÁLISE
# =============================================================================

def step_collect_files(state, config, cmd_line_ignore):
    """Etapa 1: Coleta os arquivos Python a serem analisados."""
    state['files_to_process'] = collect_files_to_analyze(config, cmd_line_ignore) # <-- USE A FUNÇÃO IMPORTADA
    return state

def step_run_syntax_probes(state, python_executable, debug):
    """Etapa 2: Executa a sonda de sintaxe. Remove arquivos com erros fatais das próximas etapas."""
    files_with_syntax_errors = set()
    for file_path in state['files_to_process']:
        findings = _run_syntax_probe(file_path, python_executable, debug)
        if findings:
            state['raw_findings'].extend(findings)
            files_with_syntax_errors.add(file_path)
    
    # Lógica "Fail-Fast": arquivos quebrados não seguem no pipeline
    state['files_to_process'] = [f for f in state['files_to_process'] if f not in files_with_syntax_errors]
    return state

def step_run_pyflakes_probes(state, python_executable, debug):
    """Etapa 3: Executa a sonda de análise estática (Pyflakes) nos arquivos restantes."""
    for file_path in state['files_to_process']:
        findings = _run_pyflakes_probe(file_path, python_executable, debug)
        state['raw_findings'].extend(findings)
    return state

def step_extract_imports(state):
    """Etapa 4: Extrai todas as declarações de import dos arquivos válidos."""
    all_imports = []
    for file_path in state['files_to_process']:
        imports = _extract_imports(file_path)
        all_imports.extend(imports)
    state['all_imports'] = all_imports
    return state

def step_run_import_probe(state, python_executable, logger, config):
    """Etapa 5: Executa a sonda de resolução de imports."""
    if state['all_imports']:
        findings = _run_import_probe(state['all_imports'], python_executable, logger, config.get('search_path'))
        state['raw_findings'].extend(findings)
    return state

def step_run_structure_analysis(state):
    """Etapa 6 (Opcional): Executa a análise estrutural de funções e riscos."""
    for file_path in state['files_to_process']:
        structure_analysis = analyze_file_structure(file_path)
        rel_file_path = os.path.relpath(file_path, state.get('root_path', '.'))
        state['file_reports'][rel_file_path] = {
            'structure_analysis': structure_analysis
        }
    return state

# =============================================================================
# FUNÇÕES AUXILIARES DE CACHE
# =============================================================================

CACHE_DIR = Path(".doxoade_cache")
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"

def _get_file_hash(file_path):
    """Calcula o hash SHA256 do conteúdo de um arquivo."""
    h = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except IOError:
        return None

def _load_cache():
    """Carrega o cache se ele for válido para a versão atual do doxoade."""
    if not CHECK_CACHE_FILE.is_file():
        return {}
    try:
        with open(CHECK_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # Invalidação de Cache: A versão do doxoade mudou?
        if cache_data.get("__doxoade_version__") != DOXOADE_VERSION:
            click.echo(Fore.YELLOW + "A versão do doxoade mudou. Invalidando o cache de análise.")
            return {}  # Cache é inválido
        
        return cache_data
    except (json.JSONDecodeError, IOError):
        return {}

def _save_cache(cache_data):
    """Salva o dicionário de cache em um arquivo JSON."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_data["__doxoade_version__"] = DOXOADE_VERSION  # Adiciona a versão ao salvar
        with open(CHECK_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
    except IOError:
        click.echo(Fore.YELLOW + "\nAviso: Não foi possível escrever no arquivo de cache.")


# =============================================================================
# O ORQUESTRADOR DO PIPELINE
# =============================================================================

def _enrich_findings_with_solutions(findings):
    """
    (Gênese V2 - Expandido) Consulta o DB por soluções exatas E aplica templates genéricos.
    
    Templates suportados:
    - REMOVE_LINE: Remove a linha problemática
    - REMOVE_F_PREFIX: Remove o 'f' de f-strings sem placeholders
    - REPLACE_WITH_UNDERSCORE: Substitui variável por '_'
    - ADD_IMPORT_OR_DEFINE: Apenas sugere (ação manual necessária)
    - FIX_INDENTATION: Apenas sugere (ação manual necessária)
    """
    if not findings: return
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM solution_templates ORDER BY confidence DESC")
        templates = cursor.fetchall()

        for finding in findings:
            # 1. Tenta encontrar uma solução exata primeiro
            finding_hash = finding.get('hash')
            if finding_hash:
                cursor.execute("SELECT stable_content, error_line FROM solutions WHERE finding_hash = ? LIMIT 1", (finding_hash,))
                exact_solution = cursor.fetchone()
                if exact_solution:
                    finding['suggestion_content'] = exact_solution['stable_content']
                    finding['suggestion_line'] = exact_solution['error_line']
                    finding['suggestion_source'] = "EXACT"
                    continue

            # 2. Tenta aplicar um template
            message = finding.get('message', '')
            category = finding.get('category', '')
            
            for template in templates:
                if template['category'] != category:
                    continue

                # Constrói regex a partir do pattern
                pattern_str = template['problem_pattern']
                pattern_with_markers = (pattern_str
                    .replace('<MODULE>', '___MODULE___')
                    .replace('<VAR>', '___VAR___')
                    .replace('<LINE>', '___LINE___'))
                escaped_pattern = re.escape(pattern_with_markers)
                pattern_regex_str = (escaped_pattern
                    .replace('___MODULE___', '(.+?)')
                    .replace('___VAR___', '(.+?)')
                    .replace('___LINE___', r'(\d+)'))
                
                match = re.fullmatch(pattern_regex_str, message)
                if not match:
                    continue
                
                # Aplica a solução baseada no tipo de template
                solution_type = template['solution_template']
                file_path = finding.get('file')
                line_num = finding.get('line')
                
                if not file_path or not line_num:
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    if line_num < 1 or line_num > len(lines):
                        continue
                    
                    original_line = lines[line_num - 1]
                    
                    # =========================================================
                    # APLICADORES DE TEMPLATE
                    # =========================================================
                    
                    if solution_type == "REMOVE_LINE":
                        # Remove a linha problemática
                        new_lines = lines[:line_num-1] + lines[line_num:]
                        finding['suggestion_content'] = "".join(new_lines)
                        finding['suggestion_line'] = line_num
                        finding['suggestion_source'] = "TEMPLATE"
                        finding['suggestion_action'] = "Remover linha"
                        break
                    
                    elif solution_type == "REMOVE_F_PREFIX":
                        # Remove o 'f' de f-strings
                        # Encontra f" ou f' e remove o f
                        new_line = re.sub(r'\bf(["\'])', r'\1', original_line)
                        if new_line != original_line:
                            new_lines = lines[:line_num-1] + [new_line] + lines[line_num:]
                            finding['suggestion_content'] = "".join(new_lines)
                            finding['suggestion_line'] = line_num
                            finding['suggestion_source'] = "TEMPLATE"
                            finding['suggestion_action'] = "Remover prefixo 'f'"
                            break
                    
                    elif solution_type == "REPLACE_WITH_UNDERSCORE":
                        # Substitui "as var:" por "as _:" em except
                        # Ou "var =" por "_ =" em atribuições
                        var_name = match.group(1) if match.groups() else None
                        if var_name:
                            # Tenta substituir em padrão "as var"
                            new_line = re.sub(rf'\bas\s+{re.escape(var_name)}\b', 'as _', original_line)
                            if new_line == original_line:
                                # Tenta substituir atribuição simples
                                new_line = re.sub(rf'^(\s*){re.escape(var_name)}\s*=', r'\1_ =', original_line)
                            
                            if new_line != original_line:
                                new_lines = lines[:line_num-1] + [new_line] + lines[line_num:]
                                finding['suggestion_content'] = "".join(new_lines)
                                finding['suggestion_line'] = line_num
                                finding['suggestion_source'] = "TEMPLATE"
                                finding['suggestion_action'] = f"Substituir '{var_name}' por '_'"
                                break
                    
                    elif solution_type in ("ADD_IMPORT_OR_DEFINE", "FIX_INDENTATION"):
                        # Estes requerem ação manual - apenas marca como sugestão
                        finding['suggestion_source'] = "TEMPLATE_MANUAL"
                        finding['suggestion_action'] = {
                            "ADD_IMPORT_OR_DEFINE": "Adicionar import ou definir a variável",
                            "FIX_INDENTATION": "Corrigir indentação manualmente"
                        }.get(solution_type, "Correção manual necessária")
                        break
                        
                except (IOError, IndexError, TypeError):
                    continue
    finally:
        conn.close()

def _manage_incidents(findings, project_path):
    """
    (Gênese V3) Gerencia incidentes E aprende soluções automaticamente:
    - Adiciona novos incidentes encontrados
    - Quando um incidente é resolvido, APRENDE a solução antes de removê-lo
    - Retorna estatísticas de mudanças
    """
    from ..database import get_db_connection
    from ..shared_tools import _run_git_command
    from datetime import datetime, timezone
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    stats = {'added': 0, 'resolved': 0, 'learned': 0, 'templates': 0}
    
    try:
        # 1. Obtém os incidentes atuais do banco para este projeto
        cursor.execute("SELECT * FROM open_incidents WHERE project_path = ?", (project_path,))
        existing_incidents = {row['finding_hash']: dict(row) for row in cursor.fetchall()}
        
        # 2. Obtém os hashes dos findings atuais
        current_finding_hashes = {f.get('hash') for f in findings if f.get('hash')}
        
        # 3. Identifica incidentes resolvidos (existiam antes, não existem mais)
        resolved_hashes = set(existing_incidents.keys()) - current_finding_hashes
        
        # 4. Identifica novos incidentes
        new_hashes = current_finding_hashes - set(existing_incidents.keys())
        
        # 5. APRENDE com os incidentes resolvidos ANTES de removê-los
        for resolved_hash in resolved_hashes:
            incident = existing_incidents[resolved_hash]
            file_path = incident.get('file_path', '')
            
            if not file_path:
                continue
            
            # Lê o conteúdo atual do arquivo (que agora está corrigido)
            abs_file_path = os.path.join(project_path, file_path)
            try:
                with open(abs_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    corrected_content = f.read()
            except IOError:
                continue
            
            # Salva a solução no banco
            cursor.execute(
                """INSERT OR REPLACE INTO solutions 
                   (finding_hash, stable_content, commit_hash, project_path, timestamp, file_path, message, error_line) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (resolved_hash,
                 corrected_content,
                 "local",  # Não é de um commit, é local
                 project_path,
                 datetime.now(timezone.utc).isoformat(),
                 file_path,
                 incident.get('message', ''),
                 incident.get('line'))
            )
            stats['learned'] += 1
            
            # Tenta aprender template
            if _learn_template_from_incident(cursor, incident):
                stats['templates'] += 1
            
            # Remove o incidente
            cursor.execute("DELETE FROM open_incidents WHERE finding_hash = ? AND project_path = ?", 
                         (resolved_hash, project_path))
            stats['resolved'] += 1
        
        # 6. Adiciona novos incidentes
        commit_hash = _run_git_command(['rev-parse', 'HEAD'], capture_output=True, silent_fail=True) or "N/A"
        
        for finding in findings:
            f_hash = finding.get('hash')
            if not f_hash or f_hash not in new_hashes:
                continue
            
            file_path = finding.get('file', '')
            if file_path:
                file_path = os.path.relpath(file_path, project_path).replace('\\', '/')
            
            category = finding.get('category') or 'UNCATEGORIZED'
            if category == 'UNCATEGORIZED':
                msg = finding.get('message', '')
                if 'imported but unused' in msg or 'redefinition of unused' in msg:
                    category = 'DEADCODE'
                elif 'undefined name' in msg:
                    category = 'RUNTIME-RISK'
                elif 'syntax' in msg.lower():
                    category = 'SYNTAX'
                elif 'f-string' in msg or 'assigned to but never used' in msg:
                    category = 'STYLE'
            
            cursor.execute("""
                INSERT OR REPLACE INTO open_incidents 
                (finding_hash, file_path, line, message, category, commit_hash, timestamp, project_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f_hash,
                file_path,
                finding.get('line'),
                finding.get('message', ''),
                category,
                commit_hash,
                datetime.now(timezone.utc).isoformat(),
                project_path
            ))
            stats['added'] += 1
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        click.echo(Fore.YELLOW + f"[AVISO] Erro ao gerenciar incidentes: {e}")
    finally:
        conn.close()
    
    return stats

def _learn_template_from_incident(cursor, incident):
    """
    (Gênese V3) Aprende um template a partir de um incidente resolvido.
    Chamado diretamente pelo check quando um incidente é resolvido.
    """
    from datetime import datetime, timezone
    
    message = incident.get('message', '')
    category = incident.get('category', '')
    
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
    
    # Regras de abstração
    if re.match(r"'(.+?)' imported but unused", message):
        problem_pattern = "'<MODULE>' imported but unused"
        solution_template = "REMOVE_LINE"
    
    elif re.match(r"redefinition of unused '(.+?)' from line \d+", message):
        problem_pattern = "redefinition of unused '<VAR>' from line <LINE>"
        solution_template = "REMOVE_LINE"
    
    elif message == "f-string is missing placeholders":
        problem_pattern = "f-string is missing placeholders"
        solution_template = "REMOVE_F_PREFIX"
    
    elif re.match(r"local variable '(.+?)' is assigned to but never used", message):
        problem_pattern = "local variable '<VAR>' is assigned to but never used"
        solution_template = "REPLACE_WITH_UNDERSCORE"
    
    elif re.match(r"undefined name '(.+?)'", message):
        problem_pattern = "undefined name '<VAR>'"
        solution_template = "ADD_IMPORT_OR_DEFINE"

    if not problem_pattern:
        return False

    cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (problem_pattern,))
    existing = cursor.fetchone()

    if existing:
        new_confidence = existing['confidence'] + 1
        cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_confidence, existing['id']))
        click.echo(Fore.CYAN + f"   > [GÊNESE] Template '{problem_pattern[:30]}...' → confiança {new_confidence}")
    else:
        cursor.execute(
            "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
            (problem_pattern, solution_template, category, datetime.now(timezone.utc).isoformat())
        )
        click.echo(Fore.CYAN + f"   > [GÊNESE] Novo template: '{problem_pattern}' ({solution_template})")
    
    return True

def run_check_logic(path, cmd_line_ignore, fix, debug, fast=False, no_imports=False, no_cache=False, target_files=None):
    """
    Orquestra a análise estática, combinando uma arquitetura de pipeline com um sistema de cache.
    """
    if no_cache:
        click.echo(Fore.YELLOW + "A opção --no-cache foi usada. A análise completa será executada.")
    
    cache = {} if no_cache else _load_cache()
    
    config = _get_project_config(None, start_path=path)
    if not config.get('search_path_valid'):
        return {
            'summary': {'critical': 1, 'errors': 0, 'warnings': 0, 'info': 0},
            'findings': [{
                'severity': 'CRITICAL', 
                'category': 'SETUP',
                'message': f"O diretório de código-fonte '{config.get('search_path')}' não existe."
            }]
        }

    python_executable = _get_venv_python_executable()
    if not python_executable:
        return {
            'summary': {'critical': 1, 'errors': 0, 'warnings': 0, 'info': 0},
            'findings': [{
                'severity': 'CRITICAL', 
                'category': 'SETUP',
                'message': "Ambiente virtual 'venv' não encontrado ou inválido."
            }]
        }

    analysis_state = {
        'root_path': path,
        'files_to_process': target_files if target_files else collect_files_to_analyze(config, cmd_line_ignore),
        'raw_findings': [],
        'file_reports': {}
    }
    
    files_for_next_step = []
    for file_path in analysis_state['files_to_process']:
        file_hash = _get_file_hash(file_path)
        rel_file_path = os.path.relpath(file_path, path)

        if not no_cache and file_hash and rel_file_path in cache and cache[rel_file_path].get('hash') == file_hash:
            cached_item = cache[rel_file_path]
            findings = cached_item.get('findings', [])
            imports = cached_item.get('imports', [])
            if not fast:
                analysis_state['file_reports'][rel_file_path] = {'structure_analysis': cached_item.get('structure', {})}
        else:
            syntax_findings = _run_syntax_probe(file_path, python_executable, debug)
            if syntax_findings:
                analysis_state['raw_findings'].extend(syntax_findings)
                continue

            findings, imports = _analyze_single_file_statically(file_path, python_executable, debug)
            
            structure = {}
            if not fast:
                structure = analyze_file_structure(file_path)
                analysis_state['file_reports'][rel_file_path] = {'structure_analysis': structure}
            
            if file_hash:
                cache[rel_file_path] = {'hash': file_hash, 'findings': findings, 'imports': imports, 'structure': structure}

        analysis_state['raw_findings'].extend(findings)
        files_for_next_step.append({'path': file_path, 'imports': imports})

    # --- Etapa 2: Análise Agregada de Imports ---
    all_imports = [imp for file_info in files_for_next_step for imp in file_info['imports']]
    if all_imports and not no_imports:
        temp_logger = ExecutionLogger('import_probe', path, {})
        import_findings = _run_import_probe(all_imports, python_executable, temp_logger, config.get('search_path'))
        analysis_state['raw_findings'].extend(import_findings)

    # --- Etapa 3: Correção Automática (se ativada) ---
    if fix:
        click.echo(Fore.CYAN + "\nModo de correção (--fix) ativado...")
        fix_logger = ExecutionLogger('fix', path, {})
        for file_path in analysis_state['files_to_process']:
            _fix_unused_imports(file_path, fix_logger)

    # --- BLOCO DE FINALIZAÇÃO E ENRIQUECIMENTO (GÊNESE V2) ---
    
    # 1. Adiciona hashes consistentes aos findings
    final_findings = []
    for f in analysis_state['raw_findings']:
        file = f.get('file')
        line = f.get('line')
        message = f.get('message')
        
        finding_with_hash = f.copy()

        if file and line and message:
            rel_file_path = os.path.relpath(file, path) if os.path.isabs(file) else file
            unique_str = f"{rel_file_path}:{line}:{message}"
            finding_with_hash['hash'] = hashlib.md5(unique_str.encode('utf-8', 'ignore')).hexdigest()
        else:
            finding_with_hash['hash'] = None
        
        final_findings.append(finding_with_hash) 

    # 2. Enriquece com sugestões do histórico
    _enrich_findings_with_solutions(final_findings)
    
    # 3. GÊNESE V2: Gerencia incidentes ativamente
    project_path = os.path.abspath(path)
    incident_stats = _manage_incidents(final_findings, project_path)
    
    # Mostra estatísticas de incidentes (apenas se houver mudanças)
    if incident_stats['added'] > 0 or incident_stats['resolved'] > 0:
        parts = []
        if incident_stats['added'] > 0:
            parts.append(f"{incident_stats['added']} novo(s)")
        if incident_stats['resolved'] > 0:
            parts.append(f"{incident_stats['resolved']} resolvido(s)")
        if incident_stats['learned'] > 0:
            parts.append(f"{incident_stats['learned']} solução(ões) aprendida(s)")
        if incident_stats['templates'] > 0:
            parts.append(f"{incident_stats['templates']} template(s) criado(s)/reforçado(s)")
        click.echo(Fore.CYAN + f"   > [GÊNESE] {', '.join(parts)}")

    # 4. Passa os resultados para o logger
    with ExecutionLogger('check', path, {'fix': fix, 'debug': debug}) as logger:
        for finding in final_findings:
            snippet = _get_code_snippet(finding.get('file'), finding.get('line'))
            logger.add_finding(
                severity=finding['severity'], 
                message=finding.get('message', ''),
                category=finding.get('category', 'UNCATEGORIZED'),
                file=finding.get('file'), 
                line=finding.get('line'), 
                snippet=snippet, 
                details=finding.get('details'),
                suggestion_content=finding.get('suggestion_content'),
                suggestion_line=finding.get('suggestion_line'),
                finding_hash=finding.get('hash')
            )
        
        if not no_cache:
            _save_cache(cache)
            
        return logger.results

# =============================================================================
# O COMANDO CLICK
# =============================================================================

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=False), default='.')
@click.option('--ignore', 'cmd_line_ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--fix', is_flag=True, help="Tenta corrigir problemas automaticamente.")
@click.option('--debug', is_flag=True, help="Ativa a saída de depuração detalhada.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--fast', is_flag=True, help="Executa uma análise rápida, pulando etapas lentas como a análise estrutural.")
@click.option('--no-imports', is_flag=True, help="Pula a verificação de imports não resolvidos.")
@click.option('--no-cache', is_flag=True, help="Força uma reanálise completa, ignorando o cache.")
def check(ctx, path, cmd_line_ignore, fix, debug, output_format, fast, no_imports, no_cache):
    """Análise estática e estrutural completa do projeto."""
    if not debug and output_format == 'text':
        click.echo(Fore.YELLOW + "[CHECK] Executando análise...")
        
    results = run_check_logic(
        path, cmd_line_ignore, fix, debug, 
        fast=fast, no_imports=no_imports, no_cache=no_cache
    )
    _update_open_incidents(results, os.path.abspath(path)) 
    
    if output_format == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not debug:
            _present_results('text', results)
    
    if results.get('summary', {}).get('critical', 0) > 0:
        sys.exit(1)