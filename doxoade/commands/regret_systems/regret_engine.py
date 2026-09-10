# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_engine.py
"""
⚙️ Motor Orquestrador de Detecção de Regressões — Doxoade Regret Engine.
Fase 1: Suporte a Diretórios (Target Router Polimórfico) e Fail-Safe de I/O.
"""
from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

from doxoade.tools.doxcolors import Fore, Style

try:
    from doxoade.commands.regret_systems.regret_git_reader import RegretGitReader
    from doxoade.commands.regret_systems.regret_backup_reader import RegretBackupReader
    from doxoade.commands.regret_systems.regret_lua_inspector import RegretLuaInspector, RegretFinding
    from doxoade.commands.regret_systems.regret_python_inspector import RegretPythonInspector
    from doxoade.commands.regret_systems.regret_reporter import RegretReporter
except ImportError:
    from .regret_git_reader import RegretGitReader
    from .regret_backup_reader import RegretBackupReader
    from .regret_lua_inspector import RegretLuaInspector, RegretFinding
    from .regret_python_inspector import RegretPythonInspector
    from .regret_reporter import RegretReporter


class RegretEngine:
    """Orquestrador central do ciclo de análise de regressão."""

    @classmethod
    def collect_directory_targets(
        cls,
        dir_path: Path,
        revision: str = "HEAD",
        use_backup: bool = False,
        backup_id: Optional[str] = None
    ) -> List[Path]:
        """
        Coleta recursivamente arquivos (.lua, .py) dentro de um diretório
        que possuam alterações contra a revisão base (Git ou Backup).
        """
        allowed_exts = {".lua", ".py"}
        ignored_dirs = {
            ".git", "venv", ".venv", "__pycache__", "build", "dist",
            ".doxoade", ".doxoade_cache", "node_modules", ".vscode", ".idea", "tests"
        }

        candidates: List[Path] = []
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            for file_name in files:
                p = Path(root) / file_name
                if p.suffix.lower() in allowed_exts:
                    candidates.append(p)

        uncommitted = set(RegretGitReader.get_uncommitted_files())

        # Se houver arquivos modificados detectados pelo Git na pasta alvo, foca neles
        if not use_backup and revision in ("HEAD", "ORIG_HEAD"):
            modified_in_dir = [p for p in candidates if p in uncommitted]
            if modified_in_dir:
                return sorted(modified_in_dir)

        # Caso contrário (backup ou revisão histórica específica), filtra os que têm diff real contra a base
        targets_with_diff: List[Path] = []
        for p in candidates:
            if use_backup:
                old_code, _ = RegretBackupReader.get_file_content_from_backup(p, backup_id=backup_id)
            else:
                old_code = RegretGitReader.get_file_content_at_revision(p, revision=revision)

            if old_code is not None:
                try:
                    new_code = p.read_text(encoding="utf-8", errors="replace")
                    if old_code != new_code:
                        targets_with_diff.append(p)
                except Exception:
                    pass
            elif p in uncommitted:
                targets_with_diff.append(p)

        return sorted(targets_with_diff)

    @classmethod
    def analyze_file(
        cls,
        file_path: Path,
        revision: str = "HEAD",
        use_backup: bool = False,
        backup_id: Optional[str] = None,
        verbose: bool = True
    ) -> List[RegretFinding]:
        # Defesa contra passagem indevida de diretório
        if file_path.exists() and file_path.is_dir():
            return []

        origin_label = revision
        old_code = None

        if use_backup:
            old_code, b_id = RegretBackupReader.get_file_content_from_backup(file_path, backup_id=backup_id)
            origin_label = f"backup:{b_id}"
        else:
            old_code = RegretGitReader.get_file_content_at_revision(file_path, revision=revision)
            # Blindagem: auto-fallback para backup apenas se estiver comparando a working-tree
            # local (HEAD / ORIG_HEAD). Se for um commit histórico explícito (-b <hash>),
            # um arquivo ausente significa apenas que foi criado em commits posteriores.
            if old_code is None and revision in ("HEAD", "ORIG_HEAD", ""):
                old_code, b_id = RegretBackupReader.get_file_content_from_backup(file_path)
                if old_code is not None:
                    origin_label = f"auto-fallback:backup:{b_id}"

        if old_code is None:
            return []

        findings: List[RegretFinding] = []

        # Modo SPLIT / DELETED: o arquivo existia na base mas não existe mais no disco
        if not file_path.exists() or not file_path.is_file():
            target_dir = file_path.parent
            if not target_dir.exists():
                target_dir = Path.cwd()

            sibling_sources: Dict[str, str] = {}
            if file_path.parent.exists():
                for f in file_path.parent.glob(f"*{file_path.suffix}"):
                    if f.is_file() and f.name != file_path.name:
                        try:
                            sibling_sources[f.name] = f.read_text(encoding="utf-8", errors="replace")
                        except Exception:
                            pass

            if file_path.suffix == ".lua":
                findings = RegretLuaInspector.compare(
                    old_code, new_code, file_name=file_path.name, sibling_sources=sibling_sources
                )
            elif file_path.suffix == ".py":
                findings = RegretPythonInspector.compare(old_code, new_code, file_name=file_path.name)

            origin_label += " (SPLIT/DELETED MODE)"
            RegretReporter.render_file_report(file_path, origin_label, findings, verbose=verbose)
            return findings

        try:
            new_code = file_path.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError):
            return []

        if file_path.suffix == ".lua":
            findings = RegretLuaInspector.compare(old_code, new_code, file_name=file_path.name)
        elif file_path.suffix == ".py":
            findings = RegretPythonInspector.compare(old_code, new_code, file_name=file_path.name)

        RegretReporter.render_file_report(file_path, origin_label, findings, verbose=verbose)
        return findings

    @classmethod
    def dump_findings_to_dumppot(cls, all_findings: Dict[str, List[RegretFinding]], project_root: Optional[Path] = None) -> Optional[Path]:
        root = project_root or Path.cwd()
        dox_dir = root / ".doxoade"
        dox_dir.mkdir(parents=True, exist_ok=True)
        dumppot_file = dox_dir / "dumppot.txt"

        lines = [
            "\n" + "=" * 80,
            f"📋 DOXOADE REGRET RECOVERY DUMP — {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80 + "\n"
        ]

        total_dumped = 0
        for fname, findings in all_findings.items():
            for f in findings:
                if f.snippet_lost and f.severity in ("critical", "high", "medium"):
                    total_dumped += 1
                    lines.append(f"# [{f.severity.upper()}] {f.category} in {fname} (Symbol: {f.identifier})")
                    lines.append(f"# Impact: {f.impact_description}")
                    lines.append(f"# Mitigation: {f.mitigation_hint}")
                    lines.append("```lua" if fname.endswith(".lua") else "```python")
                    lines.append(f.snippet_lost)
                    lines.append("```\n")

        if total_dumped > 0:
            with open(dumppot_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return dumppot_file
        return None

    @classmethod
    def run_suite(
        cls,
        target_path: Optional[str] = None,
        base_revision: Optional[str] = None,
        use_backup: bool = False,
        backup_id: Optional[str] = None,
        commits_back: int = 1,
        dump_to_pot: bool = False,
        verbose: bool = True
    ) -> Dict[str, Any]:
        revision = RegretGitReader.resolve_best_base_revision(
            requested_base=base_revision,
            commits_back=commits_back
        )

        targets: List[Path] = []
        if target_path:
            p = Path(target_path)
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()

            if not p.exists():
                print(f"\n{Fore.RED}✖ Alvo não encontrado: {p}{Fore.RESET}\n")
                return {
                    "total_files": 0,
                    "total_regressions": 0,
                    "total_relocations": 0,
                    "total_volatiles": 0,
                    "total_ux": 0,
                    "results": {}
                }

            if p.is_file():
                targets.append(p)
            elif p.is_dir():
                targets = cls.collect_directory_targets(
                    p,
                    revision=revision,
                    use_backup=use_backup,
                    backup_id=backup_id
                )
        else:
            targets = RegretGitReader.get_uncommitted_files()

        if not targets:
            alvo_nome = Path(target_path).name if target_path else "working tree"
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Nenhum arquivo com alterações encontrado em [{alvo_nome}] contra [{revision}].{Style.RESET_ALL}\n")
            return {
                "total_files": 0,
                "total_regressions": 0,
                "total_relocations": 0,
                "total_volatiles": 0,
                "total_ux": 0,
                "results": {}
            }

        total_real_regressions = 0
        total_relocations = 0
        total_volatiles = 0
        total_ux = 0
        results_map: Dict[str, List[RegretFinding]] = {}

        for t in targets:
            findings = cls.analyze_file(
                t,
                revision=revision,
                use_backup=use_backup,
                backup_id=backup_id,
                verbose=verbose
            ) or []

            results_map[t.name] = findings
            total_real_regressions += sum(1 for f in findings if f.severity in ("critical", "high"))
            total_volatiles += sum(1 for f in findings if f.category == "VOLATILE_MUTATION")
            total_ux += sum(1 for f in findings if f.category in ("UX_BUTTON_LOST", "UX_DEFAULT_CHANGED", "MODIFIED_MODERATE"))
            total_relocations += sum(1 for f in findings if f.severity in ("info", "low") and f.category not in ("UX_DEFAULT_CHANGED", "MODIFIED_LIGHT"))

        RegretReporter.render_summary(len(targets), total_real_regressions, total_relocations, total_volatiles, total_ux)

        if dump_to_pot and (total_real_regressions > 0 or total_volatiles > 0):
            pot_path = cls.dump_findings_to_dumppot(results_map)
            if pot_path:
                print(f"  💾 Trechos salvos com sucesso em: {pot_path}\n")

        return {
            "total_files": len(targets),
            "total_regressions": total_real_regressions,
            "total_relocations": total_relocations,
            "total_volatiles": total_volatiles,
            "total_ux": total_ux,
            "results": results_map
        }
