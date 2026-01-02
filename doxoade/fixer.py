# doxoade/fixer.py
import os
import re
import logging
from colorama import Fore

class AutoFixer:
    def __init__(self, logger):
        self.logger = logger

    def apply_fix(self, file_path, line_number, fix_type, context=None):
        """Aplica uma correção específica no arquivo."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            idx = line_number - 1
            if idx < 0 or idx >= len(lines):
                return False

            modified = False
            new_lines = list(lines)

            # --- ESTRATÉGIAS ---

            if fix_type == "REMOVE_LINE":
                # Comenta a linha em vez de deletar (Mais seguro / Reversível)
                if not new_lines[idx].strip().startswith("#"):
                    new_lines[idx] = f"# [DOX-UNUSED] {new_lines[idx]}"
                    modified = True
            
            elif fix_type == "COMMENT_BLOCK":
                modified = self._apply_comment_block(new_lines, idx)

            elif fix_type == "FIX_UNUSED_IMPORT":
                # [NOVO] Estratégia Cirúrgica
                var_name = context.get('var_name') if context else None
                modified = self._apply_smart_import_fix(new_lines, idx, var_name)

            elif fix_type == "REMOVE_F_PREFIX":
                modified = self._apply_remove_f_prefix(new_lines, idx)
                
            elif fix_type == "REPLACE_WITH_UNDERSCORE":
                var_name = context.get('var_name')
                modified = self._apply_replace_underscore(new_lines, idx, var_name)

            elif fix_type == "FIX_BARE_EXCEPT":
                modified = self._apply_fix_bare_except(new_lines, idx)

            if modified:
                return self._save_file(file_path, new_lines)
            return False

        except Exception:
            return False

    def _save_file(self, file_path, lines):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        except IOError:
            return False

    def _apply_comment_block(self, lines, idx):
        if lines[idx].strip().startswith("#"): return False
        initial_indent = len(lines[idx]) - len(lines[idx].lstrip())
        
        lines[idx] = f"# [DOX-UNUSED] {lines[idx]}"
        
        i = idx + 1
        while i < len(lines):
            line = lines[i]
            if not line.strip(): 
                i += 1
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent > initial_indent:
                lines[i] = f"# {line}"
                i += 1
            else:
                break
        return True

    def _apply_smart_import_fix(self, lines, idx, var_name):
        """
        Remove um símbolo específico de uma linha de import sem quebrar a sintaxe.
        Trata: 'from x import a, b' -> 'from x import a'
        """
        line = lines[idx]
        
        # 1. Se a linha tem parênteses abrindo e é apenas a abertura, NÃO comenta (evita SyntaxError)
        if '(' in line and var_name not in line:
            return False

        # 2. Se o símbolo é o único no import, comenta a linha toda
        # Regex para detectar se há mais de um símbolo após o 'import'
        symbols_match = re.search(r'import\s+(.+)', line)
        if symbols_match:
            symbols_str = symbols_match.group(1).strip('() \n')
            symbols_list = [s.strip() for s in symbols_str.split(',')]
            
            if len(symbols_list) <= 1:
                lines[idx] = f"# [DOX-UNUSED] {line}"
                return True
            
            # 3. Neurocirurgia: Remove apenas o símbolo inútil e limpa as vírgulas
            new_symbols = [s for s in symbols_list if s != var_name]
            new_symbols_str = ", ".join(new_symbols)
            
            # Reconstrói a linha mantendo a estrutura (from ou import puro)
            if 'from' in line:
                module_part = line.split('import')[0]
                lines[idx] = f"{module_part}import {new_symbols_str}\n"
            else:
                lines[idx] = f"import {new_symbols_str}\n"
            return True
            
        return False

    def _apply_remove_f_prefix(self, lines, idx):
        original = lines[idx]
        new_line = re.sub(r'\bf(["\'])', r'\1', original)
        if new_line != original:
            lines[idx] = new_line
            return True
        return False
    
    def _apply_replace_underscore(self, lines, idx, var_name):
        if not var_name: return False
        original = lines[idx]
        clean_var = var_name.split('.')[-1]
        
        new_line = re.sub(rf'\b{re.escape(clean_var)}\s*=', '_ =', original)
        if new_line == original:
            new_line = re.sub(rf'\bas\s+{re.escape(clean_var)}\b', 'as _', original)
            
        if new_line != original:
            lines[idx] = new_line
            return True
        return False

    def _apply_fix_bare_except(self, lines, idx):
        """Substitui 'except:' por 'except Exception:' preservando indentação."""
        original = lines[idx]
        
        # Regex: Encontra 'except' seguido de espaços opcionais e ':'
        # Substitui por 'except Exception:'
        # O count=1 garante que substituímos apenas a instrução, preservando o resto da linha se houver
        new_line = re.sub(r'except\s*:', 'except Exception:', original, count=1)
        
        if new_line != original:
            lines[idx] = new_line
            return True
        return False