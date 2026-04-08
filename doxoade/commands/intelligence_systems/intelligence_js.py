# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_js.py
"""Motor de Análise Semântica para JavaScript (PASC Compliance)."""
import re

class JSSemanticAnalyzer:
    def __init__(self, content: str):
        self.content = content
        self.lines_of_code = 0
        self.functions_count = 0
        self.async_functions = 0
        self.api_calls = 0
        self.dom_manipulations = 0
        self.complexity = 0
        self.imports = []
        self._parse()

    def _parse(self):
        try:
            self.lines_of_code = len(self.content.splitlines())
            
            # Remove comentários de bloco /* */ e de linha //
            clean_content = re.sub(r'/\*.*?\*/', '', self.content, flags=re.DOTALL)
            clean_content = re.sub(r'//.*', '', clean_content)

            # Contagem de Funções (function keyword e arrow functions)
            func_matches = len(re.findall(r'\bfunction\b', clean_content))
            arrow_matches = len(re.findall(r'=>', clean_content))
            self.functions_count = func_matches + arrow_matches

            # Funções e chamadas Assíncronas
            self.async_functions = len(re.findall(r'\b(async|await|Promise)\b', clean_content))

            # Chamadas de Rede / API
            self.api_calls = len(re.findall(r'\b(fetch|axios|XMLHttpRequest)\b', clean_content))

            # Manipulação de DOM (Indicador de script focado em UI)
            dom_methods = r'\b(getElementById|querySelector|querySelectorAll|addEventListener|createElement|appendChild)\b'
            self.dom_manipulations = len(re.findall(dom_methods, clean_content))

            # Controle de fluxo para base de complexidade ciclomatica
            flow_control = len(re.findall(r'\b(if|for|while|switch|catch)\b', clean_content))

            # Mapeamento de Dependências (ESM imports e CommonJS requires)
            imports_esm = re.findall(r'import\s+.*?\s+from\s+[\'"](.*?)[\'"]', clean_content)
            requires_cjs = re.findall(r'require\([\'"](.*?)[\'"]\)', clean_content)
            self.imports = list(set(imports_esm + requires_cjs))

            # Cálculo heurístico de complexidade base
            self.complexity = flow_control + self.async_functions + (self.functions_count // 2)

        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context="JSSemanticAnalyzer._parse", silent=True)

    def get_summary(self):
        return {
            "lines": self.lines_of_code,
            "complexity": self.complexity,
            "js_stats": {
                "total_functions": self.functions_count,
                "async_functions": self.async_functions,
                "api_calls": self.api_calls,
                "dom_manipulations": self.dom_manipulations,
                "dependencies_count": len(self.imports)
            }
        }