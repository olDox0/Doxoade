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
NATIVE_KERNELS = {
    'nexus_raw_search', 'nexus_asm_vec_search', 'nexus_asm_cmov', 
    'nexus_asm_popcount', 'nexus_path_normalize', 'nexus_get_filename' }
NATIVE_RESERVED = {
    'nexus_asm_cmov', 'nexus_asm_popcount', 'nexus_asm_vec_search', 
    'nexus_asm_crc32', 'nexus_raw_search', 'nexus_path_normalize' }
    
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
    if node_count > 10000:
        return (False, f'complexidade alta (nodes={node_count})')
    risky_hits = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            risky_hits += sum((1 for a in node.names if a.name.split('.')[0] in _RISKY_IMPORTS))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split('.')[0] in _RISKY_IMPORTS:
                risky_hits += 1
    if risky_hits >= 2 and node_count > 3000:
        return (False, f'arquivo complexo com APIs sensíveis (risk={risky_hits}, nodes={node_count})')
    return (True, None)

class BodyPurityScanner(ast.NodeVisitor):
    """Analista de Segurança Estrita: Protege o GIL contra código de logística."""
    def __init__(self):
        self.is_pure_c = True
        # Nódulos que SEMPRE exigem o interpretador Python (GIL)
        self.forbidden_nodes = (
            ast.Dict, ast.List, ast.Set, ast.Str, ast.JoinedStr, 
            ast.Yield, ast.YieldFrom, ast.Await, ast.With,
            ast.Constant # No 3.12, strings são Constants
        )

    def visit_Constant(self, node):
        # Se houver qualquer string ou valor que não seja um número, exige GIL
        if isinstance(node.value, (str, bytes, dict, list, tuple)):
            self.is_pure_c = False
        self.generic_visit(node)

    def visit_BinOp(self, node):
        # O operador '/' do pathlib é veneno para o NOGIL
        self.is_pure_c = False
        self.generic_visit(node)

    def visit_Call(self, node):
        # Praticamente qualquer chamada de função Python exige GIL
        self.is_pure_c = False
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # obj.attr exige o sistema de introspecção do Python
        self.is_pure_c = False
        self.generic_visit(node)

    def visit_Return(self, node):
        # Se retornar algo que não seja um número simples, exige GIL
        if node.value and not isinstance(node.value, ast.Num):
            if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float))):
                self.is_pure_c = False
        self.generic_visit(node)

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

        # [ALVO OMEGA] Conversão de Import Relativo para Absoluto
        if node.level and node.level > 0:
            try:
                # 1. Detecta a posição do arquivo (ex: doxoade/tools/analysis.py)
                p = Path(self.target_path).resolve()
                parts = list(p.parts)
                
                # 2. Localiza a âncora 'doxoade' no caminho do Windows
                if 'doxoade' in parts:
                    idx = parts.index('doxoade')
                    # Pega a hierarquia de pacotes: ['doxoade', 'tools']
                    pkg_hierarchy = parts[idx:-1]
                    
                    # Sobe níveis se for .. ou ...
                    for _ in range(node.level - 1):
                        if pkg_hierarchy: pkg_hierarchy.pop()
                    
                    base_prefix = ".".join(pkg_hierarchy)
                    
                    # 3. Reescreve o módulo (ex: doxoade.tools.streamer)
                    if node.module:
                        node.module = f"{base_prefix}.{node.module}"
                    else:
                        node.module = base_prefix
                    
                    node.level = 0 # Agora o binário é SOBERANO (Import Absoluto)
            except Exception:
                pass # Fallback para stubs se a lógica de path falhar

        # [CONTINUIDADE] Lógica de Blacklist e Stubs
        if node.level and node.level > 0:
            # Se ainda sobrou algum ponto, vira stub por segurança
            stubs = []
            for alias in node.names:
                stub_name = alias.asname or alias.name
                if stub_name == '*': continue
                self._blacklisted_names.add(stub_name)
                stubs.append(ast.Assign(
                    targets=[ast.Name(id=stub_name, ctx=ast.Store())], 
                    value=ast.Call(func=ast.Name(id='_Stub', ctx=ast.Load()), args=[], keywords=[]), 
                    lineno=node.lineno))
            return stubs if stubs else None

        if node.module and self._is_blacklisted(node.module):
            for alias in node.names: self._blacklisted_names.add(alias.asname or alias.name)
            return None

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
        TRANSFORMAÇÃO DE ELITE:
        Detecta: pyd_path.name
        Gera: nexus_get_filename(pyd_path)
        """
        if node.attr == 'name':
            # Se for um atributo .name, desviamos para o Kernel C
            return ast.Call(
                func=ast.Name(id='nexus_get_filename', ctx=ast.Load()),
                args=[node.value], # O objeto original (que será convertido em string)
                keywords=[]
            )
        return self.generic_visit(node)

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
        p = Path(file_path)
        raw_source = p.read_text(encoding='utf-8', errors='ignore')
        
        # 1. Extração Estrita de Future Imports
        future_imports = re.findall(r'^(from\s+__future__\s+import\s+.+)$', raw_source, re.M)
        clean_source = re.sub(r'^(from\s+__future__\s+import\s+.+)$', '', raw_source, flags=re.M)
        
        tree = ast.parse(clean_source)
        self._local_funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        
        # 2. Ordem de Ouro do Cabeçalho (PASC-Compliant)
        pyx_lines = []
        if future_imports:
            pyx_lines.extend(future_imports)
            
        pyx_lines.extend([
            "# cython: language_level=3",
            "# cython: boundscheck=False",
            "# cython: wraparound=True",
            "# cython: cdivision=True",
            "# cython: initializedcheck=False",
            "import sys, os, json, struct",
            "from libc.stdint cimport int64_t, uint8_t",
            "",
            "class _Stub:",
            "    def __getattr__(self, _): return _Stub()",
            "    def __call__(self, *a, **kw): return _Stub()",
            "",
            "Fore = _Stub()",
            "Style = _Stub()",
            "Back = _Stub()"
        ])

        for name in self.blacklist:
            if name not in {'Fore', 'Style', 'Back'}:
                pyx_lines.append(f"{name} = _Stub()")

        # 3. Injeção de Stubs Única (Evita Redundância)
        pyx_lines.append("class _Stub:")
        pyx_lines.append("    def __getattr__(self, _): return _Stub()")
        pyx_lines.append("    def __call__(self, *a, **kw): return _Stub()")
        
        # Coleta nomes para stubbing dinâmico
        stub_targets = set(self.blacklist)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, 'module', '') or ''
                if mod in self.blacklist or any(n.name in self.blacklist for n in node.names):
                    for alias in node.names:
                        stub_targets.add(alias.asname or alias.name)

        for name in stub_targets:
            pyx_lines.append(f"{name} = _Stub()")

        # 4. Linkagem de Kernels de Elite (C, ASM e NOGIL)
        # Usamos aspas duplas para o extern from, o Cython lida melhor com isso
        pyx_lines.append('\n# --- NEXUS NATIVE KERNELS (Tier 1 Elite) ---')
        pyx_lines.append('cdef extern from "nexus_asm.h" nogil:')
        pyx_lines.append('    int64_t nexus_asm_cmov(int64_t selector, int64_t val_true, int64_t val_false)')
        pyx_lines.append('    long nexus_asm_popcount(long value)')
        pyx_lines.append('    int64_t nexus_asm_vec_search(const uint8_t* buf, int64_t len, int64_t target)')
        
        pyx_lines.append('\ncdef extern from "nexus_kernels.h" nogil:')
        pyx_lines.append('    int64_t nexus_raw_search(const uint8_t* h, int64_t hl, const uint8_t* n, int64_t nl)')
        pyx_lines.append('    void nexus_path_normalize(char* path)')
        pyx_lines.append('    const char* nexus_get_filename(const char* path)')

        # 5. Transformação de Corpo
        optimized_functions = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in NATIVE_KERNELS:
                    continue 
                optimized_functions.append(node.name)
                pyx_lines.append(self._forge_node(node))
            elif isinstance(node, ast.ClassDef):
                pyx_lines.append(f"class {node.name}:")
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        pyx_lines.append(self._forge_node(sub, indent="    "))
                    else:
                        pyx_lines.append("    " + ast.unparse(sub).replace("\n", "\n    "))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # Pula imports que já viraram stubs
                is_black = hasattr(node, 'module') and node.module in self.blacklist
                if not is_black:
                    pyx_lines.append(ast.unparse(node))
            else:
                pyx_lines.append(ast.unparse(node))

        # 6. Sincronia de Assinatura
        pyx_lines.append("\n# --- INTERNAL NEXUS LINKS ---")
        for func_name in optimized_functions:
            pyx_lines.append(f"{func_name} = {func_name}_vulcan_optimized")

        node_count = sum(1 for _ in ast.walk(tree))
        self.last_node_count = node_count 

        return "\n".join(pyx_lines)

    def _optimize_branchless(self, node):
        """
        Detecta ternários: x = val_a if condition else val_b
        E converte para: x = nexus_asm_cmov(condition, val_a, val_b)
        """
        if isinstance(node, ast.IfExp):
            # Apenas para tipos compatíveis com 64-bit (inteiros/bools)
            return ast.Call(
                func=ast.Name(id='nexus_asm_cmov', ctx=ast.Load()),
                args=[node.test, node.body, node.orelse],
                keywords=[]
            )
        return node

    def _forge_node(self, node, indent=""):
        """Orquestrador de Tradução: Decisões de Nível 1 (Nativo) e Nível 2 (Híbrido)."""
        name = node.name if indent else f"{node.name}_vulcan_optimized"
        hot_vars = self._identify_hot_vars(node)
        
        # 1. Preparação de Argumentos
        forbidden = {'kwargs', 'args', 'self', 'cls'}
        arg_names = {a.arg for a in node.args.args}
        if node.args.vararg: arg_names.add(node.args.vararg.arg)
        if node.args.kwarg: arg_names.add(node.args.kwarg.arg)

        # 2. Transformação de Lógica (Branchless)
        class BranchlessTransformer(ast.NodeTransformer):
            def _is_numeric_constant(self, n):
                """Verifica se o valor é compatível com o CMOV de hardware."""
                if isinstance(n, ast.Constant):
                    # Somente números e booleanos cabem no registrador do ASM
                    return isinstance(n.value, (int, bool, float))
                return False

            def visit_IfExp(self, n):
                # SÓ transforma em ASM se ambos os lados forem numéricos
                if self._is_numeric_constant(n.body) and self._is_numeric_constant(n.orelse):
                    return ast.Call(
                        func=ast.Name(id='nexus_asm_cmov', ctx=ast.Load()),
                        args=[n.test, n.body, n.orelse],
                        keywords=[]
                    )
                # Se for string (como no analysis.py), mantém o ternário original do Python
                return n
        
        node = BranchlessTransformer().visit(node)

        # 3. Limpeza de Metadados Python
        for arg in node.args.args: arg.annotation = None
        node.returns = None
        args_str = ast.unparse(node.args)
        
        # 4. Caso Especial: Varint (Bypass Total)
        if node.name == "encode_varint":
            return "\n".join([
                f"{indent}def {name}(long n):", 
                f"{indent}    cdef unsigned char[10] buf", 
                f"{indent}    cdef int length = nexus_encode_varint_branchless(n, buf)", 
                f"{indent}    return bytearray(buf[:length])"
            ])

        # 5. DETECÇÃO DE BUSCA ATÔMICA (Identificação antes da geração)
        is_search_loop = False
        for child in ast.walk(node):
            if isinstance(child, ast.Compare):
                if isinstance(child.left, ast.Subscript):
                    is_search_loop = True
                    break

        # 6. Geração de Código Especializado (NOGIL Atomic Search)
        if is_search_loop and len(node.args.args) >= 2:
            arg_data = node.args.args[0].arg
            arg_pat = node.args.args[1].arg
            
            # [INTELIGÊNCIA DEhardware] Decide se usa SIMD (1 byte) ou Memmem (N bytes)
            # Nota: Esta decisão ocorre em tempo de transpilação!
            # Se não pudermos determinar o tamanho agora, o código gerado fará o check no C.
            
            search_code = [
                f"{indent}def {name}({args_str}):",
                f"{indent}    cdef long pos = -1",
                f"{indent}    cdef const uint8_t* ptr_data = <const uint8_t*> {arg_data}", # Cast explícito
                f"{indent}    cdef long len_data = len({arg_data})",
                f"{indent}    cdef const uint8_t* ptr_pat = <const uint8_t*> {arg_pat}", # Cast explícito
                f"{indent}    cdef long len_pat = len({arg_pat})",
                f"{indent}    with nogil:",
                f"{indent}        if len_pat == 1:",
                # Usamos a desreferência direta de ponteiro C para evitar o GIL
                f"{indent}            pos = nexus_asm_vec_search(ptr_data, len_data, <int64_t>ptr_pat[0])",
                f"{indent}        else:",
                f"{indent}            pos = nexus_raw_search(ptr_data, len_data, ptr_pat, len_pat)",
                f"{indent}    return pos"
            ]
            return "\n".join(search_code)

        # 7. Caso Geral (Python Híbrido Otimizado)
        scanner = BodyPurityScanner()
        scanner.visit(node)
        is_nogil_candidate = scanner.is_pure_c and not any(arg.arg in {'self', 'cls'} for arg in node.args.args)
        
        code = [f"{indent}def {name}({args_str}):"]
        
        if is_nogil_candidate:
            code.append(f"{indent}    with nogil:")
            indent += "    "
            
        if hot_vars:
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

    def visit_For(self, node):
        # Sempre que virmos um 'for i in range', o 'i' deve ser C puro.
        if isinstance(node.target, ast.Name):
            self.vars_to_type[node.target.id] = "Py_ssize_t" 
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # 1. Heurística de Nomes (Padrão de Engenharia)
        integers = {'n', 'i', 'j', 'k', 'idx', 'count', 'size', 'length', 'offset', 'delta', 'attempt', 'retries'}
        # Variáveis de loop e tentativa (Sempre Ints de C)
        infra_counters = {'attempt', 'retries', 'attempt_no', 'timeout', 'returncode', 'step'}
        
        # 2. Modificação na visitação
        for arg in node.args.args:
            if arg.arg.lower() in infra_counters:
                self.vars_to_type[arg.arg] = "int" # Usa int de C puro

        # 2. Varredura de Atribuições
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
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
    