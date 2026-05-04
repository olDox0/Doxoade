# doxoade/doxoade/tools/vulcan/forge.py
import ast
import os
import re
from pathlib import Path
from typing import Set
_BLACKLIST = frozenset({'click', 'rich', 'colorama', 'progressbar', 'prompt_toolkit', 'curses', 'ansi', 'ansitowin32', 'initialise', 'win32', 'winterm', '_winconsole', 'psutil', 'sqlite3', 'radon', 'pathspec', '__main__', 'doxcolors', 'termui'})
_CYTHON_RESERVED_IDENTIFIERS = frozenset({'include', 'cdef', 'cimport', 'cpdef', 'ctypedef', 'extern', 'gil', 'nogil', 'public', 'readonly'})
_SEMANTIC_COMMENT_PREFIXES = ('# cython:', '# ---', '# type:', '# noqa', '# pragma:')
#_STUB_HEADER = "class _Stub:\n    RESET = RESET_ALL = BRIGHT = DIM = NORMAL = ''\n    RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ''\n    def __init__(self, *a, **kw): pass\n    def __call__(self, *a, **kw):\n        if len(a) == 1 and callable(a[0]) and not kw: return a[0]\n        return _Stub()\n    def __getattr__(self, _): return _Stub()\n    def __add__(self, o): return o if isinstance(o, str) else _Stub()\n    def __radd__(self, o): return o if isinstance(o, str) else _Stub()\n    def __str__(self): return ''\n    def __repr__(self): return ''\n    def __bool__(self): return False\nclick = colorama = rich = progressbar = prompt_toolkit = psutil = _Stub()\nFore = Back = Style = echo = secho = prompt = confirm = _Stub()\nargument = option = command = group = pass_context = Context = cli = _Stub()\nimport os\nimport sys\nimport re\nimport os as _os\nimport sys as _sys\n"
_STUB_HEADER = """
class _Stub:
    def __getattr__(self, _): return _Stub()
    def __call__(self, *a, **kw): return _Stub()
"""
_SKIP_FILENAMES = frozenset({'__init__.py', '__main__.py'})
_RISKY_IMPORTS = frozenset({'ctypes', 'socket', 'subprocess', 'threading', 'multiprocessing', 'asyncio', 'llama_cpp'})
_BLANK_RE = re.compile('\\n{3,}')
_PYX_HEADER = '# cython: language_level=3, boundscheck=False, wraparound=False\n# cython: initializedcheck=False, cdivision=True\n'

def enrich_pyx(source_code):
    tree = ast.parse(source_code)
    enricher = SmartEnricher()
    enricher.visit(tree)

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

