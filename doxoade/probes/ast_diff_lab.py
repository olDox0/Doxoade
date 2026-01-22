import ast
import json
# [DOX-UNUSED] import sys

def get_ast_structure(code):
    """Simplifica a AST para comparação."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    
    # Pega o primeiro nó significativo
    if not tree.body: return None
    return tree.body[0]

def analyze_transformation(code_old, code_new):
    node_old = get_ast_structure(code_old)
    node_new = get_ast_structure(code_new)
    
    if not node_old or not node_new:
        return {"type": "UNKNOWN", "confidence": 0}
    
    # Detecção de WRAP (Envelopamento)
    # Se o nó novo é um container (Try, If) e contém o nó velho dentro
    
    # Caso 1: Try/Except
    if isinstance(node_new, ast.Try):
        # Verifica se o código antigo está no corpo do Try
        # Simplificação: Compara a string do código (normalizada)
        # Em produção, compararíamos a sub-árvore
        old_str = ast.unparse(node_old).strip()
        new_body_str = "\n".join([ast.unparse(n) for n in node_new.body]).strip()
        
        if old_str in new_body_str:
            handlers = [h.type.id for h in node_new.handlers if isinstance(h.type, ast.Name)]
            return {
                "action": "WRAP",
                "wrapper": "TRY_EXCEPT",
                "handlers": handlers,
                "confidence": 0.9
            }

    # Caso 2: If (Guard Clause)
    if isinstance(node_new, ast.If):
        old_str = ast.unparse(node_old).strip()
        new_body_str = "\n".join([ast.unparse(n) for n in node_new.body]).strip()
        
        if old_str in new_body_str:
            condition = ast.unparse(node_new.test)
            return {
                "action": "WRAP",
                "wrapper": "IF_CHECK",
                "condition": condition,
                "confidence": 0.8
            }
            
    return {"type": "NO_MATCH", "confidence": 0}

if __name__ == "__main__":
    # Teste Hardcoded para Prova de Conceito
    old = "x = 10 / 0"
    new = """
try:
    x = 10 / 0
except ZeroDivisionError:
    pass
"""
    result = analyze_transformation(old, new)
    print(json.dumps(result, indent=2))