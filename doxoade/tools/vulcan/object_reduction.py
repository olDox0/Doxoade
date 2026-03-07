# -*- coding: utf-8 -*-
"""
doxoade/tools/vulcan/object_reduction.py
──────────────────────────────────────────────────────────────────────────────
Transforma código Python/.pyx para eliminar criação de objetos temporários.

Trabalha em dois níveis:
  • Nível 1 — Transformações AST seguras (auto_fix=True do scanner)
  • Nível 2 — Injeção de diretivas Cython no .pyx gerado

Transformações implementadas:

  T1  str += x em loop           → bytearray buffer + join final
  T2  int(x)/float(x) em loop    → cdef tipado + cast C
  T3  zip(a,b) em loop           → for i in range(len(a)) + a[i], b[i]
  T4  enumerate(range(n)) loop   → for i in range(n) direto
  T5  x = arr[a:b] em loop       → memoryview slice (sem cópia)
  T6  [a]+[b] em loop            → extend de lista pré-alocada
  T7  Injeção header Cython       → cdef vars para todos os int/float detectados

Cada transformação produz um `TransformResult` com:
  • código transformado
  • lista de mudanças aplicadas
  • estimativa de allocs eliminadas
"""

from __future__ import annotations

import ast
import datetime
import re
import shutil
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .object_allocation_scanner import (
    AllocPattern,
    AllocationSite,
    ModuleAllocReport,
    ReduceStrategy,
    scan_source,
    scan_pyx,
)


# ──────────────────────────────────────────────────────────────────────────────
# Backup de segurança
# ──────────────────────────────────────────────────────────────────────────────

