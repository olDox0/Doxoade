# -*- coding: utf-8 -*-
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

def is_trivial_or_config(node: ast.FunctionDef) -> bool:
    """Verifica se a função deve ser ignorada por ser configuração ou vazia."""
    if _has_ignored_decorator(node): return True
    return _is_body_placeholder(node)

def _has_ignored_decorator(node):
    for d in node.decorator_list:
        func = d.func if isinstance(d, ast.Call) else d
        if isinstance(func, (ast.Attribute, ast.Name)):
            name = getattr(func, 'attr', getattr(func, 'id', ''))
            if name == 'group': return True
    return False

def _is_body_placeholder(node):
    body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, (ast.Constant, ast.Str)))]
    if not body: return True
    if len(body) == 1:
        s = body[0]
        if isinstance(s, ast.Pass): return True
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis: return True
    return False

def find_clones(files: list) -> list:
    """Orquestrador de busca de duplicatas (CC: 3)."""
    hashes = {}
    for f_path in files:
        _process_file_for_hashes(f_path, hashes)
    
    clones = []
    for h_val, occurrences in hashes.items():
        if len(occurrences) > 1:
            clones.extend(_generate_clone_findings(h_val, occurrences))
    return clones

def _process_file_for_hashes(file_path: str, hashes: dict):
    """Especialista: Varre um arquivo e extrai assinaturas estruturais."""
    c_path = file_path.replace('\\', '/').lower()
    if not os.path.exists(c_path): return

    try:
        with open(c_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=file_path)
            
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('__') or is_trivial_or_config(node):
                    continue
                
                h = get_structural_hash(node)
                if h not in hashes: hashes[h] = []
                hashes[h].append({'file': c_path, 'line': node.lineno, 'name': node.name})
    except Exception: pass

def _generate_clone_findings(h_val: str, occurrences: list) -> list:
    """Especialista: Transforma colisões de hash em alertas do linter."""
    files_set = {o['file'] for o in occurrences}
    is_cross = len(files_set) > 1
    
    names = ", ".join(list({o['name'] for o in occurrences}))
    locs = [f"{os.path.basename(o['file'])}:{o['line']}" for o in occurrences]
    
    msg = f"Lógica duplicada (Struc-Hash {h_val[:6]}). Funções: [{names}]."
    details = f"Detecção em: {', '.join(locs)}."
    
    return [{
        'severity': 'WARNING' if is_cross else 'INFO',
        'category': 'DUPLICATION',
        'message': msg,
        'file': occ['file'],
        'line': occ['line'],
        'details': details
    } for occ in occurrences]

# No final de ambos os arquivos:
if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read().strip()
        data = json.loads(raw_input) if raw_input else []
        files = data.get("files", []) if isinstance(data, dict) else data
        print(json.dumps(find_clones(files)))
    except Exception:
        print("[]")