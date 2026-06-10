# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/scribe.py
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
        self.mem_regex = re.compile(r'\b(malloc|free|calloc|realloc|PyMem_Malloc|PyMem_Free)\b\s*\(')
        
        self.soteria_dir = Path(__file__).resolve().parent
        self.soteria_src = self.soteria_dir / "src"
        self.soteria_inc = self.soteria_dir / "include"
        
        self.alloc_map = {
            "malloc":      "ALLOC_MALLOC",
            "free":        "ALLOC_MALLOC",
            "calloc":      "ALLOC_MALLOC",
            "realloc":     "ALLOC_MALLOC",
            "PyMem_Malloc":"ALLOC_PYMEM",
            "PyMem_Free":  "ALLOC_PYMEM"
        }
        
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
        if "soteria_malloc_ext" in content: return content
        
        safe_filename = filename.replace("\\", "/")
        lines = content.splitlines()
        
        # Header de Definição para o Cython entender os símbolos C da Sotéria
        new_lines = [
            '# --- SOTERIA VULCAN SHIELD ---',
            'cdef extern from "soteria.h":',
            '    void soteria_mark(const char* msg, const char* file, int line) nogil',
            '    void* soteria_malloc_ext(size_t s, int origin, const char* f, int l) nogil',
            '    void soteria_free_ext(void* p, int origin, const char* f, int l) nogil',
            '    int ALLOC_MALLOC = 1',
            '    int ALLOC_PYMEM = 2',
            ''
        ]

        mem_pattern = re.compile(r'\b(malloc|free|PyMem_Malloc|PyMem_Free)\b\s*\((.*)\)')

        for i, line in enumerate(lines):
            ln_num = i + 1
            stripped = line.strip()
            
            # Filtros de segurança do Cython
            prev_line = lines[i-1].strip() if i > 0 else ""
            if "switch" in prev_line and prev_line.endswith("{"):
                new_lines.append(line)
                continue
                
            current_line = line

            # 1. Vacina de Memória no Cython
            mem_match = mem_pattern.search(current_line)
            if mem_match:
                func_name = mem_match.group(1)
                args = mem_match.group(2)
                origin = "ALLOC_PYMEM" if "PyMem" in func_name else "ALLOC_MALLOC"
                sot_func = "soteria_free_ext" if "free" in func_name.lower() else "soteria_malloc_ext"
                
                current_line = mem_pattern.sub(f'{sot_func}({args}, {origin}, "{safe_filename}", {ln_num})', current_line)

            # 2. Rastro de Chamadas Externas
            if "ctypes." in current_line:
                indent = self._get_indent(current_line)
                new_lines.append(f'{indent}soteria_mark("PRE-CALL: Ctypes", "{safe_filename}", {ln_num})')

            # 3. Rastro de Funções Cython
            match = self.pyx_func_regex.match(current_line)
            if match and not (":" in current_line and current_line.split(":", 1)[1].strip()):
                name = match.group('name')
                indent = match.group('indent') + "    "
                new_lines.append(current_line)
                new_lines.append(f'{indent}soteria_mark("TRACEBACK: {name}", "{safe_filename}", {ln_num})')
                continue

            new_lines.append(current_line)

        return "\n".join(new_lines)

    def instrument_code(self, content, filename):
        if "soteria_free_ext" in content or "soteria_malloc_ext" in content: 
            return content
        safe_fn = filename.replace("\\", "/")
        lines = content.splitlines()
        new_lines = []
        if "soteria.h" not in content: new_lines.append('#include "soteria.h"\n')

        stats = {"io": 0, "func": 0, "mem": 0}
        mem_pattern = re.compile(r'\b(malloc|free|calloc|realloc|PyMem_Malloc|PyMem_Free)\b\s*\((.*)\)')
        io_re = re.compile(r'\b(fopen|printf|fprintf|CreateThread)\b\s*\(')

        for i, line in enumerate(lines):
            ln_num = i + 1
            stripped = line.strip()
            if not stripped or "SOTERIA_ENTER" in stripped or "soteria_" in stripped:
                new_lines.append(line)
                continue
            if stripped.startswith(("//", "/*")):
                new_lines.append(line)
                continue
            indent = self._get_indent(line)
            current_line = line
            mem_match = mem_pattern.search(current_line)
            if mem_match:
                stats["mem"] += 1
                func_name = mem_match.group(1)
                args = mem_match.group(2)
                origin = self.alloc_map.get(func_name, "ALLOC_UNKNOWN")
                sot_func = "soteria_free_ext" if "free" in func_name.lower() else "soteria_malloc_ext"
                current_line = mem_pattern.sub(f'{sot_func}({args}, {origin}, "{safe_fn}", {ln_num})', current_line)

            io_match = io_re.search(current_line)
            if io_match:
                stats["io"] += 1
                func = io_match.group(1)
                new_lines.append(f'{indent}soteria_io_trace("{func}", "Chamada IO", "{safe_fn}", {ln_num});')

            func_match = self.c_func_regex.match(current_line)
            if func_match:
                stats["func"] += 1
                new_lines.append(current_line)
                func_name = func_match.group(2)
                if func_name not in self.blacklist:
                    new_lines.append(f'{indent}    SOTERIA_ENTER("{func_name}");')
                continue
            new_lines.append(current_line)
    
        chief_heartbeat("SCRIBE", "VACCINATION_C", {"file": filename, "stats": stats})
        return "\n".join(new_lines)

    def generate_shadow(self, src_dir, shadow_dir):
        """Cria uma cópia vacinada do projeto em uma pasta paralela."""
        from pathlib import Path
        src_path_root = Path(src_dir)
        dst_path_root = Path(shadow_dir)
        
        if not src_path_root.exists(): return

        for py_file in src_path_root.rglob("*.py"):
            # Pula pastas de sistema
            if any(x in str(py_file) for x in ['venv', '.git', '__pycache__']):
                continue
                
            rel_path = py_file.relative_to(src_path_root)
            target_file = dst_path_root / rel_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # [FIX] LEITURA ROBUSTA: Tenta UTF-8, mas ignora erros de caractere
                # Isso impede o crash se houver um 'é' ou 'ç' em comentário salvo em Latin-1
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f_in:
                    content = f_in.read()
                
                vacinado = self.instrument_code(content, py_file.name)
                
                with open(target_file, 'w', encoding='utf-8') as f_out:
                    f_out.write(vacinado)
            except Exception as e:
                # Se falhar mesmo assim, logamos no Hades mas não paramos a forja
                chief_heartbeat("SCRIBE", "SHADOW_FAIL", {"file": py_file.name, "error": str(e)})
                continue