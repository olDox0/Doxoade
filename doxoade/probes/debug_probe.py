# doxoade/probes/debug_probe.py
import sys
import os
import json
import traceback
import types

def safe_serialize(obj, depth=0):
    """Converte objetos complexos em representações seguras para JSON."""
    if depth > 2: return "..."
    
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(x, depth+1) for x in obj[:10]] # Limita tamanho
    if isinstance(obj, dict):
        return {str(k): safe_serialize(v, depth+1) for k, v in list(obj.items())[:10]}
    if isinstance(obj, types.FunctionType):
        return f"<function {obj.__name__}>"
    if isinstance(obj, types.ModuleType):
        return f"<module {obj.__name__}>"
    
    # Fallback genérico
    try:
        return str(obj)
    except:
        return "<unserializable>"

def run_debug(script_path):
    abs_path = os.path.abspath(script_path)
    sys.path.insert(0, os.path.dirname(abs_path))
    
    debug_data = {
        'status': 'unknown',
        'variables': {},
        'functions': [],
        'error': None,
        'traceback': None
    }

    try:
        # Executa o script em um contexto isolado
        globs = {'__name__': '__main__', '__file__': abs_path}
        with open(abs_path, 'rb') as f:
            code = compile(f.read(), abs_path, 'exec')
            exec(code, globs)
        
        # SUCESSO: Captura estado global final
        debug_data['status'] = 'success'
        for k, v in globs.items():
            if not k.startswith('__'):
                if isinstance(v, types.FunctionType):
                    debug_data['functions'].append(k)
                elif not isinstance(v, types.ModuleType):
                    debug_data['variables'][k] = safe_serialize(v)

    except Exception:
        # FALHA: Captura estado local do erro
        etype, value, tb = sys.exc_info()
        debug_data['status'] = 'error'
        debug_data['error'] = f"{etype.__name__}: {value}"
        # Pega o último frame (onde o erro ocorreu no script do usuário)
        # Precisamos filtrar frames do próprio probe
        while tb.tb_next:
            tb = tb.tb_next
            
        frame = tb.tb_frame
        debug_data['traceback'] = traceback.format_exc()
        
        # Captura variáveis locais no momento da morte
        for k, v in frame.f_locals.items():
            if not k.startswith('__'):
                 debug_data['variables'][k] = safe_serialize(v)

    # Imprime o marcador especial e o JSON para o processo pai pegar
    print("\n---DOXOADE-DEBUG-DATA---")
    print(json.dumps(debug_data))

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    run_debug(sys.argv[1])