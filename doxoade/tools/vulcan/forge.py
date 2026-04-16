# doxoade/doxoade/tools/vulcan/forge.py
import ast
import re
from pathlib import Path
from typing import Set
_BLACKLIST = frozenset({'click', 'rich', 'colorama', 'progressbar', 'prompt_toolkit', 'curses', 'ansi', 'ansitowin32', 'initialise', 'win32', 'winterm', '_winconsole', 'psutil', 'sqlite3', 'radon', 'pathspec', '__main__', 'doxcolors', 'termui'})
_CYTHON_RESERVED_IDENTIFIERS = frozenset({'include', 'cdef', 'cimport', 'cpdef', 'ctypedef', 'extern', 'gil', 'nogil', 'public', 'readonly'})
_SEMANTIC_COMMENT_PREFIXES = ('# cython:', '# ---', '# type:', '# noqa', '# pragma:')
_STUB_HEADER = "class _Stub:\n    RESET = RESET_ALL = BRIGHT = DIM = NORMAL = ''\n    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''\n    def __init__(self, *a, **kw): pass\n    def __call__(self, *a, **kw):\n        if len(a) == 1 and callable(a[0]) and not kw: return a[0]\n        return _Stub()\n    def __getattr__(self, _): return _Stub()\n    def __add__(self, o): return o if isinstance(o, str) else _Stub()\n    def __radd__(self, o): return o if isinstance(o, str) else _Stub()\n    def __str__(self): return ''\n    def __repr__(self): return ''\n    def __bool__(self): return False\nclick = colorama = rich = progressbar = prompt_toolkit = psutil = _Stub()\nFore = Back = Style = echo = secho = prompt = confirm = _Stub()\nargument = option = command = group = pass_context = Context = cli = _Stub()\nimport os\nimport sys\nimport re\nimport os as _os\nimport sys as _sys\n"
_SKIP_FILENAMES = frozenset({'__init__.py', '__main__.py'})
_RISKY_IMPORTS = frozenset({'ctypes', 'socket', 'subprocess', 'threading', 'multiprocessing', 'asyncio', 'llama_cpp'})
_BLANK_RE = re.compile('\\n{3,}')

def _strip_pyx_source(code: str) -> str:
    """
    Remove comentários puros e linhas em branco excessivas do .pyx gerado.

    Benefícios para o Cython:
      - Parser lê menos bytes → transpilação mais rápida
      - Arquivo .c gerado também é menor → GCC mais rápido

    Preserva comentários semânticos:
      # cython: ...   → diretivas de compilação
      # type: ...     → anotações de tipo para type checkers
      # noqa          → supressão de linting
      # pragma: ...   → cobertura de testes
      # ---           → separadores visuais
    """
    lines_out = []
    for line in code.splitlines():
        stripped = line.strip()
        if any((stripped.startswith(p) for p in _SEMANTIC_COMMENT_PREFIXES)):
            lines_out.append(line)
        elif stripped.startswith('#'):
            continue
        else:
            lines_out.append(line)
    result = '\n'.join(lines_out)
    result = _BLANK_RE.sub('\n\n', result)
    return result.strip() + '\n'

def assess_file_for_vulcan(file_path: str) -> tuple[bool, str | None]:
    """Heurística de elegibilidade. Retorna (True, None) para bons candidatos."""
    p = Path(file_path)
    if p.name in _SKIP_FILENAMES:
        return (False, f'arquivo de entrada/namespace ({p.name})')
    try:
        source = p.read_text(encoding='utf-8', errors='ignore')
        tree = ast.parse(source)
    except Exception as e:
        return (False, f'AST inválida ({type(e).__name__})')
    node_count = sum((1 for _ in ast.walk(tree)))
    if node_count > 3000:
        return (False, f'complexidade alta (nodes={node_count})')
    risky_hits = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            risky_hits += sum((1 for a in node.names if a.name.split('.')[0] in _RISKY_IMPORTS))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split('.')[0] in _RISKY_IMPORTS:
                risky_hits += 1
    if risky_hits >= 2 and node_count > 1000:
        return (False, f'arquivo complexo com APIs sensíveis (risk={risky_hits}, nodes={node_count})')
    return (True, None)

