# doxoade/fixer.py
import os
import re
#from colorama import Fore, Style

class AutoFixer:
    def __init__(self, logger=None):
        self.logger = logger

    def apply_fix(self, file_path, line_num, solution_type, context_data=None):
        """
        Aplica uma correção atômica em um arquivo baseada em um template.
        Retorna True se houve alteração.
        """
        if not os.path.exists(file_path):
            return False

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if line_num < 1 or line_num > len(lines):
                return False

            original_line = lines[line_num - 1]
            new_lines = list(lines)
            modified = False
            
            # --- LÓGICA DOS TEMPLATES ---

            if solution_type == "REMOVE_LINE":
                # Estratégia Segura: Comentar a linha mantendo a indentação
                # Regex para capturar a indentação inicial
                indent_match = re.match(r"^(\s*)", original_line)
                indent = indent_match.group(1) if indent_match else ""
                
                # O conteúdo sem a indentação
                content = original_line.lstrip()
                
                # Reescreve como comentário com tag
                new_lines[line_num - 1] = f"{indent}# [DOX-UNUSED] {content}"
                modified = True

            elif solution_type == "REMOVE_F_PREFIX":
                # Remove f" ou f'
                fixed_line = re.sub(r'\bf(["\'])', r'\1', original_line)
                if fixed_line != original_line:
                    new_lines[line_num - 1] = fixed_line
                    modified = True

            elif solution_type == "REPLACE_WITH_UNDERSCORE":
                # Recebe a variável alvo via context_data
                var_name = context_data.get('var_name')
                if var_name:
                    # 1. Prepara a linha comentada (Histórico)
                    indent_match = re.match(r"^(\s*)", original_line)
                    indent = indent_match.group(1) if indent_match else ""
                    content = original_line.lstrip()
                    comment_line = f"{indent}# [DOX-UNUSED] {content}"
                    
                    # 2. Prepara a linha corrigida
                    fixed_line = original_line # Começa com original
                    
                    # Tenta 'var =' -> '_ ='
                    fixed_line = re.sub(rf'^(\s*){re.escape(var_name)}\s*=', r'\1_ =', fixed_line)
                    # Tenta 'as var' -> 'as _'
                    if fixed_line == original_line:
                        fixed_line = re.sub(rf'\bas\s+{re.escape(var_name)}\b', 'as _', fixed_line)
                    
                    if fixed_line != original_line:
                        # Substitui a linha original pela corrigida...
                        new_lines[line_num - 1] = fixed_line
                        # ... E insere a comentada ANTES dela
                        new_lines.insert(line_num - 1, comment_line)
                        modified = True

            # --- GRAVAÇÃO ---
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                return True

        except Exception as e:
            if self.logger:
                self.logger.add_finding('ERROR', f"Falha ao aplicar fix em {file_path}: {e}")
            return False
            
        return False