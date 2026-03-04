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
  4. ImportCombiner          — funde imports consecutivos numa única instrução
  5. GlobalImportAliaser     — aplica alias (as Ia1) em imports de nomes longos
  6. SafeLocalNameMinifier   — renomeia variáveis e aliases de forma segura
"""

from __future__ import annotations

import ast
import string
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    _ast_unparse = ast.unparse
except AttributeError:
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
    _SCOPE_ACCESSORS = frozenset({'locals', 'vars', 'exec', 'eval', 'globals', 'dir', 'inspect'})

    def optimize_file(self, path: Path) -> FileOptReport:
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

            # 4. Combina imports consecutivos
            tree = ImportCombiner().visit(tree)

            # 5. Minifica nomes globais de imports
            tree = GlobalImportAliaser().visit(tree)

            # 6. Minifica nomes locais de forma 100% segura
            if not has_scope_access:
                mn = SafeLocalNameMinifier()
                tree = mn.visit(tree)
                report.locals_minified = mn.count

            ast.fix_missing_locations(tree)

            if not _ast_unparse:
                raise RuntimeError("ast.unparse indisponível.")

            optimized = _ast_unparse(tree)

            # 7. Fusão Horizontal Blindada (Se falhar, degrada graciosamente)
            try:
                compacted = self.compact_lines_safely(optimized)
                ast.parse(compacted)  # Valida sintaxe antes de confirmar
                optimized = compacted
            except SyntaxError as e:
                print(f"\n\033[33m[DEBUG] Compactação horizontal ignorada em {path.name}: {e}\033[0m")
            
            # Validação final de segurança
            ast.parse(optimized)  

            path.write_text(optimized, encoding='utf-8')
            report.final_bytes = len(optimized.encode('utf-8'))

        except Exception as exc:
            import traceback
            print(f"\n\033[31m[ERRO CRÍTICO] Falha total em {path.name}: {exc}\033[0m")
            try:
                path.write_text(source, encoding='utf-8')
            except Exception:
                pass
            report.skipped    = True
            report.skip_reason = f"otimização revertida: {exc}"
            report.final_bytes = report.original_bytes

        return report

    def optimize_directory(self, directory: Path) -> dict:
        reports =[self.optimize_file(py_file) for py_file in sorted(directory.rglob('*.py'))]

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

        return {**summary, 'summary': summary, 'files': [r.__dict__ for r in reports]}

    def _has_scope_accessor(self, tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node)
                if name and name in self._SCOPE_ACCESSORS:
                    return True
        return False

    @staticmethod
    def compact_lines_safely(code: str) -> str:
        lines = code.split('\n')
        if not lines: return ""
        
        out_lines =[]
        current_line = lines[0]
        def get_indent(s): return len(s) - len(s.lstrip())
            
        compound_keywords = (
            'if ', 'for ', 'while ', 'def ', 'class ', 'try:', 'with ', 
            'elif ', 'else:', 'except', 'finally:', '@', 'async ', 'match ', 'case '
        )
        
        for i in range(1, len(lines)):
            nxt = lines[i]
            if not nxt.strip():
                continue
                
            curr_indent = get_indent(current_line)
            nxt_indent = get_indent(nxt)
            
            is_compound_curr = current_line.lstrip().startswith(compound_keywords)
            is_compound_nxt = nxt.lstrip().startswith(compound_keywords)
            ends_with_colon = current_line.rstrip().endswith(':')
            
            # PROTEÇÃO ABSOLUTA: Ignora a concatenação se a linha envolver QUALQUER aspas.
            # Evita fatiar docstrings ou strings multilinhas.
            has_quotes = "'" in current_line or '"' in current_line or "'" in nxt or '"' in nxt
            
            if (curr_indent == nxt_indent and curr_indent > 0 and 
                not has_quotes and not ends_with_colon and 
                not is_compound_curr and not is_compound_nxt):
                current_line = current_line + "; " + nxt.lstrip()
            else:
                out_lines.append(current_line)
                current_line = nxt
                
        out_lines.append(current_line)
        return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Visitantes AST
# ---------------------------------------------------------------------------

class DocstringRemover(ast.NodeTransformer):
    def __init__(self):
        self.count = 0
    def _strip(self, node):
        if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)
            self.count += 1
            if not node.body: node.body.append(ast.Pass())
        return node
    def visit_Module(self, node): self.generic_visit(node); return self._strip(node)
    def visit_FunctionDef(self, node): self.generic_visit(node); return self._strip(node)
    visit_AsyncFunctionDef = visit_FunctionDef
    def visit_ClassDef(self, node): self.generic_visit(node); return self._strip(node)


class DeadBranchEliminator(ast.NodeTransformer):
    def __init__(self): self.count = 0
    def _always_false(self, test): return isinstance(test, ast.Constant) and not bool(test.value) and test.value is not True
    def _always_true(self, test): return isinstance(test, ast.Constant) and bool(test.value) and not isinstance(test.value, str)
    def visit_If(self, node):
        self.generic_visit(node)
        if self._always_false(node.test): self.count += 1; return node.orelse if node.orelse else None
        if self._always_true(node.test): self.count += 1; return node.body
        return node
    def visit_While(self, node):
        self.generic_visit(node)
        if self._always_false(node.test): self.count += 1; return None
        return node


class UnusedImportRemover:
    _SIDE_EFFECT_KEEP = frozenset({'__future__', 'logging', 'warnings', 'traceback', 'atexit', 'signal', 'site', 'antigravity', 'this'})
    def __init__(self): self.count = 0
    def process(self, tree):
        used = self._collect_used_names(tree)
        transformer = _ImportTransformer(used, self._SIDE_EFFECT_KEEP)
        res = transformer.visit(tree)
        self.count = transformer.count
        return res
    @staticmethod
    def _collect_used_names(tree):
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name): names.add(node.id)
            elif isinstance(node, ast.Attribute): names.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str): names.add(node.value)
        return names

class _ImportTransformer(ast.NodeTransformer):
    def __init__(self, used_names, side_effects):
        self._used = used_names; self._side_effects = side_effects; self.count = 0
    def visit_Import(self, node):
        kept =[]
        for alias in node.names:
            root = alias.name.split('.')[0]
            if root in self._side_effects: kept.append(alias); continue
            bound = alias.asname if alias.asname else alias.name
            if bound.split('.')[0] in self._used: kept.append(alias)
            else: self.count += 1
        if not kept: return None
        node.names = kept
        return node


class ImportCombiner(ast.NodeTransformer):
    def _combine(self, body):
        new_body =[]
        curr_import = None
        for stmt in body:
            if type(stmt) is ast.Import:
                if curr_import is None:
                    curr_import = stmt
                    new_body.append(curr_import)
                else:
                    curr_import.names.extend(stmt.names)
            else:
                curr_import = None
                new_body.append(self.visit(stmt))
        return new_body

    def generic_visit(self, node):
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                setattr(node, field, self._combine(old_value))
            elif isinstance(old_value, ast.AST):
                setattr(node, field, self.visit(old_value))
        return node


class GlobalImportAliaser(ast.NodeTransformer):
    def __init__(self):
        self.import_map = {}
        self.counter = 1

    def _get_alias(self):
        alias = f"Ia{self.counter}"
        self.counter += 1
        return alias

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == '*': continue
            orig = alias.asname or alias.name
            if len(orig) > 4: 
                new_alias = self._get_alias()
                alias.asname = new_alias
                self.import_map[orig] = new_alias
        return node
        
    def visit_Import(self, node):
        for alias in node.names:
            orig = alias.asname or alias.name
            if len(orig) > 6: 
                new_alias = self._get_alias()
                alias.asname = new_alias
                self.import_map[orig] = new_alias
        return node

    def visit_Name(self, node):
        if node.id in self.import_map:
            node.id = self.import_map[node.id]
        return node


class SafeLocalNameMinifier(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self._name_generator = self._short_name_generator()
        self.scope_maps =[]
        self.count = 0 

    def _short_name_generator(self):
        chars = string.ascii_lowercase
        yield from (f"_{c}" for c in chars)
        for length in itertools.count(2):
            for p in itertools.product(chars, repeat=length):
                yield f"_{''.join(p)}"

    class _VarCollector(ast.NodeVisitor):
        def __init__(self, excluded_names):
            self.local_vars = set()
            self.excluded = set(excluded_names)
            self.is_unsafe = False
            self.globals_nonlocals = set()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in {'locals', 'vars', 'eval', 'exec'}:
                self.is_unsafe = True
            self.generic_visit(node)

        def visit_Global(self, node): self.globals_nonlocals.update(node.names)
        def visit_Nonlocal(self, node): self.globals_nonlocals.update(node.names)

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store) and node.id not in self.excluded:
                self.local_vars.add(node.id)

        def visit_Import(self, node):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    if name not in self.excluded:
                        self.local_vars.add(name)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name != '*':
                    name = alias.asname or alias.name
                    if name not in self.excluded:
                        self.local_vars.add(name)

        def visit_FunctionDef(self, node): pass
        def visit_AsyncFunctionDef(self, node): pass
        def visit_ClassDef(self, node): pass
        def visit_Lambda(self, node): pass
        def visit_GeneratorExp(self, node): pass
        def visit_ListComp(self, node): pass
        def visit_DictComp(self, node): pass
        def visit_SetComp(self, node): pass

    def visit_FunctionDef(self, node):
        excluded = set()
        args = node.args
        for arg in args.args + getattr(args, 'kwonlyargs',[]) + getattr(args, 'posonlyargs',[]):
            excluded.add(arg.arg)
        if args.vararg: excluded.add(args.vararg.arg)
        if args.kwarg: excluded.add(args.kwarg.arg)

        collector = self._VarCollector(excluded)
        for stmt in node.body:
            collector.visit(stmt)

        rename_map = {}
        if not collector.is_unsafe:
            safe_targets = collector.local_vars - collector.globals_nonlocals
            for var in sorted(safe_targets):
                rename_map[var] = next(self._name_generator)
            self.count += len(rename_map)

        self.scope_maps.append(rename_map)
        node.body =[self.visit(stmt) for stmt in node.body]
        self.scope_maps.pop()
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Name(self, node):
        if self.scope_maps:
            current_map = self.scope_maps[-1]
            if node.id in current_map:
                node.id = current_map[node.id]
        return node

    def visit_Import(self, node):
        if self.scope_maps:
            current_map = self.scope_maps[-1]
            for alias in node.names:
                orig_name = alias.asname or alias.name
                if orig_name in current_map and '.' not in alias.name:
                    alias.asname = current_map[orig_name]
        return node

    def visit_ImportFrom(self, node):
        if self.scope_maps:
            current_map = self.scope_maps[-1]
            for alias in node.names:
                orig_name = alias.asname or alias.name
                if orig_name in current_map:
                    alias.asname = current_map[orig_name]
        return node


def _call_name(node: ast.Call) -> Optional[str]:
    try:
        if isinstance(node.func, ast.Name): return node.func.id
        if isinstance(node.func, ast.Attribute): return node.func.attr
    except Exception:
        pass
    return None