# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/forge.py (v96.9 Platinum)
import ast
from typing import Set

# ---------------------------------------------------------------------------
# Módulos bloqueados — imports removidos e substituídos por stubs no .pyx.
# ---------------------------------------------------------------------------
_BLACKLIST = frozenset({
    # UI / Terminal
    'click', 'rich', 'colorama', 'progressbar', 'prompt_toolkit', 'curses',
    # Submodules explícitos do colorama
    'ansi', 'ansitowin32', 'initialise', 'win32', 'winterm', '_winconsole',
    # C-extension heavy / OS-level
    'psutil', 'sqlite3', 'radon', 'pathspec',
    # Internos do doxoade já compilados (evita import circular no silo)
    'doxcolors', 'termui',
})

# Arquivos do próprio Vulcan que NÃO devem ser compilados.
# Eles usam imports relativos (from .environment import ...) que o Cython
# não consegue resolver dentro do silo isolado → returncode=3221356611.
_VULCAN_SELF = frozenset({
    # Módulos internos do Vulcan (imports relativos quebram no silo)
    'autopilot', 'compiler', 'forge', 'bridge', 'advisor',
    'environment', 'core', 'guards', 'lab', 'sentinel',
    'diagnostic', 'optimizer', 'reaper', 'asm_kernels',
    # Colorama internals: usam ctypes raw + estruturas C que o Cython não transpila.
    # Já estão no _BLACKLIST para remoção de imports; aqui evitamos compilar o
    # próprio módulo (resulta em Cython.Compiler.Errors.CompileError).
    'termui', '_winconsole', 'win32', 'winterm', 'ansitowin32', 'initialise',
    # Outros módulos pesados em ctypes/C-extensions que falham no silo Cython
    '_compat', '_pswindows',
})

# ---------------------------------------------------------------------------
# Stubs injetados no header do .pyx.
#
# Estratégia: cada módulo blacklisted torna-se uma instância de _Stub.
# _Stub responde a qualquer acesso de atributo (click.group, Fore.RED, etc.)
# retornando a si mesmo, permitindo chamadas encadeadas sem NameError.
# ---------------------------------------------------------------------------
_STUB_HEADER = '''\
# --- VULCAN STUBS: substituições de imports blacklisted ---
class _Stub:
    """Absorve qualquer acesso de atributo ou chamada sem erro."""
    RESET = RESET_ALL = BRIGHT = DIM = NORMAL = ''
    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''

    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw): return _Stub()
    def __getattr__(self, _): return _Stub()
    def __add__(self, o): return o if isinstance(o, str) else _Stub()
    def __radd__(self, o): return o if isinstance(o, str) else _Stub()
    def __str__(self): return ''
    def __repr__(self): return ''
    def __bool__(self): return False
    # Suporte a uso como decorador: @cli.command() → retorna a função intacta
    def __call__(self, *a, **kw):
        if len(a) == 1 and callable(a[0]) and not kw:
            return a[0]   # comportamento de decorador pass-through
        return _Stub()

# Nomes de módulo (usados como `click.X`, `colorama.Fore`, etc.)
click         = _Stub()
colorama      = _Stub()
rich          = _Stub()
progressbar   = _Stub()
prompt_toolkit = _Stub()
psutil        = _Stub()

# Nomes de atributo comuns importados diretamente
Fore          = _Stub()
Back          = _Stub()
Style         = _Stub()
echo          = _Stub()
secho         = _Stub()
prompt        = _Stub()
confirm       = _Stub()
argument      = _Stub()
option        = _Stub()
command       = _Stub()
group         = _Stub()
pass_context  = _Stub()
Context       = _Stub()
cli           = _Stub()
# --- FIM DOS STUBS ---
'''



_SKIP_FILENAMES = frozenset({'__init__.py', '__main__.py'})
_RISKY_IMPORTS = frozenset({'ctypes', 'socket', 'subprocess', 'threading', 'multiprocessing', 'asyncio', 'llama_cpp'})


def assess_file_for_vulcan(file_path: str) -> tuple[bool, str | None]:
    """Heurística de elegibilidade para reduzir compilações desfuncionais.

    Retorna (True, None) quando o arquivo é bom candidato para forja.
    """
    from pathlib import Path

    p = Path(file_path)
    if p.name in _SKIP_FILENAMES:
        return False, f"arquivo de entrada/namespace ({p.name})"

    if VulcanForge.is_self_referential(str(p)):
        return False, "módulo interno do Vulcan"

    try:
        source = p.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(source)
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
        self.original_imports: list = []
        self.blacklist: Set[str] = _BLACKLIST
        self._blacklisted_names: Set[str] = set()

    @staticmethod
    def is_self_referential(file_path: str) -> bool:
        """
        Retorna True se o arquivo faz parte do próprio Vulcan.
        Esses módulos usam imports relativos que o Cython não resolve no silo.
        """
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
        # __future__ precisa estar no topo absoluto; após inserir header do Vulcan
        # ele quebraria a compilação Cython. Removemos por segurança.
        if node.module == '__future__':
            return None

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
        node.annotation = None
        return node

    def visit_AnnAssign(self, node):
        if node.value is None:
            return None
        return ast.Assign(
            targets=[node.target],
            value=node.value,
            lineno=node.lineno,
        )

    def visit_FunctionDef(self, node):
        node.returns = None
        node.decorator_list = []
        if not node.name.endswith('_vulcan_optimized'):
            node.name = f"{node.name}_vulcan_optimized"
        self.generic_visit(node)
        return node

    def generate_source(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        tree = ast.parse(source)
        transformed = self.visit(tree)
        ast.fix_missing_locations(transformed)

        header  = "# cython: language_level=3, boundscheck=False, wraparound=False\n"
        header += "import sys, os, json\n"
        header += "try: from typing import *\nexcept: pass\n\n"
        header += _STUB_HEADER

        return header + ast.unparse(transformed)