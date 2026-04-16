# doxoade/doxoade/commands/intelligence_systems/intelligence_css.py
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
            clean_content = re.sub('/\\*.*?\\*/', '', self.content, flags=re.DOTALL)
            self.media_queries = len(re.findall('@media\\s*[^{]+\\{', clean_content, flags=re.IGNORECASE))
            self.rulesets = clean_content.count('{')
            self.important_tags = clean_content.count('!important')
            self.css_vars = len(re.findall('--[\\w-]+\\s*:', clean_content))
            self.complexity = self.rulesets + self.important_tags * 2
        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context='CSSSemanticAnalyzer._parse', silent=True)

    def get_summary(self):
        return {'lines': self.lines_of_code, 'complexity': self.complexity, 'css_stats': {'rulesets': self.rulesets, 'media_queries': self.media_queries, 'important_tags': self.important_tags, 'css_variables': self.css_vars}}