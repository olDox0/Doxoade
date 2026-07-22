# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/scribe.py
"""
Sotéria Scribe v5.0 — Vaccinator de Código (C nativo + fallback Python).
"""
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
        self._lib = None

        self.pyx_func_regex = re.compile(r'^\s*(def|cdef|cpdef)\s+(\w+)\s*\(')
        self.c_func_regex = re.compile(r'^([\w\s\*]+?)\s*(\w+)\s*\(([^)]*)\)\s*\{')
        self.mem_pattern = re.compile(
            r'\b(malloc|free|calloc|realloc|PyMem_Malloc|PyMem_Free)\b\s*\((.*)\)')
        self.io_re = re.compile(r'\b(fopen|printf|fprintf|CreateThread)\b\s*\(')

        self.blacklist = {
            'soteria_mark', 'soteria_dispatch', 'soteria_init', 'main',
            'if', 'while', 'for', 'return', 'else', 'switch'
        }
        self.alloc_map = {
            "malloc": "ALLOC_MALLOC", "free": "ALLOC_MALLOC",
            "calloc": "ALLOC_MALLOC", "realloc": "ALLOC_MALLOC",
            "PyMem_Malloc": "ALLOC_PYMEM", "PyMem_Free": "ALLOC_PYMEM"
        }

    # ─────────────────────────────────────────────────────────────
    # NATIVE KERNEL (DLL)
    # ─────────────────────────────────────────────────────────────
    def _load_lib(self):
        """Carrega a DLL com assinatura v4.0 (5 parâmetros)."""
        if self._lib:
            return self._lib
        if self.dll_path.exists():
            try:
                self._lib = ctypes.CDLL(str(self.dll_path))
                self._lib.vax_process_buffer.argtypes = [
                    ctypes.c_char_p,   # input
                    ctypes.c_char_p,   # output
                    ctypes.c_int,      # in_len
                    ctypes.c_int,      # out_len
                    ctypes.c_int       # is_c_lang
                ]
                self._lib.vax_process_buffer.restype = ctypes.c_int
                return self._lib
            except Exception:
                return None
        return None

    # ─────────────────────────────────────────────────────────────
    # ORQUESTRADOR
    # ─────────────────────────────────────────────────────────────
    def instrument_code(self, content, filename):
        """C nativo para .c/.cpp/.h — fallback Python para .py/.pyx."""
        is_c = filename.endswith(('.c', '.cpp', '.h'))

        if is_c:
            kernel = self._load_lib()
            if kernel:
                try:
                    in_bytes = content.encode('utf-8', errors='ignore')
                    out_len = len(in_bytes) * 3
                    out_buffer = ctypes.create_string_buffer(out_len)
                    new_len = kernel.vax_process_buffer(
                        in_bytes, out_buffer, len(in_bytes), out_len, 1)
                    if new_len > 0:
                        return out_buffer.raw[:new_len].decode(
                            'utf-8', errors='ignore')
                except Exception:
                    pass
            return self._legacy_python_instrumentation(content, filename)
        else:
            return self._legacy_python_instrumentation(content, filename)

    # ─────────────────────────────────────────────────────────────
    # FALLBACK PYTHON
    # ─────────────────────────────────────────────────────────────
    def _legacy_python_instrumentation(self, content, filename):
        lines = content.splitlines()
        new_lines = []
        is_c = filename.endswith(('.c', '.cpp', '.h'))

        for i, line in enumerate(lines):
            new_lines.append(line)
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", "/*")):
                continue
            match = (self.c_func_regex.match(line) if is_c
                     else self.pyx_func_regex.match(line))
            if match:
                name = match.group(2)
                if name not in self.blacklist:
                    tag = (f'SOTERIA_ENTER("{name}");' if is_c
                           else f'# TRACE: {name}')
                    new_lines.append(f"    {tag}")
        return "\n".join(new_lines)

    # ─────────────────────────────────────────────────────────────
    # CYTHON HIGH-THROUGHPUT
    # ─────────────────────────────────────────────────────────────
    def instrument_pyx(self, content, filename):
        if "soteria_malloc_ext" in content:
            return content
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
            if not stripped or stripped.startswith(("#", "'''", '"""')):
                new_lines.append(line)
                continue
            ln_num = i + 1
            if "(" in stripped:
                if any(x in stripped for x in ["malloc", "free", "PyMem"]):
                    line = self.mem_pattern.sub(
                        lambda m: (
                            f'soteria_{"free" if "free" in m.group(1).lower() else "malloc"}_ext('
                            f'{m.group(2)}, '
                            f'{"ALLOC_PYMEM" if "PyMem" in m.group(1) else "ALLOC_MALLOC"}, '
                            f'"{safe_filename}", {ln_num})'),
                        line)
                match = self.pyx_func_regex.match(line)
                if match:
                    name = match.group(2)
                    indent = match.group(0).split(match.group(1))[0]
                    new_lines.append(line)
                    new_lines.append(
                        f'{indent}    soteria_mark("TRACEBACK: {name}", '
                        f'"{safe_filename}", {ln_num})')
                    continue
            if "ctypes." in stripped:
                new_lines.append(
                    f'{self._get_indent(line)}soteria_mark('
                    f'"PRE-CALL: Ctypes", "{safe_filename}", {ln_num})')
            new_lines.append(line)
        return "\n".join(new_lines)

    @staticmethod
    def _get_indent(line: str) -> str:
        return line[:len(line) - len(line.lstrip())]

    # ─────────────────────────────────────────────────────────────
    # SHADOW GENERATION
    # ─────────────────────────────────────────────────────────────
    def generate_shadow(self, src_dir, shadow_dir):
        src_root = Path(src_dir).resolve()
        dst_root = Path(shadow_dir).resolve()
        FORBIDDEN = {'.doxoade', 'venv', '.git', '__pycache__',
                     'build', 'dist', 'logs'}
        if not src_root.exists():
            return
        count = 0
        for root, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs
                       if d not in FORBIDDEN and not d.startswith('.')]
            for file in files:
                if not file.endswith(('.py', '.pyx', '.c', '.cpp', '.h')):
                    continue
                if 'shadow_exec' in file or 'vax' in file:
                    continue
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
                except Exception:
                    continue
        chief_heartbeat("SCRIBE", "SHADOW_STABILIZED", {"count": count})