# doxoade/doxoade/tools/aegis/aegis_utils.py
"""
Security & Integrity Utilities - Aegis Guard v2.3.
Hardened against introspection and taint injection.
Compliance: MPoT-4, MPoT-8, PASC-6.
"""
import hashlib
import ast
import sys
import logging
import os
import builtins
from pathlib import Path
from typing import List, Dict

from doxoade.tools.vulcan.meta_finder import install as vulcan_install
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

__all__ = ['calculate_integrity_hash', 'restricted_safe_exec', 'simulate_taint_analysis', 'generate_exploit_poc', 'validate_execution_context']
SOURCES = {'input', 'sys.argv', 'environ', 'get_json', 'args', 'read'}
SINKS = {'eval', 'exec', 'os.system', 'subprocess.run', 'sub_run', 'sub_popen'}
QUARANTINE_ZONES = ['tests/', 'regression_tests/', 'proposital_error_files/', 'old/', 'check_exame.py']
_AST_VALIDATION_CACHE = {}

def calculate_integrity_hash(root_path: Path) -> str:
    """Generates a deterministic SHA-256 hash of the core code."""
    if not root_path.exists():
        raise ValueError('Integrity Error: Root path missing.')
    hasher = hashlib.sha256()
    for path in sorted(root_path.rglob('*.py')):
        path_str = str(path).replace('\\', '/')
        ignored = ['venv', '.git', '__pycache__', '.doxoade_cache', 'tests', 'chief_dossier.json']
        if any((x in path_str for x in ignored)):
            continue
        try:
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hasher.update(chunk)
        except OSError as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            print(f'\x1b[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\x1b[0\n')
            exc_trace(exc_tb)
            continue
    return hasher.hexdigest()

def validate_execution_context(file_path: str, is_test_mode: bool):
    """
    Strict Access Control (Aegis Rule 19).
    Blocks execution of test artifacts in standard mode.
    """
    if not file_path:
        raise ValueError('Aegis Error: Null path provided.')
    norm_path = os.path.normpath(file_path).replace('\\', '/')
    is_quarantined = any((zone in norm_path for zone in QUARANTINE_ZONES))
    if is_quarantined and (not is_test_mode):
        file_name = os.path.basename(file_path)
        raise PermissionError(f"Aegis Access Denied: '{file_name}' is in quarantine.\n   > REASON: Running test artifacts in production mode is forbidden.\n   > ACTION: Use 'doxoade run <script> --test-mode' to authorize.")

def simulate_taint_analysis(file_path: str) -> List[Dict]:
    """Advanced Taint Tracking Orchestrator (MPoT-4)."""
    if not Path(file_path).is_file():
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        taint_map = _map_taint_sources(tree)
        return _audit_sinks_for_vulnerabilities(tree, taint_map)
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        print(f'\x1b[31m ■ Exception type: {e} ■ Exception value: {exc_obj}\x1b[0m\n')
        exc_trace(exc_tb)
        logging.debug(f'\nTaint Analysis Skip {file_path}: {e}')
        return []

def _map_taint_sources(tree: ast.AST) -> Dict[str, str]:
    """Identifies variables assigned from untrusted sources."""
    tainted = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func_id = getattr(node.value.func, 'id', None)
            if func_id in SOURCES:
                for target in node.targets:
                    if hasattr(target, 'id'):
                        tainted[target.id] = func_id
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
                vulns.append({'line': node.lineno, 'function': func_id, 'trigger': trigger, 'status': 'EXPLOITABLE' if trigger else 'CONTROLLED', 'impact': 'Arbitrary Code Execution' if func_id in ['eval', 'exec'] else 'Command Injection'})
    return vulns

def generate_exploit_poc(function_name: str) -> str:
    """Generates a canary payload to prove vulnerability."""
    return "print('--- AEGIS BYPASS ATTEMPT ---')" if function_name in ['eval', 'exec'] else 'whoami'