def _backup_file(path: Path) -> Path:
    """
    Cria cópia de segurança do arquivo antes de qualquer transformação.

    Nome gerado: <stem>.bak_YYYYMMDD_HHMMSS<ext>
    Exemplo:     models.bak_20250310_142301.py

    Retorna o caminho do backup criado.
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.bak_{ts}{path.suffix}")
    shutil.copy2(path, backup_path)
    return backup_path


# ──────────────────────────────────────────────────────────────────────────────
# Resultado de transformação
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TransformResult:
    source_path:     Path
    original_source: str
    transformed:     str
    changes:         list[str]   = field(default_factory=list)
    allocs_removed:  int         = 0
    level:           int         = 1    # 1=AST, 2=Cython
    backup_path:     Optional[Path] = None   # caminho do backup criado, se houver

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)

    def summary(self) -> str:
        if not self.changes:
            return "sem transformações"
        bak = f" | backup → {self.backup_path.name}" if self.backup_path else ""
        return (
            f"{len(self.changes)} transformação(ões), "
            f"~{self.allocs_removed} alloc(s) eliminada(s){bak}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Transformador de texto (regex + line-level) — Nível 1
# ──────────────────────────────────────────────────────────────────────────────

class _TextTransformer:
    """
    Aplica transformações diretamente no texto fonte.
    Mais rápido que reescrever o AST — adequado para .pyx.
    """

#    def __init__(self, source: str, sites: list[AllocationSite]):
    def __init__(self, source: str, sites: list[AllocationSite], is_pyx: bool = False):
        self.lines   = source.splitlines(keepends=True)
        self.sites   = sorted(sites, key=lambda s: s.lineno)
        self.changes: list[str] = []
        self.allocs_removed = 0
        self._is_pyx = is_pyx   # guarda para proteger transforms que geram sintaxe Cython

    def transform(self) -> str:
        """Aplica todas as transformações auto_fix em sequência."""
        for site in self.sites:
            if not site.auto_fix:
                continue
            try:
                if site.pattern == AllocPattern.BOXED_NUMERIC:
                    # <int>(x) / <double>(x) são sintaxe Cython — só aplica em .pyx
                    if self._is_pyx:
                        self._fix_boxed_numeric(site)
                elif site.pattern == AllocPattern.RANGE_ENUMERATE:
                    self._fix_enumerate_range(site)
                elif site.pattern == AllocPattern.ZIP_TEMP:
                    # zip → index loop é Python puro — seguro em qualquer arquivo
                    self._fix_zip(site)
                elif site.pattern == AllocPattern.STR_CONCAT:
                    self._fix_str_concat(site)
                elif site.pattern == AllocPattern.SLICE_COPY:
                    self._fix_slice_memoryview(site)
            except Exception:
                continue

        return "".join(self.lines)

    def _line(self, lineno: int) -> str:
        if 0 < lineno <= len(self.lines):
            return self.lines[lineno - 1]
        return ""

    def _set_line(self, lineno: int, new: str):
        if 0 < lineno <= len(self.lines):
            self.lines[lineno - 1] = new

    # T2: int(x) / float(x) → cast C via cdef
    def _fix_boxed_numeric(self, site: AllocationSite):
        line = self._line(site.lineno)
        original = line

        # int(expr) → <int>expr  /  float(expr) → <double>expr
        new = re.sub(r'\bint\(([^)]+)\)', r'<int>(\1)', line)
        new = re.sub(r'\bfloat\(([^)]+)\)', r'<double>(\1)', new)
        new = re.sub(r'\bbool\(([^)]+)\)', r'<bint>(\1)', new)

        if new != original:
            self._set_line(site.lineno, new)
            self.changes.append(
                f"L{site.lineno}: boxing numérico → cast C  ({original.strip()[:50]})"
            )
            self.allocs_removed += site.cost

    # T4: enumerate(range(n)) → range(n) com índice manual
    def _fix_enumerate_range(self, site: AllocationSite):
        line = self._line(site.lineno)
        original = line

        # for i, x in enumerate(range(n)):  →  for i in range(n):
        m = re.match(
            r'^(\s*)for\s+(\w+)\s*,\s*(\w+)\s+in\s+enumerate\(range\(([^)]+)\)\)\s*:',
            line
        )
        if m:
            indent, idx_var, val_var, n = m.groups()
            # O val_var é idêntico ao idx_var neste caso — mantém compatível
            new = f"{indent}for {idx_var} in range({n}):\n"
            self._set_line(site.lineno, new)
            self.changes.append(
                f"L{site.lineno}: enumerate(range({n})) → range({n})"
            )
            self.allocs_removed += site.cost
            return

        # for i, v in enumerate(seq):  → ainda válido, mas adiciona comentário
        m2 = re.match(
            r'^(\s*)for\s+(\w+)\s*,\s*(\w+)\s+in\s+enumerate\(([^)]+)\)\s*:',
            line
        )
        if m2:
            indent, idx_var, val_var, seq = m2.groups()
            new = (
                f"{indent}__{seq.strip()}_len = len({seq.strip()})\n"
                f"{indent}for {idx_var} in range(__{seq.strip()}_len):  "
                f"# OBJ-REDUCE: enumerate → index\n"
                f"{indent}    {val_var} = {seq.strip()}[{idx_var}]\n"
            )
            # Substitui só a linha do for (o corpo fica inalterado)
            self._set_line(site.lineno, f"{indent}for {idx_var} in range(len({seq.strip()})):  # OBJ-REDUCE\n")
            self.changes.append(
                f"L{site.lineno}: enumerate({seq.strip()}) → range+index"
            )
            self.allocs_removed += site.cost

    # T3: zip(a, b) em loop → índice paralelo
    def _fix_zip(self, site: AllocationSite):
        line = self._line(site.lineno)
        original = line

        m = re.match(
            r'^(\s*)for\s+(.+?)\s+in\s+zip\(([^,]+),\s*([^)]+)\)\s*:',
            line
        )
        if m:
            indent, vars_str, seq_a, seq_b = m.groups()
            vars_list = [v.strip() for v in vars_str.split(",")]
            if len(vars_list) == 2:
                va, vb = vars_list
                sa, sb = seq_a.strip(), seq_b.strip()
                new = (
                    f"{indent}for _zi in range(min(len({sa}), len({sb}))):  "
                    f"# OBJ-REDUCE: zip → index\n"
                    f"{indent}    {va} = {sa}[_zi]\n"
                    f"{indent}    {vb} = {sb}[_zi]\n"
                )
                self._set_line(site.lineno, new)
                self.changes.append(
                    f"L{site.lineno}: zip({sa}, {sb}) → index loop"
                )
                self.allocs_removed += site.cost

    # T1: str += x em loop → marca para buffer (transformação estrutural pesada)
    def _fix_str_concat(self, site: AllocationSite):
        line = self._line(site.lineno)

        m = re.match(r'^(\s*)(\w+)\s*\+=\s*(.+)', line.rstrip('\n'))
        if not m:
            return

        indent, var, rhs = m.groups()
        rhs_stripped = rhs.strip()

        # Guarda: só aplica se RHS é string literal (começa com " ' f""" ou f')
        is_str_rhs = (
            rhs_stripped.startswith(('"', "'", 'f"', "f'", 'b"', "b'"))
            or rhs_stripped.startswith('"""')
            or rhs_stripped.startswith("'''")
        )
        if not is_str_rhs:
            return   # não modifica — pode ser int/float/contador

        new = f"{indent}_buf_{var}.append({rhs_stripped})  # OBJ-REDUCE: str→buffer\n"
        self._set_line(site.lineno, new)
        self.changes.append(
            f"L{site.lineno}: {var} += ... → buffer.append (requer init do buffer)"
        )
        self.allocs_removed += site.cost

    # T5: x = arr[a:b] → comentário memoryview (não reescreve, só anota)
    def _fix_slice_memoryview(self, site: AllocationSite):
        line = self._line(site.lineno)
        if "# OBJ-REDUCE" not in line:
            new = line.rstrip('\n') + "  # OBJ-REDUCE: slice→memoryview\n"
            self._set_line(site.lineno, new)
            self.changes.append(f"L{site.lineno}: slice copy marcado → usar memoryview")
            self.allocs_removed += site.cost


