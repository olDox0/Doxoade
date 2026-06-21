# doxoade/doxoade/commands/check_systems/fixer.py
import os
import re

def get_block_indent(lines, line_index):
    """Detecta a identação correta para uma linha baseada nas linhas superiores."""
    for i in range(line_index - 1, -1, -1):
        line = lines[i]
        if line.strip() and not line.strip().startswith('#'):
            indent = re.match(r"^\s*", line).group()
            # Se a linha anterior termina em ':', o próximo nível deve ser +4 espaços
            if line.strip().endswith(':'):
                return indent + "    "
            return indent
    return ""

def repair_indentation(file_path):
    """Varre o arquivo e realinha linhas com espaços inválidos (1-3 espaços)."""
    if not os.path.exists(file_path): return False
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    new_lines = []
    changed = False
    
    for i, line in enumerate(lines):
        # Alvo: imports ou comandos injetados com 1 a 3 espaços
        stripped = line.strip()
        if (stripped.startswith(('import ', 'from ', 'chief_heartbeat', '_dox'))) and \
           (line.startswith(' ') and not line.startswith('    ')):
            
            # Detecta a indentação correta baseada no bloco anterior
            correct_indent = get_block_indent(new_lines, i)
            new_line = correct_indent + stripped + "\n"
            
            if new_line != line:
                new_lines.append(new_line)
                changed = True
                continue
        
        new_lines.append(line)
    
    if changed:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    return False

