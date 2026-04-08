# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_css.py
"""Motor de Análise Semântica para CSS (PASC Compliance)."""
import re

class CSSSemanticAnalyzer:
    def __init__(self, content: str):
        self.content = content
        self.lines_of_code = 0
        self.rulesets = 0
        self.media_queries = 0
        self.important_tags = 0
        self.css_vars = 0
        self.complexity = 0
        self._parse()
        
    def _parse(self):
        try:
            self.lines_of_code = len(self.content.splitlines())
            
            # Remove comentários /* ... */ para evitar contagem de código morto
            clean_content = re.sub(r'/\*.*?\*/', '', self.content, flags=re.DOTALL)
            
            # Extração de métricas estruturais
            self.media_queries = len(re.findall(r'@media\s*[^{]+\{', clean_content, flags=re.IGNORECASE))
            self.rulesets = clean_content.count('{')
            self.important_tags = clean_content.count('!important')
            
            # Detecta declarações de variáveis CSS (ex: --cor-primaria: #fff;)
            self.css_vars = len(re.findall(r'--[\w-]+\s*:', clean_content))
            
            # Cálculo da complexidade: 
            # 1 ponto por ruleset + 2 pontos de penalidade por cada !important
            self.complexity = self.rulesets + (self.important_tags * 2)
            
        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context="CSSSemanticAnalyzer._parse", silent=True)
            
    def get_summary(self):
        return {
            "lines": self.lines_of_code,
            "complexity": self.complexity,
            "css_stats": {
                "rulesets": self.rulesets,
                "media_queries": self.media_queries,
                "important_tags": self.important_tags,
                "css_variables": self.css_vars
            }
        }