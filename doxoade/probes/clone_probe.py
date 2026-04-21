# doxoade/doxoade/probes/clone_probe.py
import sys
import os
import json
import hashlib
import copy
import binascii
import ast
from doxoade.tools.vulcan.bridge import vulcan_bridge

class StructuralNormalizer(ast.NodeTransformer):
    """Normaliza a AST focando na ESTRUTURA (MPoT-1)."""

    def __init__(self):
        self.name_map = {}
        self.arg_counter = 0
        self.var_counter = 0

    def visit_FunctionDef(self, node):
        if ast.get_docstring(node):
            if len(node.body) > 0 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                node.body.pop(0)
        node.returns = None
        node.decorator_list = []
        node.name = '_anonymous'
        for arg in node.args.args:
            arg.annotation = None
            new_name = f'arg_{self.arg_counter}'
            self.name_map[arg.arg] = new_name
            arg.arg = new_name
            self.arg_counter += 1
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if node.id in self.name_map:
            node.id = self.name_map[node.id]
        elif isinstance(node.ctx, ast.Store):
            new_name = f'var_{self.var_counter}'
            self.name_map[node.id] = new_name
            node.id = new_name
            self.var_counter += 1
        return node

def find_clones_turbo(hashes_list):
    """Ponte C-Level."""
    v_mod = vulcan_bridge.get_optimized_module('vulcan_dry')
    if v_mod and hasattr(v_mod, 'find_duplicate_signatures'):
        raw_buffer = bytearray()
        for h in hashes_list:
            try:
                raw_buffer.extend(binascii.unhexlify(h['hash']))
            except Exception:
                continue
        indices = v_mod.find_duplicate_signatures(raw_buffer, 32)
        return [(hashes_list[i], hashes_list[j]) for i, j in indices]
    return None

def find_clones(files: list) -> list:
    """Orquestrador Central."""
    hashes_dict = {}
    for f_path in files:
        _process_file_for_hashes(f_path, hashes_dict)
    flat_hashes = []
    for h_val, occurrences in hashes_dict.items():
        for occ in occurrences:
            flat_hashes.append({'hash': h_val, 'file': occ['file'], 'line': occ['line'], 'name': occ['name']})
    results = find_clones_turbo(flat_hashes)
    if results:
        return _format_results(results)
    clones = []
    for h_val, occurrences in hashes_dict.items():
        if len(occurrences) > 1:
            clones.extend(_generate_clone_findings(h_val, occurrences))
    return []

def get_structural_hash(node):
    node_copy = copy.deepcopy(node)
    normalized = StructuralNormalizer().visit(node_copy)
    dump = ast.dump(normalized, include_attributes=False)
    return hashlib.sha256(dump.encode('utf-8')).hexdigest()

def _process_file_for_hashes(file_path: str, hashes: dict):
    if not os.path.exists(file_path):
        return
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and (not node.name.startswith('__')):
                h = get_structural_hash(node)
                if h not in hashes:
                    hashes[h] = []
                hashes[h].append({'file': file_path, 'line': node.lineno, 'name': node.name, 'hash': h})
    except Exception:
        pass

def _generate_clone_findings(h_val, occurrences):
    return [{'severity': 'INFO', 'category': 'DUPLICATION', 'message': f"Lógica duplicada (Hash {h_val[:6]}). Funções: {o['name']}", 'file': o['file'], 'line': o['line']} for o in occurrences]

def _format_results(results_list):
    return [{'severity': 'INFO', 'category': 'DUPLICATION', 'message': f"Match Vulcan: {a['name']} == {b['name']}", 'file': a['file'], 'line': a['line']} for a, b in results_list]
if __name__ == '__main__':
    try:
        raw_in = sys.stdin.read().strip()
        data = json.loads(raw_in) if raw_in else {'files': []}
        print(json.dumps(find_clones(data.get('files', []))))
    except Exception:
        print('[]')