class AutoFixer:

    def __init__(self, logger):
        self.logger = logger

    def simulate_fix(self, file_path, line_number, fix_type, context=None):
        """Retorna apenas a linha transformada para visualização."""
        try:
            abs_path = os.path.normpath(os.path.abspath(file_path))
            if not os.path.exists(abs_path): return None
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            idx = line_number - 1
            temp_lines = list(lines)
            modified = False
            
            if fix_type == 'FIX_UNUSED_IMPORT':
                modified = self._apply_smart_import_fix(temp_lines, idx, context.get('var_name'))
            elif fix_type == 'INDENT_ERR':
                modified = self._simulate_indent_surgery(temp_lines, line_number)
            elif fix_type == 'FIX_BLOCK_SYNTAX':
                # No FIX_BLOCK_SYNTAX, alteramos a linha ANTERIOR (idx - 1)
                modified = self._repair_empty_block(temp_lines, idx)
                if modified: return temp_lines[idx - 1].strip()
            elif fix_type == 'REPLACE_WITH_UNDERSCORE':
                modified = self._apply_comment_unused_line(temp_lines, idx)
            elif fix_type == 'RESTRICT_EXCEPTION':
                modified = self._apply_forensic_exception_fix(temp_lines, idx, abs_path)
                if modified:
                    # Gera uma prévia visual descritiva do bloco forense injetado
                    base_line = temp_lines[idx].strip()
                    p1 = temp_lines[idx + 1].strip()
                    p2 = temp_lines[idx + 2].strip()
                    p3 = temp_lines[idx + 3].strip()
                    return f"{base_line}\n         +      | {p1}\n         +      | {p2}\n         +      | {p3}\n         +      | ... [BLOCO FORENSE INJETADO]"
            elif fix_type == 'REMOVE_F_PREFIX':
                modified = self._apply_remove_f_prefix(temp_lines, idx)
            elif fix_type == 'RESTORE_UNUSED':
                modified = self._apply_restore_line(temp_lines, idx)
            elif fix_type == 'ADD_IMPORT':
                module = context.get('module', 'module')
                return f"import {module}"
            elif fix_type == 'MOVE_FUTURE':
                modified = self._apply_move_future(temp_lines, idx)
            
            if modified:
                if fix_type == 'ADD_IMPORT':
                    module = context.get('module', 'module')
                    return f"import {module}"
                return temp_lines[idx].strip()
            return None
        except Exception: return None

    def _simulate_indent_surgery(self, lines, line_num):
        """Modifica e gera a prévia do realinhamento para a visualização."""
        idx = line_num - 1
        if idx < 0 or idx >= len(lines): return False
        target_line = lines[idx]
        stripped = target_line.lstrip()
        
        # Busca a indentação correta olhando para cima
        correct_indent = ""
        for i in range(idx - 1, -1, -1):
            prev = lines[i]
            if prev.strip() and not prev.strip().startswith('#'):
                indent_match = re.match(r"^(\s*)", prev)
                correct_indent = indent_match.group(1) if indent_match else ""
                
                # Se a linha anterior abre um bloco, esta deve ter +4 espaços
                if prev.strip().endswith(':'):
                    correct_indent += "    "
                    break
        
        new_line = correct_indent + stripped
        if new_line != target_line:
            lines[idx] = new_line
            return True
        return False

    def _apply_move_future(self, lines, idx):
        """Move a instrução __future__ para o topo real do arquivo."""
        if idx >= len(lines): return False
        
        future_line = lines.pop(idx)
        insert_idx = 0
        
        # 1. Se houver Shebang (#!), pula para a linha 2
        if lines and lines[0].startswith('#!'):
            insert_idx = 1
            
        # 2. Se houver Docstring de módulo, pula para depois dela
        if len(lines) > insert_idx:
            first_content = lines[insert_idx].strip()
            if first_content.startswith(('"""', "'''")):
                if first_content.count('"""') == 2 or first_content.count("'''") == 2:
                    insert_idx += 1
                else:
                    # Busca o fechamento da docstring
                    for i in range(insert_idx + 1, min(len(lines), 50)):
                        if '"""' in lines[i] or "'''" in lines[i]:
                            insert_idx = i + 1
                            break

        lines.insert(insert_idx, future_line)
        return True

    def apply_fix(self, file_path, line_number, fix_type, context=None):
        try:
            abs_path = os.path.normpath(os.path.abspath(file_path))
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            idx = line_number - 1
            new_lines = list(lines)
            modified = False
            
            if fix_type == 'FIX_UNUSED_IMPORT':
                modified = self._apply_smart_import_fix(new_lines, idx, context.get('var_name'))
            elif fix_type == 'INDENT_ERR':
                if self._apply_indent_surgery(abs_path, line_number):
                    return True
                try:
                    from doxoade.tools.vulcan.indent_fixer import perform_indent_surgery
                    return perform_indent_surgery(abs_path)
                except Exception:
                    return False
            elif fix_type == 'REPLACE_WITH_UNDERSCORE':
                modified = self._apply_comment_unused_line(new_lines, idx)
            elif fix_type == 'FIX_BLOCK_SYNTAX':
                modified = self._repair_empty_block(new_lines, idx)
            elif fix_type == 'RESTORE_UNUSED':
                modified = self._apply_restore_line(new_lines, idx)
            elif fix_type == 'ADD_IMPORT':
                modified = self._apply_add_import(new_lines, context.get('module'))
            elif fix_type == 'RESTRICT_EXCEPTION':
                modified = self._apply_forensic_exception_fix(new_lines, idx, abs_path)
            elif fix_type == 'REMOVE_F_PREFIX':
                modified = self._apply_remove_f_prefix(new_lines, idx)
            elif fix_type == 'MOVE_FUTURE':
                modified = self._apply_move_future(new_lines, idx)

            if modified:
                return self._save_file(abs_path, new_lines)
            return False
        except Exception: return False

    def _apply_restore_line(self, lines, idx):
        """Restaura a linha removendo tags e pass, respeitando a indentação."""
        if idx >= len(lines): return False
        line = lines[idx]
        
        if '# [DOX-UNUSED]' in line:
            indent_match = re.match(r'^(\s*)', line)
            indent = indent_match.group(1) if indent_match else ""
            
            content_part = line[len(indent):]
            if content_part.strip().startswith('pass'):
                content_part = content_part.replace('pass', '', 1).lstrip()
            
            if '# [DOX-UNUSED]' in content_part:
                actual_code = content_part.split('# [DOX-UNUSED]')[1].strip()
                lines[idx] = f"{indent}{actual_code}\n"
                return True
        return False

    def _apply_add_import(self, lines, module_name):
        """Injeta import no topo apenas se não houver um import GLOBAL ativo."""
        if not module_name: return False
        
        global_import_pattern = rf'^(import|from)\s+{re.escape(module_name)}\b'
        
        for line in lines:
            if re.match(global_import_pattern, line):
                return False
        
        import_stmt = f"import {module_name}\n"
        
        insert_idx = 0
        for i, line in enumerate(lines[:30]):
            if line.startswith(('import ', 'from ')):
                insert_idx = i
                break
        
        lines.insert(insert_idx, import_stmt)
        return True

    def _apply_remove_f_prefix(self, lines, idx):
        line = lines[idx]
        new_line = re.sub('f(["\\\'])', '\\1', line, count=1)
        if new_line != line:
            lines[idx] = new_line
            return True
        return False

    def _apply_comment_unused_line(self, lines, idx):
        """Comenta linha injetando 'pass' se for a única num bloco, preservando indentação."""
        if idx >= len(lines): return False
        line = lines[idx]
        
        indent_match = re.match(r'^(\s*)', line)
        indent = indent_match.group(1) if indent_match else ""
        
        if re.search(r'(except|with|for)\s+.*\s+as\s+[\w\d_]+:', line):
            lines[idx] = re.sub(r'\s+as\s+[\w\d_]+:', ' as _:', line)
            return True

        is_block_start = False
        if idx > 0:
            for i in range(idx - 1, -1, -1):
                prev_line = lines[i].strip()
                if not prev_line or prev_line.startswith('#'): continue
                if prev_line.endswith(':'):
                    is_block_start = True
                    break

        if is_block_start:
            lines[idx] = f"{indent}pass  # [DOX-UNUSED] {line.lstrip()}"
        else:
            lines[idx] = f"{indent}# [DOX-UNUSED] {line.lstrip()}"
            
        return True

    def _repair_empty_block(self, lines, idx):
        """Repara SyntaxError de bloco vazio injetando 'pass' na linha comentada."""
        for i in [idx, idx-1]:
            if i < 0 or i >= len(lines): continue
            line = lines[i]
            if '# [DOX-UNUSED]' in line and 'pass' not in line:
                indent = re.match(r'^(\s*)', line).group(1)
                content = line.split('# [DOX-UNUSED]')[1].strip()
                lines[i] = f"{indent}pass  # [DOX-UNUSED] {content}\n"
                return True
        return False

    def _get_function_name(self, lines, idx):
        for i in range(idx - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith('def '):
                match = re.search('def\\s+([\\w\\d_]+)', line)
                return match.group(1) if match else 'global'
            if line.startswith('class '):
                break
        return 'unknown'

    def _apply_forensic_exception_fix(self, lines, idx, abs_path):
        """
        Substitui 'except:' por 'except Exception as e:' e insere o bloco forense
        respeitando estritamente a indentação base da linha original.
        """
        if idx >= len(lines):
            return False
        line = lines[idx]
        
        m = re.match(r"^(\s*)(except\s*:\s*|except\s+BaseException\s*:\s*)", line)
        if not m:
            m = re.match(r"^(\s*)except", line)
            if not m:
                return False
        
        base_indent = m.group(1)
        lines[idx] = f"{base_indent}except Exception as e:\n"
        
        indent = base_indent + "    "
        func_name = self._get_function_name(lines, idx) or "unknown"
        
        forensic_block = [
            f"{indent}import sys as _dox_sys, os as _dox_os\n",
            f"{indent}from traceback import print_tb as exc_trace\n",
            f"{indent}exc_obj, exc_tb = _dox_sys.exc_info()\n",
            f"{indent}f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]\n",
            f"{indent}line_n = exc_tb.tb_lineno\n",
            f"{indent}exc_trace(exc_tb)\n",
            f"{indent}print(f\"\\033[1;34m[ FORENSIC ]\\033[0m \\033[1mFile: {{f_name}} | L: {{line_n}} | Func: {func_name}\\033[0m\")\n",
            f"{indent}print(f\"\\033[31m  ■ Type: {{type(e).__name__}} | Value: {{e}}\\033[0m\")\n"
        ]
        
        for offset, f_line in enumerate(forensic_block, 1):
            lines.insert(idx + offset, f_line)
        return True

    def _apply_smart_import_fix(self, lines, idx, var_name):
        line = lines[idx]
        if not var_name: return False
        
        indent_match = re.match(r'^(\s*)', line)
        indent = indent_match.group(1) if indent_match else ""
        content = line.lstrip()
        
        base_name = var_name.split('.')[-1]
        
        if ',' not in content:
             if f'import {base_name}' in content or f'as {base_name}' in content:
                if idx > 0 and lines[idx-1].strip().endswith(':'):
                    lines[idx] = f'{indent}pass  # [DOX-UNUSED] {content}'
                else:
                    lines[idx] = f'{indent}# [DOX-UNUSED] {content}'
                return True

        new_content = content
        new_content = re.sub(rf',\s*\b{re.escape(base_name)}\b', '', new_content)
        new_content = re.sub(rf'\b{re.escape(base_name)}\b\s*,', '', new_content)
        
        if new_content == content:
            new_content = re.sub(rf'\bimport\s+{re.escape(base_name)}\b', 'import', new_content)

        if re.search(r'import\s*$', new_content.strip()):
             lines[idx] = f'{indent}# [DOX-UNUSED] {content}'
        else:
            lines[idx] = indent + re.sub(r'\s{2,}', ' ', new_content).strip() + '\n'
            
        return True

    def _save_file(self, file_path, lines):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        except IOError as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context=f'AutoFixer._save_file ({os.path.basename(file_path)})', debug=True)
            return False
        except Exception as e:
            import sys as exc_sys
            from traceback import print_tb as exc_trace
            _, exc_obj, exc_tb = exc_sys.exc_info()
            exc_trace(exc_tb)
            from doxoade.rescue import activate_protocol
            import traceback
            activate_protocol(traceback.format_exc())
            
    def _apply_indent_surgery(self, file_path, line_num):
        """Realinha a linha defeituosa baseada no contexto do bloco."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            idx = line_num - 1
            if idx < 0 or idx >= len(lines): return False
            
            target_line = lines[idx]
            stripped = target_line.lstrip()
            
            # 1. Busca a indentação correta olhando para cima
            correct_indent = ""
            for i in range(idx - 1, -1, -1):
                prev = lines[i]
                if prev.strip() and not prev.strip().startswith('#'):
                    indent_match = re.match(r"^(\s*)", prev)
                    correct_indent = indent_match.group(1) if indent_match else ""
                    
                    # Se a linha anterior abre um bloco, esta deve ter +4 espaços
                    if prev.strip().endswith(':'):
                        correct_indent += "    "
                    break
            
            new_line = correct_indent + stripped
            if new_line != target_line:
                lines[idx] = new_line
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                return True
            return False
        except Exception:
            return False