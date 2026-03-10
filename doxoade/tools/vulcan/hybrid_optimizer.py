# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/hybrid_optimizer.py
"""
Vulcan HybridOptimizer — Enriquecimento de .pyx com cdef antes da compilação.
==============================================================================

Posição no pipeline:
  .py → [HybridForge] → .pyx raw → [HybridOptimizer] → .pyx enriquecido → .pyd

Objetivo: passar de ~2× Python para 10-100× Python via inferência de tipos
estáticos e eliminação de overhead do interpretador em loops críticos.

Estratégia (Nova Arquitetura AST-Hoisting):
  Faz parse da AST para identificar variáveis tipáveis (contadores, flags, 
  ranges, int(), float()) e injeta as declarações `cdef` no topo
  da função, com indentação cirurgicamente clonada da própria assinatura.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
# [DOX-UNUSED] from typing import Optional


# ---------------------------------------------------------------------------
# Tipos de inferência suportados
# ---------------------------------------------------------------------------

# Nomes de variáveis que tipicamente carregam int
_INT_HINTS = frozenset({
    'i', 'j', 'k', 'n', 'idx', 'index', 'count', 'pos',
    'start', 'end', 'total', 'length', 'size', 'step',
    'lineno', 'line_num', 'line_number', 'col', 'offset',
})

# Nomes que tipicamente carregam float/double
_FLOAT_HINTS = frozenset({
    'score', 'weight', 'ratio', 'prob', 'value', 'val',
    'acc', 'accumulator', 'mean', 'avg', 'rate', 'delta',
    'elapsed', 'duration', 'time_s', 'speedup',
})

# Nomes que tipicamente carregam bool
_BOOL_HINTS = frozenset({
    'found', 'ok', 'valid', 'eligible', 'enabled', 'active',
    'has_loop', 'is_stale', 'changed', 'done', 'success',
})

# Padrões de acumulador numérico: x = 0 ou x = 0.0
_RE_INT_INIT   = re.compile(r'^(\s+)(\w+)\s*=\s*0\s*$')
_RE_FLOAT_INIT = re.compile(r'^(\s+)(\w+)\s*=\s*0\.0\s*$')

# Padrão de loop range: for VAR in range(...)
_RE_FOR_RANGE  = re.compile(r'^(\s*)for\s+(\w+)\s+in\s+range\s*\(')

# Padrão de len() em loop: n = len(x) ou direto no range
_RE_LEN_ASSIGN = re.compile(r'^(\s+)(\w+)\s*=\s*len\s*\((.+?)\)\s*$')

# Padrão de isinstance em loop
_RE_ISINSTANCE = re.compile(r'isinstance\s*\(\s*\w+\s*,\s*(\w+)\s*\)')

# Padrão de lista vazia: result = []
_RE_LIST_INIT  = re.compile(r'^(\s+)(\w+)\s*=\s*\[\s*\]\s*$')

# Padrão de dict vazio: d = {}
_RE_DICT_INIT  = re.compile(r'^(\s+)(\w+)\s*=\s*\{\s*\}\s*$')


# ---------------------------------------------------------------------------
# Resultado do enriquecimento
# ---------------------------------------------------------------------------

@dataclass
class OptimizationReport:
    """Relatório das transformações aplicadas em um .pyx."""
    module_name:    str
    transformations: list[str]  = field(default_factory=list)
    lines_added:    int         = 0
    estimated_gain: str         = "~2×"   # atualizado ao final

    def add(self, description: str):
        self.transformations.append(description)
        self.lines_added += 1

    def finalize(self):
        n = len(self.transformations)
        if n == 0:
            self.estimated_gain = "~2× (sem cdef)"
        elif n < 3:
            self.estimated_gain = "~5-10×"
        elif n < 8:
            self.estimated_gain = "~10-30×"
        else:
            self.estimated_gain = "~30-100×"


# ---------------------------------------------------------------------------
# HybridOptimizer
# ---------------------------------------------------------------------------

class HybridOptimizer:
    """
    Recebe o conteúdo de um .pyx gerado pelo HybridForge e injeta
    declarações `cdef` no topo das funções para maximizar a compilação Cython.
    """

    def optimize(
        self,
        pyx_source: str,
        module_name: str = "unknown",
    ) -> tuple[str, OptimizationReport]:
        report = OptimizationReport(module_name=module_name)

        try:
            # 1. Parse da AST do Python
            tree = ast.parse(pyx_source)
            source_lines = pyx_source.splitlines()
            
            # lineno -> list de (indent, ctype, var)
            insertions: dict[int, list[tuple[str, str, str]]] = {}

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.body:
                        continue
                        
                    first_stmt = node.body[0]
                    
                    # Ignora funções one-liner (dificuldade de injetar cdef com segurança)
                    if first_stmt.lineno == node.lineno:
                        continue

                    # Isola argumentos (não podem receber cdef local pois já foram declarados)
                    args = set()
                    for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
                        args.add(arg.arg)
                    if node.args.vararg: args.add(node.args.vararg.arg)
                    if node.args.kwarg: args.add(node.args.kwarg.arg)

                    # Isola globais/nonlocals (não podem receber cdef local)
                    globals_nonlocals = set()
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Global, ast.Nonlocal)):
                            for name in child.names:
                                globals_nonlocals.add(name)

                    blocked_names = args | globals_nonlocals

                    cdefs = {}
                    for child in ast.walk(node):
                        # a) for var in range(...)
                        if isinstance(child, ast.For) and isinstance(child.iter, ast.Call):
                            if isinstance(child.iter.func, ast.Name) and child.iter.func.id in ('range', 'xrange'):
                                if isinstance(child.target, ast.Name) and child.target.id not in blocked_names:
                                    cdefs[child.target.id] = 'Py_ssize_t'
                        
                        # b) var = ...
                        if isinstance(child, ast.Assign) and len(child.targets) == 1:
                            target = child.targets[0]
                            if isinstance(target, ast.Name) and target.id not in blocked_names:
                                var = target.id
                                val = child.value
                                
                                # Constantes numéricas/booleanas
                                if isinstance(val, ast.Constant):
                                    if type(val.value) is int and val.value == 0:
                                        if var in _INT_HINTS or var.startswith('count') or var.endswith('_count') or var.startswith('total') or var.endswith('_total'):
                                            cdefs[var] = 'long'
                                    elif type(val.value) is float and val.value == 0.0:
                                        if var in _FLOAT_HINTS or var.endswith('_s') or var.endswith('_ms') or var.endswith('_pct'):
                                            cdefs[var] = 'double'
                                    elif type(val.value) is bool:
                                        if var in _BOOL_HINTS:
                                            cdefs[var] = 'bint'
                                            
                                elif isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                                    if val.func.id == 'len':
                                        if var in _INT_HINTS | {'n', 'total', 'count', 'size', 'length'}:
                                            cdefs[var] = 'Py_ssize_t'
                                    elif val.func.id == 'float':
                                        cdefs[var] = 'double'
                                    elif val.func.id == 'int':
                                        cdefs[var] = 'long'
                    if cdefs:
                        def_line_str = source_lines[node.lineno - 1]
                        base_indent = def_line_str[:len(def_line_str) - len(def_line_str.lstrip())]
                        body_indent = base_indent + "    "
                        stmt_line_str = source_lines[first_stmt.lineno - 1]
#                        body_indent = stmt_line_str[:len(stmt_line_str) - len(stmt_line_str.lstrip())]
                        if not body_indent:
                            body_indent = "    "
                            
                        # Determina a linha de injeção (após a docstring se existir)
                        if ast.get_docstring(node):
                            insert_lineno = getattr(first_stmt, 'end_lineno', first_stmt.lineno) + 1
                        else:
                            insert_lineno = first_stmt.lineno
                            
                        if insert_lineno not in insertions:
                            insertions[insert_lineno] =[]
                            
                        for var, ctype in cdefs.items():
                            insertions[insert_lineno].append((body_indent, ctype, var))

            if not insertions:
                report.finalize()
                return pyx_source, report

            # 3. Injeta cdefs (percorrendo de trás para frente para não bagunçar os índices)
            out_lines = source_lines[:]
            for lineno in sorted(insertions.keys(), reverse=True):
                idx = max(0, min(lineno - 1, len(out_lines)))
                for indent, ctype, var in insertions[lineno]:
                    out_lines.insert(idx, f"{indent}cdef {ctype} {var}")
                    report.add(f"cdef {ctype} {var}")

            enriched = "\n".join(out_lines) + "\n"

            # 4. Validação de Sanidade (Parseia removendo cdef para confirmar integridade)
            self._validate(enriched)

            report.finalize()
            return enriched, report

        except Exception as exc:
            # Fail-graceful
            report.transformations = [f"revertido: {exc}"]
            report.estimated_gain  = "~2× (fallback)"
            return pyx_source, report

    @staticmethod
    def _validate(source: str) -> None:
        lines =[]
        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('cdef ') or stripped.startswith('# cython:'):
                continue
            lines.append(line)
        ast.parse("\n".join(lines))


    # ── Processamento principal ───────────────────────────────────────────────

    def _process_source(self, source: str, report: OptimizationReport) -> str:
        """
        Processa o .pyx linha por linha, injetando cdef onde apropriado.

        Estratégia de duas passagens:
          1ª: identifica contexto (dentro de função? dentro de loop?)
          2ª: injeta cdef com indentação correta
        """
        lines  = source.splitlines()
        result = []

        in_function    = False
        func_indent    = 0
        in_loop        = False
        loop_indent    = 0
        loop_cdefs_done: set[str] = set()   # vars já declaradas neste loop
        func_cdefs_done: set[str] = set()   # vars já declaradas nesta função

        i = 0
        while i < len(lines):
            line     = lines[i]
            stripped = line.lstrip()
            indent   = len(line) - len(stripped)

            # ── Detecta início de função ──────────────────────────────────────
            if stripped.startswith('def ') and not stripped.startswith('def _Stub'):
                in_function     = True
                func_indent     = indent
                in_loop         = False
                loop_cdefs_done = set()
                func_cdefs_done = set()
                result.append(line)
                _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                continue

            # ── Detecta saída de função (desindentação) ───────────────────────
            if in_function and stripped and indent <= func_indent and not stripped.startswith('#'):
                if not stripped.startswith('def '):
                    in_function = False
                    in_loop     = False

            # ── Fora de função: passthrough ───────────────────────────────────
            if not in_function:
                result.append(line)
                _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                continue

            inner_indent = ' ' * (indent)

            # ── 1. Loop for range() → cdef int/Py_ssize_t ────────────────────
            m = _RE_FOR_RANGE.match(line)
            if m:
                var = m.group(2)
                if var not in loop_cdefs_done and var not in func_cdefs_done:
                    ctype = 'int' if len(var) <= 2 else 'Py_ssize_t'
                    result.append(f"{inner_indent}cdef {ctype} {var}")
                    report.add(f"cdef {ctype} {var}  # loop var em range()")
                    loop_cdefs_done.add(var)
                in_loop     = True
                loop_indent = indent
                result.append(line)
                _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                continue

            # ── 2. Saída de loop (desindentação) ─────────────────────────────
            if in_loop and stripped and indent <= loop_indent and not _RE_FOR_RANGE.match(line):
                in_loop         = False
                loop_cdefs_done = set()

            # ── 3. Acumulador int: x = 0 ──────────────────────────────────────
            m = _RE_INT_INIT.match(line)
            if m:
                var = m.group(2)
                if (var in _INT_HINTS or var.startswith('count') or var.startswith('total')
                        or var.endswith('_count') or var.endswith('_total')):
                    if var not in func_cdefs_done:
                        result.append(f"{inner_indent}cdef long {var} = 0")
                        report.add(f"cdef long {var} = 0  # acumulador int")
                        func_cdefs_done.add(var)
                        _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                        continue

            # ── 4. Acumulador float: x = 0.0 ─────────────────────────────────
            m = _RE_FLOAT_INIT.match(line)
            if m:
                var = m.group(2)
                if var in _FLOAT_HINTS or var.endswith('_s') or var.endswith('_ms'):
                    if var not in func_cdefs_done:
                        result.append(f"{inner_indent}cdef double {var} = 0.0")
                        report.add(f"cdef double {var} = 0.0  # acumulador float")
                        func_cdefs_done.add(var)
                        _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                        continue

            # ── 5. len() hoisting: n = len(x) antes de loop ──────────────────
            m = _RE_LEN_ASSIGN.match(line)
            if m and not in_loop:
                var  = m.group(2)
                expr = m.group(3)
                # Injeta cdef antes da atribuição
                if var not in func_cdefs_done and var in _INT_HINTS | {'n', 'total', 'count'}:
                    result.append(f"{inner_indent}cdef int {var} = len({expr})")
                    report.add(f"cdef int {var} = len(...)  # len() hoisted")
                    func_cdefs_done.add(var)
                    _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                    continue

            # ── 6. Lista vazia com append em loop → hint de capacidade ────────
            m = _RE_LIST_INIT.match(line)
            if m:
                var = m.group(2)
                # Verifica se existe append deste var nas próximas 20 linhas
                lookahead = '\n'.join(lines[i+1:i+20])
                if f'{var}.append(' in lookahead:
                    result.append(line)
                    result.append(f"{inner_indent}# [OPT] {var}: list com append — "
                                   f"pré-alocação via {var} = [] sem cdef (Cython limite)")
                    _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                    continue

            # ── 7. Variáveis locais com nomes fortemente tipados ──────────────
            # Padrão: VAR = <bool literal>
            bool_match = re.match(r'^(\s+)(\w+)\s*=\s*(True|False)\s*$', line)
            if bool_match:
                var = bool_match.group(2)
                if var in _BOOL_HINTS and var not in func_cdefs_done:
                    val = bool_match.group(3)
                    result.append(f"{inner_indent}cdef bint {var} = {'1' if val == 'True' else '0'}")
                    report.add(f"cdef bint {var}  # bool local")
                    func_cdefs_done.add(var)
                    _buf_i.append(1)  # OBJ-REDUCE: str→buffer
                    continue

            result.append(line)
            _buf_i.append(1)  # OBJ-REDUCE: str→buffer

        return '\n'.join(result)

    # ── Validação ─────────────────────────────────────────────────────────────

    @staticmethod
    def _validate(source: str) -> None:
        """
        Valida que as partes Python do .pyx ainda são sintaticamente corretas.

        Remove linhas `cdef` antes do parse (não são Python válido).
        Levanta SyntaxError se houver problema.
        """
        # Remove directivas cdef e header Cython para validar só o Python
        python_only = '\n'.join(
            line for line in source.splitlines()
            if not line.strip().startswith('cdef ')
            and not line.strip().startswith('# cython:')
        )
        try:
            ast.parse(python_only)
        except SyntaxError as e:
            raise SyntaxError(f"Python inválido após otimização: {e}") from e


# ---------------------------------------------------------------------------
# Integração com HybridForge (patch mínimo)
# ---------------------------------------------------------------------------

def optimize_pyx_file(pyx_path: Path) -> tuple[Path, OptimizationReport]:
    """
    Lê um .pyx, enriquece com cdef e sobrescreve o arquivo.
    Chamado pelo HybridForge.generate() após escrever o .pyx raw.
    """
    optimizer = HybridOptimizer()
    module_name = pyx_path.stem

    try:
        source = pyx_path.read_text(encoding='utf-8')
        enriched, report = optimizer.optimize(source, module_name)

        if enriched != source:
            pyx_path.write_text(enriched, encoding='utf-8')

        return pyx_path, report

    except Exception as exc:
        report = OptimizationReport(module_name=module_name)
        report.transformations =[f"optimize_pyx_file falhou: {exc}"]
        report.estimated_gain  = "~2× (fallback)"
        return pyx_path, report