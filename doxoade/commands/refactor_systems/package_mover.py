# doxoade/commands/refactor_systems/package_mover.py
# doxoade/doxoade/commands/refactor_systems/package_mover.py
# -*- coding: utf-8 -*-
"""
PackageMover — movimentação segura de pacotes Python com reescrita de imports.

Objetivo:
- mover pastas/pacotes inteiros;
- reescrever imports absolutos antigos para o novo prefixo;
- mostrar diff em dry-run;
- aplicar com backup.
"""

from __future__ import annotations

import difflib
import os
import re
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from doxoade.commands.git_systems.git_merge import merge


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

BACKUP_SUFFIXES = {
    ".bak",
    ".old",
    ".orig",
    ".bkp",
    ".backup",
}

@dataclass
class FileChange:
    path: Path
    old_text: str
    new_text: str


def _module_from_path(root: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return ""

    parts = list(rel.parts)

    if not parts:
        return ""

    if parts[-1] == "__init__.py":
        parts = parts[:-1]

    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]

    return ".".join(parts)


class PackageMover:
    """
    Move um pacote Python e atualiza referências de import.

    Regras:
    - se DST existe como diretório e não houver --merge,
      SRC é movido para DST/nome_de_SRC;
    - se --merge for usado, o conteúdo de SRC é movido para DST;
    - imports absolutos antigos são reescritos.
    """

    def __init__(
        self,
        root: Path,
        src: Path,
        dst: Path,
        merge: bool = False,
        include_backups: bool = False,
    ):

        self.root = Path(root).resolve()

        src_path = Path(src)
        self.src = (
            src_path.resolve()
            if src_path.is_absolute()
            else (self.root / src_path).resolve()
        )

        dst_path = Path(dst)
        self.dst_input = dst_path

        self.dst = (
            dst_path.resolve()
            if dst_path.is_absolute()
            else (self.root / dst_path).resolve()
        )

        self.merge = merge
        self.include_backups = include_backups

        if not self.src.exists():
            raise FileNotFoundError(f"Pasta de origem não encontrada: {self.src}")

        if self.src.is_file():
            raise ValueError("O origem precisa ser uma pasta/pacote, não um arquivo.")

        if self.dst.exists() and self.dst.is_file():
            raise ValueError("O destino não pode ser um arquivo.")

        if self.dst.exists() and self.dst.is_dir() and not self.merge:
            self.new_dir = self.dst / self.src.name
        else:
            self.new_dir = self.dst

        if self.new_dir == self.src:
            raise ValueError("Origem e destino são iguais.")

        if self.src in self.new_dir.parents:
            raise ValueError("Não é possível mover uma pasta para dentro dela mesma.")

        self.old_pkg = _module_from_path(self.root, self.src)
        self.new_pkg = _module_from_path(self.root, self.new_dir)

        if not self.old_pkg:
            raise ValueError(
                f"Não consegui resolver o módulo da origem: {self.src}"
            )

        if not self.new_pkg:
            raise ValueError(
                f"Não consegui resolver o módulo do destino: {self.new_dir}"
            )

    # ------------------------------------------------------------------
    # Plano de movimentação
    # ------------------------------------------------------------------

    def planned_moves(self) -> List[Tuple[Path, Path]]:
        moves: List[Tuple[Path, Path]] = []

        for p in self.src.rglob("*"):
            if p.is_dir():
                continue

            if any(part in SKIP_DIRS for part in p.parts):
                continue

            if p.name.endswith(".importdoctor.bak"):
                continue

            if p.suffix.lower() in BACKUP_SUFFIXES and not self.include_backups:
                continue

            rel = p.relative_to(self.src)
            moves.append((p, self.new_dir / rel))

        return moves

    # ------------------------------------------------------------------
    # Reescrita de imports
    # ------------------------------------------------------------------

    def _rewrite_text(self, text: str) -> Tuple[str, bool]:
        old = re.escape(self.old_pkg)
        new = self.new_pkg

        patterns = [
            # from old.sub import x
            (
                rf"^(\s*from\s+){old}\.([\w\.]+)(\s+import\s+)",
                rf"\1{new}.\2\3",
            ),
            # from old import x
            (
                rf"^(\s*from\s+){old}(\s+import\s+)",
                rf"\1{new}\2",
            ),
            # import old.sub as x
            (
                rf"^(\s*import\s+){old}\.([\w\.]+)(.*)$",
                rf"\1{new}.\2\3",
            ),
            # import old
            (
                rf"^(\s*import\s+){old}(.*)$",
                rf"\1{new}\2",
            ),
        ]

        changed = False

        for pattern, replacement in patterns:
            new_text = re.sub(pattern, replacement, text, flags=re.MULTILINE)

            if new_text != text:
                text = new_text
                changed = True

        # Reescreve strings literais com o caminho antigo.
        # Útil para lazy maps e imports dinâmicos.
        string_patterns = [
            (
                rf"(['\"]){old}\.([\w\.]*)(['\"])",
                rf"\1{new}.\2\3",
            ),
            (
                rf"(['\"]){old}(['\"])",
                rf"\1{new}\2",
            ),
        ]

        for pattern, replacement in string_patterns:
            new_text = re.sub(pattern, replacement, text, flags=re.MULTILINE)

            if new_text != text:
                text = new_text
                changed = True

        return text, changed

    def _iter_python_files(self):
        for p in self.root.rglob("*.py"):
            if any(part.lower() in SKIP_DIRS for part in p.parts):
                continue

            if ".importdoctor.bak" in p.name:
                continue

            yield p

    def collect_changes(self) -> List[FileChange]:
        changes: List[FileChange] = []

        for py in self._iter_python_files():
            try:
                text = py.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            new_text, changed = self._rewrite_text(text)

            if changed:
                changes.append(FileChange(path=py, old_text=text, new_text=new_text))

        return changes

    # ------------------------------------------------------------------
    # Relatório / Diff
    # ------------------------------------------------------------------

    def _print_diff(self, change: FileChange, max_lines: int = 120) -> None:
        old_lines = change.old_text.splitlines()
        new_lines = change.new_text.splitlines()

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{change.path.name}",
            tofile=f"b/{change.path.name}",
            lineterm="",
        )

        printed = 0

        for line in diff:
            if printed >= max_lines:
                print("      ...")
                break

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

            printed += 1

    def report(self, verbose: bool = True) -> None:
        print("─ PACKAGE MOVER ─────────────────────────────────────────")
        print(f"Origem:       {self.src}")
        print(f"Destino:      {self.new_dir}")
        print(f"Módulo antigo: {self.old_pkg}")
        print(f"Módulo novo:   {self.new_pkg}")
        print(f"Modo:         {'merge' if self.merge else 'move-package'}")

        moves = self.planned_moves()

        print(f"Arquivos a mover: {len(moves)}")

        if verbose:
            for old_file, new_file in moves[:50]:
                print(f"  MOVE {old_file} -> {new_file}")

            if len(moves) > 50:
                print(f"  ... +{len(moves) - 50} arquivos")

            print("\nÁrvore final planejada:")
            self.render_planned_tree()

        changes = self.collect_changes()

        print(f"Arquivos com imports a atualizar: {len(changes)}")

        if verbose:
            for change in changes:
                print(f"\n  [IMPORT] {change.path}")
                self._print_diff(change)

        print("────────────────────────────────────────────────────────")

    # ------------------------------------------------------------------
    # Aplicação
    # ------------------------------------------------------------------

    def apply(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = (
            self.root
            / ".doxoade"
            / "refactor_backups"
            / f"move_{timestamp}"
        )

        backup_root.mkdir(parents=True, exist_ok=True)

        # Backup da origem
        source_backup = backup_root / self.src.name
        if self.src.exists():
            shutil.copytree(self.src, source_backup, dirs_exist_ok=True)

        changes = self.collect_changes()

        # Backup e escrita dos arquivos com imports alterados
        for change in changes:
            try:
                rel = change.path.relative_to(self.root)
                backup_file = backup_root / (
                    str(rel).replace(os.sep, "__") + ".bak"
                )
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                backup_file.write_text(change.old_text, encoding="utf-8")
                
                write_text_safe(change.path, change.new_text)
#                change.path.write_text(change.new_text, encoding="utf-8")

            except Exception as e:
                print(f"[ERRO] Falha ao atualizar {change.path}: {e}")

        # Cria diretório destino
        self.new_dir.parent.mkdir(parents=True, exist_ok=True)

        if self.merge and not (self.new_dir / "__init__.py").exists():
            (self.new_dir / "__init__.py").write_text(
                "# -*- coding: utf-8 -*-\n",
                encoding="utf-8",
            )

        # Move arquivos
        for old_file, new_file in self.planned_moves():
            if not old_file.exists():
                continue

            new_file.parent.mkdir(parents=True, exist_ok=True)

            if new_file.exists():
                overwrite_backup = backup_root / (
                    "existing_" + str(new_file.relative_to(self.root)).replace(os.sep, "__")
                )
                overwrite_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(new_file, overwrite_backup)
                new_file.unlink()

            shutil.move(str(old_file), str(new_file))

        # Remove árvore antiga
        if self.src.exists():
            shutil.rmtree(self.src, ignore_errors=True)

        print(f"✔ Pacote movido para: {self.new_dir}")
        print(f"✔ Backup em: {backup_root}")
        
    def render_planned_tree(self, max_lines: int = 240) -> None:
        """
        Exibe a árvore final planejada no estilo doxoade mk:
        - ícones 📁 / 📄
        - galhos ├── / └──
        - diretórios aninhados
        """

        moves = self.planned_moves()

        rels = sorted(
            {
                dst.relative_to(self.new_dir).as_posix()
                for _, dst in moves
            }
        )

        tree: dict = {}

        for rel in rels:
            parts = Path(rel).parts

            if not parts:
                continue

            node = tree

            for part in parts[:-1]:
                node = node.setdefault(part, {})

            node[parts[-1]] = None

        printed = 0

        def _walk(node: dict, prefix: str = "") -> None:
            nonlocal printed

            # Diretórios primeiro, depois arquivos.
            items = sorted(
                node.items(),
                key=lambda kv: (kv[1] is None, kv[0].lower()),
            )

            for idx, (name, child) in enumerate(items):
                if printed >= max_lines:
                    return

                last = idx == len(items) - 1

                connector = "└── " if last else "├── "
                icon = "📁" if isinstance(child, dict) else "📄"

                print(f"{prefix}{connector}{icon} {name}")

                printed += 1

                if isinstance(child, dict):
                    extension = "    " if last else "│   "
                    _walk(child, prefix + extension)

        print(f"📁 {self.new_dir.name}")
        _walk(tree)

        if printed >= max_lines:
            print("   ...")

    def stage(self) -> Path:
        """
        Cria um espelho da operação em .doxoade/refactor_staging.

        Não toca nos arquivos reais do projeto.
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        stage_root = (
            self.root
            / ".doxoade"
            / "refactor_staging"
            / f"move_{timestamp}"
        )

        stage_new = stage_root / "new"
        stage_original = stage_root / "original"
        stage_rewritten = stage_root / "rewritten"

        stage_new.mkdir(parents=True, exist_ok=True)
        stage_original.mkdir(parents=True, exist_ok=True)
        stage_rewritten.mkdir(parents=True, exist_ok=True)

        try:
            rel_new_dir = self.new_dir.relative_to(self.root)
        except ValueError:
            rel_new_dir = Path(self.new_dir.name)

        staged_new_dir = stage_new / rel_new_dir

        shutil.copytree(
            self.src,
            staged_new_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
            ),
        )

        changes = self.collect_changes()

        manifest = {
            "old_module": self.old_pkg,
            "new_module": self.new_pkg,
            "source": str(self.src),
            "destination": str(self.new_dir),
            "merge": self.merge,
            "include_backups": self.include_backups,
            "moves": [
                {
                    "src": str(src_file),
                    "dst": str(dst_file),
                }
                for src_file, dst_file in self.planned_moves()
            ],
            "changed_files": [
                {
                    "file": str(change.path),
                    "original_len": len(change.old_text),
                    "rewritten_len": len(change.new_text),
                }
                for change in changes
            ],
        }

        for change in changes:
            try:
                rel = change.path.relative_to(self.root)
            except ValueError:
                rel = Path(change.path.name)

            original_out = stage_original / rel
            rewritten_out = stage_rewritten / rel

            original_out.parent.mkdir(parents=True, exist_ok=True)
            rewritten_out.parent.mkdir(parents=True, exist_ok=True)

            original_out.write_text(change.old_text, encoding="utf-8")
            rewritten_out.write_text(change.new_text, encoding="utf-8")

        manifest_path = stage_root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return stage_root
