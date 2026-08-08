# doxoade/doxoade/commands/refactor_systems/import_doctor.py
# -*- coding: utf-8 -*-
"""
ImportDoctor — auditoria e reparo de imports para o Doxoade Refactor.

Objetivo:
- Indexar módulos reais do projeto.
- Detectar imports quebrados, antigos, relativos inválidos e símbolos ausentes.
- Sugerir ou aplicar correções linha a linha.
- Nunca reescrever o arquivo inteiro com ast.unparse.
- Validar com compile() antes de salvar.
"""

from __future__ import annotations

import ast
import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".doxoade",
    ".doxoade_cache",
    ".dox_agent_workspace",
    "pytest_temp_dir",
    "tests",
    "regression_tests",
}

INTERNAL_ROOTS = {
    "doxoade",
    "tools",
    "commands",
    "diagnostic",
    "shared_tools",
    "database",
    "src",
    "utils",
}

# Mapa de aliases conhecidos.
# Isso é importante para renomeações históricas do projeto.
DEPRECATED_MAP = {
    # Typhon antigo (Thoth-style)
    "src.houses.typhon_chaos.tree": "doxoade.commands.typhon_systems.typhon_tree",
    "src.houses.typhon_chaos.chaos": "doxoade.commands.typhon_systems.typhon_chaos",
    "src.houses.typhon_chaos.probes": "doxoade.commands.typhon_systems.typhon_probes",
    "src.houses.typhon_chaos.consolidated": "doxoade.commands.typhon_systems.typhon_consolidated",
    "src.houses.typhon_chaos.horus_bridge": "doxoade.commands.typhon_systems.horus_bridge",
    "src.houses.typhon_chaos.soteria_bridge": "doxoade.commands.typhon_systems.soteria_bridge",

    # Possíveis imports antigos dentro do próprio typhon_systems
    "doxoade.commands.typhon_systems.tree": "doxoade.commands.typhon_systems.typhon_tree",
    "doxoade.commands.typhon_systems.chaos": "doxoade.commands.typhon_systems.typhon_chaos",
    "doxoade.commands.typhon_systems.probes": "doxoade.commands.typhon_systems.typhon_probes",
    "doxoade.commands.typhon_systems.consolidated": "doxoade.commands.typhon_systems.typhon_consolidated",
    "doxoade.commands.typhon_systems.cmd": "doxoade.commands.typhon_systems.typhon_cmd",
}


@dataclass(frozen=True)
class ImportIssue:
    file: Path
    line: int
    end_line: int
    kind: str
    message: str
    original: str
    replacement: Optional[str] = None
    severity: str = "error"


@dataclass
class ImportReport:
    issues: List[ImportIssue] = field(default_factory=list)
    applied: bool = False
    files_changed: int = 0
    backups: List[Path] = field(default_factory=list)

    @property
    def errors(self) -> List[ImportIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ImportIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "files_changed": self.files_changed,
            "issues": [
                {
                    "file": str(i.file),
                    "line": i.line,
                    "end_line": i.end_line,
                    "kind": i.kind,
                    "message": i.message,
                    "original": i.original,
                    "replacement": i.replacement,
                    "severity": i.severity,
                }
                for i in self.issues
            ],
            "backups": [str(b) for b in self.backups],
        }


