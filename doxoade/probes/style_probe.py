# doxoade/doxoade/probes/style_probe.py
import ast
import sys
import json
import os

class ModernPowerTenVisitor(ast.NodeVisitor):

    def __init__(self, check_comments_only=False):
        self.findings = []
        self.check_comments_only = check_comments_only
        self.filename = ''

    def add_finding(self, rule, msg, line, category='STYLE'):
        self.findings.append({'severity': 'WARNING', 'category': category, 'message': f'[MPoT-{rule}] {msg}', 'file': self.filename, 'line': line})

    def visit_Module(self, node):
        if not ast.get_docstring(node):
            self.add_finding('4.Legibilidade', 'Arquivo sem docstring (cabeçalho/explicação). Adicione um resumo do propósito do módulo.', 1, 'DOCS')
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        is_magic = node.name.startswith('__') and node.name.endswith('__')
        is_test = node.name.startswith('test_')
        has_docstring = ast.get_docstring(node) is not None
        if not has_docstring and (not is_magic) and (not is_test):
            self.add_finding('4.Legibilidade', f"Função '{node.name}' não possui Docstring explicativa.", node.lineno, 'DOCS')
        if self.check_comments_only:
            return
        func_len = node.end_lineno - node.lineno
        if func_len > 60:
            self.add_finding('4.Coesão', f"Função '{node.name}' é muito longa ({func_len} linhas). Ideal < 60.", node.lineno, 'COMPLEXITY')
        defensive_checks = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.Assert, ast.Raise)):
                defensive_checks += 1
        has_logic = len(node.body) > 5
        if has_logic and defensive_checks == 0 and (not is_test) and (not is_magic):
            self.add_finding('5.Contratos', f"Função '{node.name}' tem lógica mas nenhuma asserção ou validação explícita.", node.lineno, 'ROBUSTNESS')
        for child in node.body:
            if isinstance(child, ast.Global):
                self.add_finding('6.Escopo', f"Uso de 'global' detectado em '{node.name}'. Prefira injeção de dependência ou retorno de valores.", child.lineno, 'GLOBAL-STATE')
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == node.name:
                    self.add_finding('1.Fluxo', f"Recursão detectada em '{node.name}'. Garanta que existe condição de parada segura.", child.lineno, 'RECURSION')

def analyze_style(files, comments_only):
    all_findings = []
    visitor = ModernPowerTenVisitor(check_comments_only=comments_only)
    for file_path in files:
        if not os.path.exists(file_path):
            continue
        visitor.filename = file_path
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content, filename=file_path)
            visitor.visit(tree)
        except Exception:
            continue
    all_findings.extend(visitor.findings)
    return visitor.findings
if __name__ == '__main__':
    files = []
    comments_only = False
    if len(sys.argv) > 1:
        files = [sys.argv[1]]
    elif not sys.stdin.isatty():
        try:
            input_data = sys.stdin.read().strip()
            if input_data:
                data = json.loads(input_data)
                files = data.get('files', [])
                comments_only = data.get('comments_only', False)
        except Exception:
            pass
    if files:
        print(json.dumps(analyze_style(files, comments_only)))
    else:
        print('[]')