# -*- coding: utf-8 -*-
import re, os, shutil
from pathlib import Path

class SoteriaScribe:
    def __init__(self):
        # PASC 8.15: Definição centralizada de padrões e restrições
        self.pyx_func_regex = re.compile(r'^(?P<indent>\s*)(?P<type>def|cdef|cpdef)\s+(?P<name>\w+)\s*\(', re.MULTILINE)
        self.c_func_regex = re.compile(r'^(\w+[\s\*]+)(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE)
        self.blacklist = {'soteria_mark', 'soteria_dispatch', 'soteria_init', 'main', 'PyInit', 'soteria_auto_ignite'}

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
        """Instrumentação v45.2: Injeção Linear (Pre-Statement) e Segura."""
        safe_fn = filename.replace("\\", "/")
        # Captura apenas linhas que REALMENTE executam operações de risco
        risk_regex = re.compile(r'^\s*(\*[\w\d_]+\s*=|memset|memcpy|ctypes|string_at)', re.MULTILINE)
        
        lines = content.splitlines()
        new_lines = []
        
        # Injeta headers necessários no topo
        if "soteria.h" not in content:
            new_lines.append('#include "soteria.h"\n#include <stdio.h>')

        for i, line in enumerate(lines):
            # 1. Entrada de Função
            func_match = self.c_func_regex.match(line)
            if func_match:
                new_lines.append(line)
                new_lines.append(f'    SOTERIA_ENTER("{func_match.group(2)}");')
                continue
            
            # 2. Ponto de Risco (Injeção na linha ANTERIOR para garantir captura)
            if risk_regex.search(line) and "soteria_mark" not in line:
                indent = self._get_indent(line)
                # Injetamos o rastro como uma instrução separada antes do comando
                # Isso evita quebrar a sintaxe do C e garante o flush
                new_lines.append(f'{indent}soteria_mark("CRITICAL_OP", "{safe_fn}", {i+1}); fflush(stdout);')
                new_lines.append(line)
            else:
                new_lines.append(line)
            
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