class ImportDoctor:
    """
    Motor de auditoria e correção de imports.

    Estratégia:
    - indexa módulos e símbolos;
    - resolve imports relativos;
    - detecta módulos inexistentes;
    - detecta símbolos inexistentes;
    - propõe substituições apenas nos nós de import;
    - preserva o restante do arquivo.
    """

    def __init__(self, root: Path, target: Optional[Path] = None):
        self.root = self._discover_root(Path(root).resolve())
        self.target = Path(target).resolve() if target else self.root
        self.module_map: Dict[str, Path] = {}
        self.symbol_map: Dict[str, Set[str]] = {}
        self._build_index()

    # ------------------------------------------------------------------
    # Descoberta de raiz
    # ------------------------------------------------------------------

    def _discover_root(self, path: Path) -> Path:
        base = path if path.is_dir() else path.parent

        for candidate in [base, *base.parents]:
            if (candidate / "doxoade" / "cli.py").exists():
                return candidate

            if (candidate / "pyproject.toml").exists():
                return candidate

            if (candidate / ".git").exists():
                return candidate

        return base

    # ------------------------------------------------------------------
    # Iteração de arquivos
    # ------------------------------------------------------------------

    def _iter_python_files(self, base: Path):
        if base.is_file():
            if base.suffix == ".py":
                yield base
            return

        for p in base.rglob("*.py"):
            if any(part.lower() in SKIP_DIRS for part in p.parts):
                continue

            yield p

    # ------------------------------------------------------------------
    # Indexação
    # ------------------------------------------------------------------

    def _module_name(self, path: Path) -> str:
        try:
            rel = path.resolve().relative_to(self.root)
        except ValueError:
            return ""

        parts = list(rel.with_suffix("").parts)

        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        return ".".join(parts)

    def _build_index(self) -> None:
        for py in self._iter_python_files(self.root):
            mod = self._module_name(py)

            if mod:
                self.module_map[mod] = py

            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            symbols: Set[str] = set()

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.add(node.name)

                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            symbols.add(target.id)

                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        symbols.add(node.target.id)

                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name.split(".")[0]
                        symbols.add(name)

                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        symbols.add(alias.asname or alias.name)

            if mod:
                self.symbol_map[mod] = symbols

    # ------------------------------------------------------------------
    # Utilidades de módulo
    # ------------------------------------------------------------------

    def _module_exists(self, name: str) -> bool:
        if not name:
            return False

        if name in self.module_map:
            return True

        parts = name.split(".")
        p = self.root.joinpath(*parts)

        return p.with_suffix(".py").exists() or (p / "__init__.py").exists()

    def _looks_internal(self, name: str) -> bool:
        if not name:
            return False

        top = name.split(".")[0]

        if top in INTERNAL_ROOTS:
            return True

        return any(
            m == top or m.startswith(top + ".")
            for m in self.module_map
        )

    def _fix_module_name(self, name: str) -> str:
        if not name:
            return name

        if name in DEPRECATED_MAP:
            return DEPRECATED_MAP[name]

        if self._module_exists(name):
            return name

        if not self._looks_internal(name):
            return name

        prefixed = f"doxoade.{name}"
        if self._module_exists(prefixed):
            return prefixed

        leaf = name.split(".")[-1]

        candidates = [
            m for m in self.module_map
            if m.split(".")[-1] == leaf
        ]

        if len(candidates) == 1:
            return candidates[0]

        best: Optional[str] = None
        best_score = 0.0

        for cand in self.module_map:
            score = difflib.SequenceMatcher(None, name, cand).ratio()
            if score > best_score:
                best_score = score
                best = cand

        if best and best_score >= 0.86:
            return best

        return name

    def _package_parts(self, path: Path) -> List[str]:
        try:
            rel = path.resolve().relative_to(self.root)
        except ValueError:
            return []

        return list(rel.parts[:-1])

    def _resolve_relative(
        self,
        path: Path,
        level: int,
        module: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        parts = self._package_parts(path)

        up = level - 1

        if up > len(parts):
            return None, "Import relativo profundo demais para o pacote atual."

        if up == 0:
            base_parts = parts
        else:
            base_parts = parts[:-up]

        resolved_parts = base_parts + ([module] if module else [])
        return ".".join(resolved_parts), None

    # ------------------------------------------------------------------
    # Renderização de imports
    # ------------------------------------------------------------------

    @staticmethod
    def _alias_text(name: str, asname: Optional[str]) -> str:
        return f"{name} as {asname}" if asname else name

    def _source_segment(self, lines: List[str], node: ast.AST) -> str:
        start = max(getattr(node, "lineno", 1) - 1, 0)
        end = min(getattr(node, "end_lineno", start + 1), len(lines))
        return "\n".join(lines[start:end])

    def _render_import_node(
        self,
        node: ast.AST,
        lines: List[str],
        module_rewrites: Optional[Dict[str, str]] = None,
        from_module: Optional[str] = None,
        from_level: Optional[int] = None,
    ) -> str:
        lineno = getattr(node, "lineno", 1)
        orig_line = lines[lineno - 1] if 0 <= lineno - 1 < len(lines) else ""
        indent = orig_line[: len(orig_line) - len(orig_line.lstrip())]

        if isinstance(node, ast.Import):
            names = []

            for alias in node.names:
                new_name = (module_rewrites or {}).get(alias.name, alias.name)
                names.append(self._alias_text(new_name, alias.asname))

            return indent + "import " + ", ".join(names)

        if isinstance(node, ast.ImportFrom):
            module = from_module if from_module is not None else node.module
            level = from_level if from_level is not None else node.level

            prefix = "." * level
            module_text = f"{prefix}{module}" if module else prefix

            names = [
                self._alias_text(alias.name, alias.asname)
                for alias in node.names
            ]

            single = f"from {module_text} import " + ", ".join(names)

            if len(indent + single) <= 100:
                return indent + single

            body = ",\n".join(
                indent + "    " + name + ","
                for name in names
            )

            return f"{indent}from {module_text} import (\n{body}\n{indent})"

        return ""

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan_file(self, path: Path, report: ImportReport) -> None:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            report.issues.append(
                ImportIssue(
                    file=path,
                    line=0,
                    end_line=0,
                    kind="READ_ERROR",
                    message=str(e),
                    original="",
                    replacement=None,
                    severity="error",
                )
            )
            return

        lines = text.splitlines()

        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            report.issues.append(
                ImportIssue(
                    file=path,
                    line=e.lineno or 0,
                    end_line=e.lineno or 0,
                    kind="SYNTAX_ERROR",
                    message=str(e),
                    original="",
                    replacement=None,
                    severity="error",
                )
            )
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self._scan_import(path, node, lines, report)

            elif isinstance(node, ast.ImportFrom):
                self._scan_import_from(path, node, lines, report)

    def _scan_import(
        self,
        path: Path,
        node: ast.Import,
        lines: List[str],
        report: ImportReport,
    ) -> None:
        rewrites: Dict[str, str] = {}
        missing: List[str] = []

        for alias in node.names:
            fixed = self._fix_module_name(alias.name)

            if fixed != alias.name:
                rewrites[alias.name] = fixed

            elif not self._module_exists(alias.name) and self._looks_internal(alias.name):
                missing.append(alias.name)

        if rewrites:
            original = self._source_segment(lines, node)
            replacement = self._render_import_node(
                node,
                lines,
                module_rewrites=rewrites,
            )

            message = ", ".join(
                f"{old} -> {new}"
                for old, new in rewrites.items()
            )

            report.issues.append(
                ImportIssue(
                    file=path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    kind="MODULE_REWRITE",
                    message=message,
                    original=original,
                    replacement=replacement,
                    severity="warning",
                )
            )

        for name in missing:
            report.issues.append(
                ImportIssue(
                    file=path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    kind="MODULE_NOT_FOUND",
                    message=f"import {name} — módulo não encontrado",
                    original=self._source_segment(lines, node),
                    replacement=None,
                    severity="error",
                )
            )

    def _scan_import_from(
        self,
        path: Path,
        node: ast.ImportFrom,
        lines: List[str],
        report: ImportReport,
    ) -> None:
        original = self._source_segment(lines, node)
        replacement: Optional[str] = None
        kind = "IMPORT_FROM"
        message = ""
        final_module: Optional[str] = None

        if node.level > 0:
            resolved, err = self._resolve_relative(path, node.level, node.module)

            if err:
                report.issues.append(
                    ImportIssue(
                        file=path,
                        line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        kind="RELATIVE_TOO_DEEP",
                        message=err,
                        original=original,
                        replacement=None,
                        severity="error",
                    )
                )
                return

            fixed = self._fix_module_name(resolved or "")
            final_module = fixed

            if fixed != resolved:
                replacement = self._render_import_node(
                    node,
                    lines,
                    from_module=fixed,
                    from_level=0,
                )
                kind = "MODULE_REWRITE"
                message = f"{'.' * node.level}{node.module or ''} -> {fixed}"

        else:
            fixed = self._fix_module_name(node.module or "")
            final_module = fixed

            if node.module and fixed != node.module:
                replacement = self._render_import_node(
                    node,
                    lines,
                    from_module=fixed,
                    from_level=0,
                )
                kind = "MODULE_REWRITE"
                message = f"{node.module} -> {fixed}"

        if replacement:
            report.issues.append(
                ImportIssue(
                    file=path,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    kind=kind,
                    message=message,
                    original=original,
                    replacement=replacement,
                    severity="warning",
                )
            )

        if final_module and self._module_exists(final_module):
            symbols = self.symbol_map.get(final_module)

            if symbols is not None:
                missing = []

                for alias in node.names:
                    if alias.name == "*":
                        continue

                    if self._module_exists(f"{final_module}.{alias.name}"):
                        continue

                    if alias.name not in symbols:
                        missing.append(alias.name)

                if missing:
                    report.issues.append(
                        ImportIssue(
                            file=path,
                            line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            kind="SYMBOL_NOT_FOUND",
                            message=(
                                f"from {final_module} import {', '.join(missing)} "
                                f"— símbolo(s) não encontrado(s)"
                            ),
                            original=original,
                            replacement=None,
                            severity="warning",
                        )
                    )

    # ------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------

    def run(self, apply: bool = False) -> ImportReport:
        report = ImportReport()

        for py in self._iter_python_files(self.target):
            self.scan_file(py, report)

        if apply:
            self._apply(report)
            report.applied = True

        return report

    def _apply(self, report: ImportReport) -> None:
        fixable = [i for i in report.issues if i.replacement]

        if not fixable:
            return

        by_file: Dict[Path, List[ImportIssue]] = {}

        for issue in fixable:
            by_file.setdefault(issue.file, []).append(issue)

        for file, issues in by_file.items():
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = text.splitlines()

            for issue in sorted(issues, key=lambda x: x.line, reverse=True):
                start = max(issue.line - 1, 0)
                end = min(issue.end_line, len(lines))
                end = max(end, start)

                replacement_lines = issue.replacement.splitlines()
                lines[start:end] = replacement_lines

            new_text = "\n".join(lines)

            if text.endswith("\n"):
                new_text += "\n"

            try:
                compile(new_text, str(file), "exec")
            except Exception as e:
                report.issues.append(
                    ImportIssue(
                        file=file,
                        line=0,
                        end_line=0,
                        kind="APPLY_BLOCKED",
                        message=f"Alteração rejeitada por compile(): {e}",
                        original="",
                        replacement=None,
                        severity="error",
                    )
                )
                continue

            backup = file.with_name(file.name + ".importdoctor.bak")
            backup.write_text(text, encoding="utf-8")

            file.write_text(new_text, encoding="utf-8")

            report.files_changed += 1
            report.backups.append(backup)

def _print_issue_diff(issue: ImportIssue) -> None:
    if not issue.original or not issue.replacement:
        return

    import difflib

    orig = issue.original.splitlines()
    new = issue.replacement.splitlines()

    try:
        rel = issue.file.name
    except Exception:
        rel = str(issue.file)

    diff = difflib.unified_diff(
        orig,
        new,
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
        lineterm="",
    )

    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            print(f"  {line}")

        elif line.startswith("@@"):
            print(f"  \033[36m{line}\033[0m")

        elif line.startswith("-"):
            print(f"  \033[31m{line}\033[0m")

        elif line.startswith("+"):
            print(f"  \033[32m{line}\033[0m")

        else:
            print(f"  \033[90m{line}\033[0m")

def print_report(report: ImportReport, verbose: bool = False, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    print("─ IMPORT DOCTOR ─────────────────────────────────────────")

    if not report.issues:
        print("[OK] Nenhum problema de import encontrado.")
        print(f"Aplicado: {report.applied} | Arquivos alterados: {report.files_changed}")
        return

    for issue in report.issues:
        print(
            f"[{issue.severity.upper()}] "
            f"{issue.file}:{issue.line} "
            f"[{issue.kind}] {issue.message}"
        )

        if verbose:
            if issue.original:
                print("  Original:")
                for line in issue.original.splitlines():
                    print(f"    {line}")

            if issue.replacement:
                print("  Diff:")
                _print_issue_diff(issue)

    print("────────────────────────────────────────────────────────")
    print(f"Total: {len(report.issues)}")
    print(f"Erros: {len(report.errors)} | Avisos: {len(report.warnings)}")
    print(f"Aplicado: {report.applied} | Arquivos alterados: {report.files_changed}")

    if report.backups:
        print("Backups:")
        for b in report.backups[:20]:
            print(f"  {b}")
