# doxoade/probes/orphan_probe.py
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
# [DOX-UNUSED] from pathlib import Path

class FunctionIndexer(ast.NodeVisitor):
    """Indexa todas as definições de funções."""
    def __init__(self, file_path):
        self.file_path = file_path
        self.definitions = []
        
    def visit_FunctionDef(self, node):
        # Ignora métodos mágicos
        if node.name.startswith('__') and node.name.endswith('__'):
            self.generic_visit(node)
            return
            
        # Detecta se é comando CLI
        is_cli_command = any(
            (isinstance(d, ast.Call) and hasattr(d.func, 'attr') and d.func.attr in ['command', 'group'])
            or (isinstance(d, ast.Attribute) and d.attr in ['command', 'group'])
            for d in node.decorator_list
        )
        
        self.definitions.append({
            'name': node.name,
            'line': node.lineno,
            'file': self.file_path,
            'is_cli': is_cli_command,
            'is_private': node.name.startswith('_')
        })
        
        self.generic_visit(node)

class CallTracker(ast.NodeVisitor):
    """Rastreia todas as chamadas de função."""
    def __init__(self):
        self.calls = set()
        
    def visit_Call(self, node):
        # Captura chamadas diretas: func()
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        
        # Captura chamadas de atributo: obj.func()
        elif isinstance(node.func, ast.Attribute):
            self.calls.add(node.func.attr)
            
        self.generic_visit(node)

class ExportChecker(ast.NodeVisitor):
    """Verifica se uma função está em __all__."""
    def __init__(self):
        self.exported = set()
        
    def visit_Assign(self, node):
        # Procura por __all__ = [...]
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
    # Fase 1: Indexa todas as definições
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
            
            # Indexa definições
            indexer = FunctionIndexer(file_path)
            indexer.visit(tree)
            all_definitions.extend(indexer.definitions)
            
            # Rastreia chamadas
            tracker = CallTracker()
            tracker.visit(tree)
            all_calls.update(tracker.calls)
            
            # Verifica exports
            exporter = ExportChecker()
            exporter.visit(tree)
            all_exports.update(exporter.exported)
            
        except Exception:
            continue
    
    # Fase 2: Identifica órfãs
    orphans = []
    
    for defn in all_definitions:
        func_name = defn['name']
        
        # Critérios de exclusão (não são consideradas órfãs):
        # 1. Comandos CLI (entry points)
        if defn['is_cli']:
            continue
        
        # 2. Funções exportadas explicitamente
        if func_name in all_exports:
            continue
        
        # 3. Funções chamadas em algum lugar
        if func_name in all_calls:
            continue
        
        # 4. Funções de teste (começam com test_)
        if func_name.startswith('test_'):
            continue
        
        # 5. Setups de teste
        if func_name in ['setUp', 'tearDown', 'setUpClass', 'tearDownClass']:
            continue
        
        # É uma órfã!
        severity = 'WARNING' if defn['is_private'] else 'INFO'
        category = 'DEADCODE' if not defn['is_private'] else 'UNUSED-PRIVATE'
        
        orphans.append({
            'severity': severity,
            'category': category,
            'message': f"Função '{func_name}' não é chamada em nenhum lugar do projeto.",
            'file': defn['file'],
            'line': defn['line'],
            'details': 'Considere remover ou documentar se for API pública/futura.'
        })
    
    return orphans

def main():
    """Entry point quando executado como probe standalone."""
    try:
        # Lê lista de arquivos do stdin
        input_data = sys.stdin.read()
        if not input_data:
            print("[]")
            return
        
        files = json.loads(input_data)
        findings = analyze_orphans(files)
        print(json.dumps(findings))
        
    except Exception:
        # Retorna lista vazia em caso de erro (fail-safe)
        print("[]")
        sys.exit(0)

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