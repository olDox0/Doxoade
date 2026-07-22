# doxoade/tools/recursion_guard.py
"""
Recursion Guard - Motor de Análise Estática de Recursividade.
Detecta padrões de recursão infinita ou não convergente sem executar o código.
Compliance: MPoT-4 (Análise Estática), PASC-6 (Fail-safe).

Uso:
    from doxoade.tools.recursion_guard import RecursionGuard
    guard = RecursionGuard()
    findings = guard.analyze_file('path/to/script.py')
"""
import ast
import os
from typing import List, Dict, Any, Set, Tuple
from pathlib import Path

class RecursionGuard:
    """Motor de Análise Estática de Recursividade."""
    
    def __init__(self):
        self.findings = []
        
    def analyze_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Analisa um arquivo Python em busca de riscos de recursão infinita."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            return self.analyze_source(source, file_path)
        except Exception as e:
            return [{'file': file_path, 'line': 0, 'message': f'Erro de leitura: {e}', 'category': 'RECURSION-RISK', 'severity': 'WARNING'}]

    def analyze_source(self, source: str, filename: str = '<unknown>') -> List[Dict[str, Any]]:
        self.findings = []
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError:
            return []
            
        visitor = _RecursionVisitor(filename, self.findings)
        visitor.visit(tree)
        
        # Verifica ciclos de recursão indireta (A -> B -> A)
        cycles = visitor.find_cycles()
        for cycle in cycles:
            if len(cycle) > 2: 
                self.findings.append({
                    'file': filename,
                    'line': 0,
                    'category': 'RECURSION-RISK',
                    'severity': 'WARNING',
                    'message': f"Recursão indireta detectada (Ciclo): {' -> '.join(cycle)}. Verifique se há caso base.",
                    'meta': {'type': 'indirect_cycle', 'cycle': cycle}
                })
                
        return self.findings

class _RecursionVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, findings: list):
        self.filename = filename
        self.findings = findings
        self.func_args = {}
        self.func_nodes = {}
        self.call_graph = {}
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._register_and_analyze(node)
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._register_and_analyze(node)
        
    def _register_and_analyze(self, node):
        func_name = node.name
        args = [arg.arg for arg in node.args.args]
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
            
        self.func_args[func_name] = args
        self.func_nodes[func_name] = node
        
        # Constrói grafo de chamadas para detectar recursão indireta
        calls = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name) and child.func.value.id == 'self':
                        calls.add(child.func.attr)
        self.call_graph[func_name] = calls
        
        # Analisa recursão direta
        self._check_direct_recursion(node, func_name, args)
        self.generic_visit(node)

    def _check_direct_recursion(self, func_node, func_name: str, args: List[str]):
        for child in ast.walk(func_node):
            if isinstance(child, ast.Call):
                # Chamada direta: func_name(...)
                if isinstance(child.func, ast.Name) and child.func.id == func_name:
                    self._evaluate_recursive_call(child, func_name, args, func_node)
                # Chamada de método: self.func_name(...)
                elif isinstance(child.func, ast.Attribute) and child.func.attr == func_name:
                    if isinstance(child.func.value, ast.Name) and child.func.value.id == 'self':
                        self._evaluate_recursive_call(child, func_name, args, func_node, is_method=True)

    def _evaluate_recursive_call(self, call_node: ast.Call, func_name: str, args: List[str], func_node, is_method=False):
        line = call_node.lineno
        call_arg_names = []
        has_complex_expr = False
        
        for arg in call_node.args:
            if isinstance(arg, ast.Name):
                call_arg_names.append(arg.id)
            else:
                has_complex_expr = True
                call_arg_names.append(None)
                
        # Remove *args e **kwargs da comparação direta
        pure_args = [a for a in args if not a.startswith('*')]
        # Se for método, o primeiro argumento é 'self', que é implícito na chamada
        compare_args = pure_args[1:] if is_method else pure_args
        
        # 1. Risco Crítico: Mesmos argumentos exatos (Sem mutação de estado)
        if not has_complex_expr and call_arg_names and call_arg_names == compare_args[:len(call_arg_names)] and len(call_arg_names) == len(compare_args):
            is_guarded = self._is_guarded_by_base_case(func_node, call_node)
            if not is_guarded:
                self.findings.append({
                    'file': self.filename,
                    'line': line,
                    'category': 'RECURSION-RISK',
                    'severity': 'CRITICAL',
                    'message': f"Recursão infinita provável: '{func_name}' chama a si mesma com os mesmos argumentos sem mutação de estado ou caso base.",
                    'meta': {'type': 'identical_args_unguarded', 'func': func_name}
                })
        # 2. Risco Crítico: Função sem argumentos chamando a si mesma
        elif not call_arg_names and not compare_args:
            is_guarded = self._is_guarded_by_base_case(func_node, call_node)
            if not is_guarded:
                self.findings.append({
                    'file': self.filename,
                    'line': line,
                    'category': 'RECURSION-RISK',
                    'severity': 'CRITICAL',
                    'message': f"Recursão infinita garantida: '{func_name}' não possui argumentos e não tem caso base.",
                    'meta': {'type': 'no_args_unguarded', 'func': func_name}
                })

    def _is_guarded_by_base_case(self, func_node, call_node) -> bool:
        """
        Heurística: Verifica se existe um 'If', 'Return' ou 'Raise' 
        no corpo da função antes da chamada, ou se a chamada está aninhada em um bloco condicional.
        """
        has_base_case_logic = False
        for stmt in func_node.body:
            if isinstance(stmt, (ast.If, ast.Return, ast.Raise)):
                has_base_case_logic = True
                break
            if hasattr(stmt, 'lineno') and stmt.lineno >= call_node.lineno:
                break
                
        is_nested = self._is_nested_in_conditional(func_node, call_node)
        return has_base_case_logic or is_nested

    def _is_nested_in_conditional(self, root_node, target_node) -> bool:
        for node in ast.walk(root_node):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try)):
                for child in ast.walk(node):
                    if child is target_node:
                        return True
        return False

    def find_cycles(self) -> List[List[str]]:
        """Algoritmo DFS para encontrar ciclos no grafo de chamadas (Recursão Indireta)."""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.call_graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            
            path.pop()
            rec_stack.remove(node)
            
        for func in self.call_graph:
            if func not in visited:
                dfs(func, [])
                
        return cycles