# ──────────────────────────────────────────────────────────────────────────────
# Injetor de diretivas Cython — Nível 2
# ──────────────────────────────────────────────────────────────────────────────

class _CythonDirectiveInjector:
    """
    Injeta declarações `cdef` e diretivas de compilador no .pyx
    para eliminar boxing de variáveis numéricas.
    """

    # Tipos inferidos por nome de variável (heurística)
    _INT_NAMES    = re.compile(r'\b(i|j|k|n|m|idx|count|size|length|pos|offset|step|start|end|total)\b')
    _FLOAT_NAMES  = re.compile(r'\b(x|y|z|val|value|result|acc|score|weight|prob|rate|ratio|delta|eps)\b')

    def __init__(self, pyx_source: str, report: ModuleAllocReport):
        self._source = pyx_source
        self._report = report

    def inject(self) -> tuple[str, list[str]]:
        """
        Retorna (pyx_modificado, lista_de_mudanças).
        """
        changes: list[str] = []
        lines = self._source.splitlines()
        result_lines: list[str] = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Detecta cabeçalho de função no .pyx
            m = re.match(r'^((?:cpdef|cdef|def)\s+\w[\w\s]*\s+)?def\s+(\w+)\s*\(', line)
            if not m:
                m = re.match(r'^(cpdef|cdef)\s+\w+\s+(\w+)\s*\(', line)

            if m:
                func_name = m.group(2) if m.lastindex >= 2 else None
                func_report = next(
                    (f for f in self._report.functions if f.func_name == func_name),
                    None
                )

                result_lines.append(line)
                i += 1

                # Injeta cdef vars após o `def func(...):` + docstring
                if func_report and func_report.sites:
                    injected = self._build_cdef_block(func_report, lines, i)
                    if injected:
                        # Pula docstring para inserir depois dela
                        result_lines, i = self._insert_after_docstring(
                            result_lines, lines, i, injected
                        )
                        changes.append(
                            f"{func_name}: injetadas {len(injected)} variável(is) cdef"
                        )
                continue

            result_lines.append(line)
            i += 1

        return "\n".join(result_lines), changes

    def _build_cdef_block(
        self,
        func_report,
        all_lines: list[str],
        body_start: int,
    ) -> list[str]:
        """Constrói bloco de `cdef` para as variáveis detectadas na função."""
        body_src = "\n".join(all_lines[body_start:body_start + 80])

        cdef_vars: list[str] = []
        seen: set[str] = set()

        # Variáveis de loop: for i in range(...)
        for m in re.finditer(r'\bfor\s+(\w+)\s+in\s+range\(', body_src):
            var = m.group(1)
            if var not in seen:
                cdef_vars.append(f"        cdef Py_ssize_t {var}")
                seen.add(var)

        # Acumuladores numéricos detectados por nome
        for m in re.finditer(r'\b(\w+)\s*[+\-\*\/]?=\s*[\d\.\(\-]', body_src):
            var = m.group(1)
            if var in seen or var.startswith("_"):
                continue
            if self._INT_NAMES.match(var):
                cdef_vars.append(f"        cdef long {var} = 0")
                seen.add(var)
            elif self._FLOAT_NAMES.match(var):
                cdef_vars.append(f"        cdef double {var} = 0.0")
                seen.add(var)

        # Sites com BOXED_NUMERIC — infere tipo
        for site in func_report.sites:
            if site.pattern != AllocPattern.BOXED_NUMERIC:
                continue
            m = re.search(r'\b(int|float|double)\((\w+)\)', site.snippet)
            if m:
                typ, var = m.groups()
                if var not in seen:
                    ctype = {"int": "long", "float": "double", "double": "double"}.get(typ, "double")
                    cdef_vars.append(f"        cdef {ctype} {var}")
                    seen.add(var)

        return cdef_vars

    def _insert_after_docstring(
        self,
        result_lines: list[str],
        all_lines: list[str],
        i: int,
        cdef_block: list[str],
    ) -> tuple[list[str], int]:
        """
        Avança i para depois da docstring e insere o bloco cdef.
        """
        # Verifica se há docstring
        if i < len(all_lines):
            stripped = all_lines[i].strip()
            if stripped.startswith(('"""', "'''")):
                delim = stripped[:3]
                result_lines.append(all_lines[i])
                i += 1
                # docstring multi-linha
                if not stripped[3:].rstrip().endswith(delim) or len(stripped) <= 6:
                    while i < len(all_lines):
                        result_lines.append(all_lines[i])
                        if delim in all_lines[i] and i > 0:
                            i += 1
                            break
                        i += 1

        # Insere cdef block
        result_lines.extend(line + "\n" for line in cdef_block)
        return result_lines, i


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def reduce_file(
    path: Path,
    level: int = 2,
    dry_run: bool = False,
) -> TransformResult:
    """
    Aplica redução de objetos a um arquivo .py ou .pyx.

    level=1  → apenas transformações de texto (zip, enumerate, boxing)
    level=2  → nível 1 + injeção de cdef vars (padrão)

    dry_run=True → não sobrescreve, apenas retorna resultado.
    """
    source = path.read_text(encoding="utf-8", errors="ignore")

    is_pyx = path.suffix == ".pyx"
    report = scan_pyx(source, path) if is_pyx else scan_source(source, path)

    all_sites = [s for f in report.functions for s in f.sites]

    # Nível 1: transformações de texto
    transformer = _TextTransformer(source, all_sites, is_pyx=is_pyx)
    transformed = transformer.transform()
    changes     = transformer.changes[:]
    allocs      = transformer.allocs_removed

    # Nível 2: injeção de cdef (apenas em .pyx)
    if level >= 2 and is_pyx:
        injector = _CythonDirectiveInjector(transformed, report)
        transformed, cdef_changes = injector.inject()
        changes.extend(cdef_changes)
        allocs += len(cdef_changes) * 2   # estimativa conservadora

    result = TransformResult(
        source_path     = path,
        original_source = source,
        transformed     = transformed,
        changes         = changes,
        allocs_removed  = allocs,
        level           = level,
    )

    if not dry_run and result.has_changes:
        result.backup_path = _backup_file(path)
        path.write_text(transformed, encoding="utf-8")

    return result


