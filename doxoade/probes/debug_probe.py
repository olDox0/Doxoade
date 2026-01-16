# doxoade/probes/debug_probe.py
import sys
import os
import json
import traceback
import types

# [FIX] Força UTF-8 no stdout para suportar emojis no Windows (Protocolo anti-cp1252)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
def safe_serialize(obj, depth=0):
    """Converte objetos complexos em representações seguras para JSON."""
    if depth > 2: return "..."
    
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(x, depth+1) for x in obj[:10]]
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v, depth+1) for k, v in list(obj.items())[:10]}
    if isinstance(obj, types.FunctionType):
        return f"<function {obj.__name__}>"
    if isinstance(obj, types.ModuleType):
        return f"<module {obj.__name__}>"
    
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"

def _setup_package_context(script_path):
    """
    Mágica para permitir imports relativos (from ..tools import x).
    Sobe a árvore de diretórios procurando __init__.py para definir o pacote.
    """
    abs_path = os.path.abspath(script_path)
    directory = os.path.dirname(abs_path)
    package_parts = []

    # Sobe enquanto encontrar __init__.py
    current = directory
    while os.path.exists(os.path.join(current, '__init__.py')):
        package_parts.insert(0, os.path.basename(current))
        parent = os.path.dirname(current)
        if parent == current: # Evita loop infinito na raiz do disco
            break
        current = parent
    
    # O 'current' agora é a raiz do projeto (onde o pacote começa)
    # Adicionamos ao sys.path para o Python achar os módulos
    if current not in sys.path:
        sys.path.insert(0, current)
    
    # Retorna o nome do pacote (ex: "doxoade.commands")
    return ".".join(package_parts) if package_parts else None

def run_debug(script_path):
    """Analisa o estado de um script sob o Lazarus Protocol (Aegis)."""
    if not script_path: raise ValueError("script_path required.")
    
    abs_path = os.path.abspath(script_path)
    package_name = _setup_package_context(abs_path)
    
    debug_data = {'status': 'unknown', 'variables': {}, 'functions': [], 'error': None}

    try:
        # Executa o script injetando o __package__ correto
        globs = {
            '__name__': '__main__', 
            '__file__': abs_path,
            '__package__': package_name  # <--- A CHAVE DA CORREÇÃO
        }
        
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            code = compile(f.read(), abs_path, 'exec')
            exec(code, globs) # noqa
        from ..tools.security_utils import restricted_safe_exec
        restricted_safe_exec(content, globs)
        
        debug_data['status'] = 'success'
        for k, v in globs.items():
            if not k.startswith('__'):
                if isinstance(v, types.FunctionType):
                    debug_data['functions'].append(k)
                elif not isinstance(v, types.ModuleType):
                    debug_data['variables'][k] = safe_serialize(v)

    except Exception as e:
        debug_data['status'] = 'error'
        debug_data['error'] = str(e)
        etype, value, tb = sys.exc_info()
        
        # Filtra frames do probe para mostrar onde errou no script do usuário
        while tb.tb_next:
            tb = tb.tb_next
            
        frame = tb.tb_frame
        debug_data['traceback'] = traceback.format_exc()
        
        for k, v in frame.f_locals.items():
            if not k.startswith('__'):
                 debug_data['variables'][k] = safe_serialize(v)

    print("\n---DOXOADE-DEBUG-DATA---")
    print(json.dumps(debug_data))

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    run_debug(sys.argv[1])