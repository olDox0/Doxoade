# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/forge.py (v97.0 — reserved keyword attribute fix + pyx strip)
import ast
import re
from typing import Set

_BLACKLIST = frozenset({
    'click', 'rich', 'colorama', 'progressbar', 'prompt_toolkit', 'curses',
    'ansi', 'ansitowin32', 'initialise', 'win32', 'winterm', '_winconsole',
    'psutil', 'sqlite3', 'radon', 'pathspec', '__main__',
    'doxcolors', 'termui',
})

_VULCAN_SELF = frozenset({
    'autopilot', 'compiler', 'forge', 'bridge', 'advisor',
    'environment', 'core', 'guards', 'lab', 'sentinel',
    'diagnostic', 'optimizer', 'reaper', 'asm_kernels',
    'termui', '_winconsole', 'win32', 'winterm', 'ansitowin32', 'initialise',
    '_compat', '_pswindows',
})

# Palavras reservadas Cython que quebram quando usadas como argumento OU atributo.
# Quando encontradas como atributo: obj.include → getattr(obj, 'include')
_CYTHON_RESERVED_IDENTIFIERS = frozenset({
    'include', 'cdef', 'cimport', 'cpdef', 'ctypedef', 'extern',
    'gil', 'nogil', 'public', 'readonly',
})

_STUB_HEADER = '''\
class _Stub:
    RESET = RESET_ALL = BRIGHT = DIM = NORMAL = ''
    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''
    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw):
        if len(a) == 1 and callable(a[0]) and not kw: return a[0]
        return _Stub()
    def __getattr__(self, _): return _Stub()
    def __add__(self, o): return o if isinstance(o, str) else _Stub()
    def __radd__(self, o): return o if isinstance(o, str) else _Stub()
    def __str__(self): return ''
    def __repr__(self): return ''
    def __bool__(self): return False
click = colorama = rich = progressbar = prompt_toolkit = psutil = _Stub()
Fore = Back = Style = echo = secho = prompt = confirm = _Stub()
argument = option = command = group = pass_context = Context = cli = _Stub()
import os
import sys
import re
import os as _os
import sys as _sys
'''

_SKIP_FILENAMES   = frozenset({'__init__.py', '__main__.py'})
_RISKY_IMPORTS    = frozenset({
    'ctypes', 'socket', 'subprocess', 'threading',
    'multiprocessing', 'asyncio', 'llama_cpp',
})

# Regex para strip de comentários inline (não destrói strings com #)
_COMMENT_RE = re.compile(r'(?m)^\s*#.*\n?')
_BLANK_RE   = re.compile(r'\n{3,}')


def _strip_pyx_source(code: str) -> str:
    """
    Remove comentários puros e linhas em branco excessivas do .pyx gerado.

    Benefícios para o Cython:
      - Parser lê menos bytes → transpilação mais rápida
      - Arquivo .c gerado também é menor → GCC mais rápido

    NÃO remove comentários de diretiva (# cython: ...) pois são semânticos.
    """
    lines_out = []
    for line in code.splitlines():
        stripped = line.strip()
        # Mantém diretivas Cython e linhas de código não-comentário
        if stripped.startswith('# cython:') or stripped.startswith('# ---'):
            lines_out.append(line)
        elif stripped.startswith('#'):
            continue  # remove comentário puro
        else:
            lines_out.append(line)

    # Colapsa sequências de mais de 2 linhas em branco para 1
    result = '\n'.join(lines_out)
    result = _BLANK_RE.sub('\n\n', result)
    return result.strip() + '\n'


