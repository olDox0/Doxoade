# doxoade/probes/debug_probe.py
import sys
import os
import json
import traceback
import types

def _bootstrap(script_path):
    """Detecta a raiz do projeto e o nome correto do pacote (Aegis Ready)."""
    abs_path = os.path.abspath(script_path)
    
    # Encontra a última ocorrência da pasta do pacote para evitar duplicação (doxoade.doxoade)
    parts = abs_path.replace('\\', '/').split('/')
    
    # A raiz do projeto é onde o primeiro 'doxoade' aparece no caminho
    try:
        idx = parts.index('doxoade')
        project_root = "/".join(parts[:idx])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # O nome do pacote deve começar a partir do último 'doxoade' antes do script
        # para garantir que imports relativos '..' funcionem
        package_parts = []
        current = os.path.dirname(abs_path)
        while os.path.exists(os.path.join(current, '__init__.py')):
            package_parts.insert(0, os.path.basename(current))
            current = os.path.dirname(current)
            if os.path.basename(current) == 'doxoade':
                package_parts.insert(0, 'doxoade')
                break
        
        return ".".join(package_parts) if package_parts else None
    except ValueError:
        return None

def safe_serialize(obj, depth=0):
    if depth > 2: return "..."
    if isinstance(obj, (str, int, float, bool, type(None))): return obj
    if isinstance(obj, (list, tuple)): return [safe_serialize(x, depth+1) for x in obj[:5]]
    if isinstance(obj, dict): return {str(k): safe_serialize(v, depth+1) for k, v in list(obj.items())[:5]}
    return str(type(obj).__name__)

def run_debug(script_path):
    abs_path = os.path.abspath(script_path)
    package_name = _bootstrap(abs_path)
    
    debug_data = {'status': 'unknown', 'variables': {}, 'error': None}

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        from doxoade.tools.security_utils import restricted_safe_exec

        globs = {
            '__name__': '__main__',
            '__file__': abs_path,
            '__package__': package_name,
        }

        # Execução via Aegis com permissão de import para depuração de infra
        restricted_safe_exec(content, globs, allow_imports=True)
        
        debug_data['status'] = 'success'
        for k, v in globs.items():
            if not k.startswith('__') and not isinstance(v, types.ModuleType):
                debug_data['variables'][k] = safe_serialize(v)

    except Exception as e:
        debug_data['status'] = 'error'
        debug_data['error'] = str(e)
        _, _, tb = sys.exc_info()
        while tb.tb_next: tb = tb.tb_next
        frame = tb.tb_frame
        debug_data['traceback'] = traceback.format_exc()
        debug_data['line'] = tb.tb_lineno
        for k, v in frame.f_locals.items():
            if not k.startswith('__'):
                 debug_data['variables'][k] = safe_serialize(v)

    print("\n---DOXOADE-DEBUG-DATA---")
    print(json.dumps(debug_data, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_debug(sys.argv[1])