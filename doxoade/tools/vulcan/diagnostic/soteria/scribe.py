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
        self.risk_regex = re.compile(r'(\*[\w\d_]+\s*=|[\w\d_]+\+\+|[\w\d_]+--|malloc|free|exit\(|Sleep\(|CX_DIE)')
        self.c_func_regex = re.compile(r'^([\w\s\*]+?)\s*(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE)
        self.var_capture_regex = re.compile(r'([a-zA-Z_]\w*)\s*=[^=]')
        self.assignment_regex = re.compile(r'([a-zA-Z_]\w*)\s*=[^=]')
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
        if "SOTERIA_ENTER" in content or "soteria_mark" in content:
            return content
        safe_fn = filename.replace("\\", "/")
        assignment_regex = re.compile(r'([a-zA-Z_]\w*)\s*=[^=]')
        risk_regex = re.compile(r'(\*[\w\d_]+\s*=|malloc|dx_arena_alloc|free|exit\(|CX_DIE|if.*arena->offset)')
#        risk_regex = re.compile(r'(\*[\w\d_]+\s*=|memset|memcpy|malloc|dx_arena_alloc|free|CX_DIE|exit\()')
        lines = content.splitlines()
        new_lines = []
        
        if "soteria.h" not in content:
            new_lines.append('#include "soteria.h"\n#include <stdio.h>\n')

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "/*")) or "soteria_" in line:
                new_lines.append(line); continue

            # 1. Marcos de Entrada (Pilha)
            func_match = self.c_func_regex.match(line)
            if func_match:
                name = func_match.group(2)
                new_lines.append(line)
                if not name.startswith('__Pyx') and name not in self.blacklist:
                    new_lines.append(f'    SOTERIA_ENTER("{name}");')
                continue
                
            match_var = self.var_capture_regex.search(line)
            if match_var:
                var_name = match_var.group(1)
                # Injeta um log que tenta imprimir o valor da variável (se for int/ptr)
                new_lines.append(f'{indent}soteria_mark_ext("VAR_SNAPSHOT", "{safe_fn}", {i+1}, "{var_name}", (long long){var_name});')


            # 2. FIX: MARCO DE LINHA (Breadcrumbs)
            # Injeta o rastro ANTES da linha de risco para capturar o exato local do OOM
            is_indented = line.startswith((" ", "\t"))
            #if stripped.startswith((" ", "\t")) and risk_regex.search(line):
            if line.startswith((" ", "\t")) and self.risk_regex.search(line):
                indent = self._get_indent(line)
                # Tenta identificar qual variável está sendo manipulada
                match_var = assignment_regex.search(line)
                if match_var:
                    v_name = match_var.group(1)
                    # Injeta o capturador de valor
                    new_lines.append(f'{indent}soteria_mark_var("{v_name}", (long long){v_name}, "{safe_fn}", {i+1});')
                else:
                    new_lines.append(f'{indent}soteria_mark("OP_RISCO", "{safe_fn}", {i+1});')
            
            new_lines.append(line)

        vacinadas = content.count("SOTERIA_ENTER")
        marcos = content.count("soteria_mark")
        # Auditoria visível no metal_build
        if vacinadas > 0:
            print(f"      💉 [SCRIBE] {filename}: {vacinadas} funções e {marcos} marcos injetados.")
        
        final_content = "\n".join(new_lines)
        
        # [META-AUDIT] Conta as injeções no conteúdo FINAL
        v_count = final_content.count("SOTERIA_ENTER")
        m_count = final_content.count("soteria_mark")
        
        if v_count > 0 or m_count > 0:
            print(f"      💉 [SCRIBE] {filename}: {v_count} funções e {m_count} marcos injetados.")
            
        chief_heartbeat("SCRIBE", "VACCINATION_SUMMARY", {
            "file": filename,
            "hooks_injected": vacinadas,
            "marks_injected": marcos,
            "has_soteria_h": "soteria.h" in content
        })
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