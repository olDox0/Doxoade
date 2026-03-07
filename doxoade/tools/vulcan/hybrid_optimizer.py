# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/hybrid_optimizer.py
"""
Vulcan HybridOptimizer — Enriquecimento de .pyx com cdef antes da compilação.
==============================================================================

Posição no pipeline:
  .py → [HybridForge] → .pyx raw → [HybridOptimizer] → .pyx enriquecido → .pyd

Objetivo: passar de ~2× Python para 10-100× Python via inferência de tipos
estáticos e eliminação de overhead do interpretador em loops críticos.

Transformações aplicadas:
  1. Loop hoisting      : cdef int i / cdef Py_ssize_t i em for range()
  2. Acumulador         : cdef double/long para variáveis acc em loops
  3. len() hoisting     : cdef int _n = len(x) antes do loop
  4. Variáveis locais   : cdef tipado para atribuições inferíveis
  5. isinstance cache   : pré-resolve referência de tipo em loops ast.walk
  6. list capacity hint : comentário informativo (Cython não expõe direto)

Compliance:
  OSL-4  : única responsabilidade — só transforma .pyx, não compila
  OSL-5  : nunca levanta exceção para o chamador — retorna source original em falha
  MPoT-3 : zero alocação desnecessária no parse de linhas
  PASC-6 : fail-graceful — se a transformação produz código inválido, reverte
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
    declarações `cdef` para maximizar a velocidade de compilação Cython.

    OSL-5: optimize() nunca levanta exceção — retorna source original em falha.
    """

    def optimize(
        self,
        pyx_source: str,
        module_name: str = "unknown",
    ) -> tuple[str, OptimizationReport]:
        """
        Entry-point principal.

        Retorna (pyx_enriquecido, relatório).
        Se a transformação produz Python inválido, retorna (source_original, relatório_vazio).
        """
        report = OptimizationReport(module_name=module_name)

        try:
            enriched = self._process_source(pyx_source, report)

            # Validação: o .pyx enriquecido ainda deve ser parseável
            # (Cython é um superset — o cdef não é Python, mas as partes
            # Python precisam estar corretas)
            self._validate(enriched)

            report.finalize()
            return enriched, report

        except Exception as exc:
            # Fail-graceful: reverte para o source original
            report.transformations = [f"revertido: {exc}"]
            report.estimated_gain  = "~2× (fallback)"
            return pyx_source, report

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
    Retorna (pyx_path, relatório).
    OSL-5: nunca levanta exceção.
    """
    optimizer = HybridOptimizer()
    module_name = pyx_path.stem

    try:
        source   = pyx_path.read_text(encoding='utf-8')
        enriched, report = optimizer.optimize(source, module_name)

        if enriched != source:
            pyx_path.write_text(enriched, encoding='utf-8')

        return pyx_path, report

    except Exception as exc:
        report = OptimizationReport(module_name=module_name)
        report.transformations = [f"optimize_pyx_file falhou: {exc}"]
        report.estimated_gain  = "~2× (fallback)"
        return pyx_path, report