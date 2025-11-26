# doxoade/learning.py
import re
import click
import difflib
#import json
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
        (Gênese V8) Analisa a transformação e salva um template flexível.
        """
        # 1. Abstrai a mensagem
        abstract_msg = self._abstract_message_dynamic(message)
        
        try:
            orig_lines = original.splitlines()
            corr_lines = corrected.splitlines()
            
            # Usa difflib para achar o bloco exato que mudou
            matcher = difflib.SequenceMatcher(None, orig_lines, corr_lines)
            
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                # line_num é 1-based, indices são 0-based
                error_idx = line_num - 1
                
                # CASO 1: DELEÇÃO (REMOVE_LINE)
                # Se o erro estava numa linha que foi deletada
                if tag == 'delete' and i1 <= error_idx < i2:
                    print(Fore.MAGENTA + f"   > [GÊNESE V8] Padrão de Deleção Detectado: {abstract_msg}")
                    return self._save_template(
                        pattern=abstract_msg, 
                        template='REMOVE_LINE', 
                        category=category, 
                        source="FLEXIBLE_DEL"
                    )

                # CASO 2: SUBSTITUIÇÃO (APPLY_DIFF)
                # Se o erro estava numa linha que foi alterada
                elif tag == 'replace' and i1 <= error_idx < i2:
                    # Captura os blocos
                    old_block = "\n".join(orig_lines[i1:i2])
                    new_block = "\n".join(corr_lines[j1:j2])
                    
                    import json
                    diff_data = json.dumps({
                        'old': old_block,
                        'new': new_block,
                        'op': tag
                    })
                    
                    print(Fore.MAGENTA + f"   > [GÊNESE V8] Padrão de Substituição Detectado: {abstract_msg}")
                    return self._save_template(
                        pattern=abstract_msg, 
                        template='APPLY_DIFF', 
                        category=category, 
                        source="FLEXIBLE_DIFF",
                        diff_pattern=diff_data
                    )
                
                # CASO 3: INSERÇÃO (Complexo, deixamos para depois ou tratamos como DIFF sem old_block)
                # O problema do insert é que não temos 'old_block' para o fixer procurar onde inserir.
                # O fixer precisa de contexto. Por enquanto, ignoramos INSERT puro.

        except Exception as e:
            print(Fore.RED + f"[ERRO LEARNING] Falha ao analisar diff: {e}")
            import traceback
            print(traceback.format_exc())
            
        return False

    def _abstract_message_dynamic(self, message):
        """Tenta tornar a mensagem genérica usando heurísticas."""
        msg = message
        # Strings entre aspas (ex: 'foo') -> '<STR>'
        msg = re.sub(r"'.*?'", "'<STR>'", msg)
        # Números -> '<NUM>'
        msg = re.sub(r"\b\d+\b", "<NUM>", msg)
        return msg
        
    def _save_template(self, pattern, template, category, source, diff_pattern=None):
        # Verifica se já existe
        self.cursor.execute("SELECT id, confidence FROM solution_templates WHERE problem_pattern = ?", (pattern,))
        existing = self.cursor.fetchone()

        if existing:
            # ... (update confidence igual) ...
            # Opcional: Atualizar o diff se ele for melhor? Por enquanto, só confiança.
            new_conf = existing['confidence'] + 1
            self.cursor.execute("UPDATE solution_templates SET confidence = ? WHERE id = ?", (new_conf, existing['id']))
            print(Fore.CYAN + f"   > [GÊNESE] Template '{pattern[:30]}...' reforçado (Conf: {new_conf})")
        else:
            # INSERT CORRIGIDO
            # Precisamos garantir que as colunas existam no DB (v14)
            
            # Define o tipo
            tpl_type = "FLEXIBLE" if source.startswith("FLEXIBLE") else "HARDCODED"
            
            self.cursor.execute(
                """
                INSERT INTO solution_templates 
                (problem_pattern, solution_template, category, created_at, type, diff_pattern) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (pattern, template, category, datetime.now(timezone.utc).isoformat(), tpl_type, diff_pattern)
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