# doxoade/fixer.py
"""
Motor de Correção (AutoFixer).
Aplica patches cirúrgicos no código fonte com base em templates.
"""
import os
import re
#from colorama import Fore

class AutoFixer:
    def __init__(self, logger):
        self.logger = logger

    def apply_fix(self, file_path, line_num, template_type, context):
        """
        Despacha a correção para a estratégia adequada.
        """
        if not os.path.exists(file_path):
            self.logger.add_finding('ERROR', f"Arquivo não encontrado: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Validação de limites
            if line_num < 1 or line_num > len(lines):
                return False

            # Despacho de Estratégia
            if template_type == "REMOVE_LINE":
                return self._apply_remove_line(file_path, lines, line_num)
            
            elif template_type == "REMOVE_F_PREFIX":
                return self._apply_remove_f_prefix(file_path, lines, line_num)
            
            elif template_type == "REPLACE_WITH_UNDERSCORE":
                return self._apply_replace_with_underscore(file_path, lines, line_num, context)
            
            # Adicione novas estratégias aqui
            
            return False

        except Exception as e:
            self.logger.add_finding('ERROR', f"Falha ao aplicar fix em {file_path}: {e}")
            return False

    def _save_file(self, file_path, lines):
        """Escreve o arquivo de volta no disco."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        except IOError:
            return False

    def _apply_remove_line(self, file_path, lines, line_num):
        """Estratégia: Comentar a linha (Soft Delete)."""
        idx = line_num - 1
        original = lines[idx]
        
        # Evita comentar duas vezes
        if original.strip().startswith("# [DOX-UNUSED]"):
            return False
            
        # Preserva a indentação
        indent = len(original) - len(original.lstrip())
        spaces = original[:indent]
        content = original.strip()
        
        lines[idx] = f"{spaces}# [DOX-UNUSED] {content}\n"
        return self._save_file(file_path, lines)

    def _apply_remove_f_prefix(self, file_path, lines, line_num):
        """Estratégia: Remover prefixo f de strings."""
        idx = line_num - 1
        original = lines[idx]
        
        # Regex seguro para f" ou f'
        new_line = re.sub(r'\bf(["\'])', r'\1', original)
        
        if new_line == original: return False
        
        lines[idx] = new_line
        return self._save_file(file_path, lines)

    def _apply_replace_with_underscore(self, file_path, lines, line_num, context):
        """Estratégia: Substituir variável não usada por _."""
        var_name = context.get('var_name')
        if not var_name: return False
        
        idx = line_num - 1
        original = lines[idx]
        
        # Tenta: "as var" -> "as _"
        new_line = re.sub(rf'\bas\s+{re.escape(var_name)}\b', 'as _', original)
        
        # Tenta: "var =" -> "_ =" (no início da linha ou após indentação)
        if new_line == original:
             new_line = re.sub(rf'^(\s*){re.escape(var_name)}\s*=', r'\1_ =', original)
             
        if new_line == original: return False
        
        lines[idx] = new_line
        return self._save_file(file_path, lines)