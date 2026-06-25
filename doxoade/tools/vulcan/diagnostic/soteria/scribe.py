# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/scribe.py
import re
import os
import ctypes
from pathlib import Path
from doxoade.tools.telemetry_tools.logger import chief_heartbeat

class SoteriaScribe:
    def __init__(self):
        self.soteria_dir = Path(__file__).resolve().parent
        self.soteria_src = self.soteria_dir / "src"
        self.soteria_inc = self.soteria_dir / "include"
        
        self.dll_path = self.soteria_dir / "native" / "soteria_scribe_advance.dll"
#        self.dll_path = Path(__file__).resolve().parent / "native" / "soteria_scribe_advance.dll"
#        self.dll_path = Path(__file__).parent / "native" / "soteria_scribe_advance.dll"
        self._lib = None
        self.pyx_func_regex = re.compile(r'^\s*(def|cdef|cpdef)\s+(\w+)\s*\(')
        self.c_func_regex = re.compile(r'^([\w\s\*]+?)\s*(\w+)\s*\(([^)]*)\)\s*\{')
        self.mem_pattern = re.compile(r'\b(malloc|free|calloc|realloc|PyMem_Malloc|PyMem_Free)\b\s*\((.*)\)')
        self.io_re = re.compile(r'\b(fopen|printf|fprintf|CreateThread)\b\s*\(')
        
        #self.blacklist = {'main', 'if', 'while', 'for', 'return', 'else', 'switch'}
        self.blacklist = {
            'soteria_mark', 'soteria_dispatch', 'soteria_init', 'main', 
            'if', 'while', 'for', 'return', 'else', 'switch'
        }
        
        self.alloc_map = {
            "malloc": "ALLOC_MALLOC", "free": "ALLOC_MALLOC",
            "calloc": "ALLOC_MALLOC", "realloc": "ALLOC_MALLOC",
            "PyMem_Malloc": "ALLOC_PYMEM", "PyMem_Free": "ALLOC_PYMEM"
        }

    def _get_indent(self, line: str) -> str:
        return line[:len(line) - len(line.lstrip())]

    def instrument_pyx(self, content, filename):
        """Otimizado para Cython High-Throughput."""
        if "soteria_malloc_ext" in content: return content
        
        lines = content.splitlines()
        new_lines = [
            'cdef extern from "soteria.h":',
            '    void soteria_mark(const char* msg, const char* file, int line) nogil',
            '    void* soteria_malloc_ext(size_t s, int origin, const char* f, int l) nogil',
            '    void soteria_free_ext(void* p, int origin, const char* f, int l) nogil',
            '    int ALLOC_MALLOC = 1',
            '    int ALLOC_PYMEM = 2',
            ''
        ]

        safe_filename = filename.replace("\\", "/")

        for i, line in enumerate(lines):
            stripped = line.strip()
            # SHORT-CIRCUIT: Se a linha for vazia ou comentário, pula Regex
            if not stripped or stripped.startswith(("#", "'''", '"""')):
                new_lines.append(line)
                continue

            ln_num = i + 1
            
            # Filtro rápido para funções e chamadas
            if "(" in stripped:
                # Vacina de Memória
                if any(x in stripped for x in ["malloc", "free", "PyMem"]):
                    line = self.mem_pattern.sub(
                        lambda m: f'soteria_{"free" if "free" in m.group(1).lower() else "malloc"}_ext({m.group(2)}, {"ALLOC_PYMEM" if "PyMem" in m.group(1) else "ALLOC_MALLOC"}, "{safe_filename}", {ln_num})', 
                        line
                    )

                # Rastro de Funções
                match = self.pyx_func_regex.match(line)
                if match:
                    name = match.group(2)
                    indent = match.group(0).split(match.group(1))[0]
                    new_lines.append(line)
                    new_lines.append(f'{indent}    soteria_mark("TRACEBACK: {name}", "{safe_filename}", {ln_num})')
                    continue

            if "ctypes." in stripped:
                new_lines.append(f'{self._get_indent(line)}soteria_mark("PRE-CALL: Ctypes", "{safe_filename}", {ln_num})')

            new_lines.append(line)

        return "\n".join(new_lines)

    def _load_lib(self):
        if not self._lib and self.dll_path.exists():
            self._lib = ctypes.CDLL(str(self.dll_path))
            self._lib.vax_process_buffer.argtypes = [
                ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int
            ]
            self._lib.vax_process_buffer.restype = ctypes.c_int
        return self._lib

    def _load_native_kernel(self):
        """Tenta carregar o acelerador em C."""
        if self._lib: return self._lib
        if self.dll_path.exists():
            try:
                self._lib = ctypes.CDLL(str(self.dll_path))
                self._lib.vax_process_buffer.argtypes = [
                    ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int
                ]
                self._lib.vax_process_buffer.restype = ctypes.c_int
                return self._lib
            except Exception: return None
        return None

    def _legacy_python_instrumentation(self, content, filename):
        """Fallback: Lógica original em Python (usada no bootstrap)."""
        lines = content.splitlines()
        new_lines = []
        is_c = filename.endswith(('.c', '.cpp', '.h'))
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*")): continue
            
            match = self.c_func_regex.match(line) if is_c else self.pyx_func_regex.match(line)
            if match:
                name = match.group(2)
                if name not in self.blacklist:
                    tag = f'SOTERIA_ENTER("{name}");' if is_c else f'# TRACE: {name}'
                    new_lines.append(f"    {tag}")
        return "\n".join(new_lines)

    def instrument_code(self, content, filename):
        """Orquestrador: Tenta C, senão cai para Python."""
        kernel = self._load_native_kernel()
        
        if not kernel:
            return self._legacy_python_instrumentation(content, filename)

        try:
            in_bytes = content.encode('utf-8', errors='ignore')
            out_buffer = ctypes.create_string_buffer(len(in_bytes) * 2)
            is_c = 1 if filename.endswith(('.c', '.cpp', '.h')) else 0
            
            new_len = kernel.vax_process_buffer(in_bytes, out_buffer, len(in_bytes), is_c)
            return out_buffer.raw[:new_len].decode('utf-8', errors='ignore')
        except Exception:
            return self._legacy_python_instrumentation(content, filename)

    def generate_shadow(self, src_dir, shadow_dir):
        """Cria cópia vacinada com Isolamento Industrial (Anti-Plague)."""
        from pathlib import Path
        src_root = Path(src_dir).resolve()
        dst_root = Path(shadow_dir).resolve()
        
        # PODA ESTRITA: Nunca entrar nessas pastas
        FORBIDDEN = {'.doxoade', 'venv', '.git', '__pycache__', 'build', 'dist', 'logs'}

        if not src_root.exists(): return

        count = 0
        for root, dirs, files in os.walk(src_root):
            # Remove pastas proibidas do walk antes de descer
            dirs[:] = [d for d in dirs if d not in FORBIDDEN and not d.startswith('.')]
            
            for file in files:
                # SÓ vacina Bricks reais. Pula arquivos sintéticos/temporários
                if not file.endswith(('.py', '.pyx', '.c', '.cpp', '.h')): continue
                if 'shadow_exec' in file or 'vax' in file: continue
                
                f_path = Path(root) / file
                rel = f_path.relative_to(src_root)
                target = dst_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    content = f_path.read_text(encoding='utf-8', errors='ignore')
                    if f_path.suffix == '.py':
                        from .python_scribe import generate_python_shadow
                        vacinado = generate_python_shadow(content, f_path.name)
                    else:
                        vacinado = self.instrument_code(content, f_path.name)
                    
                    target.write_text(vacinado, encoding='utf-8')
                    count += 1
                except Exception: continue

        chief_heartbeat("SCRIBE", "SHADOW_STABILIZED", {"count": count})