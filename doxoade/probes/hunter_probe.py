# doxoade/probes/hunter_probe.py
import ast
import sys
import json

class RiskHunter(ast.NodeVisitor):
    def __init__(self):
        self.findings = []

    def add_finding(self, node, severity, category, message):
        self.findings.append({
            'severity': severity,
            'category': category,
            'message': message,
            'line': node.lineno
        })

    def visit_FunctionDef(self, node):
        # REGRA 1: Argumentos Padrão Mutáveis (Lista ou Dic)
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.add_finding(
                    node, 'ERROR', 'RISK-MUTABLE',
                    f"Argumento padrão mutável detectado na função '{node.name}'. "
                    "Isso retém estado entre chamadas. Use 'None' como padrão."
                )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        # REGRA 2: Except Genérico (Bare Except)
        if node.type is None:
            self.add_finding(
                node, 'WARNING', 'RISK-EXCEPTION',
                "Uso de 'except:' genérico detectado. "
                "Isso captura interrupções de sistema. Use 'except Exception:'."
            )
        self.generic_visit(node)

    def visit_Compare(self, node):
        # REGRA 3: Comparação com None usando ==
        # Estrutura: left [ops] comparators
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                if (isinstance(comparator, ast.Constant) and comparator.value is None):
                    msg = "Comparação '== None' não é recomendada. Use 'is None'."
                    if isinstance(op, ast.NotEq):
                        msg = "Comparação '!= None' não é recomendada. Use 'is not None'."
                    
                    self.add_finding(node, 'WARNING', 'STYLE', msg)
        self.generic_visit(node)

    def visit_Call(self, node):
        # REGRA 4: Funções Perigosas
        if isinstance(node.func, ast.Name):
            if node.func.id in ['eval', 'exec']:
                self.add_finding(
                    node, 'CRITICAL', 'SECURITY',
                    f"Uso de '{node.func.id}' detectado. Alto risco de segurança."
                )
        self.generic_visit(node)

def hunt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=file_path)
        hunter = RiskHunter()
        hunter.visit(tree)
        
        # Imprime JSON para o check.py ler
        print(json.dumps(hunter.findings))
        
    except Exception as e:
        # Se falhar, retorna erro estruturado
        error = [{'severity': 'ERROR', 'category': 'INTERNAL', 'message': str(e), 'line': 1}]
        print(json.dumps(error))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    hunt(sys.argv[1])