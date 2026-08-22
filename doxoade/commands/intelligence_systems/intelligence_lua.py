# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_lua.py
"""Motor de Análise Semântica para Lua (Lite-XL & PASC Compliance)."""
import re


class LuaSemanticAnalyzer:
    def __init__(self, content: str):
        self.content = content
        self.lines_of_code = 0
        self.functions_count = 0
        self.local_functions = 0
        self.requires_count = 0
        self.metatable_ops = 0
        self.complexity = 0
        self.imports = []
        self.function_names = []
        self._parse()

    def _parse(self):
        try:
            self.lines_of_code = len(self.content.splitlines())
            # Remove blocos de comentário --[[ ... ]] e comentários de linha --
            clean_content = re.sub(r'--\[\[.*?\]\]', '', self.content, flags=re.DOTALL)
            clean_content = re.sub(r'--.*', '', clean_content)

            # 1. Extração de nomes de funções em Lua:
            # - function nome(...)
            # - local function nome(...)
            # - function Classe:metodo(...) ou Classe.metodo(...)
            # - local nome = function(...)
            func_patterns = [
                r'\b(?:local\s+)?function\s+([\w\.\:]+)\s*\(',
                r'\b([\w\.\:]+)\s*=\s*function\s*\('
            ]
            names = []
            for pat in func_patterns:
                names.extend(re.findall(pat, clean_content))
            self.function_names = sorted(list(set(names)))
            self.functions_count = len(names) or len(re.findall(r'\bfunction\b', clean_content))
            self.local_functions = len(re.findall(r'\blocal\s+function\b', clean_content))

            # 2. Require / Módulos importados
            requires = re.findall(r'\brequire\s*\(?\s*[\'"]([^\'"]+)[\'"]\s*\)?', clean_content)
            self.imports = list(set(requires))
            self.requires_count = len(self.imports)

            # 3. Metatables & POO
            self.metatable_ops = len(re.findall(r'\b(setmetatable|getmetatable)\b', clean_content))

            # 4. Complexidade ciclomática estimada
            flow_control = len(re.findall(r'\b(if|elseif|for|while|repeat)\b', clean_content))
            self.complexity = flow_control + (self.functions_count // 2) + self.metatable_ops

        except Exception as e:
            try:
                from doxoade.tools.error_info import handle_error
                handle_error(e, context='LuaSemanticAnalyzer._parse', silent=True)
            except Exception:
                pass

    def get_summary(self):
        return {
            'lines': self.lines_of_code,
            'complexity': self.complexity,
            'functions': self.function_names,
            'lua_stats': {
                'total_functions': self.functions_count,
                'local_functions': self.local_functions,
                'metatable_operations': self.metatable_ops,
                'dependencies_count': self.requires_count
            }
        }
