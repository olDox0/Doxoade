# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/lib_optimizer.py
"""
LibOptimizer — Otimizador AST seguro para cópias de fontes de bibliotecas.
==========================================================================

Aplicado à cópia isolada dos .py ANTES do HybridIgnite.
O original no venv NUNCA é tocado.

Transformações (ordenadas do mais para o menos seguro):
  1. DocstringRemover        — remove docstrings de módulo/classe/função
  2. DeadBranchEliminator    — elimina `if False/True/0/1:`, `while False:`
  3. UnusedImportRemover     — remove `import X` nunca referenciado
  4. LocalNameMinifier       — renomeia variáveis locais para nomes curtos
                               (_a, _b, ...) dentro de funções sem escopo aninhado

Regras de segurança:
  - Nunca renomeia nomes públicos (nível de módulo)
  - Nunca renomeia parâmetros de função
  - Nunca renomeia se a função usa locals()/vars()/exec()/eval()
  - Nunca renomeia nomes que aparecem como string literal na mesma função
    (proteção contra getattr(obj, 'varname'))
  - Nunca entra em funções aninhadas ao minificar
  - Revert automático se o resultado falhar no parse de validação

Compliance:
  OSL-4: cada classe tem responsabilidade única
  OSL-5: optimize_file() nunca levanta exceção — revert em falha
  PASC-6: fail-graceful em qualquer etapa
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    _ast_unparse = ast.unparse
except AttributeError:  # Python < 3.9
    try:
        import astor
        _ast_unparse = astor.to_source
    except Exception:
        _ast_unparse = None

# ---------------------------------------------------------------------------
# Estrutura de relatório por arquivo
# ---------------------------------------------------------------------------

@dataclass
class FileOptReport:
    """Resultado da otimização de um arquivo .py."""
    path:                str
    original_bytes:      int   = 0
    final_bytes:         int   = 0
    docstrings_removed:  int   = 0
    dead_branches:       int   = 0
    imports_removed:     int   = 0
    locals_minified:     int   = 0
    skipped:             bool  = False
    skip_reason:         str   = ""

    @property
    def bytes_saved(self) -> int:
        return max(0, self.original_bytes - self.final_bytes)

    @property
    def was_changed(self) -> bool:
        return not self.skipped and self.bytes_saved > 0


# ---------------------------------------------------------------------------
# LibOptimizer — orquestrador
# ---------------------------------------------------------------------------

class LibOptimizer:
    """
    Aplica pipeline de otimizações AST em todos os .py de um diretório.

    Uso:
        optimizer = LibOptimizer()
        stats = optimizer.optimize_directory(work_copy_path)
    """

    # Chamadas que acessam escopo local por nome → tornam renomeação insegura
    _SCOPE_ACCESSORS = frozenset({'locals', 'vars', 'exec', 'eval', 'globals',
                                   'dir', 'inspect'})

    def optimize_file(self, path: Path) -> FileOptReport:
        """
        Otimiza um único arquivo .py in-place (cópia de trabalho).

        PASC-6: nunca levanta exceção. Em qualquer falha, o arquivo
        original é restaurado e o relatório marca skipped=True.
        """
        report = FileOptReport(path=str(path))

        try:
            source = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as exc:
            report.skipped    = True
            report.skip_reason = f"leitura falhou: {exc}"
            return report

        report.original_bytes = len(source.encode('utf-8'))

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            report.skipped    = True
            report.skip_reason = f"parse error: {exc}"
            return report

        # Detecta uso de acessores de escopo (desativa LocalNameMinifier)
        has_scope_access = self._has_scope_accessor(tree)

        try:
            # 1. Remove docstrings
            ds = DocstringRemover()
            tree = ds.visit(tree)
            report.docstrings_removed = ds.count

            # 2. Elimina dead branches
            db = DeadBranchEliminator()
            tree = db.visit(tree)
            report.dead_branches = db.count

            # 3. Remove imports não usados
            ui = UnusedImportRemover()
            tree = ui.process(tree)
            report.imports_removed = ui.count

            # 4. Minifica nomes locais (se seguro)
            if not has_scope_access:
                mn = LocalNameMinifier()
                tree = mn.visit(tree)
                report.locals_minified = mn.count

            ast.fix_missing_locations(tree)

            # Valida o resultado antes de sobrescrever
            if not _ast_unparse:
                raise RuntimeError("ast.unparse indisponível (Python < 3.9 e astor ausente)")

            optimized = _ast_unparse(tree)
            ast.parse(optimized)  # valida — se falhar, vai para o except

            path.write_text(optimized, encoding='utf-8')
            report.final_bytes = len(optimized.encode('utf-8'))

        except Exception as exc:
            # Revert: restaura o fonte original
            try:
                path.write_text(source, encoding='utf-8')
            except Exception:
                pass
            report.skipped    = True
            report.skip_reason = f"otimização revertida: {exc}"
            report.final_bytes = report.original_bytes

        return report

    def optimize_directory(self, directory: Path) -> dict:
        """
        Otimiza todos os .py do diretório recursivamente.
        Retorna dicionário de estatísticas agregadas e lista de relatórios por arquivo.

        Compatibilidade: retorna as chaves top-level esperadas por código legado
        (files_processed, files_optimized, ...) e também um sub-dicionário 'summary'
        e a lista detalhada 'files'.
        """
        reports: list[FileOptReport] = []

        for py_file in sorted(directory.rglob('*.py')):
            reports.append(self.optimize_file(py_file))

        summary = {
            'files_processed':   len(reports),
            'files_optimized':   sum(1 for r in reports if r.was_changed),
            'files_skipped':     sum(1 for r in reports if r.skipped),
            'bytes_saved':       sum(r.bytes_saved for r in reports),
            'docstrings_removed': sum(r.docstrings_removed for r in reports),
            'dead_branches':     sum(r.dead_branches for r in reports),
            'imports_removed':   sum(r.imports_removed for r in reports),
            'locals_minified':   sum(r.locals_minified for r in reports),
        }

        return {
            # para compatibilidade direta (flat)
            **summary,
            # detalhamento adicional
            'summary': summary,
            'files': [r.__dict__ for r in reports],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _has_scope_accessor(self, tree: ast.AST) -> bool:
        """True se o módulo usa calls que acessam locals por nome."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name and name in self._SCOPE_ACCESSORS:
                    return True
        return False


