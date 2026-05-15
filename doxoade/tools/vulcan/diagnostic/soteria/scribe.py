# -*- coding: utf-8 -*-
import re, os, shutil
from pathlib import Path

class SoteriaScribe:
    def __init__(self):
        # PASC 8.15: Definição centralizada de padrões e restrições
        self.pyx_func_regex = re.compile(r'^(?P<indent>\s*)(?P<type>def|cdef|cpdef)\s+(?P<name>\w+)\s*\(', re.MULTILINE)
        self.c_func_regex = re.compile(r'^(\w+[\s\*]+)(\w+)\s*\(([^)]*)\)\s*\{', re.MULTILINE)
        self.blacklist = {'soteria_mark', 'soteria_dispatch', 'soteria_init', 'main', 'PyInit', 'soteria_auto_ignite'}

    def instrument_pyx(self, content, filename):
        """Injeta rastro nativo no Cython (PASC 8.18)."""
        lines = content.splitlines()
        new_lines = ['cdef extern from "soteria.h":', '    void soteria_mark(char* msg, char* file, int line)', '']
        for i, line in enumerate(lines):
            new_lines.append(line)
            match = self.pyx_func_regex.match(line)
            if match:
                name = match.group('name')
                indent = match.group('indent') + "    "
                new_lines.append(f'{indent}soteria_mark("TRACEBACK: {name}", "{filename}", {i+1})')
        return "\n".join(new_lines)

    def instrument_code(self, content, filename):
        if 'soteria.h' not in content:
            content = f'#include "soteria.h"\n{content}'
        
        # Regex para capturar funções C e Cython
        func_regex = re.compile(r'^((?:static\s+)?[a-zA-Z_]\w*[\s\*]+)([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*\{', re.MULTILINE)

        def _inject(match):
            head, name, args = match.group(1), match.group(2), match.group(3)
            if any(x in name for x in self.blacklist) or name.startswith('__Pyx'):
                return match.group(0)
            
            # Injeta o rastreador de pilha
            return f'{head}{name}({args}) {{\n    SOTERIA_ENTER("{name}");'

        return func_regex.sub(_inject, content)

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