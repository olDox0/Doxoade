# -*- coding: utf-8 -*-
# doxoade/tools/security_utils.py
"""
Security & Integrity Utilities - Aegis Guard v2.3.
Hardened against introspection and taint injection.
Compliance: MPoT-4, MPoT-8, PASC-6.
"""
import hashlib
import ast
import logging
import os  # FIX: Adicionado import global essencial
from colorama import Fore
from pathlib import Path
from typing import Optional, List, Dict

__all__ = ['calculate_integrity_hash', 'restricted_safe_exec', 'simulate_taint_analysis', 'generate_exploit_poc', 'validate_execution_context']

# --- CONFIGURAÇÃO DE SEGURANÇA ---
SOURCES = {'input', 'sys.argv', 'environ', 'get_json', 'args', 'read'}
SINKS = {'eval', 'exec', 'os.system', 'subprocess.run', 'sub_run', 'sub_popen'}
QUARANTINE_ZONES = ["tests/", "regression_tests/", "proposital_error_files/", "old/", "check_exame.py"]

def calculate_integrity_hash(root_path: Path) -> str:
    """Generates a deterministic SHA-256 hash of the core code."""
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
        except OSError as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f"\033[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n")
            exc_trace(exc_tb)
            continue
            
    return hasher.hexdigest()

def validate_execution_context(file_path: str, is_test_mode: bool):
    """
    Strict Access Control (Aegis Rule 19).
    Blocks execution of test artifacts in standard mode.
    """
    if not file_path:
        raise ValueError("Aegis Error: Null path provided.")

    norm_path = os.path.normpath(file_path).replace("\\", "/")
    is_quarantined = any(zone in norm_path for zone in QUARANTINE_ZONES)

    if is_quarantined and not is_test_mode:
        # PASC-6.2: Verbosidade na mensagem de erro
        file_name = os.path.basename(file_path)
        raise PermissionError(
            f"Aegis Access Denied: '{file_name}' is in quarantine.\n"
            "   > REASON: Running test artifacts in production mode is forbidden.\n"
            "   > ACTION: Use 'doxoade run <script> --test-mode' to authorize."
        )

def simulate_taint_analysis(file_path: str) -> List[Dict]:
    """Advanced Taint Tracking Orchestrator (MPoT-4)."""
    if not Path(file_path).is_file(): return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        taint_map = _map_taint_sources(tree)
        return _audit_sinks_for_vulnerabilities(tree, taint_map)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n")
        exc_trace(exc_tb)
        logging.debug(f"\nTaint Analysis Skip {file_path}: {e}")
        return []

def _map_taint_sources(tree: ast.AST) -> Dict[str, str]:
    """Identifies variables assigned from untrusted sources."""
    tainted = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_id = getattr(node.value.func, 'id', None)
            if func_id in SOURCES:
                for target in node.targets:
                    if hasattr(target, 'id'): tainted[target.id] = func_id
    return tainted

def _audit_sinks_for_vulnerabilities(tree: ast.AST, taint_map: dict) -> List[Dict]:
    """Checks and classifies sinks for transparency (PASC-6.2)."""
    vulns = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_id = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
            if func_id in SINKS:
                trigger = None
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id in taint_map:
                        trigger = {'var': arg.id, 'origin': taint_map[arg.id]}
                
                vulns.append({
                    'line': node.lineno, 'function': func_id,
                    'trigger': trigger,
                    'status': 'EXPLOITABLE' if trigger else 'CONTROLLED',
                    'impact': "Arbitrary Code Execution" if func_id in ['eval', 'exec'] else "Command Injection"
                })
    return vulns

def generate_exploit_poc(function_name: str) -> str:
    """Generates a canary payload to prove vulnerability."""
    return "print('--- AEGIS BYPASS ATTEMPT ---')" if function_name in ['eval', 'exec'] else "whoami"

def restricted_safe_exec(code_str: str, globals_dict: Optional[dict] = None, allow_imports: bool = False):
    import builtins
    import sys
    import os

    safe_builtins = {}
    if allow_imports:
        # Injeção de funções e módulos essenciais para o Core
        essential = [
            '__import__', '__build_class__', 'print', 'len', 'range', 'dict', 
            'list', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'Exception', 
            'type', 'isinstance', 'iter', 'next', 'enumerate', 'zip', 'open',
            'getattr', 'setattr', 'hasattr', 'repr'
        ]

        for func in essential:
            if hasattr(builtins, func):
                safe_builtins[func] = getattr(builtins, func)
        
        # Módulos de sistema precisam estar acessíveis nos builtins para scripts do Core
        safe_builtins['sys'] = sys
        safe_builtins['os'] = os

    safe_globals = {"__builtins__": safe_builtins}
    if globals_dict:
        safe_globals.update(globals_dict)
    
    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if not allow_imports and isinstance(node, (ast.Import, ast.ImportFrom)):
                raise RuntimeError("Sandbox Breach: Dynamic imports forbidden.")
            
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                allowed = {
                    '__name__', '__file__', '__package__', '__path__', # __path__ é VITAL
                    '__module__', '__loader__', '__spec__', '__dict__',
                    '__all__', '__class__', '__init__', '__str__', '__repr__', 
                    '__enter__', '__exit__', '__call__', '__mro__', '__bases__'
                }
                if node.attr not in allowed:
                    raise RuntimeError(f"Sandbox Breach: Private access ({node.attr}) blocked.")

        compiled = compile(tree, filename="<sandbox>", mode="exec")
        # Injeção segura
        exec(compiled, safe_globals) # noqa: B102
        
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\n")
        exc_trace(exc_tb)
        raise RuntimeError(f"\nAegis Sandbox Blocked: {e}")
