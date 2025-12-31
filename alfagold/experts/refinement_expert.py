# alfagold/experts/refinement_expert.py
import re

class RefinementExpert:
    """
    Expert de Refinamento v3.0 (Indentation Engine).
    Focado em transformar 'soup code' em Python estruturado.
    """
    def process(self, raw_code):
        # 1. Deduplicação (Ruído Neural)
        code = self._deduplicate(raw_code)
        
        # 2. Espaçamento Sintático (Gramática)
        code = self._fix_spacing(code)
        
        # 3. Indentação e Newlines (Estrutura)
        code = self._apply_indentation(code)
        
        # 4. Limpeza Final
        code = code.replace(" .", ".").replace(" :", ":").replace("( ", "(")
        return code.strip()

    def _deduplicate(self, text):
        # Palavras: 'caminho caminho' -> 'caminho'
        text = re.sub(r'\b(\w+)(?:\s+\1\b)+', r'\1', text)
        # Pontuação: '::' -> ':'
        text = re.sub(r'([:,;=])\1+', r'\1', text)
        # Aspas malucas: "'w''w'" -> "'w'"
        text = re.sub(r"('[\w\.]+')\1+", r"\1", text)
        return text

    def _fix_spacing(self, text):
        keywords = ["def", "with", "as", "import", "return", "if", "else", "for", "while", "in"]
        for kw in keywords:
            # Garante espaço após keyword
            text = re.sub(rf'(?<=\b{kw})([a-zA-Z0-9_\'\"])', r' \1', text)
            # Garante espaço antes de keyword se estiver colada em pontuação
            text = re.sub(rf'([):])({kw}\b)', r'\1 \2', text)

        text = re.sub(r',(\S)', r', \1', text)
        return text

    def _apply_indentation(self, text):
        """Transforma one-liners em blocos indentados."""
        # Se encontrar ":keyword", quebra linha
        # Ex: ":with" -> ":\n    with"
        
        # Padrão: : seguido de comando
        pattern = r':\s*(with|if|for|return|print|open)'
        
        def replacer(match):
            return f":\n    {match.group(1)}"
            
        text = re.sub(pattern, replacer, text)
        
        # Correção específica para 'with open' colado
        text = text.replace("withopen", "with open")
        
        return text