class VulcanForge(ast.NodeTransformer):
    """Transpilador Estrutural: Converte Python moderno em C-Style limpo."""

    def __init__(self, target_path: str=''):
        super().__init__()
        self.original_imports: list = []
        self.blacklist: Set[str] = _BLACKLIST
        self._blacklisted_names: Set[str] = set()
        self._name_rewrites: list[dict[str, str]] = []

    @staticmethod
    def _sanitize_identifier(name: str) -> str:
        if name in _CYTHON_RESERVED_IDENTIFIERS:
            return f'_{name}'
        return name

    def _is_blacklisted(self, module: str) -> bool:
        if not module:
            return False
        parts = module.replace('-', '_').split('.')
        return any((p in self.blacklist for p in parts))

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
        if node.level and node.level > 0:
            stubs = []
            for alias in node.names:
                stub_name = alias.asname or alias.name
                if stub_name == '*':
                    continue
                self._blacklisted_names.add(stub_name)
                stubs.append(ast.Assign(targets=[ast.Name(id=stub_name, ctx=ast.Store())], value=ast.Call(func=ast.Name(id='_Stub', ctx=ast.Load()), args=[], keywords=[]), lineno=node.lineno))
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
                       (tratado aqui para cobrir AugAssign e Tuple targets,
                        que visit_Assign não alcança)
        """
        if node.attr not in _CYTHON_RESERVED_IDENTIFIERS:
            return self.generic_visit(node)
        self.generic_visit(node)
        if isinstance(node.ctx, ast.Load):
            return ast.Call(func=ast.Name(id='getattr', ctx=ast.Load()), args=[node.value, ast.Constant(value=node.attr)], keywords=[])
        return node

    def visit_Assign(self, node):
        """
        Converte atribuição simples a atributo reservado em setattr().

        x.include = val  →  setattr(x, 'include', val)
        """
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute) and (node.targets[0].attr in _CYTHON_RESERVED_IDENTIFIERS):
            self.generic_visit(node)
            attr_node = node.targets[0]
            return ast.Expr(value=ast.Call(func=ast.Name(id='setattr', ctx=ast.Load()), args=[attr_node.value, ast.Constant(value=attr_node.attr), node.value], keywords=[]))
        self.generic_visit(node)
        return node

    def visit_AugAssign(self, node):
        """
        FIX #1: Converte AugAssign com atributo reservado em setattr + getattr.

        obj.include += val
        →  setattr(obj, 'include', getattr(obj, 'include') + val)

        Sem este visitor, `obj.include += val` gerava parse error no Cython
        pois visit_Assign nunca é chamado para AugAssign.
        """
        self.generic_visit(node)
        if isinstance(node.target, ast.Attribute) and node.target.attr in _CYTHON_RESERVED_IDENTIFIERS:
            obj = node.target.value
            attr = node.target.attr
            new_value = ast.BinOp(left=ast.Call(func=ast.Name(id='getattr', ctx=ast.Load()), args=[obj, ast.Constant(value=attr)], keywords=[]), op=node.op, right=node.value)
            return ast.Expr(value=ast.Call(func=ast.Name(id='setattr', ctx=ast.Load()), args=[obj, ast.Constant(value=attr), new_value], keywords=[]))
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
          x: int               →  mantido como AnnAssign com anotação 'object'
                                  (FIX #3: necessário para campos de @dataclass sem valor)
          x: int = field(...)  →  x: object = field(...)  (dataclass field com valor:
                                   mantém anotação como 'object' para @dataclass)
        """
        if node.value is None:
            node.annotation = ast.Name(id='object', ctx=ast.Load())
            return node
        is_dataclass_field = isinstance(node.value, ast.Call) and isinstance(getattr(node.value, 'func', None), ast.Name) and (node.value.func.id in ('field', 'Field', 'dataclass_field'))
        if is_dataclass_field:
            node.annotation = ast.Name(id='object', ctx=ast.Load())
            return node
        return ast.Assign(targets=[node.target], value=node.value, lineno=node.lineno)

    def _transform_funcdef(self, node):
        """
        Lógica compartilhada entre visit_FunctionDef e visit_AsyncFunctionDef.
        Remove type hints, decorators e aplica sufixo _vulcan_optimized.
        """
        node.returns = None
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
            node.name = f'{node.name}_vulcan_optimized'
        try:
            self.generic_visit(node)
        finally:
            if name_map:
                self._name_rewrites.pop()
        return node

    def visit_FunctionDef(self, node):
        return self._transform_funcdef(node)

    def visit_AsyncFunctionDef(self, node):
        return self._transform_funcdef(node)

    def generate_source(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()
        tree = ast.parse(source)
        transformed = self.visit(tree)
        ast.fix_missing_locations(transformed)
        header = '# cython: language_level=3, boundscheck=False, wraparound=False\n'
        header += 'import sys, os, json\n'
        header += 'try: from typing import *\nexcept: pass\n\n'
        header += _STUB_HEADER
        raw = header + ast.unparse(transformed)
        return _strip_pyx_source(raw)