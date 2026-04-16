# doxoade/doxoade/commands/impact_systems/impact_logic.py
import os
import ast
import click
from typing import Dict, List
from doxoade.tools.streamer import ufs
from .impact_utils import path_to_module_name, resolve_relative_import
from .impact_state import ImpactState
from doxoade.tools.filesystem import get_file_metadata

class ImpactVisitor(ast.NodeTransformer):

    def __init__(self, current_module):
        super().__init__()
        self.imports = set()
        self.calls = set()
        self.defines = {}
        self.current_module = current_module
        self._current_func = None
        self._call_count = 0

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        return node

    def visit_ImportFrom(self, node):
        resolved = resolve_relative_import(node.module, node.level, self.current_module)
        if resolved:
            self.imports.add(resolved)
        return node

    def visit_FunctionDef(self, node):
        func_name = node.name
        self.defines[func_name] = {'line': node.lineno, 'calls': []}
        old_ctx = self._current_func
        self._current_func = func_name
        self.generic_visit(node)
        self._current_func = old_ctx
        return node

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_Call(self, node):
        self._call_count += 1
        if self._call_count > 1000:
            return node
        name = ''
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name:
            self.calls.add(name)
            if self._current_func:
                self.defines[self._current_func]['calls'].append(name)
        return self.generic_visit(node)

def build_project_index(search_path: str, ignore_patterns: set, old_index: dict) -> dict:
    """Mapeamento Diferencial Otimizado (Zero I/O Duplicado)."""
    new_index = {}
    from doxoade.dnm import DNM
    dnm = DNM(search_path)
    all_files = dnm.scan(extensions=['py'])
    files_to_process = []
    for fp in all_files:
        mod_name = path_to_module_name(fp, search_path)
        mtime, size = get_file_metadata(fp)
        cached = old_index.get(mod_name)
        if cached and cached.get('mtime') == mtime and (cached.get('size') == size):
            new_index[mod_name] = cached
            continue
        files_to_process.append((fp, mod_name, mtime, size))
    if not files_to_process:
        return new_index
    with click.progressbar(files_to_process, label='Sincronizando Nexus Index') as bar:
        for fp, mod_name, mtime, size in bar:
            try:
                lines = ufs.get_lines(fp)
                if not lines:
                    continue
                content = ''.join(lines)
                tree = ast.parse(content)
                v = ImpactVisitor(mod_name)
                v.visit(tree)
                new_index[mod_name] = {'path': os.path.relpath(fp, search_path), 'mtime': mtime, 'size': size, 'imports': list(v.imports), 'calls': list(v.calls), 'defines': list(v.defines.keys()), 'metadata': v.defines}
            except Exception as e:
                new_index[mod_name] = {'path': os.path.relpath(fp, search_path), 'error': str(e), 'imports': [], 'calls': [], 'defines': [], 'metadata': {}}
                continue
    return new_index

def get_external_consumers(state: ImpactState, func_filter: str=None) -> List[Dict]:
    consumers = []
    target = state.target_module
    target_defines = state.get_defined_functions()
    for mod, data in state.index.items():
        if mod == target:
            continue
        if target in data.get('imports', []):
            hits = set(data.get('calls', [])).intersection(target_defines)
            if func_filter:
                hits = {h for h in hits if h == func_filter}
            if hits:
                consumers.append({'path': data['path'], 'calls': sorted(list(hits))})
    return consumers
