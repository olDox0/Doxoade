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

from .._version import __version__ as DOXOADE_VERSION
from ..database import get_db_connection
from ..fixer import AutoFixer
from ..learning import LearningEngine
from ..shared_tools import (
    ExecutionLogger, 
    _present_results,
    _get_code_snippet,
    _get_venv_python_executable,
    _get_project_config,
    collect_files_to_analyze,
    analyze_file_structure,
    _update_open_incidents,
    _get_file_hash
)

# [REFATORAÇÃO] Importa a lógica de filtros do novo módulo
from .check_filters import filter_and_inject_findings

def _get_probe_path(probe_name):
    """Encontra o caminho para um arquivo de sonda de forma segura."""
    try:
        # Tenta método moderno (Python 3.9+) - Evita DeprecationWarning
        if hasattr(resources, 'files'):
            return str(resources.files('doxoade.probes').joinpath(probe_name))

        # Fallback para Python < 3.9
        with resources.path('doxoade.probes', probe_name) as probe_path:
            return str(probe_path)
    except Exception:
        # Fallback para ambientes muito antigos ou zipados
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

def _run_syntax_probe(file_path, python_executable, debug=False):
    findings = []
    probe_path = _get_probe_path('syntax_probe.py')
    syntax_cmd = [python_executable, probe_path, file_path]
    try:
        result = subprocess.run(syntax_cmd, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace')
        if result.returncode != 0:
            findings.append({'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': f"Erro de sintaxe: {result.stderr.strip()}", 'file': file_path, 'line': 1})
    except Exception as e:
        findings.append({'severity': 'CRITICAL', 'category': 'SYNTAX', 'message': str(e), 'file': file_path})
    return findings

def _run_pyflakes_probe(file_path, python_executable, debug=False):
    findings = []
    probe_path = _get_probe_path('static_probe.py')
    cmd = [python_executable, probe_path, file_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        for line in result.stdout.splitlines():
            if ":" in line:
                parts = line.split(":", 3)
                if len(parts) >= 4:
                    msg = parts[3].strip()
                    cat = 'DEADCODE' if 'unused' in msg else ('RUNTIME-RISK' if 'undefined' in msg else 'STYLE')
                    findings.append({'severity': 'WARNING', 'category': cat, 'message': msg, 'file': file_path, 'line': int(parts[1])})
    except Exception: pass
    return findings

def _run_hunter_probe(file_path, python_executable, debug=False):
    findings = []
    probe_path = _get_probe_path('hunter_probe.py')
    try:
        result = subprocess.run([python_executable, probe_path, file_path], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.stdout.strip():
            data = json.loads(result.stdout)
            for item in data:
                item['file'] = file_path
                findings.append(item)
    except Exception: pass
    return findings

def _run_import_probe(all_imports, venv_python, logger, search_path):
    unique = sorted(list({imp['module'] for imp in all_imports}))
    if not unique: return []
    try:
        probe_path = _get_probe_path('import_probe.py')
        process = subprocess.run([venv_python, probe_path], input=json.dumps(unique), capture_output=True, text=True, check=True, encoding='utf-8')
        missing = set(json.loads(process.stdout))
    except Exception: return []
    
    truly_missing = set()
    for m in missing:
        if not os.path.exists(os.path.join(search_path, f"{m}.py")) and not os.path.isdir(os.path.join(search_path, m)):
            truly_missing.add(m)
            
    findings = []
    IGNORE = {'setuptools', 'kivy'}
    for imp in all_imports:
        if imp['module'] in truly_missing and imp['module'] not in IGNORE:
            findings.append({'severity': 'CRITICAL', 'category': 'DEPENDENCY', 'message': f"Import não resolvido: '{imp['module']}'", 'file': imp['file'], 'line': imp['line']})
    return findings

def _extract_imports(file_path):
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        tree = ast.parse(content, filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names: imports.append({'module': alias.name.split('.')[0], 'line': node.lineno, 'file': file_path})
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.append({'module': node.module.split('.')[0], 'line': node.lineno, 'file': file_path})
    except Exception: pass
    return imports
    
def _analyze_single_file_statically(file_path, python_executable, debug=False):
    syntax = _run_syntax_probe(file_path, python_executable, debug)
    if syntax: return syntax, []
    pf = _run_pyflakes_probe(file_path, python_executable, debug)
    imps = _extract_imports(file_path)
    return pf, imps
    
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

STDLIB_MODULES = {
    'sys': ['exit', 'path', 'argv', 'stdout', 'stderr', 'stdin', 'version', 'platform', 'modules'],
    'os': ['path', 'getcwd', 'chdir', 'listdir', 'mkdir', 'makedirs', 'remove', 'rename', 'environ', 
           'sep', 'name', 'walk', 'stat', 'getenv', 'system', 'popen'],
    're': ['match', 'search', 'findall', 'sub', 'split', 'compile', 'fullmatch', 'escape', 'IGNORECASE', 'VERBOSE'],
    'json': ['dumps', 'loads', 'dump', 'load', 'JSONDecodeError'],
    'datetime': ['datetime', 'date', 'time', 'timedelta', 'timezone'],
    'time': ['sleep', 'time', 'monotonic', 'perf_counter'],
    'hashlib': ['md5', 'sha256', 'sha1', 'sha512'],
    'sqlite3': ['connect', 'Row', 'Error', 'OperationalError'],
    'subprocess': ['run', 'Popen', 'PIPE', 'CalledProcessError', 'check_output'],
    'pathlib': ['Path', 'PurePath'],
    'ast': ['parse', 'walk', 'literal_eval', 'NodeVisitor', 'dump'],
    'shutil': ['copy', 'copy2', 'copytree', 'rmtree', 'move'],
    'io': ['StringIO', 'BytesIO'],
    'collections': ['Counter', 'defaultdict', 'OrderedDict', 'namedtuple', 'deque'],
    'functools': ['wraps', 'partial', 'lru_cache', 'reduce'],
    'itertools': ['chain', 'cycle', 'repeat', 'combinations', 'permutations'],
    'traceback': ['format_exc', 'print_exc', 'extract_tb'],
    'importlib': ['import_module', 'resources'],
    'toml': ['load', 'dump', 'loads', 'dumps', 'TomlDecodeError'],
    'click': ['command', 'group', 'option', 'argument', 'echo', 'pass_context', 'Path', 'Choice'],
}

# Mapeamento de módulos de terceiros comuns
COMMON_THIRD_PARTY = {
    'colorama': ['Fore', 'Back', 'Style', 'init'],
    'pyflakes': ['api', 'checker'],
    'requests': ['get', 'post', 'put', 'delete', 'Session', 'Response'],
    'flask': ['Flask', 'request', 'render_template', 'redirect', 'url_for'],
    'pytest': ['fixture', 'mark', 'raises'],
}

# Combina os dois dicionários
ALL_KNOWN_MODULES = {**STDLIB_MODULES, **COMMON_THIRD_PARTY}

def _analyze_dependencies(findings, file_path):
    """
    (Gênese V3 - Abdução) Analisa dependências e enriquece findings de 'undefined name'
    com informação sobre qual import provavelmente está faltando.
    """
    if not findings:
        return findings
    
    # Filtra apenas os findings de 'undefined name'
    undefined_findings = [f for f in findings if 'undefined name' in f.get('message', '')]
    
    if not undefined_findings:
        return findings
    
    # Lê os imports atuais do arquivo
    current_imports = _extract_current_imports(file_path)
    
    for finding in undefined_findings:
        message = finding.get('message', '')
        match = re.match(r"undefined name '(.+?)'", message)
        if not match:
            continue
        
        undefined_name = match.group(1)
        
        # Caso 1: O nome indefinido É um módulo conhecido
        if undefined_name in ALL_KNOWN_MODULES:
            if undefined_name not in current_imports:
                finding['missing_import'] = undefined_name
                finding['import_suggestion'] = f"import {undefined_name}"
                finding['dependency_type'] = 'MISSING_MODULE_IMPORT'
                continue
        
        # Caso 2: O nome indefinido é um EXPORT de algum módulo conhecido
        for module, exports in ALL_KNOWN_MODULES.items():
            if undefined_name in exports:
                if module not in current_imports:
                    finding['missing_import'] = module
                    finding['import_suggestion'] = f"from {module} import {undefined_name}"
                    finding['dependency_type'] = 'MISSING_SYMBOL_IMPORT'
                    break
                else:
                    # Módulo importado mas símbolo não
                    import_info = current_imports.get(module, {})
                    if import_info.get('type') == 'import' and undefined_name in exports:
                        # Usou "import module" mas está tentando usar "symbol" diretamente
                        finding['import_suggestion'] = f"Use '{module}.{undefined_name}' ou 'from {module} import {undefined_name}'"
                        finding['dependency_type'] = 'WRONG_IMPORT_STYLE'
                        break
        
        # Caso 3: Tenta inferir do contexto (nome similar a módulos conhecidos)
        if 'missing_import' not in finding:
            # Verifica se é uma variação comum (ex: 'Fore' -> 'colorama')
            for module, exports in ALL_KNOWN_MODULES.items():
                if undefined_name in exports:
                    finding['missing_import'] = module
                    finding['import_suggestion'] = f"from {module} import {undefined_name}"
                    finding['dependency_type'] = 'INFERRED_IMPORT'
                    break
    
    return findings


def _extract_current_imports(file_path):
    """
    Extrai os imports atuais de um arquivo Python.
    Retorna um dicionário: {nome_módulo: {type: 'import'|'from', symbols: [...]}}
    """
    imports = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    imports[module_name] = {
                        'type': 'import',
                        'alias': alias.asname,
                        'symbols': []
                    }
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    symbols = [alias.name for alias in node.names]
                    if module_name in imports:
                        imports[module_name]['symbols'].extend(symbols)
                    else:
                        imports[module_name] = {
                            'type': 'from',
                            'alias': None,
                            'symbols': symbols
                        }
    except (SyntaxError, IOError):
        pass
    
    return imports

def _enrich_with_dependency_analysis(findings, project_path):
    """
    Enriquece os findings com análise de dependências.
    """
    # Agrupa findings por arquivo
    by_file = {}
    for f in findings:
        file_path = f.get('file')
        if file_path:
            abs_path = os.path.join(project_path, file_path) if not os.path.isabs(file_path) else file_path
            if abs_path not in by_file:
                by_file[abs_path] = []
            by_file[abs_path].append(f)

    for file_path, file_findings in by_file.items():
        _analyze_dependencies(file_findings, file_path)

    return findings

def _enrich_findings_with_solutions(findings):
    """
    (Gênese V2 - Expandido) Consulta o DB por soluções exatas E aplica templates genéricos.
    """
    if not findings: return
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM solution_templates ORDER BY confidence DESC")
        templates = cursor.fetchall()

        for finding in findings:
            if finding.get('import_suggestion'):
                continue
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
                        # Sugere ação manual
                        if not finding.get('import_suggestion'):
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
    (Gênese V3) Gerencia incidentes E aprende soluções automaticamente.
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
            
            # Tenta aprender template (Gênese V8)
            learner = LearningEngine(cursor) 
            original_content = None # Tenta recuperar o conteúdo antigo do git se possível, aqui simplificado
            if learner.learn_from_incident(incident, corrected_content, original_content):
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
        # click.echo(Fore.YELLOW + f"[AVISO] Erro ao gerenciar incidentes: {e}")
    finally:
        conn.close()
    
    return stats

def _run_smart_fix(findings, project_path, logger):
    fixer = AutoFixer(logger)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    fixed_count = 0
    
    try:
        cursor.execute("SELECT * FROM solution_templates WHERE confidence > 0")
        templates = cursor.fetchall()
        
        sorted_findings = sorted(findings, key=lambda x: x.get('line', 0), reverse=True)
        
        for finding in sorted_findings:
            msg = finding.get('message', '')
            category = finding.get('category', '')
            matched_template = None
            context = {}
            
            for t in templates:
                if t['category'] != category: 
                    continue
                
                pattern_regex = (re.escape(t['problem_pattern'])
                    .replace('<MODULE>', '(.+?)')
                    .replace('<VAR>', '(.+?)')
                    .replace('<LINE>', r'(\d+)'))
                
                match = re.fullmatch(pattern_regex, msg)
                if match:
                    matched_template = t
                    if t['solution_template'] == 'REPLACE_WITH_UNDERSCORE' and match.groups():
                        context['var_name'] = match.group(1)
                    break
            
            if matched_template:
                raw_path = finding['file']
                if os.path.isabs(raw_path):
                    file_abs = raw_path
                else:
                    file_abs = os.path.abspath(os.path.join(project_path, raw_path))
                file_abs = os.path.normpath(file_abs)
                
                if fixer.apply_fix(file_abs, finding['line'], matched_template['solution_template'], context):
                    fixed_count += 1
                    click.echo(Fore.GREEN + f"   > [AUTOFIX] Aplicado: {matched_template['solution_template']} em {finding['file']}:{finding['line']}")
                    
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO AUTOFIX] {e}")
    finally:
        conn.close()
    
    return fixed_count

def _run_clone_probe(files, python_executable, debug=False):
    findings = []
    probe_path = _get_probe_path('clone_probe.py')
    if len(files) < 2: return []
    if debug: click.echo(Fore.CYAN + f"   > [DEBUG] Iniciando análise de clones em {len(files)} arquivos...")
    try:
        input_json = json.dumps(files)
        cmd = [python_executable, probe_path]
        result = subprocess.run(cmd, input=input_json, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0 and result.stdout.strip():
            findings.extend(json.loads(result.stdout))
    except Exception: pass
    return findings

def _run_xref_probe(files, python_executable, project_root, debug=False):
    """Executa a Sonda de Referência Cruzada (XRef)."""
    if not files: return []
    probe_path = _get_probe_path('xref_probe.py')
    if debug: click.echo(Fore.CYAN + f"   > [DEBUG] Executando XRef Probe (Integridade) em {len(files)} arquivos...")
    findings = []
    try:
        input_json = json.dumps(files)
        cmd = [python_executable, probe_path, project_root]
        result = subprocess.run(cmd, input=input_json, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0 and result.stdout.strip():
            findings = json.loads(result.stdout)
    except Exception: pass
    return findings

def run_check_logic(path, cmd_line_ignore, fix, debug, fast=False, no_imports=False, no_cache=False, target_files=None, check_clones=False):
    if no_cache: click.echo(Fore.YELLOW + "A opção --no-cache foi usada.")
    cache = {} if no_cache else _load_cache()

    is_single_file = os.path.isfile(path)
    if is_single_file:
        root_path = os.path.dirname(os.path.abspath(path))
        config = {'search_path_valid': True, 'root_path': root_path}
        if not target_files: target_files = [path]
    else:
        root_path = os.path.abspath(path)
        config = _get_project_config(None, start_path=path)
        if not config.get('search_path_valid'): return {'summary': {'critical': 1}, 'findings': []}

    python_exe = _get_venv_python_executable() or sys.executable
    
    # Lógica de exclusão robusta
    ignore_list = config.get('ignore', [])
    if cmd_line_ignore:
        ignore_list.extend(cmd_line_ignore)
    
    # Normaliza padrões de ignore
    ignore_patterns = [p.strip('/\\').lower() for p in ignore_list]
    # Adiciona padrões padrão do sistema
    ignore_patterns.extend(['venv', 'build', 'dist', '.git', '__pycache__', '.doxoade_cache', 'pytest_temp_dir'])

    if target_files:
        # Se alvos foram passados (ex: pelo 'save'), filtramos eles contra o ignore config
        files = []
        for f in target_files:
            # Verifica se alguma parte do caminho está na lista de ignore
            parts = f.replace('\\', '/').split('/')
            if not any(part.lower() in ignore_patterns for part in parts):
                files.append(f)
            else:
                # Opcional: Avisar em debug que foi ignorado
                if debug: click.echo(f"   > [DEBUG] Ignorando '{f}' (match em config)")
    else:
        # Coleta automática
        files = collect_files_to_analyze(config, cmd_line_ignore)

    analysis = {'raw_findings': [], 'files': files}
    valid_files = []

    # --- FASE 1: Análise Individual (Arquivos Isolados) ---
    for fp in files:
        h = _get_file_hash(fp)
        rel = os.path.relpath(fp, root_path) if not is_single_file else os.path.basename(fp)

        if not no_cache and h and rel in cache and cache[rel].get('hash') == h:
            analysis['raw_findings'].extend(cache[rel].get('findings', []))
            valid_files.append(fp)
        else:
            syn = _run_syntax_probe(fp, python_exe)
            if syn:
                analysis['raw_findings'].extend(syn)
                continue

            valid_files.append(fp)
            pf = _run_pyflakes_probe(fp, python_exe)
            ht = _run_hunter_probe(fp, python_exe)
            findings = pf + ht
            analysis['raw_findings'].extend(findings)
            if h: cache[rel] = {'hash': h, 'findings': findings}

    # --- FASE 2: Análise Global (Cross-File) ---
    
    # 2.1 Clones (Duplicação)
    if (check_clones or not fast) and valid_files:
        analysis['raw_findings'].extend(_run_clone_probe(valid_files, python_exe, debug))

    # 2.2 XRef (Integridade de Links)
    if not fast and valid_files:
        xref_findings = _run_xref_probe(valid_files, python_exe, root_path, debug)
        analysis['raw_findings'].extend(xref_findings)

    # --- FASE 3: Enriquecimento e Correção ---
    _enrich_with_dependency_analysis(analysis['raw_findings'], root_path)
    _enrich_findings_with_solutions(analysis['raw_findings'])

    if fix:
        click.echo(Fore.CYAN + "\nModo de correção (--fix) ativado...")
        with ExecutionLogger('autofix', root_path, {}) as fix_logger:
            count = _run_smart_fix(analysis['raw_findings'], root_path, fix_logger)
        if count > 0: click.echo(Fore.GREEN + f"   > Total de correções: {count}")

    # Finalization (Hash calculation, Filtering, Output)
    final = []
    for f in analysis['raw_findings']:
        if not f.get('hash'):
            u = f"{f.get('file')}:{f.get('line')}:{f.get('message')}"
            f['hash'] = hashlib.md5(u.encode('utf-8')).hexdigest()
        final.append(f)

    filtered = []
    by_file = {}
    for f in final:
        p = f.get('file')
        if p:
            if p not in by_file: by_file[p] = []
            by_file[p].append(f)

    for fp in files:
        # Busca tanto por caminho absoluto quanto relativo para garantir
        fs = by_file.get(fp) or by_file.get(os.path.abspath(fp)) or []
        filtered.extend(filter_and_inject_findings(fs, fp))

    with ExecutionLogger('check', root_path, {'fix': fix}) as logger:
        for f in filtered:
            s = _get_code_snippet(f.get('file'), f.get('line'))
            logger.add_finding(
                severity=f['severity'],
                message=f.get('message'),
                category=f.get('category', 'UNCATEGORIZED'),
                file=f.get('file'),
                line=f.get('line'),
                snippet=s,
                finding_hash=f.get('hash'),
                suggestion_content=f.get('suggestion_content'),
                suggestion_line=f.get('suggestion_line'),
                suggestion_source=f.get('suggestion_source'),
                suggestion_action=f.get('suggestion_action'),
                import_suggestion=f.get('import_suggestion'),
                dependency_type=f.get('dependency_type'),
                missing_import=f.get('missing_import')
            )
        if not no_cache: _save_cache(cache)
        return logger.results

# =============================================================================
# O COMANDO CLICK
# =============================================================================

@click.command('check')
@click.pass_context
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta.")
@click.option('--fix', is_flag=True, help="Tenta corrigir problemas automaticamente.")
@click.option('--debug', is_flag=True, help="Ativa a saída de depuração detalhada.")
@click.option('--format', 'output_format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
@click.option('--fast', is_flag=True, help="Executa uma análise rápida (pula clones/estrutura).")
@click.option('--no-imports', is_flag=True, help="Pula a verificação de imports não resolvidos.")
@click.option('--no-cache', is_flag=True, help="Força uma reanálise completa, ignorando o cache.")
@click.option('--clones', is_flag=True, help="Força a análise de código duplicado (DRY).")
def check(ctx, path, ignore, fix, debug, output_format, fast, no_imports, no_cache, clones):
    """Análise estática, estrutural e de duplicatas completa do projeto."""
    if not debug and output_format == 'text':
        click.echo(Fore.YELLOW + "[CHECK] Executando análise...")
        
    results = run_check_logic(
        path, ignore, fix, debug, 
        fast=fast, no_imports=no_imports, no_cache=no_cache, check_clones=clones
    )
    _update_open_incidents(results, os.path.abspath(path)) 
    
    if output_format == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not debug:
            _present_results('text', results)
    
    if results.get('summary', {}).get('critical', 0) > 0:
        sys.exit(1)

if __name__ == "__main__":
    check()