class VulcanForge:
    """Transpilador Estrutural: Converte Python moderno em C-Style limpo."""

    def __init__(self, target_path: str=''):
        super().__init__()
        self.original_imports: list = []
        self.blacklist: Set[str] = _BLACKLIST
        self._blacklisted_names: Set[str] = set()
        self._name_rewrites: list[dict[str, str]] = []
        self.target_path = target_path
        self.blacklist = {'click', 'rich', 'colorama', 'progressbar', 'click_echo'}
        self.hot_names = {'n', 'i', 'j', 'k', 'idx', 'count', 'size', 'offset', 'delta', 'last_id', 'current_id', 'doc_id'}

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

    def generate_source(self, file_path):
        p = Path(file_path)
        raw_source = p.read_text(encoding='utf-8', errors='ignore')
        
        # Extração de Future Imports
        future_imports = re.findall(r'^(from\s+__future__\s+import\s+.+)$', raw_source, re.M)
        clean_source = re.sub(r'^(from\s+__future__\s+import\s+.+)$', '', raw_source, flags=re.M)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(clean_source)
        
        header = "\n".join(future_imports) + "\n" if future_imports else ""
        header += _PYX_HEADER + _STUB_HEADER
        
        local_functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self._local_funcs = local_functions
        
        # [INTELLIGENCE] Coleta nomes que serão stubbed (fantasiados)
        stub_targets = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in self.blacklist:
                for alias in node.names:
                    stub_targets.add(alias.asname or alias.name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.blacklist:
                        stub_targets.add(alias.asname or alias.name)

        # [INTELLIGENCE] Só injeta o link nativo se a função 'encode_varint' estiver presente
        needs_nexus_math = "def encode_varint" in content
        
        pyx_lines = []
        if future_imports:
            pyx_lines.extend(future_imports)
        
        pyx_lines = [
            "# cython: language_level=3",
            "# cython: boundscheck=False",
            "# cython: wraparound=True", # Volte para True para evitar avisos de [-1]
            "# cython: cdivision=True",
            "import sys, os, json, struct",
            "from libc.stdint cimport int64_t",
            "",
            # Definição única da classe _Stub
            "class _Stub:",
            "    def __getattr__(self, _): return _Stub()",
            "    def __call__(self, *a, **kw): return _Stub()"
        ]

        pyx_lines.append("\n# --- NEXUS NATIVE KERNELS (Tier 1 Elite) ---")
        pyx_lines.append("cdef extern nogil:")
        pyx_lines.append("    int64_t nexus_raw_search(const unsigned char* haystack, long h_len, const unsigned char* needle, long n_len)")
        pyx_lines.append("    long nexus_asm_popcount(long value)")

        for name in self.blacklist:
            pyx_lines.append(f"{name} = _Stub()")
       
        pyx_lines.append(_STUB_HEADER)

        if needs_nexus_math:
            # Localiza o caminho absoluto do kernel no Core do Doxoade
            import doxoade.tools.vulcan as v_mod
            kernel_path = os.path.join(os.path.dirname(v_mod.__file__), 'nexus_math.c')
            kernel_path = kernel_path.replace("\\", "/") # Normaliza para o Cython
            
            pyx_lines.append("\n# --- NATIVE KERNEL LINK (Tier 1) ---")
            # O SEGREDO: Usamos o caminho absoluto. O GCC não terá como errar.
            pyx_lines.append(f"cdef extern from '{kernel_path}' nogil:")
            pyx_lines.append("    int nexus_encode_varint_branchless(unsigned long n, unsigned char* out)")

        pyx_lines.append("class _Stub:\n    def __getattr__(self, _): return _Stub()\n    def __call__(self, *a, **kw): return _Stub()")
        
        # Injeta os fantasmas para as libs de UI
        for name in stub_targets.union(self.blacklist):
            pyx_lines.append(f"{name} = _Stub()")

        optimized_functions = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                optimized_functions.append(node.name)
                pyx_lines.append(self._forge_node(node))
            elif isinstance(node, ast.ClassDef):
                pyx_lines.append(f"class {node.name}:")
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        pyx_lines.append(self._forge_node(sub, indent="    "))
                    else:
                        pyx_lines.append("    " + ast.unparse(sub).replace("\n", "\n    "))
            else:
                # Pula imports originais que estão na blacklist
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if hasattr(node, 'module') and node.module in self.blacklist: continue
                pyx_lines.append(ast.unparse(node))

        pyx_lines.append("\n# --- INTERNAL NEXUS LINKS ---")
        for func_name in optimized_functions:
            pyx_lines.append(f"{func_name} = {func_name}_vulcan_optimized")

        return "\n".join(pyx_lines)

    def _forge_node(self, node, indent=""):
        name = node.name if indent else f"{node.name}_vulcan_optimized"
        hot_vars = self._identify_hot_vars(node)
        
        # Bloqueia tipagem de argumentos e nomes reservados
        forbidden = {'kwargs', 'args', 'self', 'cls'}
        arg_names = {a.arg for a in node.args.args}
        if node.args.vararg: arg_names.add(node.args.vararg.arg)
        if node.args.kwarg: arg_names.add(node.args.kwarg.arg)

        class InternalCallFixer(ast.NodeTransformer):
            def __init__(self, locals): self.locals = locals
            def visit_Call(self, n):
                if isinstance(n.func, ast.Name) and n.func.id in self.locals:
                    # Redireciona para a versão otimizada se estiver no mesmo módulo
                    n.func.id = f"{n.func.id}_vulcan_optimized"
                return n

        # Aplica a correção antes de dar unparse
        fixer = InternalCallFixer(self._local_funcs)
        node = fixer.visit(node)

        # Limpeza de anotações complexas
        for arg in node.args.args: arg.annotation = None
        node.returns = None

        args_str = ast.unparse(node.args)
        
        if node.name == "encode_varint":
            return "\n".join([f"{indent}def {name}(long n):", f"{indent}    cdef unsigned char[10] buf", f"{indent}    cdef int length = nexus_encode_varint_branchless(n, buf)", f"{indent}    return bytearray(buf[:length])"])

        code = [f"{indent}def {name}({args_str}):"]
        if hot_vars:
            code.append(f"{indent}    # --- VULCAN HOT VARS ---")
            for var, ctype in hot_vars.items():
                if var not in arg_names and var not in forbidden:
                    code.append(f"{indent}    cdef {ctype} {var}")
        
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant): continue
            line = ast.unparse(stmt).replace("\n", "\n" + indent + "    ")
            code.append(f"{indent}    {line}")
        return "\n".join(code)

    def _forge_function(self, node):
        """Transforma uma função Python em uma função C-Enhanced."""
        func_name = f"{node.name}_vulcan_optimized"
        
        # Identifica variáveis para tipagem automática
        hot_vars = self._identify_hot_vars(node)
        
        # Reconstrói a assinatura
        args = ast.unparse(node.args)
        
        lines = [f"def {func_name}({args}):"]
        
        # Injeta as declarações cdef (Nervos de Aço)
        if hot_vars:
            lines.append("    # --- VULCAN TYPE INJECTION ---")
            for var, ctype in hot_vars.items():
                lines.append(f"    cdef {ctype} {var}")
        
        # Extrai o corpo da função e remove o 'def' original
        body_code = ""
        for stmt in node.body:
            # Pula docstrings para economizar bytes e parsing
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            body_code += "    " + ast.unparse(stmt).replace("\n", "\n    ") + "\n"
        
        lines.append(body_code)
        return "\n".join(lines)
        
    def _identify_hot_vars(self, node):
        vars_found = {}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign):
                for target in sub.targets:
                    if isinstance(target, ast.Name):
                        # PROTEÇÃO: Ignora qualquer variável que comece com '_'
                        if target.id in self.hot_names and not target.id.startswith('_'):
                            vars_found[target.id] = "long"
        return vars_found

    @staticmethod
    def is_self_referential(path):
        return "doxoade/tools/vulcan" in path.replace("\\", "/")
        
