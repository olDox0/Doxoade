# doxoade/learning.py
import re
import click
import difflib
from datetime import datetime, timezone
from colorama import Fore

class LearningEngine:
    def __init__(self, cursor):
        self.cursor = cursor

    def learn_from_incident(self, incident, corrected_content, original_content):
        """
        Ponto de entrada principal. Tenta aprender um template a partir de um incidente resolvido.
        Retorna True se aprendeu algo novo ou reforçou algo existente.
        """
        message = incident.get('message', '')
        category = incident.get('category', '')
        line_num = incident.get('line')

        # 1. Tenta Abstração Rígida (Regras Conhecidas - Legado Gênese V2)
        if self._learn_hardcoded_rules(message, category):
            return True

        # 2. Tenta Abstração Flexível (Gênese V8 - Novo!)
        if original_content and corrected_content and line_num:
            return self._learn_flexible_pattern(message, category, original_content, corrected_content, line_num)
            
        return False

    def _learn_hardcoded_rules(self, message, category):
        """Regras legadas baseadas em regex estático."""
        problem_pattern = None
        solution_template = None

        # DEADCODE
        if re.match(r"'(.+?)' imported but unused", message):
            problem_pattern = "'<MODULE>' imported but unused"
            solution_template = "REMOVE_LINE"
        elif re.match(r"redefinition of unused '(.+?)' from line \d+", message):
            problem_pattern = "redefinition of unused '<VAR>' from line <LINE>"
            solution_template = "REMOVE_LINE"
        # STYLE
        elif message == "f-string is missing placeholders":
            problem_pattern = "f-string is missing placeholders"
            solution_template = "REMOVE_F_PREFIX"
        elif re.match(r"local variable '(.+?)' is assigned to but never used", message):
            problem_pattern = "local variable '<VAR>' is assigned to but never used"
            solution_template = "REPLACE_WITH_UNDERSCORE"
        # RUNTIME
        elif re.match(r"undefined name '(.+?)'", message):
            problem_pattern = "undefined name '<VAR>'"
            solution_template = "ADD_IMPORT_OR_DEFINE"

        if problem_pattern:
            return self._save_template(problem_pattern, solution_template, category, "HARDCODED")
        
        return False

    def _learn_flexible_pattern(self, message, category, original, corrected, line_num):
        """
        (Gênese V8) Tenta entender o que mudou no código e criar um padrão genérico.
        """
        try:
            orig_lines = original.splitlines()
            corr_lines = corrected.splitlines()
            
            if line_num > len(orig_lines): return False
            
            # Focamos na linha do erro
