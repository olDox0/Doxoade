# -*- coding: utf-8 -*-
"""
Motor Gênese & Abdução (v15.1 Gold).
Responsável por sugerir correções (Inteligência Simbólica) e inferir imports.
Evolução: MPoT-Aware, Detecção de Complexidade e Blindagem de Caminhos.
"""

import re
import ast
import os
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from doxoade.database import get_db_connection

# --- DADOS DE CONHECIMENTO (STDLIB & THIRD PARTY) ---
# Mantidos para suportar a lógica de Abdução de Imports
STDLIB_MODULES = {
    'sys': ['exit', 'path', 'argv', 'stdout', 'stderr', 'stdin', 'version', 'modules'],
    'os': ['path', 'getcwd', 'chdir', 'listdir', 'mkdir', 'environ', 'name', 'walk', 'stat'],
    'math': ['ceil', 'floor', 'sqrt', 'pi', 'pow', 'cos', 'sin', 'tan'],
    'random': ['randint', 'choice', 'shuffle', 'random', 'seed'],
    're': ['match', 'search', 'findall', 'sub', 'compile', 'fullmatch', 'escape'],
    'json': ['dumps', 'loads', 'dump', 'load', 'JSONDecodeError'],
    'datetime': ['datetime', 'date', 'time', 'timedelta', 'timezone'],
    'time': ['sleep', 'time', 'monotonic', 'perf_counter'],
    'hashlib': ['md5', 'sha256', 'sha1'],
    'subprocess': ['run', 'Popen', 'PIPE', 'CalledProcessError'],
    'pathlib': ['Path', 'PurePath'],
    'ast': ['parse', 'walk', 'NodeVisitor', 'unparse'],
    'shutil': ['copy', 'copy2', 'rmtree', 'move'],
    'collections': ['Counter', 'defaultdict', 'deque', 'namedtuple'],
}

COMMON_THIRD_PARTY = {
    'colorama': ['Fore', 'Back', 'Style', 'init'],
    'rich': ['console', 'table', 'panel', 'progress'],
    'pytest': ['fixture', 'mark', 'raises'],
}

ALL_KNOWN_MODULES = {**STDLIB_MODULES, **COMMON_THIRD_PARTY}

# --- LÓGICA DE ABDUÇÃO (INFERÊNCIA DE IMPORTS) ---

def _extract_current_imports(file_path: str) -> Dict[str, Any]:
    """Extrai os imports existentes no arquivo para evitar duplicatas."""
    imports = {}
    try:
        if not os.path.exists(file_path): return {}
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
    except Exception: pass
    return imports

def _analyze_dependencies(findings: List[Dict[str, Any]], file_path: str):
    """Cruza nomes indefinidos com a base de conhecimento para sugerir imports."""
    undefined = [f for f in findings if 'undefined name' in f.get('message', '')]
    if not undefined: return findings
    
    current_imports = _extract_current_imports(file_path)
    
    for f in undefined:
        match = re.search(r"undefined name '(.+?)'", f.get('message', ''))
        if not match: continue
        name = match.group(1)
        
        # Tenta sugerir o import do módulo ou do símbolo
        if name in ALL_KNOWN_MODULES and name not in current_imports:
            f['import_suggestion'] = f"import {name}"
        else:
            for mod, exports in ALL_KNOWN_MODULES.items():
                if name in exports and mod not in current_imports:
                    f['import_suggestion'] = f"from {mod} import {name}"
                    break
    return findings

# --- LÓGICA DE ENRIQUECIMENTO (GÊNESE) ---

def _simulate_fix(finding: Dict[str, Any], project_root: str, file_path: str, line_num: int, 
                  pattern: str, replacement: str, source: str, action: str):
    """Simula a correção garantindo que o arquivo seja encontrado."""
    try:
        # Resolve o caminho absoluto de forma resiliente
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


