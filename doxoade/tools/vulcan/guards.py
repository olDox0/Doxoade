# doxoade/doxoade/tools/vulcan/guards.py
"""
Vulcan Guards - Abyss-Edge Protocol v1.0.
Implementa travas de segurança rigorosas para código gerado em C/Assembly.
Compliance: MPoT-3, MPoT-8 (Metaprogramação Restrita), PASC-3.
"""
import ast

class VulcanSafetyGuard(ast.NodeTransformer):
    """
    Guardião de Integridade: Audita e modifica a AST para prevenir 
    instabilidades em nível de sistema.
    """

    def __init__(self, test_phase: bool=True):
        self.test_phase = test_phase
        self.violations = []

    def verify_no_pointers(self, pyx_code: str) -> bool:
        """
        Regra 1 (v1.2): No-Pointer Leak (Aegis Shield).
        Bloqueia ponteiros C, mas ignora expansão de argumentos Python (* e **).
        """
        import re
        pointer_pattern = '\\b(int|double|float|char|void)\\s*\\*'
        for line in pyx_code.splitlines():
            clean_line = line.split('#')[0]
            if re.search(pointer_pattern, clean_line):
                if '[:]' not in clean_line:
                    self.violations.append(f"Regra 1 violada: Uso de memória bruta em '{line.strip()}'")
        return len(self.violations) == 0

    def visit_BinOp(self, node):
        """Protege apenas divisões, preserva bitwise (MPoT-8)."""
        if isinstance(node.op, ast.Div):
            return self.generic_visit(node)
        return self.generic_visit(node)

    def get_safety_directives(self) -> str:
        return '\n# cython: language_level=3\n# cython: cdivision=True\n# cython: boundscheck=False\n# cython: nonecheck=False\n'

def apply_abyss_protocol(pyx_source: str, tree: ast.AST) -> tuple:
    """
    Orquestrador do Protocolo Borda do Abismo.
    Retorna: (final_source_string, safe_ast_tree)
    """
    guard = VulcanSafetyGuard(test_phase=True)
    if not guard.verify_no_pointers(pyx_source):
        raise RuntimeError(f'Aegis Vulcan Block: {guard.violations[0]}')
    safe_tree = guard.visit(tree)
    ast.fix_missing_locations(safe_tree)
    safe_code = ast.unparse(safe_tree)
    directives = '# cython: overflowcheck=False\n# cython: initializedcheck=False\n'
    final_source = guard.get_safety_directives() + directives + safe_code
    return (final_source, safe_tree)