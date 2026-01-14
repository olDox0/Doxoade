# doxoade/probes/clone_probe.py
import ast
import hashlib
import sys
import json
import os
import copy

class StructuralNormalizer(ast.NodeTransformer):
    """
    Normaliza a AST focando na ESTRUTURA, ignorando nomes de variáveis.
    """
    def __init__(self):
        self.name_map = {}
        self.arg_counter = 0
        self.var_counter = 0

    def visit_FunctionDef(self, node):
        # Remove docstrings para a normalização
        if ast.get_docstring(node):
            if len(node.body) > 0 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                node.body.pop(0)
        
        # Remove anotações e decorators
        node.returns = None
        node.decorator_list = []
        
        # Anonimiza o nome da função
        node.name = "_anonymous"
        
        self._map_arguments(node.args)
        self.generic_visit(node)
        return node

    def _map_arguments(self, args_node):
        for arg in args_node.args:
            arg.annotation = None
            new_name = f"arg_{self.arg_counter}"
            self.name_map[arg.arg] = new_name
            arg.arg = new_name
            self.arg_counter += 1
        if args_node.vararg:
            args_node.vararg.annotation = None
            new_name = f"arg_{self.arg_counter}"
            self.name_map[args_node.vararg.arg] = new_name
            args_node.vararg.arg = new_name
            self.arg_counter += 1

    def visit_Name(self, node):
        if node.id in self.name_map:
            node.id = self.name_map[node.id]
        elif isinstance(node.ctx, ast.Store):
            new_name = f"var_{self.var_counter}"
            self.name_map[node.id] = new_name
            node.id = new_name
            self.var_counter += 1
        return node

    def visit_arg(self, node):
        node.annotation = None
        return node

def get_structural_hash(node):
    """Gera hash baseado em uma CÓPIA anonimizada da estrutura."""
    node_copy = copy.deepcopy(node)
    normalizer = StructuralNormalizer()
    normalized_node = normalizer.visit(node_copy)
    dump = ast.dump(normalized_node, include_attributes=False)
    return hashlib.sha256(dump.encode('utf-8')).hexdigest()

def is_trivial_or_config(node):
    """
    Verifica se a função deve ser ignorada:
    1. Se é um @click.group ou @*.group
    2. Se o corpo é apenas 'pass' ou '...' (placeholder)
    """
    # 1. Filtro de Decorator (Evita Click Groups)
    for decorator in node.decorator_list:
        # Lida com @click.group() -> Call
        if isinstance(decorator, ast.Call):
            func = decorator.func
        else:
            func = decorator
            
        # Verifica atributo .group (ex: click.group, cli.group)
        if isinstance(func, ast.Attribute) and func.attr == 'group':
            return True
        # Verifica nome direto (ex: @group)
        if isinstance(func, ast.Name) and func.id == 'group':
            return True

    # 2. Filtro de Corpo Trivial (Placeholder)
    # Filtra docstrings manualmente para checar o que sobra
    effective_body = [
        stmt for stmt in node.body 
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
    ]
    
    # Se não sobrou nada ou só tem 'pass', ignora
    if not effective_body:
        return True
    
    if len(effective_body) == 1:
        stmt = effective_body[0]
        # É 'pass'?
        if isinstance(stmt, ast.Pass):
            return True
        # É '...' (Ellipsis)?
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
            return True
            
    return False

def find_clones(files):
    hashes = {}
    clones = []

    for file_path in files:
        c_path = file_path.replace('\\', '/').lower() # Garante paridade
        if not os.path.exists(c_path): continue
        
        try:
            with open(c_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=file_path)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Ignora métodos mágicos
                    if node.name.startswith('__') and node.name.endswith('__'): continue
                    
                    # --- NOVO FILTRO INTELIGENTE ---
                    if is_trivial_or_config(node):
                        continue
                    # -------------------------------

                    func_hash = get_structural_hash(node)
                    
                    if func_hash not in hashes:
                        hashes[func_hash] = []
                    
                    hashes[func_hash].append({
                        'file': c_path, # Guarda o canônico
                        'line': node.lineno,
                        'name': node.name
                    })
        except Exception:
            continue

    for h, occurrences in hashes.items():
        if len(occurrences) > 1:
            files_set = {o['file'] for o in occurrences}
            is_cross_file = len(files_set) > 1
            severity = "WARNING" if is_cross_file else "INFO"
            
            names_found = list({o['name'] for o in occurrences})
            names_str = ", ".join(names_found)
            locations = [f"{os.path.basename(o['file'])}:{o['line']}" for o in occurrences]
            
            msg = f"Lógica duplicada (Hash {h[:6]}). Funções: [{names_str}]."
            if is_cross_file:
                details = f"Duplicação detectada em múltiplos arquivos: {', '.join(locations)}. Considere mover para shared_tools."
            else:
                details = f"Duplicação interna no mesmo arquivo: {locations[0]}."

            for occ in occurrences:
                clones.append({
                    'severity': severity,
                    'category': 'DUPLICATION',
                    'message': msg,
                    'file': occ['file'],
                    'line': occ['line'],
                    'details': details
                })

    return clones

# No final de ambos os arquivos:
if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print("[]")
        else:
            data = json.loads(raw_input)
            # Suporta tanto lista direta quanto dicionário de contexto
            files = data.get("files", []) if isinstance(data, dict) else data
            
            # Chama a função principal correspondente
            # (find_clones para clone_probe ou analyze_orphans para orphan_probe)
            if "clone" in sys.argv[0]:
                print(json.dumps(find_clones(files)))
            else:
                print(json.dumps(analyze_orphans(files)))
    except Exception:
        print("[]")