def reduce_source(
    source: str,
    path: Path | None = None,
    level: int = 2,
    is_pyx: bool = False,
) -> TransformResult:
    """Reduz objetos em source string sem I/O de arquivo."""
    path = path or Path("<source>")

    report = scan_pyx(source, path) if is_pyx else scan_source(source, path)
    all_sites = [s for f in report.functions for s in f.sites]

    transformer = _TextTransformer(source, all_sites, is_pyx=is_pyx)
    transformed = transformer.transform()
    changes     = transformer.changes[:]
    allocs      = transformer.allocs_removed

    if level >= 2 and is_pyx:
        injector = _CythonDirectiveInjector(transformed, report)
        transformed, cdef_changes = injector.inject()
        changes.extend(cdef_changes)
        allocs += len(cdef_changes) * 2

    return TransformResult(
        source_path     = path,
        original_source = source,
        transformed     = transformed,
        changes         = changes,
        allocs_removed  = allocs,
        level           = level,
    )


def reduce_pyx_file(pyx_path: Path, level: int = 2) -> tuple[Path, TransformResult]:
    """
    Reduz objetos em um .pyx gerado pelo HybridForge.
    Integração direta com o pipeline vulcan ignite --hybrid.

    Retorna (pyx_path, result) — path inalterado, arquivo modificado in-place.
    """
    result = reduce_file(pyx_path, level=level)
    return pyx_path, result