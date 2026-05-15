# -*- coding: utf-8 -*-
import re, os, shutil
from pathlib import Path

class SoteriaScribe:
    def __init__(self):
        # Captura def, cdef, cpdef
        self.pyx_func_regex = re.compile(r'^(?P<indent>\s*)(?P<type>def|cdef|cpdef)\s+(?P<name>\w+)\s*\(', re.MULTILINE)

    def instrument_pyx(self, content, filename):
        """Injeta rastro nativo no Cython (PASC 8.18)."""
        lines = content.splitlines()
        new_lines = []
        
        # Ponte para Sotéria C
        new_lines.append('cdef extern from "soteria.h":')
        new_lines.append('    void soteria_mark(char* msg, char* file, int line)')
        new_lines.append('')

        for i, line in enumerate(lines):
            new_lines.append(line)
            match = self.pyx_func_regex.match(line)
            if match:
                indent = match.group('indent') + "    "
                name = match.group('name')
                # Injeta rastro com o nome do arquivo .pyx original
                mark = f'{indent}soteria_mark("TRACEBACK: {name}", "{filename}", {i+1})'
                new_lines.append(mark)
        return "\n".join(new_lines)

    def generate_shadow(self, src_dir, shadow_dir):
        """Busca resiliente de fontes (PASC 8.14)."""
        if os.path.exists(shadow_dir): shutil.rmtree(shadow_dir)
        os.makedirs(shadow_dir, exist_ok=True)
        
        # Varre o diretório em busca de .pyx
        for f in os.listdir(src_dir):
            if f.endswith('.pyx'):
                with open(os.path.join(src_dir, f), 'r', encoding='utf-8') as s:
                    data = self.instrument_pyx(s.read(), f)
                with open(os.path.join(shadow_dir, f), 'w', encoding='utf-8') as d:
                    d.write(data)