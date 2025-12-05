# doxoade/learning.py
"""
Motor de Aprendizado (Gênese).
Analisa incidentes resolvidos e cria templates de correção.
"""
import re
#import difflib
from datetime import datetime, timezone
from colorama import Fore

class LearningEngine:
    def __init__(self, cursor):
        self.cursor = cursor

    def learn_from_incident(self, incident, corrected_content, original_content):
        """
        Ponto de entrada do aprendizado.
        Tenta estratégias do mais simples (Hardcoded) ao mais complexo (Indutivo).
        """
        # [MPoT-5] Contrato: Dados mínimos necessários
        if not incident or not incident.get('message'):
            return False

        # 1. Estratégia Rápida: Regras conhecidas
        if self._learn_hardcoded_rules(incident):
            return True

        # 2. Estratégia Profunda: Análise de Diff (Requer conteúdo original)
        if corrected_content and original_content:
            return self._learn_from_diff(incident, original_content, corrected_content)
            
        return False

    def _learn_hardcoded_rules(self, incident):
        """Aplica regras pré-definidas para erros comuns."""
        msg = incident['message']
        category = incident['category']
        
        pattern = None
        template = None
        
        # Padrões de DEADCODE
        if 'imported but unused' in msg:
            pattern = "'<MODULE>' imported but unused"
            template = "REMOVE_LINE"
        elif 'redefinition of unused' in msg:
            pattern = "redefinition of unused '<VAR>' from line <LINE>"
            template = "REMOVE_LINE"
            
        # Padrões de STYLE
        elif "f-string is missing placeholders" in msg:
            pattern = "f-string is missing placeholders"
            template = "REMOVE_F_PREFIX"
        elif "is assigned to but never used" in msg:
            pattern = "local variable '<VAR>' is assigned to but never used"
            template = "REPLACE_WITH_UNDERSCORE"
            
        if pattern and template:
            return self._save_template(pattern, template, category)
        return False

    def _learn_from_diff(self, incident, original, corrected):
        """
        (Gênese V8/V15) Tenta induzir uma regra observando a mudança.
        """
        line_num = incident.get('line')
        if not line_num: return False

        # Extrai as linhas relevantes
        orig_lines = original.splitlines()
        corr_lines = corrected.splitlines()
        
        # Foca na vizinhança do erro
        idx = line_num - 1
        if idx >= len(orig_lines): return False
        
        orig_line = orig_lines[idx].strip()
        
        # Tenta achar a linha correspondente no corrigido
        # (Heurística simples: mesma linha)
        if idx < len(corr_lines):
            corr_line = corr_lines[idx].strip()
        else:
            corr_line = "" # Linha removida
            
        # Se a linha foi comentada com [DOX-UNUSED], aprendemos REMOVE_LINE
        if "[DOX-UNUSED]" in corr_line and orig_line in corr_line:
            # Abstrai a mensagem de erro para criar o padrão
            pattern = self._abstract_message_dynamic(incident['message'])
            return self._save_template(pattern, "REMOVE_LINE", incident['category'])
            
        return False

    def _abstract_message_dynamic(self, message):
        """Transforma mensagem concreta em padrão abstrato (Regex)."""
        # Substitui nomes entre aspas por <VAR>
        # Ex: "Module 'os' not found" -> "Module '<VAR>' not found"
        pattern = re.sub(r"'[^']+'", "'<VAR>'", message)
        
        # Substitui números de linha
        pattern = re.sub(r"line \d+", "line <LINE>", pattern)
        
        return pattern

    def _save_template(self, pattern, template, category):
        """Persiste o conhecimento no banco de dados."""
        try:
            # Verifica existência
            self.cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (pattern,))
            existing = self.cursor.fetchone()

            if existing:
                new_conf = existing['confidence'] + 1
                self.cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_conf, existing['id']))
                print(f"{Fore.CYAN}   > [GÊNESE] Template '{pattern}' reforçado (Conf: {new_conf})")
            else:
                self.cursor.execute(
                    "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at, confidence) VALUES (?, ?, ?, ?, 1)",
                    (pattern, template, category, datetime.now(timezone.utc).isoformat())
                )
                print(f"{Fore.CYAN}   > [GÊNESE] Novo template (HARDCODED): '{pattern}'")
            return True
        except Exception:
            return False