# -*- coding: utf-8 -*-
# doxoade\tools\vulcan\diagnostic\soteria\scribe.py
import re, os, shutil
from pathlib import Path

from doxoade.tools.telemetry_tools.logger import chief_heartbeat

class SoteriaScribe:
    def __init__(self):
        # PASC 8.15: Definição centralizada de padrões e restrições
        self.pyx_func_regex = re.compile(r'^(?P<indent>\s*)(?P<type>def|cdef|cpdef)\s+(?P<name>\w+)\s*\(', re.MULTILINE)
#        self.c_func_regex = re.compile(r'^(\w+[\s\*]+)(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE)
#        self.risk_regex = re.compile(r'(\*[\w\d_]+\s*=|[\w\d_]+\+\+|[\w\d_]+--|malloc|free|exit\(|Sleep\(|CX_DIE)')
        self.risk_regex = re.compile(r'(\*[\w\d_]+\s*=|malloc|free|soteria_validate|exit\(|CX_DIE)')
        self.c_func_regex = re.compile(r'^([\w\s\*]+?)\s*(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE)
        self.var_capture_regex = re.compile(r'([a-zA-Z_]\w*)\s*=[^=]')
        self.assignment_regex = re.compile(r'([a-zA-Z_]\w*)\s*=[^=]')
#        self.io_regex = re.compile(r'\b(fopen|fclose|fwrite|fread|printf|fprintf|sprintf|system|remove|rename)\s*\(')
        self.io_regex = re.compile(r'\b(fopen|fclose|fwrite|fread|printf|fprintf|soteria_mark|malloc|free)\s*\(')
        self.blacklist = {
            'soteria_mark', 'soteria_dispatch', 'soteria_init', 'main', 
            'soteria_push', 'soteria_malloc', 'soteria_free', 'soteria_validate',
            'soteria_payload', 'soteria_capture_identity', 'soteria_dump_stack_trace',
            'soteria_exception_handler', 'soteria_auto_ignite',
            'dx_arena_alloc', 'dx_arena_init', 'dx_xorshift64', 
            'dx_random_float', 'dx_random_normal',
            'switch', 'if', 'while', 'for', 'return', 'else'
        }

    def _get_indent(self, line: str) -> str:
        """Calcula a indentação de uma linha para manter a gramática Python."""
        return line[:len(line) - len(line.lstrip())]


    def instrument_pyx(self, content, filename):
        """Injeta rastro nativo no Cython protegendo contra caminhos Windows e one-liners."""
        # [OURO] Normaliza o caminho para evitar a "Unicode Escape Plague" (\U)
        safe_filename = filename.replace("\\", "/")
        
        lines = content.splitlines()
#        new_lines = ['cdef extern from "soteria.h":', '    void soteria_mark(char* msg, char* file, int line)', '']
        new_lines = [
            'cdef extern from "soteria.h":', 
            '    void soteria_mark(const char* msg, const char* file, int line)', 
            ''
        ]
        for i, line in enumerate(lines):
            stripped = line.strip()
            prev_line = lines[i-1].strip() if i > 0 else ""
            if "switch" in prev_line and prev_line.endswith("{"):
                new_lines.append(line)
                continue
            if "ctypes." in line:
                indent = self._get_indent(line)
                new_lines.append(f'{indent}soteria_mark("PRE-CALL: Chamada externa perigosa", "{safe_filename}", {i+1})')
            new_lines.append(line)
            match = self.pyx_func_regex.match(line)
            if match:
                # Proteção contra one-liners
                if ":" in line and line.split(":", 1)[1].strip():
                    continue
                
                name = match.group('name')
                indent = match.group('indent') + "    "
                # Usa o safe_filename aqui
                new_lines.append(f'{indent}soteria_mark("TRACEBACK: {name}", "{safe_filename}", {i+1})')
        return "\n".join(new_lines)

    def instrument_code(self, content, filename):
        #if "soteria_io_trace" in content: return content
        if "soteria_io_trace" in content and "const char*" in content: return content
        
        safe_fn = filename.replace("\\", "/")
        # Regex para capturar funções de sistema
#        io_re = re.compile(r'\b(fopen|printf|fprintf|malloc|free|CreateThread)\s*\(')
        io_re = re.compile(r'\b(fopen|printf|fprintf|malloc|free|CreateThread)\b\s*\(')        
        lines = content.splitlines()
        new_lines = []
        if "soteria.h" not in content: new_lines.append('#include "soteria.h"\n')

        stats = {"io": 0, "func": 0}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or "soteria_" in line or stripped.startswith(("//", "/*")):
                new_lines.append(line); continue

            indent = self._get_indent(line)

            # --- VACCINE: IO_SNIFFER ---
            io_match = io_re.search(line)
            if io_match:
                stats["io"] += 1
                func = io_match.group(1)
                # Tenta pegar o primeiro argumento para o rastro de conteúdo
                arg_match = re.search(rf'{func}\s*\(\s*([^,)]+)', line)
                payload = arg_match.group(1).replace('"', "'") if arg_match else "N/A"
#                new_lines.append(f'{indent}soteria_io_trace("{func}", "{payload}", "{safe_fn}", {i+1});')
                new_lines.append(f'{indent}soteria_io_trace("{func}", (const char*)"{payload}", "{safe_fn}", {i+1});')

            # --- VACCINE: ENTER_FUNC ---
            func_match = self.c_func_regex.match(line)
            if func_match:
                stats["func"] += 1
                new_lines.append(line)
                if func_match.group(2) not in self.blacklist:
                    new_lines.append(f'    SOTERIA_ENTER("{func_match.group(2)}");')
                continue

            new_lines.append(line)
        
        from doxoade.tools.telemetry_tools.logger import chief_heartbeat
        chief_heartbeat("SCRIBE", "VACCINATION", {"file": filename, "stats": stats})
        return "\n".join(new_lines)

    def generate_shadow(self, src_dir, shadow_dir):
        """Cria sombra instrumentada (PASC 8.17)."""
        if os.path.exists(shadow_dir): shutil.rmtree(shadow_dir)
        os.makedirs(shadow_dir, exist_ok=True)
        for f in os.listdir(src_dir):
            src_path = os.path.join(src_dir, f)
            dest_path = os.path.join(shadow_dir, f)
            if f.endswith('.pyx'):
                data = self.instrument_pyx(open(src_path, 'r', encoding='utf-8').read(), f)
                open(dest_path, 'w', encoding='utf-8').write(data)
            elif f.endswith('.c'):
                data = self.instrument_code(open(src_path, 'r', encoding='utf-8').read(), f)
                open(dest_path, 'w', encoding='utf-8').write(data)