# ---------------------------------------------------------------------------
# 1. DocstringRemover
# ---------------------------------------------------------------------------

class DocstringRemover(ast.NodeTransformer):
    """
    Remove docstrings de módulos, funções e classes.

    Uma docstring é o primeiro statement do corpo quando é um
    ast.Expr contendo um ast.Constant(str).
    Se o corpo ficar vazio após a remoção, insere `pass`.
    """

    def __init__(self):
        self.count = 0

    def _strip(self, node):
        if (node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)
            self.count += 1
            if not node.body:
                node.body.append(ast.Pass())
        return node

    def visit_Module(self, node):
        self.generic_visit(node)
        return self._strip(node)

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        return self._strip(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        return self._strip(node)


# ---------------------------------------------------------------------------
# 2. DeadBranchEliminator
# ---------------------------------------------------------------------------

class DeadBranchEliminator(ast.NodeTransformer):
    """
    Elimina branches que nunca executam:
      if False / if 0 / if None  → remove bloco if, mantém else (se houver)
      if True  / if 1            → mantém corpo, descarta else
      while False / while 0      → remove loop inteiro

    Só atua em literais — não tenta avaliar expressões.
    """

    def __init__(self):
        self.count = 0

    @staticmethod
    def _always_false(test: ast.expr) -> bool:
        return (isinstance(test, ast.Constant)
                and not bool(test.value)
                and test.value is not True)

    @staticmethod
    def _always_true(test: ast.expr) -> bool:
        return (isinstance(test, ast.Constant)
                and bool(test.value)
                and not isinstance(test.value, str))

    def visit_If(self, node: ast.If):
        self.generic_visit(node)

        if self._always_false(node.test):
            self.count += 1
            # Retorna o else (pode ser lista ou vazio)
            return node.orelse if node.orelse else None

        if self._always_true(node.test):
            self.count += 1
            return node.body   # descarta o else

        return node

    def visit_While(self, node: ast.While):
        self.generic_visit(node)

        if self._always_false(node.test):
            self.count += 1
            return None   # remove o loop morto

        return node


# ---------------------------------------------------------------------------
# 3. UnusedImportRemover
# ---------------------------------------------------------------------------

class UnusedImportRemover:
    """
    Remove `import X` / `import X as Y` quando o nome ligado (Y ou X)
    não aparece em NENHUM Name node no módulo.

    Conservativo por design:
      - Não toca `from X import Y` (efeitos colaterais comuns)
      - Preserva módulos com side-effects conhecidos
      - Preserva imports usados como strings em getattr/hasattr
      - Não remove se o nome aparece em __all__
    """

    _SIDE_EFFECT_KEEP = frozenset({
        '__future__', 'logging', 'warnings', 'traceback', 'atexit',
        'signal', 'site', 'antigravity', 'this',
    })

    def __init__(self):
        self.count = 0

    def process(self, tree: ast.Module) -> ast.Module:
        """Coleta nomes usados e aplica remoção."""
        used = self._collect_used_names(tree)
        self._used = used
        return self.visit(tree)

    def visit(self, node: ast.AST) -> ast.AST:
        """Wrapper que delega ao NodeTransformer interno."""
        transformer = _ImportTransformer(self._used, self._SIDE_EFFECT_KEEP)
        result = transformer.visit(node)
        self.count = transformer.count
        return result

    @staticmethod
    def _collect_used_names(tree: ast.AST) -> set[str]:
        """
        Coleta todos os nomes referenciados no módulo.
        Inclui strings literais (proteção para getattr(m, 'name')).
        """
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Proteção para getattr(obj, 'some_name')
                names.add(node.value)
        return names


class _ImportTransformer(ast.NodeTransformer):
    """Visitor interno que remove imports não usados."""

    def __init__(self, used_names: set[str], side_effects: frozenset[str]):
        self._used = used_names
        self._side_effects = side_effects
        self.count = 0

    def visit_Import(self, node: ast.Import) -> Optional[ast.Import]:
        kept = []
        for alias in node.names:
            root = alias.name.split('.')[0]

            if root in self._side_effects:
                kept.append(alias)
                continue

            # Nome ligado: `import os as _os` → `_os`;  `import os` → `os`
            bound = alias.asname if alias.asname else alias.name
            # Para `import os.path`, o nome acessível é `os`
            bound_root = bound.split('.')[0]

            if bound_root in self._used:
                kept.append(alias)
            else:
                self.count += 1

        if not kept:
            return None
        node.names = kept
        return node


# ---------------------------------------------------------------------------
# 4. LocalNameMinifier
# ---------------------------------------------------------------------------

class LocalNameMinifier(ast.NodeTransformer):
    """
    Minifica nomes de variáveis locais em funções simples (sem escopo aninhado).

    Critérios de elegibilidade da função:
      - Não contém FunctionDef / AsyncFunctionDef / Lambda aninhados
      - Não usa chamadas que acessam locals() pelo nome (verificado no orquestrador)

    Critérios de elegibilidade da variável:
      - Tem contexto Store dentro da função (é local)
      - Não é parâmetro da função
      - Não é `self` / `cls` / dunder
      - Nome original tem > 2 caracteres (nomes curtos já são "minificados")
      - Não aparece como string literal dentro da função
        (ex: getattr(obj, 'var_name') ficaria quebrado)

    Nomes gerados: _a, _b, ..., _z, _aa, _ab, ..., _az, _ba, ...
    """

    # Builtins e nomes especiais que NUNCA devem ser sombreados
    _PROTECTED = frozenset({
        'self', 'cls', 'True', 'False', 'None',
        'len', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
        'reversed', 'sum', 'min', 'max', 'abs', 'round', 'any', 'all',
        'isinstance', 'issubclass', 'type', 'id', 'hash', 'repr', 'str',
        'int', 'float', 'bool', 'list', 'dict', 'set', 'tuple', 'bytes',
        'bytearray', 'memoryview', 'object', 'super',
        'hasattr', 'getattr', 'setattr', 'delattr', 'vars', 'dir',
        'open', 'print', 'input', 'format', 'bin', 'hex', 'oct',
        'chr', 'ord', 'iter', 'next', 'callable',
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
        'AttributeError', 'StopIteration', 'RuntimeError', 'OSError',
        'IOError', 'FileNotFoundError', 'ImportError', 'NameError',
        'NotImplementedError', 'OverflowError', 'ZeroDivisionError',
        'BaseException', 'GeneratorExit', 'SystemExit', 'KeyboardInterrupt',
    })

    def __init__(self):
        self.count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        # Processa funções aninhadas primeiro (com seu próprio escopo)
        self.generic_visit(node)
        # Tenta minificar esta função
        self._minify(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def _minify(self, func: ast.FunctionDef):
        # Guard: não minifica funções que contêm escopo aninhado
        for child in ast.walk(func):
            if child is func:
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.Lambda)):
                return

        # Coleta nomes protegidos: parâmetros + constantes de classe
        protected = set(self._PROTECTED)
        for arg in (func.args.args + func.args.posonlyargs
                    + func.args.kwonlyargs):
            protected.add(arg.arg)
        if func.args.vararg:
            protected.add(func.args.vararg.arg)
        if func.args.kwarg:
            protected.add(func.args.kwarg.arg)

        # Nomes que aparecem como strings literais na função
        # → renomear quebraria getattr(obj, 'name')
        string_refs: set[str] = set()
        for child in ast.walk(func):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                string_refs.add(child.value)

        # Coleta variáveis locais elegíveis para renomeação
        candidates: set[str] = set()
        for child in ast.walk(func):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                name = child.id
                if (name not in protected
                        and not name.startswith('_')      # evita vars "já curtas"
                        and not name.startswith('__')
                        and name not in string_refs
                        and len(name) > 2):
                    candidates.add(name)

        if not candidates:
            return

        # Gera mapeamento deterministico (sorted → builds are reproducible)
        existing_names = self._all_names_in(func)
        mapping: dict[str, str] = {}
        counter = 0
        for original in sorted(candidates):
            new = self._gen_name(counter)
            # Evita colisão com nomes já existentes
            while new in existing_names or new in protected:
                counter += 1
                new = self._gen_name(counter)
            mapping[original] = new
            existing_names.add(new)
            counter += 1

        if not mapping:
            return

        # Aplica renomeação DENTRO da função (generic_visit desce direto
        # no corpo sem acionar visit_FunctionDef no nó raiz, que retornaria
        # sem processar filhos — os nós aninhados ainda são protegidos pelo
        # visit_FunctionDef do renamer).
        _NameRenamer(mapping).generic_visit(func)
        self.count += len(mapping)

    @staticmethod
    def _all_names_in(func: ast.FunctionDef) -> set[str]:
        """Coleta todos os nomes referenciados na função (para evitar colisão)."""
        names: set[str] = set()
        for child in ast.walk(func):
            if isinstance(child, ast.Name):
                names.add(child.id)
            elif isinstance(child, ast.arg):
                names.add(child.arg)
        return names

    @staticmethod
    def _gen_name(n: int) -> str:
        """
        Gera nomes curtos com prefixo underscore:
          0 → _a, 1 → _b, ..., 25 → _z, 26 → _aa, 27 → _ab, ...
        O underscore evita conflito com builtins de letra única (e, f, i…).
        """
        chars = 'abcdefghijklmnopqrstuvwxyz'
        result = ''
        n += 1
        while n > 0:
            n -= 1
            result = chars[n % 26] + result
            n //= 26
        return f'_{result}'


class _NameRenamer(ast.NodeTransformer):
    """
    Visitor que renomeia Name nodes de acordo com um mapeamento.
    Não descende em FunctionDef/Lambda aninhados (escopo separado).
    """

    def __init__(self, mapping: dict[str, str]):
        self._m = mapping

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self._m:
            node.id = self._m[node.id]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        # Parâmetros não são renomeados — já protegidos pelo minifier
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        # Não desce em funções aninhadas (escopo próprio)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> ast.Lambda:
        return node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_name(node: ast.Call) -> Optional[str]:
    """Extrai o nome de uma chamada de função de forma segura."""
    try:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
    except Exception:
        pass
    return None