# doxoade/doxoade/probes/orphan_probe.py
"""
Orphan Probe - Detector de Funções Órfãs
=========================================
Identifica funções que:
1. Não são chamadas em nenhum arquivo do projeto
2. Não são exportadas (__all__)
3. Não são comandos CLI (decoradores @click.command)
4. Não são métodos mágicos (__init__, __str__, etc)
"""
import ast
import sys
import json
import os

class FunctionIndexer(ast.NodeVisitor):
    """Indexa todas as definições de funções."""

    def __init__(self, file_path):
        self.file_path = file_path
        self.definitions = []

    def visit_FunctionDef(self, node):
        if node.name.startswith('__') and node.name.endswith('__'):
            self.generic_visit(node)
            return
        is_cli_command = any((isinstance(d, ast.Call) and hasattr(d.func, 'attr') and (d.func.attr in ['command', 'group']) or (isinstance(d, ast.Attribute) and d.attr in ['command', 'group']) for d in node.decorator_list))
        self.definitions.append({'name': node.name, 'line': node.lineno, 'file': self.file_path, 'is_cli': is_cli_command, 'is_private': node.name.startswith('_')})
        self.generic_visit(node)

class CallTracker(ast.NodeVisitor):
    """Rastreia todas as chamadas de função."""

    def __init__(self):
        self.calls = set()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
        self.generic_visit(node)

class ExportChecker(ast.NodeVisitor):
    """Verifica se uma função está em __all__."""

    def __init__(self):
        self.exported = set()

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == '__all__':
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant):
                            self.exported.add(elt.value)
        self.generic_visit(node)

def analyze_orphans(files):
    """
    Análise principal: encontra funções órfãs.
    
    Args:
        files: Lista de caminhos de arquivos Python
        
    Returns:
        Lista de findings com funções órfãs detectadas
    """
    all_definitions = []
    all_calls = set()
    all_exports = set()
    for file_path in files:
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content, filename=file_path)
            indexer = FunctionIndexer(file_path)
            indexer.visit(tree)
            all_definitions.extend(indexer.definitions)
            tracker = CallTracker()
            tracker.visit(tree)
            all_calls.update(tracker.calls)
            exporter = ExportChecker()
            exporter.visit(tree)
            all_exports.update(exporter.exported)
        except Exception:
            continue
    orphans = []
    for defn in all_definitions:
        func_name = defn['name']
        if defn['is_cli']:
            continue
        if func_name in all_exports:
            continue
        if func_name in all_calls:
            continue
        if func_name.startswith('test_'):
            continue
        if func_name in ['setUp', 'tearDown', 'setUpClass', 'tearDownClass']:
            continue
        severity = 'WARNING' if defn['is_private'] else 'INFO'
        category = 'DEADCODE' if not defn['is_private'] else 'UNUSED-PRIVATE'
        orphans.append({'severity': severity, 'category': category, 'message': f"Função '{func_name}' não é chamada em nenhum lugar do projeto.", 'file': defn['file'], 'line': defn['line'], 'details': 'Considere remover ou documentar se for API pública/futura.'})
    return orphans

def main():
    """Entry point quando executado como probe standalone."""
    try:
        input_data = sys.stdin.read()
        if not input_data:
            print('[]')
            return
        files = json.loads(input_data)
        findings = analyze_orphans(files)
        print(json.dumps(findings))
    except Exception:
        print('[]')
        sys.exit(0)
if __name__ == '__main__':
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print('[]')
        else:
            data = json.loads(raw_input)
            files = data.get('files', []) if isinstance(data, dict) else data
            print(json.dumps(analyze_orphans(files)))
    except Exception as e:
        sys.stderr.write(f'ProbeError:Orphan:{str(e)}')
        print('[]')