# doxoade/probes/clone_probe.py
import sys
import json
import ast
import hashlib
from collections import defaultdict

def normalize_and_hash(func_node):
    """
    Gera um hash da função. Tenta ser agnóstico a formatação.
    """
    # 1. Remove Docstring
    body_nodes = func_node.body
    if body_nodes and isinstance(body_nodes[0], ast.Expr) and \
       isinstance(body_nodes[0].value, ast.Constant) and \
       isinstance(body_nodes[0].value.value, str):
        body_nodes = body_nodes[1:]

    # Ignora funções muito pequenas
    if len(body_nodes) < 2: # Reduzi para 2 para garantir que pegue o teste
        return None

    normalized_code = ""
    
    # 2. Tenta usar ast.unparse (Python 3.9+)
    if hasattr(ast, 'unparse'):
        for node in body_nodes:
            normalized_code += ast.unparse(node)
    else:
        # Fallback para Python < 3.9 (usa representação da árvore)
        # sys.stderr.write(f"[DEBUG] Fallback ast.dump para {func_node.name}\n")
        for node in body_nodes:
            normalized_code += ast.dump(node)

    if not normalized_code:
        return None

    # 3. Gera Hash
    return hashlib.md5(normalized_code.encode('utf-8')).hexdigest()

def analyze_clones(files):
    registry = defaultdict(list)
    processed_count = 0
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content)
            processed_count += 1
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith('__') and node.name.endswith('__'):
                        continue
                        
                    func_hash = normalize_and_hash(node)
                    if func_hash:
                        registry[func_hash].append({
                            'file': file_path,
                            'line': node.lineno,
                            'name': node.name
                        })
        except Exception as e:
            sys.stderr.write(f"[WARN] Falha ao ler {file_path}: {e}\n")
            continue

    # Debug info para stderr (Check.py vai capturar se usar --debug)
    if processed_count == 0:
        sys.stderr.write("[INFO] Nenhum arquivo foi processado com sucesso.\n")

    duplicates = []
    for f_hash, occurrences in registry.items():
        if len(occurrences) > 1:
            duplicates.append(occurrences)
            
    return duplicates

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read()
        if not input_data:
            print("[]")
            sys.exit(0)
            
        files_to_check = json.loads(input_data)
        
        # Debug: Avisa quantos arquivos recebeu
        # sys.stderr.write(f"[INFO] CloneProbe recebeu {len(files_to_check)} arquivos.\n")
        
        results = analyze_clones(files_to_check)
        print(json.dumps(results))
    except Exception as e:
        sys.stderr.write(f"Clone Probe Error: {e}\n")
        print("[]")
        sys.exit(1)