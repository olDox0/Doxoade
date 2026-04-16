# doxoade/doxoade/commands/check_systems/fixer.py
import os
import re

class AutoFixer:

    def __init__(self, logger):
        self.logger = logger

    def apply_fix(self, file_path, line_number, fix_type, context=None):
        try:
            abs_path = os.path.normpath(os.path.abspath(file_path))
            if not os.path.exists(abs_path):
                return False
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            idx = line_number - 1
            if idx < 0 or idx >= len(lines):
                return False
            modified = False
            new_lines = list(lines)
            if fix_type == 'FIX_UNUSED_IMPORT':
                var_name = context.get('var_name') if context else None
                modified = self._apply_smart_import_fix(new_lines, idx, var_name)
            elif fix_type == 'REPLACE_WITH_UNDERSCORE':
                modified = self._apply_comment_unused_line(new_lines, idx)
            elif fix_type == 'RESTRICT_EXCEPTION':
                modified = self._apply_forensic_exception_fix(new_lines, idx, abs_path)
            elif fix_type == 'REMOVE_F_PREFIX':
                modified = self._apply_remove_f_prefix(new_lines, idx)
            if modified:
                return self._save_file(abs_path, new_lines)
            return False
        except Exception as e:
            from doxoade.tools.error_info import handle_error
            handle_error(e, context=f'AutoFixer.apply_fix ({os.path.basename(file_path)}:{line_number})', debug=True)
            return False

    def _apply_remove_f_prefix(self, lines, idx):
        line = lines[idx]
        new_line = re.sub('f(["\\\'])', '\\1', line, count=1)
        if new_line != line:
            lines[idx] = new_line
            return True
        return False

    def _apply_comment_unused_line(self, lines, idx):
        line = lines[idx]
        block_pattern = '^(?P<indent>\\s*)(?P<type>with|for)\\s+(?P<logic>.+)\\s+as\\s+(?P<var>[\\w\\d_]+):'
        match = re.search(block_pattern, line)
        if match:
            new_line = re.sub('\\s+as\\s+[\\w\\d_]+:', ' as _:', line)
            lines[idx] = new_line
            return True
        if not line.strip().startswith('#'):
            lines[idx] = f'# [DOX-UNUSED] {line}'
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

    def _apply_forensic_exception_fix(self, lines, idx, file_path):
        original = lines[idx]
        if not re.search('^\\s*except\\s*:', original):
            return False
        raw_indent = re.match('^(\\s*)', original).group(1)
        step = '\t' if '\t' in ''.join(lines[:10]) else '    '
        func_name = self._get_function_name(lines, idx)
        is_infra = any((x in file_path.replace('\\', '/') for x in ['probes/', 'tools/', 'database.py']))
        match_inline = re.search('except\\s*:\\s*(.*)', original)
        inline_stmt = match_inline.group(1).strip() if match_inline else ''
        if inline_stmt == 'pass':
            inline_stmt = ''
        if is_infra:
            new_block = [f'{raw_indent}except Exception as e:\n', f'{raw_indent}{step}import logging as _dox_log\n', f'{raw_indent}{step}_dox_log.error(f"[INFRA] {func_name}: {{e}}")\n']
        else:
            new_block = [f'{raw_indent}except Exception as e:\n', f'{raw_indent}{step}import sys as _dox_sys, os as _dox_os\n', f'{raw_indent}{step}exc_obj, exc_tb = _dox_sys.exc_info() #exc_type\n', f'{raw_indent}{step}f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]\n', f'{raw_indent}{step}line_n = exc_tb.tb_lineno\n', f'{raw_indent}{step}print(f"\\033[1;34m[ FORENSIC ]\\033[0m \\033[1mFile: {{f_name}} | L: {{line_n}} | Func: {func_name}\\033[0m")\n', f'{raw_indent}{step}print(f"\\033[31m  ■ Type: {{type(e).__name__}} | Value: {{e}}\\033[0m")\n']
        if inline_stmt:
            new_block.append(f'{raw_indent}{step}{inline_stmt}\n')
        lines[idx] = ''.join(new_block)
        return True

    def _apply_smart_import_fix(self, lines, idx, var_name):
        line = lines[idx]
        if not var_name:
            return False
        base_name = var_name.split('.')[-1]
        if ',' not in line and 'import ' + base_name in line:
            lines[idx] = f'# [DOX-UNUSED] {line}'
            return True
        patterns = [f',\\s*\\b{re.escape(base_name)}\\b', f'\\b{re.escape(base_name)}\\b\\s*,', f'\\bimport\\s+{re.escape(base_name)}\\b']
        new_line = line
        for p in patterns:
            new_line = re.sub(p, '', new_line)
        if re.search('import\\s*$', new_line.strip()):
            lines[idx] = f'# [DOX-UNUSED] {line}'
        else:
            lines[idx] = re.sub('\\s+', ' ', new_line).rstrip() + '\n'
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