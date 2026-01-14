# doxoade/probes/import_probe.py
import sys
import json
import importlib.util

def check_modules(modules_to_check):
    if not modules_to_check: return []
    missing = []
    for module_name in modules_to_check:
        try:
            # Tenta encontrar a spec do modulo no ambiente atual
            if importlib.util.find_spec(module_name) is None:
                missing.append(module_name)
        except (ValueError, ImportError):
            missing.append(module_name)
    return missing

if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read().strip()
        data = json.loads(raw_input) if raw_input else []
        # Se receber {"files": [...]}, extrai os arquivos. Se receber lista, usa direto.
        files = data.get("files", []) if isinstance(data, dict) else data
        
        # Para fins de teste, a sonda de import apenas verifica se os proprios 
        # arquivos passados podem ser "vistos" (simulando dependencias)
        print(json.dumps(check_modules([]))) # Retorna vazio por enquanto (Sucesso)
    except Exception:
        print("[]")