class SmartEnricher(ast.NodeVisitor):
    """Analista Semântico: Transforma intenção Python em Tipos C."""
    def __init__(self):
        self.vars_to_type = {} # nome -> tipo C

    def visit_FunctionDef(self, node):
        # 1. Heurística de Nomes (Padrão de Engenharia)
        integers = {'n', 'i', 'j', 'k', 'idx', 'count', 'size', 'length', 'offset', 'delta', 'attempt', 'retries'}
        
        # Analisa Argumentos
        for arg in node.args.args:
            if arg.arg.lower() in integers:
                self.vars_to_type[arg.arg] = "long"

        # 2. Varredura de Atribuições
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                # Se x = 0 ou x = 1, tratamos como long
                if isinstance(child.value, ast.Constant) and type(child.value.value) is int:
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            self.vars_to_type[target.id] = "long"
            
            # Se for alvo de range, é obrigatoriamente um índice (Py_ssize_t)
            if isinstance(child, ast.For):
                if isinstance(child.target, ast.Name):
                    self.vars_to_type[child.target.id] = "Py_ssize_t"

    def get_cdef_block(self):
        """Gera as linhas de declaração C."""
        return [f"    cdef {ctype} {name}" for name, ctype in self.vars_to_type.items()]

def transform_to_optimized_pyx(source_code):
    tree = ast.parse(source_code)
    
    # Adicionamos diretivas de ALTA PERFORMANCE no topo do arquivo
    header = [
        "# cython: language_level=3",
        "# cython: boundscheck=False",   # Desativa check de limite de lista (Velocidade!)
        "# cython: wraparound=False",    # Desativa índices negativos (Velocidade!)
        "# cython: cdivision=True",     # Divisão em C puro (Branchless-friendly)",
        "# cython: initializedcheck=False",
        "import sys, os",
        "from libc.stdint cimport int64_t"
    ]

    # Para cada função, rodamos o Enricher
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            enricher = SmartEnricher()
            enricher.visit(node)
            # Aqui injetamos as declarações cdef no início do corpo da função
            # (Essa lógica será feita durante a reconstrução do texto)
    