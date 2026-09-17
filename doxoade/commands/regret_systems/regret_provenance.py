# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_provenance.py
"""
🏛️ DOXOADE FILE PROVENANCE ENGINE — Rastreamento de Origem e Genealogia Ancestral.
Identifica a certidão de nascimento de arquivos, linhagem via Git e perdas de
capacidades decorrentes de cisão/modularização (Splits de God Classes e Templates).
Compliance: ProDeNov 1.2.1 | PASC-6.1
"""
from __future__ import annotations
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

try:
    from doxoade.commands.regret_systems.regret_git_reader import RegretGitReader
    from doxoade.commands.regret_systems.regret_lua_inspector import (
        RegretLuaInspector,
        LuaCapabilityInventory,
        RegretFinding,
    )
    from doxoade.commands.regret_systems.regret_python_inspector import (
        RegretPythonInspector,
        PythonInventory,
    )
except ImportError:
    from .regret_git_reader import RegretGitReader
    from .regret_lua_inspector import (
        RegretLuaInspector,
        LuaCapabilityInventory,
        RegretFinding,
    )
    from .regret_python_inspector import (
        RegretPythonInspector,
        PythonInventory,
    )


@dataclass
class FileOriginMeta:
    """Certidão de nascimento e metadados históricos de um arquivo."""
    file_path: Path
    created_commit: str = "unknown"
    created_date: str = "unknown"
    created_author: str = "unknown"
    initial_commit_msg: str = ""
    is_split_child: bool = False
    parent_file_name: Optional[str] = None
    ancestor_path: Optional[Path] = None
    lineage_length: int = 1
    rename_history: List[str] = field(default_factory=list)