def restricted_safe_exec(code_input, globals_dict=None, **kwargs):
    """
    Executa código em sandbox com suporte ao NSR (Shadow Runtime).
    Garante que símbolos vacinados sejam exportados corretamente para o CLI.
    """
    import builtins as _builtins 
    
    # 1. Normalização de Parâmetros
    allow_imports = kwargs.get('allow_imports', False)
    filename = kwargs.get('filename', '<sandbox>')
    
    # [VITAL] target_context DEVE ser a referência direta ao dicionário do módulo
    # para que getattr(mod, 'save') funcione no cli.py
    if globals_dict is None:
        target_context = {}
    else:
        target_context = globals_dict

    # 2. Garantia de Builtins (Evita NameError: 'builtins' is not defined)
    if '__builtins__' not in target_context:
        if globals_dict is not None:
            target_context['__builtins__'] = _builtins.__dict__
        else:
            essential = ['__import__', 'print', 'len', 'range', 'dict', 'list', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'Exception', 'type', 'isinstance', 'open', 'getattr', 'setattr', 'hasattr']
            target_context['__builtins__'] = {k: getattr(_builtins, k) for k in essential if hasattr(_builtins, k)}

    compiled = None

    # --- CAMADA A: TRATAMENTO DE STRINGS (FLUXO PADRÃO) ---
    if isinstance(code_input, str):
        if not code_input.strip(): 
            return
            
        code_hash = hashlib.sha256(code_input.encode('utf-8')).hexdigest()
        cache_key = (code_hash, allow_imports)

        if cache_key in _AST_VALIDATION_CACHE:
            compiled = _AST_VALIDATION_CACHE[cache_key]
        else:
            tree = ast.parse(code_input, filename=filename)
            _validate_ast_safety(tree, allow_imports)
            compiled = compile(tree, filename=filename, mode='exec')
            _AST_VALIDATION_CACHE[cache_key] = compiled

    # --- CAMADA B: TRATAMENTO DE CODE OBJECTS (FLUXO NSR/SHADOW) ---
    else:
        compiled = code_input

    # --- CAMADA C: SETUP DE AMBIENTE E EXECUÇÃO ---
    abs_path = os.path.abspath(filename)
    project_anchor = _find_project_root(os.path.dirname(abs_path))
    old_cwd = os.getcwd()

    # Sincronia de Metadados
    target_context.setdefault('__file__', abs_path)
    target_context.setdefault('__name__', '__main__')

    try:
        os.chdir(project_anchor)
        
        # Injeta a raiz no path para que o Shadow encontre os submódulos
        import sys
        if project_anchor not in sys.path:
            sys.path.insert(0, project_anchor)
        
        # --- EXECUÇÃO FINAL (Aegis Core) ---
        from doxoade.tools.aegis.aegis_core import nexus_exec
        # NSR: Operamos diretamente no target_context para preencher o módulo
        return nexus_exec(compiled, target_context)

    except Exception as e:
        if isinstance(e, FileNotFoundError):
            print(f'\x1b[33m   [!] Erro de Caminho: {e.filename}\x1b[0m')
        _handle_sandbox_exception(e)
        raise
    finally:
        os.chdir(old_cwd)

def _inject_target_environment(file_path: str):
    """Injeta caminhos do projeto no sys.path de forma limpa."""
    target_dir = os.path.dirname(os.path.abspath(file_path))
    if target_dir not in sys.path:
        sys.path.insert(0, target_dir)
    current = target_dir
    while current != os.path.dirname(current):
        venv_path = os.path.join(current, 'venv')
        if os.path.exists(venv_path):
            sp = os.path.join(venv_path, 'Lib', 'site-packages') if os.name == 'nt' else os.path.join(venv_path, 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages')
            if os.path.exists(sp) and sp not in sys.path:
                sys.path.insert(1, sp)
            break
        current = os.path.dirname(current)

def _get_safe_builtins(allow_imports: bool) -> dict:
    """Configura o dicionário de builtins permitido (PASC 8.12)."""
    import builtins
    if allow_imports:
        return builtins.__dict__.copy()
    essential = ['__import__', '__build_class__', 'print', 'len', 'range', 'dict', 'list', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'Exception', 'type', 'isinstance', 'iter', 'next', 'enumerate', 'zip', 'open', 'getattr', 'setattr', 'hasattr', 'repr']
    safe = {k: getattr(builtins, k) for k in essential if hasattr(builtins, k)}
    safe['sys'], safe['os'] = (sys, os)
    return safe

def _validate_ast_safety(tree: ast.AST, allow_imports: bool):
    """Filtro Semântico Aegis."""
    for node in ast.walk(tree):
        if not allow_imports and isinstance(node, (ast.Import, ast.ImportFrom)):
            raise RuntimeError('Sandbox Breach: Dynamic imports forbidden.')
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            forbidden = {'__subclasses__', '__globals__', '__builtins__', '__code__'}
            if node.attr in forbidden:
                raise RuntimeError('Sandbox Breach: Private access blocked.')

def _handle_sandbox_exception(e, filename=None):
    """Dispatcher Forense."""
    if isinstance(e, OSError) and "access violation" in str(e).lower():
        sys.stderr.write(f"\n{Fore.RED}🛡️  [AEGIS] Bloqueio de Segurança: Violação Proibida.{Style.RESET_ALL}\n")
        return # Deixa o sinal fluir para o Lazarus
    if isinstance(e, (NameError, ImportError, ModuleNotFoundError, SyntaxError)):
        raise e
    import os as _os
    _, _, exc_tb = sys.exc_info()
    f_name = _os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else 'unknown'
    line_n = exc_tb.tb_lineno if exc_tb else 0
    msg = f'\x1b[1;34m\n[ FORENSIC:AEGIS ]\x1b[0m \x1b[1mFile: {f_name} | L: {line_n}\x1b[0m\n'
    msg += f'\x1b[31m    ■ Exception: {type(e).__name__} | Value: {e}\x1b[0m'
    print(msg)
    raise RuntimeError(f'Aegis Sandbox Blocked: {e}')
