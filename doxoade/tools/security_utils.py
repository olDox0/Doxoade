# -*- coding: utf-8 -*-
"""
Security & Integrity Utilities - Aegis Guard v2.2.
Consolidated and hardened against introspection and taint injection.
Compliance: MPoT-4, MPoT-8, PASC-6.
"""
import hashlib
import ast
import logging
from pathlib import Path
from typing import Optional, List, Dict

__all__ = ['calculate_integrity_hash', 'restricted_safe_exec', 'simulate_taint_analysis', 'generate_exploit_poc']

# --- CONFIGURAÇÃO DE SEGURANÇA ---
SOURCES = {'input', 'sys.argv', 'environ', 'get_json', 'args', 'read'}
SINKS = {'eval', 'exec', 'os.system', 'subprocess.run', 'sub_run', 'sub_popen'}

def calculate_integrity_hash(root_path: Path) -> str:
    """Generates a deterministic SHA-256 hash of the core source code."""
    if not root_path.exists(): raise ValueError("Integrity Error: Root path missing.")
    hasher = hashlib.sha256()
    for path in sorted(root_path.rglob("*.py")):
        path_str = str(path).replace("\\", "/")
        ignored = ["venv", ".git", "__pycache__", ".doxoade_cache", "tests", "chief_dossier.json"]
        if any(x in path_str for x in ignored): continue
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
        except OSError: continue
    return hasher.hexdigest()

def simulate_taint_analysis(file_path: str) -> List[Dict]:
    """
    Advanced Taint Tracking Orchestrator (MPoT-4).
    Maps data flow from untrusted sources to dangerous sinks.
    """
    if not Path(file_path).is_file(): return []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        
        taint_map = _map_taint_sources(tree)
        return _audit_sinks_for_vulnerabilities(tree, taint_map)
        
    except Exception as e:
        logging.debug(f"Taint Analysis Skip {file_path}: {e}")
        return []

def _map_taint_sources(tree: ast.AST) -> Dict[str, str]:
    """Expert: Identifies variables assigned from untrusted sources."""
    tainted = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_id = getattr(node.value.func, 'id', None)
            if func_id in SOURCES:
                for target in node.targets:
                    if hasattr(target, 'id'): tainted[target.id] = func_id
    return tainted

def _audit_sinks_for_vulnerabilities(tree: ast.AST, taint_map: dict) -> List[Dict]:
    """Expert: Checks all sinks and classifies them as CONTROLLED or EXPLOITABLE."""
    vulns = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_id = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
            if func_id in SINKS:
                vulns.append(_classify_sink_node(node, func_id, taint_map))
    return vulns

def _classify_sink_node(node: ast.Call, func_id: str, taint_map: dict) -> Dict:
    """
    Classificador Sofisticado de Sinks (Aegis-Protocol).
    Analisa a composição de comandos para distinguir entre 
    automação legítima e risco de injeção.
    """
    trigger = None
    is_shell = False
    is_dynamic_cmd = False
    
    # 1. Busca por shell=True nos keywords
    for keyword in node.keywords:
        if keyword.arg == 'shell':
            if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                is_shell = True
            elif not isinstance(keyword.value, ast.Constant):
                is_shell = True # Dinâmico é considerado perigoso

    # 2. Analisa a composição do comando (primeiro argumento)
    if node.args:
        cmd_arg = node.args[0]
        # Se o comando não for uma lista de constantes, é dinâmico
        if not isinstance(cmd_arg, ast.List):
            is_dynamic_cmd = True
            
        # Rastreio de Taint (Veneno vindo de fontes externas)
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in taint_map:
                trigger = {'var': arg.id, 'origin': taint_map[arg.id]}

    # 3. Determinação de Status
    if trigger or (is_shell and is_dynamic_cmd):
        status = 'EXPLOITABLE'
    elif is_shell or is_dynamic_cmd:
        status = 'SUSPICIOUS' # Precisa de revisão humana
    else:
        status = 'CONTROLLED' # Lista fixa, shell=False

    return {
        'line': node.lineno, 
        'function': func_id,
        'trigger': trigger,
        'status': status,
        'impact': "ACE (Arbitrary Code Execution)" if func_id in ['eval', 'exec'] else "Command Injection",
        'details': {
            'shell': is_shell,
            'dynamic': is_dynamic_cmd
        }
    }

def generate_exploit_poc(function_name: str) -> str:
    """Generates a canary payload to prove vulnerability."""
    if function_name in ['eval', 'exec']:
        return "print('--- AEGIS BYPASS ATTEMPT ---')"
    return "whoami"

def restricted_safe_exec(code_str: str, globals_dict: Optional[dict] = None):
    """Executes code in a restricted sandbox with introspection block (Aegis)."""
    safe_globals = {"__builtins__": {}}
    if globals_dict: safe_globals.update(globals_dict)
    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                raise RuntimeError("Sandbox Breach: Dynamic imports are forbidden.")
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise RuntimeError(f"Sandbox Breach: Private access ({node.attr}) blocked.")

        compiled = compile(tree, filename="<sandbox>", mode="exec")
        exec(compiled, safe_globals) # noqa: B102
    except Exception as e:
        raise RuntimeError(f"Aegis Sandbox Blocked Execution: {e}")