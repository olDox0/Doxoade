# doxoade/doxoade/tools/genesis.py
"""
Motor Gênese & Abdução (v15.1 Gold).
Responsável por sugerir correções (Inteligência Simbólica) e inferir imports.
Evolução: MPoT-Aware, Detecção de Complexidade e Blindagem de Caminhos.
"""
import re
import ast
import os
import doxoade.tools.aegis.nexus_db as sqlite3  # noqa
from typing import List, Dict, Any
STDLIB_MODULES = {'sys': ['exit', 'path', 'argv', 'stdout', 'stderr', 'stdin', 'version', 'modules'], 'os': ['path', 'getcwd', 'chdir', 'listdir', 'mkdir', 'environ', 'name', 'walk', 'stat'], 'math': ['ceil', 'floor', 'sqrt', 'pi', 'pow', 'cos', 'sin', 'tan'], 'random': ['randint', 'choice', 'shuffle', 'random', 'seed'], 're': ['match', 'search', 'findall', 'sub', 'compile', 'fullmatch', 'escape'], 'json': ['dumps', 'loads', 'dump', 'load', 'JSONDecodeError'], 'datetime': ['datetime', 'date', 'time', 'timedelta', 'timezone'], 'time': ['sleep', 'time', 'monotonic', 'perf_counter'], 'hashlib': ['md5', 'sha256', 'sha1'], 'subprocess': ['run', 'Popen', 'PIPE', 'CalledProcessError'], 'pathlib': ['Path', 'PurePath'], 'ast': ['parse', 'walk', 'NodeVisitor', 'unparse'], 'shutil': ['copy', 'copy2', 'rmtree', 'move'], 'collections': ['Counter', 'defaultdict', 'deque', 'namedtuple']}
COMMON_THIRD_PARTY = {'colorama': ['Fore', 'Back', 'Style', 'init'], 'rich': ['console', 'table', 'panel', 'progress'], 'pytest': ['fixture', 'mark', 'raises']}
ALL_KNOWN_MODULES = {**STDLIB_MODULES, **COMMON_THIRD_PARTY}

def _extract_current_imports(file_path: str) -> Dict[str, Any]:
    """Extrai os imports existentes no arquivo para evitar duplicatas."""
    imports = {}
    try:
        if not os.path.exists(file_path):
            return {}
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    imports[module_name] = {'type': 'import', 'symbols': []}
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    symbols = [alias.name for alias in node.names]
                    if module_name in imports:
                        imports[module_name]['symbols'].extend(symbols)
                    else:
                        imports[module_name] = {'type': 'from', 'symbols': symbols}
    except Exception:
        pass
    return imports

def _analyze_dependencies(findings: List[Dict[str, Any]], file_path: str):
    """Cruza nomes indefinidos com a base de conhecimento para sugerir imports."""
    undefined = [f for f in findings if 'undefined name' in f.get('message', '')]
    if not undefined:
        return findings
    current_imports = _extract_current_imports(file_path)
    for f in undefined:
        match = re.search("undefined name '(.+?)'", f.get('message', ''))
        if not match:
            continue
        name = match.group(1)
        if name in ALL_KNOWN_MODULES and name not in current_imports:
            f['import_suggestion'] = f'import {name}'
        else:
            for mod, exports in ALL_KNOWN_MODULES.items():
                if name in exports and mod not in current_imports:
                    f['import_suggestion'] = f'from {mod} import {name}'
                    break
    return findings

def _simulate_fix(finding: Dict[str, Any], project_root: str, file_path: str, line_num: int, pattern: str, replacement: str, source: str, action: str):
    """Simula a correção garantindo que o arquivo seja encontrado."""
    try:
        if os.path.isabs(file_path):
            abs_path = file_path
        else:
            abs_path = os.path.normpath(os.path.join(project_root, file_path))
        if not os.path.exists(abs_path):
            return
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        idx = line_num - 1
        if 0 <= idx < len(lines):
            original = lines[idx]
            new_line = re.sub(pattern, replacement, original, count=1)
            if new_line != original:
                finding['suggestion_content'] = new_line
                finding['suggestion_line'] = line_num
                finding['suggestion_source'] = source
                finding['suggestion_action'] = action
    except Exception:
        pass

def _apply_solution_template(finding: Dict[str, Any], templates: List[sqlite3.Row]) -> bool:
    """Tenta casar o erro com um padrão aprendido no banco de dados."""
    message = finding.get('message', '')
    category = finding.get('category', '').upper()
    file_path = finding.get('file')
    line_num = finding.get('line')
    for t in templates:
        if t['category'] != category:
            continue
        regex = re.escape(t['problem_pattern']).replace('<MODULE>', '(.+?)').replace('<VAR>', '(.+?)').replace('<LINE>', '(\\d+)')
        if re.fullmatch(regex, message):
            _simulate_fix(finding, file_path, line_num, '^(.*)$', t['solution_template'], 'MEMÓRIA (Gênese)', 'Aplicar Template')
            return True
    return False

def _enrich_findings_with_solutions(findings: List[Dict[str, Any]], project_root: str):
    """MPoT-17: Rotula achados. Prioridade para Regras Nativas."""
    if not findings:
        return
    for f in findings:
        _apply_native_intelligence(f, project_root)

def _apply_native_intelligence(finding: Dict[str, Any], project_root: str):
    """Sentencia achados com IDs técnicos usando mapeamento de dicionário (CC: 2)."""
    msg = finding.get('message', '').lower()
    line_num = finding.get('line')
    snippet = finding.get('snippet', {})
    line_content = ''
    if snippet:
        line_content = snippet.get(str(line_num), snippet.get(line_num, '')).strip()
    patterns = {'f-string is missing placeholders': 'REMOVE_F_PREFIX', 'except:': 'RESTRICT_EXCEPTION', 'imported but unused': 'FIX_UNUSED_IMPORT'}
    for phrase, action in patterns.items():
        if phrase in msg:
            finding['suggestion_action'] = action
            break
    if 'assigned to but never used' in msg:
        is_multiple = ',' in line_content.split('=')[0] if '=' in line_content else False
        finding['suggestion_action'] = 'REPLACE_WITH_UNDERSCORE' if not is_multiple else None
    if finding.get('suggestion_action'):
        finding['suggestion_source'] = 'GÊNESE (Nativa)'

def _enrich_with_dependency_analysis(findings: List[Dict[str, Any]], project_path: str):
    """Agrupa por arquivo e aplica abdução de dependências."""
    by_file = {}
    for f in findings:
        path = f.get('file')
        if path:
            abs_p = os.path.join(project_path, path) if not os.path.isabs(path) else path
            if abs_p not in by_file:
                by_file[abs_p] = []
            by_file[abs_p].append(f)
    for path, file_findings in by_file.items():
        _analyze_dependencies(file_findings, path)
    return findings