class FileProvenanceEngine:
    """Motor de Genealogia de Arquivos e Verificação de Herança Ancestral."""

    # Padrões heurísticos de documentação de cisão (Doxoade Docstring Pattern)
    RE_SPLIT_DOCSTRING = re.compile(
        r"(?:split\s+de|extra[ií]do\s+de|modulariza[çc][ãa]o\s+de|dividido\s+a\s+partir\s+de)\s+([a-zA-Z0-9_\-.]+\.(?:py|lua))",
        re.IGNORECASE,
    )

    @classmethod
    def resolve_lineage(cls, file_path: Path) -> FileOriginMeta:
        """
        [PLANO A & B] Reconstrói a linhagem do arquivo via git log --follow
        e heurísticas semânticas de cabeçalho.
        """
        meta = FileOriginMeta(file_path=file_path)
        if not file_path.exists():
            return meta

        root = RegretGitReader.get_repo_root(file_path.parent)
        try:
            rel_path = file_path.relative_to(root).as_posix()
        except ValueError:
            rel_path = file_path.as_posix()

        # 1. PLANO A: Consulta histórica no Git com rastreamento de renames (--follow)
        try:
            cmd = [
                "git", "log", "--follow",
                "--format=%H|%an|%ad|%s",
                "--date=short",
                "--name-status",
                "--", rel_path
            ]
            res = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace"
            )

            if res.returncode == 0 and res.stdout.strip():
                blocks = res.stdout.strip().split("\n\n")
                meta.lineage_length = len(blocks)
                
                # O commit mais antigo está no final da lista
                oldest_block = blocks[-1].strip().splitlines()
                if oldest_block:
                    header = oldest_block[0]
                    parts = header.split("|", 3)
                    if len(parts) >= 4:
                        meta.created_commit = parts[0][:8]
                        meta.created_author = parts[1]
                        meta.created_date = parts[2]
                        meta.initial_commit_msg = parts[3]

                # Rastreia histórico de renames
                for b in blocks:
                    for line in b.splitlines():
                        if line.startswith("R") and "\t" in line:
                            meta.rename_history.append(line.strip())

        except Exception:
            pass

        with RegretGitReader._GIT_LOCK:
            try:
                cmd = [
                    "git", "log", "--follow",
                    "--format=%H|%an|%ad|%s",
                    "--date=short",
                    "--name-status",
                    "-n", "10",  # Limita aos 10 commits mais relevantes para poupar I/O
                    "--", rel_path
                ]
                res = subprocess.run(
                    cmd,
                    cwd=str(root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=3,
                    encoding="utf-8",
                    errors="replace"
                )
                if res.returncode == 0 and res.stdout.strip():
                    blocks = res.stdout.strip().split("\n\n")
                    meta.lineage_length = len(blocks)
                    oldest_block = blocks[-1].strip().splitlines()
                    if oldest_block:
                        header = oldest_block[0]
                        parts = header.split("|", 3)
                        if len(parts) >= 4:
                            meta.created_commit = parts[0][:8]
                            meta.created_author = parts[1]
                            meta.created_date = parts[2]
                            meta.initial_commit_msg = parts[3]
                    for b in blocks:
                        for line in b.splitlines():
                            if line.startswith("R") and "\t" in line:
                                meta.rename_history.append(line.strip())
            except Exception:
                pass

        # 2. PLANO B: Heurística Semântica em Docstrings e Comentários do Topo
        try:
            sample_header = ""
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for _ in range(35):  # Lê as primeiras 35 linhas
                    line = f.readline()
                    if not line:
                        break
                    sample_header += line

            split_match = cls.RE_SPLIT_DOCSTRING.search(sample_header)
            if split_match:
                meta.is_split_child = True
                meta.parent_file_name = split_match.group(1).strip()
                parent_candidate = file_path.parent / meta.parent_file_name
                if parent_candidate.exists():
                    meta.ancestor_path = parent_candidate
        except Exception:
            pass

        # 3. Heurística Especial de Templates Numéricos do Lite XL (Ex: 19a..19d derivando de 19)
        if not meta.is_split_child and file_path.suffix == ".lua":
            fname = file_path.name
            m_num = re.match(r"^(\d+)[a-z]_", fname)
            if m_num:
                prefix = m_num.group(1)
                for sib in file_path.parent.glob(f"{prefix}_*.lua"):
                    if sib.is_file() and sib.name != fname:
                        meta.is_split_child = True
                        meta.parent_file_name = sib.name
                        meta.ancestor_path = sib
                        break

        return meta

    @classmethod
    def find_ancestral_leaks(
        cls,
        child_path: Path,
        parent_content: str,
        child_content: str,
        sibling_contents: Optional[Dict[str, str]] = None,
        parent_name: str = "ancestral",
        parent_commit: str = "desconhecido"
    ) -> List[RegretFinding]:
        """
        Compara o arquivo progenitor contra o filho (e irmãos) para acusar
        capacidades perdidas durante a modularização (SPLIT_CAPABILITY_LEAK).
        """
        findings: List[RegretFinding] = []
        ext = child_path.suffix.lower()

        if ext == ".lua":
            parent_inv = RegretLuaInspector.extract_inventory(parent_content, parent_name)
            child_inv = RegretLuaInspector.extract_inventory(child_content, child_path.name)

            all_children_invs = [child_inv]
            if sibling_contents:
                for sib_name, sib_code in sibling_contents.items():
                    all_children_invs.append(RegretLuaInspector.extract_inventory(sib_code, sib_name))

            merged_children = RegretLuaInspector.merge_inventories(all_children_invs)

            # 1. Comandos que o pai tinha e nenhum filho herdou
            for cmd, (snippet, _) in parent_inv.commands.items():
                if cmd not in merged_children.commands:
                    findings.append(RegretFinding(
                        category="SPLIT_CAPABILITY_LEAK",
                        identifier=f"command:{cmd}",
                        severity="high",
                        old_line_approx=1,
                        snippet_lost=snippet,
                        impact_description=(
                            f"O comando '{cmd}' existia no arquivo ancestral '{parent_name}' (commit {parent_commit}), "
                            f"mas foi omitido durante o split e não foi herdado por nenhum submódulo filho."
                        ),
                        mitigation_hint=f"Reimplemente ou anexe o comando '{cmd}' em {child_path.name}.",
                        mutation_pct=0.0
                    ))

            # 2. Atalhos que o pai tinha e nenhum filho herdou
            for key, (cmd_target, _) in parent_inv.keymaps.items():
                if key not in merged_children.keymaps:
                    findings.append(RegretFinding(
                        category="SPLIT_CAPABILITY_LEAK",
                        identifier=f"keymap:[{key}]",
                        severity="high",
                        old_line_approx=1,
                        snippet_lost=f"['{key}'] = '{cmd_target}'",
                        impact_description=(
                            f"O atalho de teclado '{key}' existia no pai '{parent_name}', "
                            f"mas foi perdido durante a modularização."
                        ),
                        mitigation_hint=f"Reinserir keymap.add {{ ['{key}'] = '{cmd_target}' }}.",
                        mutation_pct=0.0
                    ))

            # 3. Métodos contratuais críticos perdidos (Envia código COMPLETO, sem truncar)
            for sig, body in parent_inv.methods.items():
                if sig not in merged_children.methods:
                    if any(prefix in sig for prefix in ("DocView:", "Node:", "RootView:", "Doc:")):
                        findings.append(RegretFinding(
                            category="CONTRACT_ORPHANED_ON_SPLIT",
                            identifier=sig,
                            severity="critical",
                            old_line_approx=1,
                            snippet_lost=body.full_code,  # Código integral preservado!
                            impact_description=(
                                f"O hook de ciclo de vida '{sig}' foi definido em '{parent_name}' (commit {parent_commit}), "
                                f"mas foi omitido no split e não existe em nenhum submódulo."
                            ),
                            mitigation_hint=f"Verifique se o hook {sig} deve ser reimplementado em {child_path.name}.",
                            mutation_pct=0.0
                        ))

        return findings
