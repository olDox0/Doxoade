# doxoade/tools/vulcan/shadow_scribe.py
import ast

class NexusShadowScribe(ast.NodeTransformer):
    def __init__(self, filename):
        self.filename = filename

    def visit_FunctionDef(self, node):
        if node.name.startswith('_') or node.name in ['chief_heartbeat', 'activate_protocol']:
            return node

        # Injeta rastro de entrada e envolve o corpo em Try/Except/Finally
        # O finally garante que o rastro de saída (EXIT) sempre ocorra
        vax_template = ast.parse(f"""
chief_heartbeat('SHADOW', 'ENTER', {{'f': '{node.name}', 'file': '{self.filename}'}})
try:
    pass 
except Exception as _dox_err:
    import traceback as _tb
    from doxoade.rescue import activate_protocol as _ap
    _ap(_tb.format_exc(), context=locals())
    raise _dox_err
finally:
    chief_heartbeat('SHADOW', 'EXIT', {{'f': '{node.name}', 'status': 'COMPLETE'}})
""").body

        # Move o corpo original para dentro do bloco 'try' (que é o segundo nó do template)
        vax_template[1].body = node.body
        node.body = vax_template
        return node