#            bad_line = orig_lines[line_num - 1].strip()
            
            # Tenta achar a linha correspondente no arquivo corrigido
            # Isso é difícil se a linha foi deletada ou movida.
            # Vamos usar difflib para achar a mudança local
            
            matcher = difflib.SequenceMatcher(None, orig_lines, corr_lines)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                # Estamos procurando a mudança que cobre a linha do erro
                if i1 <= (line_num - 1) < i2:
                    if tag == 'replace':
                        # Substituição! Vamos analisar a transformação
                        old_snippet = "\n".join(orig_lines[i1:i2])
                        new_snippet = "\n".join(corr_lines[j1:j2])
                        
                        # Abstração Trivial: Generalizar Variáveis
                        # Se a mensagem diz "NameError: name 'xyz' is not defined"
                        # e o código mudou de 'foo(xyz)' para 'foo("xyz")'
                        # Podemos tentar abstrair 'xyz' como <VAR>
                        
                        # Por enquanto, vamos salvar um padrão genérico baseado na mensagem
                        # Ex: Transformar "ValueError: invalid literal for int() with base 10: ''"
                        # em "ValueError: invalid literal for int() with base 10: '<VAL>'"
                        
                        abstract_msg = self._abstract_message(message)
                        
                        # Se conseguirmos abstrair a mensagem, salvamos o DIFF como template
                        if abstract_msg != message:
                            # TODO: Salvar o diff abstrato. 
                            # Por hoje, apenas registramos que detectamos um padrão flexível
                            print(Fore.MAGENTA + f"   > [GÊNESE V8] Padrão Flexível Detectado: {abstract_msg}")
                            print(Fore.MAGENTA + f"     Transformação: {old_snippet.strip()} -> {new_snippet.strip()}")
                            return True
                    
                    elif tag == 'delete':
                        # Se foi deletado, cai no REMOVE_LINE, que já cobrimos ou podemos reforçar
                        pass
                        
        except Exception:
            pass
        return False

    def _abstract_message(self, message):
        """Substitui partes variáveis da mensagem por tokens."""
        # Substitui strings entre aspas
        msg = re.sub(r"'.*?'", "'<VAR>'", message)
        # Substitui números
        msg = re.sub(r"\b\d+\b", "<NUM>", msg)
        return msg

    def _save_template(self, pattern, template, category, source):
        self.cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (pattern,))
        existing = self.cursor.fetchone()

        if existing:
            new_conf = existing['confidence'] + 1
            self.cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_conf, existing['id']))
            print(Fore.CYAN + f"   > [GÊNESE] Template '{pattern[:30]}...' reforçado (Conf: {new_conf})")
        else:
            self.cursor.execute(
                "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
                (pattern, template, category, datetime.now(timezone.utc).isoformat())
            )
            print(Fore.CYAN + f"   > [GÊNESE] Novo template ({source}): '{pattern}'")
        return True
        
def _learn_template_from_incident(cursor, incident):
    """
    (Gênese V3) Aprende um template a partir de um incidente resolvido.
    Chamado diretamente pelo check quando um incidente é resolvido.
    """
    from datetime import datetime, timezone
    
    message = incident.get('message', '')
    category = incident.get('category', '')
    
    if not category:
        if 'imported but unused' in message or 'redefinition of unused' in message:
            category = 'DEADCODE'
        elif 'undefined name' in message:
            category = 'RUNTIME-RISK'
        elif 'f-string' in message or 'assigned to but never used' in message:
            category = 'STYLE'
        else:
            category = 'UNCATEGORIZED'
    
    problem_pattern = None
    solution_template = None
    
    # Regras de abstração
    if re.match(r"'(.+?)' imported but unused", message):
        problem_pattern = "'<MODULE>' imported but unused"
        solution_template = "REMOVE_LINE"
    
    elif re.match(r"redefinition of unused '(.+?)' from line \d+", message):
        problem_pattern = "redefinition of unused '<VAR>' from line <LINE>"
        solution_template = "REMOVE_LINE"
    
    elif message == "f-string is missing placeholders":
        problem_pattern = "f-string is missing placeholders"
        solution_template = "REMOVE_F_PREFIX"
    
    elif re.match(r"local variable '(.+?)' is assigned to but never used", message):
        problem_pattern = "local variable '<VAR>' is assigned to but never used"
        solution_template = "REPLACE_WITH_UNDERSCORE"
    
    elif re.match(r"undefined name '(.+?)'", message):
        problem_pattern = "undefined name '<VAR>'"
        solution_template = "ADD_IMPORT_OR_DEFINE"

    if not problem_pattern:
        return False

    cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (problem_pattern,))
    existing = cursor.fetchone()

    if existing:
        new_confidence = existing['confidence'] + 1
        cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_confidence, existing['id']))
        click.echo(Fore.CYAN + f"   > [GÊNESE] Template '{problem_pattern[:30]}...' → confiança {new_confidence}")
    else:
        cursor.execute(
            "INSERT INTO solution_templates (problem_pattern, solution_template, category, created_at) VALUES (?, ?, ?, ?)",
            (problem_pattern, solution_template, category, datetime.now(timezone.utc).isoformat())
        )
        click.echo(Fore.CYAN + f"   > [GÊNESE] Novo template: '{problem_pattern}' ({solution_template})")
    
    return True