# doxoade/doxoade/tools/vulcan/alloc_scanner.py
import ast

class AllocScanner(ast.NodeVisitor):
    """Detecta alocações de objetos pesados em Hot-Paths."""
    def visit_For(self, node):
        for child in ast.walk(node):
            # Detecta concatenação de strings ou listas em loop (Lento no N2808)
            if isinstance(child, ast.BinOp) and isinstance(child.op, (ast.Add, ast.Mult)):
                print(f"   [ALERTA:ALLOC] L{child.lineno}: Concatenação detectada em loop. Sugestão: use bytearray ou pre-allocation.")
            
            # Detecta criação de dicionários temporários
            if isinstance(child, ast.Dict):
                print(f"   [ALERTA:ALLOC] L{child.lineno}: Dicionário criado dentro de loop. Alto custo de memória.")