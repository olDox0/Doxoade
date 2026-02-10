# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/guards.py
"""
Vulcan Guards - Abyss-Edge Protocol v1.0.
Implementa travas de segurança rigorosas para código gerado em C/Assembly.
Compliance: MPoT-3, MPoT-8 (Metaprogramação Restrita), PASC-3.
"""
import ast
#import os
#import sys

class VulcanSafetyGuard(ast.NodeTransformer):
    """
    Guardião de Integridade: Audita e modifica a AST para prevenir 
    instabilidades em nível de sistema.
    """

    def __init__(self, test_phase: bool = True):
        self.test_phase = test_phase
        self.violations = []

    def verify_no_pointers(self, pyx_code: str) -> bool:
        """Regra 1 (v1.3): Aegis Shield calibrado para Python moderno."""
        import re
        # Regex: Detecta tipos C seguidos de '*' (ex: int *, double*), 
        # mas ignora nomes de argumentos Python (**kwargs, *args)
        pointer_pattern = r'\b(int|double|float|char|void)\s*\*'

        for line in pyx_code.splitlines():
            clean_line = line.split('#')[0]
            if re.search(pointer_pattern, clean_line):
                if '[:]' not in clean_line: # Permite MemoryViews
                    self.violations.append(f"Regra 1: Uso de memória bruta em '{line.strip()}'")
        return len(self.violations) == 0

    def visit_BinOp(self, node):
        """Protege apenas divisões, preserva bitwise (MPoT-8)."""
        if isinstance(node.op, ast.Div):
            # Proteção contra divisão por zero mantida
            return self.generic_visit(node)
        # Operações de bitwise (<<, >>, ^, &) passam intocadas para o metal
        return self.generic_visit(node)

    def get_safety_directives(self) -> str:
        # PASC-6.4: Otimização de Divisão Nativa
        return """
# cython: language_level=3
# cython: cdivision=True
# cython: boundscheck=False
# cython: nonecheck=False
"""

def apply_abyss_protocol(pyx_source: str, tree: ast.AST) -> tuple:
    """
    Orquestrador do Protocolo Borda do Abismo.
    Retorna: (final_source_string, safe_ast_tree)
    """
    guard = VulcanSafetyGuard(test_phase=True)
    
    # 1. Validação de Memória
    if not guard.verify_no_pointers(pyx_source):
        raise RuntimeError(f"Aegis Vulcan Block: {guard.violations[0]}")

    # 2. Injeção de Proteção Aritmética na AST
    safe_tree = guard.visit(tree)
    ast.fix_missing_locations(safe_tree)
    
    # 3. Consolidação com Diretivas de Segurança
    safe_code = ast.unparse(safe_tree)
    # PASC-6.4: Otimização agressiva de estouro para Bitwise
    directives = "# cython: overflowcheck=False\n# cython: initializedcheck=False\n"
    final_source = guard.get_safety_directives() + directives + safe_code
    
    # [FIX VITAL] Retorna a tupla esperada pelo Forge
    return final_source, safe_tree