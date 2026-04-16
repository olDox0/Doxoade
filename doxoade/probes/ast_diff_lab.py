# doxoade/doxoade/probes/ast_diff_lab.py
import ast
import json

def get_ast_structure(code):
    """Simplifica a AST para comparação."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    if not tree.body:
        return None
    return tree.body[0]

def analyze_transformation(code_old, code_new):
    node_old = get_ast_structure(code_old)
    node_new = get_ast_structure(code_new)
    if not node_old or not node_new:
        return {'type': 'UNKNOWN', 'confidence': 0}
    if isinstance(node_new, ast.Try):
        old_str = ast.unparse(node_old).strip()
        new_body_str = '\n'.join([ast.unparse(n) for n in node_new.body]).strip()
        if old_str in new_body_str:
            handlers = [h.type.id for h in node_new.handlers if isinstance(h.type, ast.Name)]
            return {'action': 'WRAP', 'wrapper': 'TRY_EXCEPT', 'handlers': handlers, 'confidence': 0.9}
    if isinstance(node_new, ast.If):
        old_str = ast.unparse(node_old).strip()
        new_body_str = '\n'.join([ast.unparse(n) for n in node_new.body]).strip()
        if old_str in new_body_str:
            condition = ast.unparse(node_new.test)
            return {'action': 'WRAP', 'wrapper': 'IF_CHECK', 'condition': condition, 'confidence': 0.8}
    return {'type': 'NO_MATCH', 'confidence': 0}
if __name__ == '__main__':
    old = 'x = 10 / 0'
    new = '\ntry:\n    x = 10 / 0\nexcept ZeroDivisionError:\n    pass\n'
    result = analyze_transformation(old, new)
    print(json.dumps(result, indent=2))