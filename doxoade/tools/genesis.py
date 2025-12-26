# doxoade/tools/genesis.py
import re
import ast
import os
import sqlite3
from doxoade.database import get_db_connection

# --- DADOS DE CONHECIMENTO ---
STDLIB_MODULES = {
    'sys': ['exit', 'path', 'argv', 'stdout', 'stderr', 'stdin', 'version', 'platform', 'modules'],
    'os': ['path', 'getcwd', 'chdir', 'listdir', 'mkdir', 'makedirs', 'remove', 'rename', 'environ', 'sep', 'name', 'walk', 'stat', 'getenv', 'system', 'popen'],
    'math': ['ceil', 'floor', 'sqrt', 'pi', 'pow', 'cos', 'sin', 'tan', 'degrees', 'radians'],
    'random': ['randint', 'choice', 'shuffle', 'random', 'seed'],
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

COMMON_THIRD_PARTY = {
    'colorama': ['Fore', 'Back', 'Style', 'init'],
    'pyflakes': ['api', 'checker'],
    'requests': ['get', 'post', 'put', 'delete', 'Session', 'Response'],
    'flask': ['Flask', 'request', 'render_template', 'redirect', 'url_for'],
    'pytest': ['fixture', 'mark', 'raises'],
}

ALL_KNOWN_MODULES = {**STDLIB_MODULES, **COMMON_THIRD_PARTY}

# --- LÓGICA DE ABDUÇÃO ---

def _extract_current_imports(file_path):
    imports = {}
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    imports[module_name] = {'type': 'import', 'alias': alias.asname, 'symbols': []}
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    symbols = [alias.name for alias in node.names]
                    if module_name in imports:
                        imports[module_name]['symbols'].extend(symbols)
                    else:
                        imports[module_name] = {'type': 'from', 'alias': None, 'symbols': symbols}
    except Exception: pass
    return imports

def _analyze_dependencies(findings, file_path):
    if not findings: return findings
    undefined_findings = [f for f in findings if 'undefined name' in f.get('message', '')]
    if not undefined_findings: return findings
    
    current_imports = _extract_current_imports(file_path)
    
    for finding in undefined_findings:
        message = finding.get('message', '')
        match = re.match(r"undefined name '(.+?)'", message)
        if not match: continue
        
        undefined_name = match.group(1)
        
        if undefined_name in ALL_KNOWN_MODULES:
            if undefined_name not in current_imports:
                finding['missing_import'] = undefined_name
                finding['import_suggestion'] = f"import {undefined_name}"
                finding['dependency_type'] = 'MISSING_MODULE_IMPORT'
                continue
        
        for module, exports in ALL_KNOWN_MODULES.items():
            if undefined_name in exports:
                if module not in current_imports:
                    finding['missing_import'] = module
                    finding['import_suggestion'] = f"from {module} import {undefined_name}"
                    finding['dependency_type'] = 'MISSING_SYMBOL_IMPORT'
                    break
                else:
                    import_info = current_imports.get(module, {})
                    if import_info.get('type') == 'import' and undefined_name in exports:
                        finding['import_suggestion'] = f"Use '{module}.{undefined_name}' ou 'from {module} import {undefined_name}'"
                        finding['dependency_type'] = 'WRONG_IMPORT_STYLE'
                        break
    return findings

def _enrich_with_dependency_analysis(findings, project_path):
    by_file = {}
    for f in findings:
        file_path = f.get('file')
        if file_path:
            abs_path = os.path.join(project_path, file_path) if not os.path.isabs(file_path) else file_path
            if abs_path not in by_file: by_file[abs_path] = []
            by_file[abs_path].append(f)

    for file_path, file_findings in by_file.items():
        _analyze_dependencies(file_findings, file_path)
    return findings

# --- LÓGICA DE SOLUÇÕES (Gênese) ---
def _enrich_findings_with_solutions(findings):
    if not findings: return
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM solution_templates ORDER BY confidence DESC")
        templates = cursor.fetchall()

        for finding in findings:
            if finding.get('import_suggestion'): continue
            
            message = finding.get('message', '')
            category = finding.get('category', '')
            file_path = finding.get('file')
            line_num = finding.get('line')

            if not file_path or not line_num: continue

            # --- 1. Tenta Solução Exata (Histórico do arquivo) ---
            finding_hash = finding.get('hash')
            if finding_hash:
                cursor.execute("SELECT stable_content, error_line FROM solutions WHERE finding_hash = ? LIMIT 1", (finding_hash,))
                exact = cursor.fetchone()
                if exact:
                    finding['suggestion_content'] = exact['stable_content']
                    finding['suggestion_line'] = exact['error_line']
                    finding['suggestion_source'] = "EXACT"
                    continue # Se achou exata, pula o resto

            # --- 2. Tenta Templates do Banco (Gênese Aprendido) ---
            template_found = False
            for template in templates:
                if template['category'] != category: continue
                
                # Prepara Regex do Template
                pattern_regex = (re.escape(template['problem_pattern'])
                    .replace('<MODULE>', '(.+?)')
                    .replace('<VAR>', '(.+?)')
                    .replace('<LINE>', r'(\d+)'))
                
                if re.fullmatch(pattern_regex, message):
                    # Aplica lógica do template para VISUALIZAÇÃO
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                        
                        idx = line_num - 1
                        if idx < 0 or idx >= len(lines): break
                        
                        sol_type = template['solution_template']
                        
                        # Simula a correção para exibição
                        new_content = None
                        action = "Aplicar correção"
                        
                        if sol_type == "REMOVE_LINE":
                            # Simulação visual de remoção (mostra linha vazia ou comentário)
                            new_content = f"# [DOX-UNUSED] {lines[idx]}" 
                            action = "Remover linha"
                        elif sol_type == "REMOVE_F_PREFIX":
                            new_content = re.sub(r'\bf(["\'])', r'\1', lines[idx])
                            action = "Remover prefixo 'f'"
                        
                        if new_content:
                            finding['suggestion_content'] = new_content
                            finding['suggestion_line'] = line_num
                            finding['suggestion_source'] = "TEMPLATE"
                            finding['suggestion_action'] = action
                            template_found = True
                            break
                    except: pass
            
            if template_found: continue

            # --- 3. Inteligência Nativa (Hardcoded Rules) ---
            # Para casos críticos que queremos garantir mesmo sem treino prévio
            
            # Regra: Except Genérico -> Except Exception
            if "Uso de 'except:' genérico detectado" in message:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    idx = line_num - 1
                    if 0 <= idx < len(lines):
                        original = lines[idx]
                        # Simula a correção
                        new_line = re.sub(r'except\s*:', 'except Exception:', original, count=1)
                        
                        if new_line != original:
                            finding['suggestion_content'] = new_line
                            finding['suggestion_line'] = line_num
                            finding['suggestion_source'] = "REGRA NATIVA (Segurança)"
                            finding['suggestion_action'] = "Restringir exceção"
                except: pass

            # Regra: Redefinição de Função -> Comentar
            elif "redefinition of unused" in message and category == 'DEADCODE':
                 try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    idx = line_num - 1
                    if 0 <= idx < len(lines):
                        finding['suggestion_content'] = f"# [DOX-UNUSED] {lines[idx]}"
                        finding['suggestion_line'] = line_num
                        finding['suggestion_source'] = "REGRA NATIVA"
                        finding['suggestion_action'] = "Comentar redefinição"
                 except: pass

    finally:
        conn.close()