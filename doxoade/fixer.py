# doxoade/fixer.py
"""
Motor de Correção (AutoFixer).
Aplica patches cirúrgicos no código fonte com base em templates.
"""
import os
import re
from colorama import Fore

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
            
            if line_num < 1 or line_num > len(lines):
                return False

            modified = False
            
            if template_type == "REMOVE_LINE":
                modified = self._apply_remove_line(lines, line_num)
            
            elif template_type == "REMOVE_F_PREFIX":
                modified = self._apply_remove_f_prefix(lines, line_num)
            
            elif template_type == "REPLACE_WITH_UNDERSCORE":
                modified = self._apply_remove_line(lines, line_num)
            
            if modified:
                return self._save_file(file_path, lines)
            
            return False

        except Exception as e:
            self.logger.add_finding('ERROR', f"Falha ao aplicar fix em {file_path}: {e}")
            return False

    def _save_file(self, file_path, lines):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        except IOError as e:
            self.logger.add_finding('ERROR', f"Erro de IO ao salvar {file_path}: {e}")
            return False

    def _apply_remove_line(self, lines, line_num):
        idx = line_num - 1
        original = lines[idx]
        print(f"DEBUG: Tentando remover linha {line_num}: {original.strip()}")
        if "# [DOX-UNUSED]" in original:
            return False
            
        stripped = original.lstrip()
        indent = original[:len(original) - len(stripped)]
        
        lines[idx] = f"{indent}# [DOX-UNUSED] {stripped}"
        return True

    def _apply_remove_f_prefix(self, lines, line_num):
        idx = line_num - 1
        original = lines[idx]
        
        new_line = re.sub(r'\bf(["\'])', r'\1', original, count=1)
        
        if new_line == original: 
            return False
        
        lines[idx] = new_line
        return True