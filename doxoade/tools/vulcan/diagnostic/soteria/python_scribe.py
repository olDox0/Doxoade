# doxoade/tools/vulcan/diagnostic/soteria/python_scribe.py
import ast

class AresShadowScribe(ast.NodeTransformer):
    def __init__(self, filename):
        self.filename = filename

    def visit_FunctionDef(self, node):
        if node.name.startswith('_'): return node
        
        # v130: Injeção de rastro forçado via print (para ser visível no stdout do rastro)
        in_msg = f" \x1b[96m[ARES:IN]  {self.filename} -> {node.name}()\x1b[0m"
        out_msg = f" \x1b[94m[ARES:OUT] {self.filename} -> {node.name}()\x1b[0m"

        def make_log(msg):
            return ast.Expr(value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()),
                args=[ast.Constant(value=msg)], keywords=[]))

        node.body = [make_log(in_msg), ast.Try(body=node.body, handlers=[], orelse=[], finalbody=[make_log(out_msg)])]
        return node

def generate_python_shadow(source_code, filename):
    try:
        tree = ast.parse(source_code)
        scribe = AresShadowScribe(filename)
        vax_tree = scribe.visit(tree)
        ast.fix_missing_locations(vax_tree)
        # Injeta import sys no topo para o Shadow funcionar
        return "import sys\n" + ast.unparse(vax_tree)
    except Exception:
        return source_code