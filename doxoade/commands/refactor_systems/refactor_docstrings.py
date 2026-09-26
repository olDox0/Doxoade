# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_docstrings.py
"""
📖 THOTH & OSÍRIS — Arqueologia e Restauração Automatizada de Docstrings v2.0.
Otimizado: Leitura em lote (Batch Git Log), Poda de Escopo e Zero Falsos-Positivos.
"""
from __future__ import annotations

import ast
import re
import click
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.git import _run_git_command
from .refactor_utils import iter_python_files, read_text_safe, write_text_safe
from .refactor_preview import print_snippet_diff


@dataclass
class DocstringTarget:
    file_path: Path
    symbol_name: str
    node_type: str
    line: int
    col_offset: int
    args_list: List[str] = field(default_factory=list)

@dataclass
class RecoveryHit:
    """Resultado da arqueologia de um símbolo."""
    target: DocstringTarget
    docstring: str
    origin_commit: str
    source_type: str  # 'GIT_FILE', 'GIT_PICKAXE', 'CANONICAL_STUB'


class DocstringArcheologist:
    """Motor arqueológico de extração histórica e injeção de docstrings."""

    def __init__(self, root: Path):
        self.root = Path(_find_project_root(root)).resolve()

    def scan_missing_in_file(self, file_path: Path) -> List[DocstringTarget]:
        """Varre o AST do arquivo e identifica funções e classes sem docstring."""
        content = read_text_safe(file_path)
        try:
            tree = ast.parse(content, filename=str(file_path))
        except Exception:
            return []

        missing: List[DocstringTarget] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(node) is None:
                    if node.name.startswith("__") and node.name.endswith("__") and node.name not in ("__init__",):
                        continue

                    node_type = (
                        "async def" if isinstance(node, ast.AsyncFunctionDef)
                        else "class" if isinstance(node, ast.ClassDef)
                        else "def"
                    )

                    args = []
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]

                    missing.append(DocstringTarget(
                        file_path=file_path.resolve(),
                        symbol_name=node.name,
                        node_type=node_type,
                        line=node.lineno,
                        col_offset=node.col_offset,
                        args_list=args
                    ))

        return missing

    def mine_git_history_batch(self, file_path: Path, depth: int = 15) -> Dict[str, Tuple[str, str]]:
        """
        ⚡ PLUMBING FAST-BATCH: Faz UMA ÚNICA chamada ao Git por arquivo,
        extraindo todas as docstrings passadas diretamente em memória (sub-100ms).
        """
        try:
            rel_path = file_path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return {}

        # 🛑 PODA DE ESCOPO: Ignora se for arquivo fora do código fonte
        if any(p in rel_path for p in ("venv/", ".git/", "site-packages/")):
            return {}

        log_raw = _run_git_command(
            ['log', f'-n{depth}', '--format=@@COMMIT:%H', '-p', '--follow', '--', rel_path],
            capture_output=True,
            silent_fail=True,
            cwd=str(self.root)
        )
        if not log_raw:
            return {}

        found_map: Dict[str, Tuple[str, str]] = {}
        commits_blocks = log_raw.split("@@COMMIT:")

        for block in commits_blocks:
            if not block.strip():
                continue
            lines = block.splitlines()
            commit_hash = lines[0].strip()[:8]
            patch_content = "\n".join(lines[1:])

            # Procura por adições ou remoções de docstrings no patch
            # Ex: +    """Descrição...""" ou -    """Descrição..."""
            matches = re.finditer(
                r'(?:def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*).*?:\s*\n\s*(?:[+-]\s*)?["\'](["\']{2})(.*?)\2',
                patch_content,
                re.DOTALL
            )
            for m in matches:
                sym_name = m.group(1)
                doc_text = m.group(3).strip()
                if doc_text and sym_name not in found_map:
                    found_map[sym_name] = (doc_text, commit_hash)

            # Fallback direto: se o commit tem a versão inteira do arquivo via show
            if not found_map:
                try:
                    full_old = _run_git_command(['show', f'{commit_hash}:{rel_path}'], capture_output=True, silent_fail=True, cwd=str(self.root))
                    if full_old:
                        tree = ast.parse(full_old)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                doc = ast.get_docstring(node)
                                if doc and node.name not in found_map:
                                    found_map[node.name] = (doc, commit_hash)
                except Exception:
                    pass

        return found_map

    def inject_docstring(self, file_content: str, target: DocstringTarget, docstring: str) -> Optional[str]:
        """Injeta a docstring formatada logo abaixo do cabeçalho def/class."""
        lines = file_content.splitlines(keepends=True)
        if target.line > len(lines):
            return None

        func_line = lines[target.line - 1]
        base_indent = func_line[:len(func_line) - len(func_line.lstrip())]
        doc_indent = base_indent + "    "

        doc_lines = docstring.strip().splitlines()
        if len(doc_lines) == 1:
            clean_doc = f'{doc_indent}"""{doc_lines[0]}"""\n'
        else:
            body = "\n".join(f"{doc_indent}{l}" if l.strip() else "" for l in doc_lines[1:])
            clean_doc = f'{doc_indent}"""\n{doc_indent}{doc_lines[0]}\n{body}\n{doc_indent}"""\n'

        insert_idx = target.line - 1
        while insert_idx < len(lines):
            line_str = lines[insert_idx].split("#")[0].strip()
            if line_str.endswith(":"):
                insert_idx += 1
                break
            insert_idx += 1

        new_lines = lines[:insert_idx] + [clean_doc] + lines[insert_idx:]
        new_text = "".join(new_lines)

        try:
            compile(new_text, str(target.file_path), "exec")
            return new_text
        except SyntaxError:
            return None

    def run_archaeology(
        self,
        target_path: Path,
        apply: bool = False,
        depth: int = 15,
        verbose: bool = False
    ) -> dict:
        target_path = Path(target_path).resolve()
        files = [target_path] if target_path.is_file() else list(iter_python_files(target_path))

        click.secho(f"\n🔍 [THOTH] Arqueologia Rápida em {len(files)} arquivo(s)...", fg="cyan", bold=True)

        total_missing = 0
        total_recovered_git = 0
        files_modified = 0

        for file_path in files:
            missing_symbols = self.scan_missing_in_file(file_path)
            if not missing_symbols:
                continue

            total_missing += len(missing_symbols)
            current_content = read_text_safe(file_path)
            modified_content = current_content
            file_changed = False

            # 🛑 1 ÚNICA chamada Git em lote por arquivo:
            git_doc_cache = self.mine_git_history_batch(file_path, depth=depth)

            for sym in sorted(missing_symbols, key=lambda s: s.line, reverse=True):
                if sym.symbol_name in git_doc_cache:
                    recovered_doc, commit_hash = git_doc_cache[sym.symbol_name]
                    injected = self.inject_docstring(modified_content, sym, recovered_doc)
                    if injected:
                        modified_content = injected
                        file_changed = True
                        total_recovered_git += 1
                        if verbose:
                            click.secho(f"  ✔ [Git ({commit_hash})] {sym.symbol_name} @ {file_path.name}:{sym.line}", fg="green")

            if file_changed:
                files_modified += 1
                orig_lines = current_content.splitlines(keepends=True)
                new_lines = modified_content.splitlines(keepends=True)
                print_snippet_diff(file_path, orig_lines, new_lines, context=2)

                if apply:
                    write_text_safe(file_path, modified_content)

        return {
            "missing": total_missing,
            "recovered_git": total_recovered_git,
            "files_modified": files_modified,
            "applied": apply
        }

    def mine_git_for_file(self, file_path: Path, depth: int = 15) -> Dict[str, Tuple[str, str]]:
        """
        [Plano A]: Varre os últimos N commits do próprio arquivo no Git
        e retorna um mapa: {symbol_name: (docstring, commit_hash)}.
        """
        try:
            rel_path = file_path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return {}

        log_raw = _run_git_command(
            ['log', f'-n{depth}', '--format=%H', '--follow', '--', rel_path],
            capture_output=True,
            silent_fail=True,
            cwd=str(self.root)
        )
        if not log_raw:
            return {}

        commits = [c.strip() for c in log_raw.splitlines() if c.strip()]
        found_map: Dict[str, Tuple[str, str]] = {}

        for commit in commits:
            historical_content = _run_git_command(
                ['show', f'{commit}:{rel_path}'],
                capture_output=True,
                silent_fail=True,
                cwd=str(self.root)
            )
            if not historical_content:
                continue

            try:
                tree = ast.parse(historical_content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        doc = ast.get_docstring(node)
                        if doc and node.name not in found_map:
                            found_map[node.name] = (doc, commit[:8])
            except Exception:
                continue

        return found_map

    def mine_git_pickaxe(self, symbol_name: str, node_type: str = "def") -> Optional[Tuple[str, str]]:
        """
        [Plano B]: Busca global no Git onde o símbolo foi definido originalmente.
        Útil para funções que mudaram de arquivo durante refatorações.
        """
        pattern = f"{node_type} {symbol_name}"
        log_raw = _run_git_command(
            ['log', '-S', pattern, '-n5', '--format=COMMIT:%H', '--name-only'],
            capture_output=True,
            silent_fail=True,
            cwd=str(self.root)
        )
        if not log_raw:
            return None

        current_commit = None
        for line in log_raw.splitlines():
            line = line.strip()
            if line.startswith("COMMIT:"):
                current_commit = line.split("COMMIT:")[1].strip()
            elif line.endswith(".py") and current_commit:
                # Testa se a versão antiga tinha docstring
                old_code = _run_git_command(
                    ['show', f'{current_commit}:{line}'],
                    capture_output=True,
                    silent_fail=True,
                    cwd=str(self.root)
                )
                if not old_code:
                    continue
                try:
                    tree = ast.parse(old_code)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if node.name == symbol_name:
                                doc = ast.get_docstring(node)
                                if doc:
                                    return (doc, f"{current_commit[:8]}:{line}")
                except Exception:
                    continue

        return None

    def generate_canonical_stub(self, target: DocstringTarget) -> str:
        """[Plano C]: Gera docstring sintética estruturada caso o histórico não possua registro."""
        clean_name = target.symbol_name.replace("_", " ").strip().capitalize()
        if target.node_type == "class":
            return f"Classe {target.symbol_name} — {clean_name}."
        
        args_desc = ""
        if target.args_list:
            args_desc = f"\nArgumentos:\n" + "\n".join(f"    {a}: Parâmetro de entrada." for a in target.args_list)

        return f"{clean_name}.{args_desc}"

    def inject_docstring(self, file_content: str, target: DocstringTarget, docstring: str) -> Optional[str]:
        """
        Injeta a docstring na posição exata após o cabeçalho 'def' ou 'class',
        respeitando a identação e validando com compile().
        """
        lines = file_content.splitlines(keepends=True)
        if target.line > len(lines):
            return None

        # Identifica a identação da função e define o recuo da docstring (4 espaços a mais)
        func_line = lines[target.line - 1]
        base_indent = func_line[:len(func_line) - len(func_line.lstrip())]
        doc_indent = base_indent + "    "

        # Formata a docstring
        doc_lines = docstring.strip().splitlines()
        if len(doc_lines) == 1:
            clean_doc = f'{doc_indent}"""{doc_lines[0]}"""\n'
        else:
            body = "\n".join(f"{doc_indent}{l}" if l.strip() else "" for l in doc_lines[1:])
            clean_doc = f'{doc_indent}"""\n{doc_indent}{doc_lines[0]}\n{body}\n{doc_indent}"""\n'

        # Procura o término do cabeçalho def/class (dois pontos ':')
        insert_idx = target.line - 1
        while insert_idx < len(lines):
            line_str = lines[insert_idx].split("#")[0].strip()
            if line_str.endswith(":"):
                insert_idx += 1
                break
            insert_idx += 1

        new_lines = lines[:insert_idx] + [clean_doc] + lines[insert_idx:]
        new_text = "".join(new_lines)

        # Validação Ma'at com compile()
        try:
            compile(new_text, str(target.file_path), "exec")
            return new_text
        except SyntaxError:
            return None

    def run_archaeology(
        self,
        target_path: Path,
        apply: bool = False,
        depth: int = 15,
        allow_stubs: bool = False,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """Orquestra o ciclo completo de auditoria e restauração."""
        target_path = Path(target_path).resolve()
        files = [target_path] if target_path.is_file() else list(iter_python_files(target_path))

        click.secho(f"\n🔍 [THOTH] Iniciando Arqueologia de Docstrings em {len(files)} arquivo(s)...", fg="cyan", bold=True)
        
        total_missing = 0
        total_recovered_git = 0
        total_stubs = 0
        files_modified = 0

        for file_path in files:
            missing_symbols = self.scan_missing_in_file(file_path)
            if not missing_symbols:
                continue

            total_missing += len(missing_symbols)
            current_content = read_text_safe(file_path)
            modified_content = current_content
            file_changed = False

            # [Plano A]: Mineração em lote no histórico do arquivo
            git_doc_cache = self.mine_git_for_file(file_path, depth=depth)

            # Processa do último para o primeiro para manter números de linha estáveis
            for sym in sorted(missing_symbols, key=lambda s: s.line, reverse=True):
                recovered_doc = None
                origin_tag = ""

                # 1. Tenta histórico local do arquivo (Plano A - Rápido)
                if sym.symbol_name in git_doc_cache:
                    recovered_doc, origin_tag = git_doc_cache[sym.symbol_name]
                    origin_tag = f"Git File ({origin_tag})"
                    total_recovered_git += 1

                # 2. Só tenta pickaxe global se --deep for passado explicitamente
                elif allow_deep_pickaxe:
                    pickaxe_res = self.mine_git_pickaxe(sym.symbol_name, sym.node_type)
                    if pickaxe_res:
                            recovered_doc, commit_ref = pickaxe_res
                            origin_tag = f"Git Pickaxe ({commit_ref})"
                            total_recovered_git += 1

                # 3. [Plano C]: Fallback de Stub Canônico se permitido
                if not recovered_doc and allow_stubs:
                    recovered_doc = self.generate_canonical_stub(sym)
                    origin_tag = "Canônico (Stub)"
                    total_stubs += 1

                if recovered_doc:
                    injected = self.inject_docstring(modified_content, sym, recovered_doc)
                    if injected:
                        modified_content = injected
                        file_changed = True
                        if verbose:
                            click.secho(f"  ✔ [{origin_tag}] {sym.symbol_name} @ {file_path.name}:{sym.line}", fg="green")

            if file_changed:
                files_modified += 1
                orig_lines = current_content.splitlines(keepends=True)
                new_lines = modified_content.splitlines(keepends=True)
                
                print_snippet_diff(file_path, orig_lines, new_lines, context=2)

                if apply:
                    write_text_safe(file_path, modified_content)

        return {
            "missing": total_missing,
            "recovered_git": total_recovered_git,
            "stubs": total_stubs,
            "files_modified": files_modified,
            "applied": apply
        }