def _try_apply_template(finding: Dict[str, Any], templates: List[sqlite3.Row]) -> bool:
    """Tenta casar o erro com um padrão aprendido no banco de dados."""
    message = finding.get('message', '')
    category = finding.get('category', '').upper()
    file_path = finding.get('file')
    line_num = finding.get('line')

    for t in templates:
        if t['category'] != category: continue
        
        # Converte padrão abstrato para Regex real
        regex = (re.escape(t['problem_pattern'])
                 .replace('<MODULE>', '(.+?)')
                 .replace('<VAR>', '(.+?)')
                 .replace('<LINE>', r'(\d+)'))
        
        if re.fullmatch(regex, message):
            _simulate_fix(finding, file_path, line_num, r'^(.*)$', 
                         t['solution_template'], "MEMÓRIA (Gênese)", "Aplicar Template")
            return True
    return False

def _apply_native_intelligence(finding: Dict[str, Any], project_root: str):
    """Regras universais ativadas por padrão."""
    message = finding.get('message', '').lower()
    category = finding.get('category', '').upper()
    file_path = finding.get('file')
    line_num = finding.get('line')

    if not file_path or not line_num: return

    # FIX: Regex mais flexível para capturar variações do erro de except
    if "except:" in message or "except" in message and "exception" not in message:
        _simulate_fix(finding, project_root, file_path, line_num, 
                     r'except\s*:', 'except Exception:', 
                     "REGRA NATIVA (Segurança)", "Restringir exceção")

    elif "f-string is missing placeholders" in message:
        _simulate_fix(finding, project_root, file_path, line_num, 
                     r'\bf(["\'])', r'\1', 
                     "REGRA NATIVA (Estilo)", "Remover prefixo 'f'")

    elif "redefinition of unused" in message:
        _simulate_fix(finding, project_root, file_path, line_num, 
                     r'^(.*)$', r'# [DOX-UNUSED] \1', 
                     "REGRA NATIVA", "Comentar redefinição")

    elif category == 'COMPLEXITY':
        # Para complexidade, injetamos um TODO acima da função
        finding['suggestion_content'] = f"# TODO: Refatorar para reduzir complexidade (CC)\n"
        finding['suggestion_line'] = line_num
        finding['suggestion_source'] = "ARQUITETO"
        finding['suggestion_action'] = "Adicionar nota de refatoração"

def _enrich_findings_with_solutions(findings: List[Dict[str, Any]], project_root: str):
    """Orquestrador. FIX: Agora exige e repassa o project_root."""
    if not findings: return
    
    conn = get_db_connection()
    try:
        conn.row_factory = sqlite3.Row
        templates = conn.execute("SELECT * FROM solution_templates ORDER BY confidence DESC").fetchall()

        for f in findings:
            if f.get('import_suggestion') or not f.get('file'):
                continue

            # Prioridade: 1. Templates -> 2. Regras Nativas
            if not _try_apply_template(f, project_root, templates):
                _apply_native_intelligence(f, project_root)
    finally:
        conn.close()

def _enrich_with_dependency_analysis(findings: List[Dict[str, Any]], project_path: str):
    """Agrupa por arquivo e aplica abdução de dependências."""
    by_file = {}
    for f in findings:
        path = f.get('file')
        if path:
            abs_p = os.path.join(project_path, path) if not os.path.isabs(path) else path
            if abs_p not in by_file: by_file[abs_p] = []
            by_file[abs_p].append(f)

    for path, file_findings in by_file.items():
        _analyze_dependencies(file_findings, path)
    return findings
    
def _try_apply_template(finding: Dict[str, Any], project_root: str, templates: List[sqlite3.Row]) -> bool:
    """Tenta casar erro com padrão aprendido. FIX: Adicionado project_root."""
    message = finding.get('message', '')
    category = finding.get('category', '').upper()
    
    for t in templates:
        if t['category'] != category: continue
        regex = (re.escape(t['problem_pattern'])
                 .replace('<MODULE>', '(.+?)').replace('<VAR>', '(.+?)').replace('<LINE>', r'(\d+)'))
        
        if re.fullmatch(regex, message):
            _simulate_fix(finding, project_root, finding['file'], finding['line'], 
                         r'^(.*)$', t['solution_template'], "MEMÓRIA (Gênese)", "Aplicar Template")
            return True
    return False