# doxoade/probes/style_probe.py
import ast
import sys
import json
import os

class ModernPowerTenVisitor(ast.NodeVisitor):
    def __init__(self, check_comments_only=False):
        self.findings = []
        self.check_comments_only = check_comments_only
        self.filename = ""

    def add_finding(self, rule, msg, line, category="STYLE"):
        self.findings.append({
            'severity': 'WARNING', # Style geralmente é warning
            'category': category,
            'message': f"[MPoT-{rule}] {msg}",
            'file': self.filename,
            'line': line
        })

    def visit_Module(self, node):
        # Solicitação: Arquivos sem auxílio para devs (Docstrings de módulo)
        if not ast.get_docstring(node):
            self.add_finding("4.Legibilidade", "Arquivo sem docstring (cabeçalho/explicação). Adicione um resumo do propósito do módulo.", 1, "DOCS")
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Definições de contexto
        is_magic = node.name.startswith("__") and node.name.endswith("__")
        is_test = node.name.startswith("test_")
#        is_init = node.name == "__init__"
        
        # --- CHECAGEM DE COMENTÁRIOS (Solicitação Específica) ---
        has_docstring = ast.get_docstring(node) is not None
        
        # Só exige docstring para funções públicas e não-mágicas (exceto se for muito complexa)
        if not has_docstring and not is_magic and not is_test:
            self.add_finding("4.Legibilidade", f"Função '{node.name}' não possui Docstring explicativa.", node.lineno, "DOCS")

        # Se a flag --comment estiver ativa, paramos por aqui
        if self.check_comments_only:
            return

        # --- CHECAGEM MPoT (Modern Power of Ten) ---

        # Regra 4: Funções curtas e coesas (~60 linhas)
        func_len = node.end_lineno - node.lineno
        if func_len > 60:
            self.add_finding("4.Coesão", f"Função '{node.name}' é muito longa ({func_len} linhas). Ideal < 60.", node.lineno, "COMPLEXITY")

        # Regra 5: Asserções e Contratos
        defensive_checks = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.Assert, ast.Raise)):
                defensive_checks += 1
        
        has_logic = len(node.body) > 5
        
        # Filtro refinado: Ignora testes, construtores e metodos mágicos na regra de contrato
        if has_logic and defensive_checks == 0 and not is_test and not is_magic:
            self.add_finding("5.Contratos", f"Função '{node.name}' tem lógica mas nenhuma asserção ou validação explícita.", node.lineno, "ROBUSTNESS")

        # Regra 6: Escopo mínimo (Uso de Global)
        for child in node.body:
            if isinstance(child, ast.Global):
                self.add_finding("6.Escopo", f"Uso de 'global' detectado em '{node.name}'. Prefira injeção de dependência ou retorno de valores.", child.lineno, "GLOBAL-STATE")

        # Regra 1: Fluxo Simples (Recursão)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == node.name:
                    self.add_finding("1.Fluxo", f"Recursão detectada em '{node.name}'. Garanta que existe condição de parada segura.", child.lineno, "RECURSION")

def analyze_style(files, comments_only):
    all_findings = []
    visitor = ModernPowerTenVisitor(check_comments_only=comments_only)

    for file_path in files:
        if not os.path.exists(file_path): continue
        
        visitor.filename = file_path
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=file_path)
            visitor.visit(tree)
            
        except Exception:
            # Ignora erros de sintaxe (o check.py já pega)
            continue
            
    # Adiciona os findings do visitor à lista geral
    all_findings.extend(visitor.findings)
    # Limpa findings do visitor para o proximo arquivo (embora aqui instanciamos um visitor unico, 
    # o ideal seria um por arquivo ou limpar a lista. O código acima acumula na lista do visitor.
    # Correção lógica:
    return visitor.findings

# doxoade/probes/style_probe.py

if __name__ == "__main__":
    files = []
    comments_only = False

    # MODO 1: Argumento CLI (Single File - Prioritário para Diagnóstico)
    if len(sys.argv) > 1:
        files = [sys.argv[1]]
    
    # MODO 2: STDIN (Batch Mode - Usado pelo Check em larga escala)
    elif not sys.stdin.isatty():
        try:
            input_data = sys.stdin.read().strip()
            if input_data:
                data = json.loads(input_data)
                files = data.get('files', [])
                comments_only = data.get('comments_only', False)
        except Exception:
            pass

    # Execução
    if files:
        # Garante que o output seja APENAS o JSON para não sujar o parser do Manager
        print(json.dumps(analyze_style(files, comments_only)))
    else:
        print("[]")