def assess_file_for_vulcan(file_path: str) -> tuple[bool, str | None]:
    """Heurística de elegibilidade. Retorna (True, None) para bons candidatos."""
    from pathlib import Path

    p = Path(file_path)
    if p.name in _SKIP_FILENAMES:
        return False, f"arquivo de entrada/namespace ({p.name})"

    if VulcanForge.is_self_referential(str(p)):
        return False, "módulo interno do Vulcan"

    try:
        source = p.read_text(encoding='utf-8', errors='ignore')
        tree   = ast.parse(source)
    except Exception as e:
        return False, f"AST inválida ({type(e).__name__})"

    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > 2400:
        return False, f"complexidade alta (nodes={node_count})"

    risky_hits = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            risky_hits += sum(1 for a in node.names if a.name.split('.')[0] in _RISKY_IMPORTS)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split('.')[0] in _RISKY_IMPORTS:
                risky_hits += 1

    if risky_hits >= 2 and node_count > 900:
        return False, f"arquivo complexo com APIs sensíveis (risk={risky_hits}, nodes={node_count})"

    return True, None


class VulcanForge(ast.NodeTransformer):
    """Transpilador Estrutural: Converte Python moderno em C-Style limpo."""

    def __init__(self, target_path: str = ""):
        super().__init__()
        self.original_imports:  list    = []
        self.blacklist:         Set[str] = _BLACKLIST
        self._blacklisted_names: Set[str] = set()
        self._name_rewrites:    list[dict[str, str]] = []

    @staticmethod
    def _sanitize_identifier(name: str) -> str:
        if name in _CYTHON_RESERVED_IDENTIFIERS:
            return f"_{name}"
        return name

    @staticmethod
    def is_self_referential(file_path: str) -> bool:
        from pathlib import Path
        stem = Path(file_path).stem.lower()
        return stem in _VULCAN_SELF

    def _is_blacklisted(self, module: str) -> bool:
        if not module:
            return False
        parts = module.replace('-', '_').split('.')
        return any(p in self.blacklist for p in parts)

    def visit_Import(self, node):
        kept = []
        for alias in node.names:
            root = alias.name.split('.')[0]
            if root in self.blacklist:
                self._blacklisted_names.add(alias.asname or root)
            else:
                kept.append(alias)
        if not kept:
            return None
        node.names = kept
        self.original_imports.append(ast.unparse(node))
        return node

    def visit_ImportFrom(self, node):
        if node.module == '__future__':
            return None

        # Imports relativos (from .sibling import X) não funcionam em binários
        # Cython isolados — converter em _Stub() para evitar ImportError em runtime.
        if node.level and node.level > 0:
            stubs = []
            for alias in node.names:
                stub_name = alias.asname or alias.name
                if stub_name == '*':
                    continue  # from .pkg import * — ignora silenciosamente
                self._blacklisted_names.add(stub_name)
                stubs.append(
                    ast.Assign(
                        targets=[ast.Name(id=stub_name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id='_Stub', ctx=ast.Load()),
                            args=[], keywords=[],
                        ),
                        lineno=node.lineno,
                    )
                )
            return stubs if stubs else None

        if node.module and self._is_blacklisted(node.module):
            for alias in node.names:
                self._blacklisted_names.add(alias.asname or alias.name)
            return None

        if node.names:
            kept = []
            for alias in node.names:
                if alias.name in self.blacklist:
                    self._blacklisted_names.add(alias.asname or alias.name)
                else:
                    kept.append(alias)
            if not kept:
                return None
            node.names = kept

        if node.module:
            self.original_imports.append(ast.unparse(node))
        return node

    def visit_arg(self, node):
        """Renomeia argumentos que colidem com palavras reservadas Cython."""
        node.annotation = None
        if isinstance(node.arg, str):
            node.arg = self._sanitize_identifier(node.arg)
        return node

    def visit_Attribute(self, node):
        """
        Converte acesso a atributo reservado Cython para getattr/setattr.

        Problema: `pattern.include` → Cython parse error
                  `Expected an identifier` porque `include` é reservado.

        Solução Load:  pattern.include        → getattr(pattern, 'include')
        Solução Store: pattern.include = val  → setattr(pattern, 'include', val)
        """
        if node.attr not in _CYTHON_RESERVED_IDENTIFIERS:
            return self.generic_visit(node)

        # Visita o objeto base antes de reescrever
        self.generic_visit(node)

        if isinstance(node.ctx, ast.Load):
            # pattern.include → getattr(pattern, 'include')
            return ast.Call(
                func=ast.Name(id='getattr', ctx=ast.Load()),
                args=[node.value, ast.Constant(value=node.attr)],
                keywords=[],
            )

        if isinstance(node.ctx, ast.Store):
            # pattern.include = val  →  (tratado no pai, ver visit_Assign)
            # Retorna o nó original — visit_Assign fará o setattr
            return node

        return node

    def visit_Assign(self, node):
        """
        Converte atribuição a atributo reservado em setattr().

        x.include = val  →  setattr(x, 'include', val)
        """
        self.generic_visit(node)

        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Attribute)
            and node.targets[0].attr in _CYTHON_RESERVED_IDENTIFIERS
        ):
            attr_node = node.targets[0]
            return ast.Expr(
                value=ast.Call(
                    func=ast.Name(id='setattr', ctx=ast.Load()),
                    args=[attr_node.value, ast.Constant(value=attr_node.attr), node.value],
                    keywords=[],
                )
            )
        return node

    def visit_Name(self, node):
        if self._name_rewrites and node.id in self._name_rewrites[-1]:
            node.id = self._name_rewrites[-1][node.id]
        return node

    def visit_AnnAssign(self, node):
        """
        Converte anotações de tipo para Cython-safe.

        Casos:
          x: int = 5          →  x = 5            (remove anotação — Cython não precisa)
          x: int               →  None             (remove anotação sem valor — não gera código)
          x: int = field(...)  →  x: object = field(...)  (dataclass field: mantém anotação
                                   como 'object' para que @dataclass não quebre)
        """
        if node.value is None:
            return None  # só anotação, sem valor — nenhum efeito em runtime

        # Detecta campo de dataclass: valor é uma Call a field() ou similar
        is_dataclass_field = (
            isinstance(node.value, ast.Call)
            and isinstance(getattr(node.value, 'func', None), ast.Name)
            and node.value.func.id in ('field', 'Field', 'dataclass_field')
        )

        if is_dataclass_field:
            # Mantém como AnnAssign com anotação 'object' — @dataclass requer anotação
            node.annotation = ast.Name(id='object', ctx=ast.Load())
            return node

        # Caso geral: converte para Assign simples sem anotação
        return ast.Assign(
            targets=[node.target],
            value=node.value,
            lineno=node.lineno,
        )

    def visit_FunctionDef(self, node):
        node.returns        = None
        node.decorator_list = []

        name_map: dict[str, str] = {}
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            args.append(node.args.vararg)
        if node.args.kwarg:
            args.append(node.args.kwarg)
        for arg in args:
            rewritten = self._sanitize_identifier(arg.arg)
            if rewritten != arg.arg:
                name_map[arg.arg] = rewritten

        if name_map:
            self._name_rewrites.append(name_map)

        if not node.name.endswith('_vulcan_optimized'):
            node.name = f"{node.name}_vulcan_optimized"

        try:
            self.generic_visit(node)
        finally:
            if name_map:
                self._name_rewrites.pop()

        return node

    def generate_source(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        tree        = ast.parse(source)
        transformed = self.visit(tree)
        ast.fix_missing_locations(transformed)

        # Diretivas Cython (semânticas — não são removidas pelo strip)
        header  = "# cython: language_level=3, boundscheck=False, wraparound=False\n"
        header += "import sys, os, json\n"
        header += "try: from typing import *\nexcept: pass\n\n"
        header += _STUB_HEADER

        raw = header + ast.unparse(transformed)

        # Strip pré-compilação: remove comentários e linhas em branco excessivas
        # Reduz tamanho do .pyx → parse Cython mais rápido → GCC mais rápido
        return _strip_pyx_source(raw)