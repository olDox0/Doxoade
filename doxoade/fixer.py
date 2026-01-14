# doxoade/fixer.py
import os
import re
import logging
from colorama import Fore

class AutoFixer:
    """
    Motor de Correção Profunda (PASC v1.2).
    Capaz de identificar blocos lógicos e realizar limpeza seletiva de símbolos.
    """
    def __init__(self, logger):
        self.logger = logger

    def apply_fix(self, file_path, line_number, fix_type, context=None):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            idx = line_number - 1
            if idx < 0 or idx >= len(lines): return False

            modified = False
            new_lines = list(lines)
            line_content = new_lines[idx].strip()

            # --- REGRA DE OURO: UPGRADE DE ESTRATÉGIA ---
            # Se mandarem remover uma linha que abre um bloco (paren ou dois pontos),
            # o Fixer automaticamente assume que deve comentar o BLOCO todo.
            if fix_type == "REMOVE_LINE":
                if line_content.endswith(':') or ('(' in line_content and ')' not in line_content):
                    fix_type = "COMMENT_BLOCK"

            # --- DESPACHO ---
            if fix_type == "FIX_UNUSED_IMPORT":
                var_name = context.get('var_name') if context else None
                modified = self._apply_smart_import_fix(new_lines, idx, var_name)

            elif fix_type == "COMMENT_BLOCK":
                modified = self._apply_comment_block(new_lines, idx)

            elif fix_type == "REMOVE_LINE":
                if not new_lines[idx].strip().startswith("#"):
                    new_lines[idx] = f"# [DOX-UNUSED] {new_lines[idx]}"
                    modified = True

            elif fix_type == "FIX_BARE_EXCEPT":
                modified = self._apply_safe_exception_fix(new_lines, idx, file_path)

            if modified:
                return self._save_file(file_path, new_lines)
            return False
        except Exception: return False

    def _apply_smart_import_fix(self, lines, idx, var_name):
        """
        Limpa imports sem quebrar o arquivo.
        Se 'from x import (a, b)' e 'a' for inútil, remove apenas 'a'.
        """
        line = lines[idx]
        if not var_name: return False
        
        # Pega apenas o nome final (ex: 'Style' de 'colorama.Style')
        base_name = var_name.split('.')[-1]

        # 1. Se abre bloco parentetizado e o símbolo não está na mesma linha
        if '(' in line and ')' not in line and base_name not in line:
            # Não fazemos nada nesta linha, o check vai apontar a linha real do símbolo dentro do bloco
            return False

        # 2. Se a linha contém outros símbolos além do que queremos remover
        # (Checagem simplificada via vírgula ou múltiplos imports)
        if ',' in line:
            # Neurocirurgia: remove o símbolo e limpa vírgulas/espaços
            pattern = rf'\b{re.escape(base_name)}\b\s*,?\s*'
            new_line = re.sub(pattern, '', line)
            # Limpa vírgula órfã no final (ex: from x import a, )
            new_line = new_line.replace('import ,', 'import').strip()
            if new_line.endswith(','): new_line = new_line[:-1]
            if new_line.strip().endswith('import'): # Ficou vazio
                 lines[idx] = f"# [DOX-UNUSED] {line}"
            else:
                 lines[idx] = new_line + "\n"
            return True
        
        # 3. Se for o único símbolo, comenta a linha toda
        lines[idx] = f"# [DOX-UNUSED] {line}"
        return True

    def _apply_comment_block(self, lines, idx):
        """Comenta o cabeçalho e TODO o corpo indentado, incluindo linhas vazias."""
        header = lines[idx]
        if header.strip().startswith("#"): return False
        
        # Calcula a indentação base do cabeçalho (ex: def ou from)
        initial_indent = len(header) - len(header.lstrip())
        lines[idx] = f"# [DOX-BLOCK] {header}"
        
        i = idx + 1
        while i < len(lines):
            line = lines[i]
            
            # Se a linha for puramente vazia, comentamos e continuamos
            if not line.strip():
                lines[i] = f"#\n"
                i += 1
                continue
            
            current_indent = len(line) - len(line.lstrip())
            
            # REGRA MPoT: Se a indentação for maior que a do cabeçalho,
            # ou se a linha começar com fechamento de bloco ')' ou '}', pertence ao bloco.
            if current_indent > initial_indent or line.strip().startswith((')', '}')):
                lines[i] = f"# {line}"
                if line.strip().startswith((')', '}')): 
                    break # Fim do bloco detectado
                i += 1
            else:
                # Encontramos uma linha com a mesma indentação ou menor: o bloco acabou.
                break
        return True

    def _apply_safe_exception_fix(self, lines, idx, file_path):
        """Transforma 'except: pass' em log estruturado."""
        original = lines[idx]
        indent = original[:len(original) - len(original.lstrip())]
        if ' as ' not in original:
            lines[idx] = re.sub(r'except\s*:?\s*', 'except Exception as e: ', original)
        if idx + 1 < len(lines) and 'pass' in lines[idx+1]:
            fname = os.path.basename(file_path)
            lines[idx+1] = f'{indent}    import logging\n{indent}    logging.error(f"[DOXO-AF] Falha em {fname} L{idx+1}: {{e}}")\n'
            return True
        return True

    def _save_file(self, file_path, lines):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        except IOError: return False