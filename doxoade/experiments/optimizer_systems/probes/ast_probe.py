import ast

def ast_probe(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        "node_count": sum(1 for _ in ast.walk(tree)),
        "has_loops": any(isinstance(n, (ast.For, ast.While)) for n in ast.walk(tree)),
    }