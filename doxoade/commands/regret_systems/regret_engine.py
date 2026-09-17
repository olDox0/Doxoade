# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/regret_engine.py
"""
⚙️ Motor Orquestrador de Detecção de Regressões — Doxoade Regret Engine.
Fase 2: Integração de Proveniência, Linhagem Histórica e Detecção de Vazamentos Ancestrais.
Compliance: ProDeNov 1.2.1 | PASC-6.1
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
    from doxoade.commands.regret_systems.regret_lua_inspector import (
        RegretLuaInspector,
        RegretFinding,
        LuaCapabilityInventory,
    )
    from doxoade.commands.regret_systems.regret_python_inspector import RegretPythonInspector
    from doxoade.commands.regret_systems.regret_reporter import RegretReporter
    from doxoade.commands.regret_systems.regret_provenance import (
        FileProvenanceEngine,
        FileOriginMeta,
    )
except ImportError:
    from .regret_git_reader import RegretGitReader
    from .regret_backup_reader import RegretBackupReader
    from .regret_lua_inspector import (
        RegretLuaInspector,
        RegretFinding,
        LuaCapabilityInventory,
    )
    from .regret_python_inspector import RegretPythonInspector
    from .regret_reporter import RegretReporter
    from .regret_provenance import (
        FileProvenanceEngine,
        FileOriginMeta,
    )


class RegretEngine:
    """Orquestrador central do ciclo de análise de regressão, orfandade e proveniência."""

    @classmethod
    def collect_directory_targets(
        cls,
        dir_path: Path,
        revision: str = "HEAD",
        use_backup: bool = False,
        backup_id: Optional[str] = None,
        all_files: bool = False,
    ) -> List[Path]:
        """
        Coleta recursivamente arquivos (.lua, .py) dentro de um diretório.
        Se all_files=True (modo --orphans / --provenance), coleta todos os arquivos válidos no disco.
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

        if all_files:
            return sorted(candidates)

        uncommitted = set(RegretGitReader.get_uncommitted_files())
        if not use_backup and revision in ("HEAD", "ORIG_HEAD"):
            modified_in_dir = [p for p in candidates if p in uncommitted]
            if modified_in_dir:
                return sorted(modified_in_dir)

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
        check_orphans: bool = False,
        check_provenance: bool = False,
        show_snippets: bool = False,
        external_lua_inventories: Optional[List[LuaCapabilityInventory]] = None,
        verbose: bool = True,
    ) -> Tuple[List[RegretFinding], Optional[FileOriginMeta]]:
        """
        Analisa um arquivo individual contra regressões, orfandades e vazamentos ancestrais.
        Retorna (lista_de_achados, metadados_de_origem).
        """
        if file_path.exists() and file_path.is_dir():
            return [], None

        origin_label = revision
        old_code = None

        if use_backup:
            old_code, b_id = RegretBackupReader.get_file_content_from_backup(file_path, backup_id=backup_id)
            origin_label = f"backup:{b_id}"
        else:
            old_code = RegretGitReader.get_file_content_at_revision(file_path, revision=revision)
            if old_code is None and revision in ("HEAD", "ORIG_HEAD", ""):
                old_code, b_id = RegretBackupReader.get_file_content_from_backup(file_path)
                if old_code is not None:
                    origin_label = f"auto-fallback:backup:{b_id}"

        findings: List[RegretFinding] = []
        origin_meta: Optional[FileOriginMeta] = None

        # 🏛️ FASE 2: Análise de Proveniência e Linhagem Ancestral
        if check_provenance and file_path.exists():
            origin_meta = FileProvenanceEngine.resolve_lineage(file_path)

            if origin_meta.is_split_child and origin_meta.ancestor_path and origin_meta.ancestor_path.exists():
                try:
                    parent_code = origin_meta.ancestor_path.read_text(encoding="utf-8", errors="replace")
                    child_code = file_path.read_text(encoding="utf-8", errors="replace")

                    # Coleta conteúdo dos arquivos irmãos da mesma pasta
                    sibling_contents: Dict[str, str] = {}
                    for sib in file_path.parent.glob(f"*{file_path.suffix}"):
                        if sib.is_file() and sib.name != file_path.name and sib.name != origin_meta.ancestor_path.name:
                            try:
                                sibling_contents[sib.name] = sib.read_text(encoding="utf-8", errors="replace")
                            except Exception:
                                pass

                    ancestral_leaks = FileProvenanceEngine.find_ancestral_leaks(
                        child_path=file_path,
                        parent_content=parent_code,
                        child_content=child_code,
                        sibling_contents=sibling_contents,
                        parent_name=origin_meta.parent_file_name or "arquivo pai",
                        parent_commit=origin_meta.created_commit
                    )
                    findings.extend(ancestral_leaks)
                except Exception:
                    pass

        # Caso o arquivo não exista no disco (modo arquivo deletado/split histórico)
        if not file_path.exists() or not file_path.is_file():
            if old_code is None:
                return [], origin_meta
            sibling_sources: Dict[str, str] = {}
            if file_path.parent.exists():
                for f in file_path.parent.glob(f"*{file_path.suffix}"):
                    if f.is_file() and f.name != file_path.name:
                        try:
                            sibling_sources[f.name] = f.read_text(encoding="utf-8", errors="replace")
                        except Exception:
                            pass

            if file_path.suffix == ".lua":
                findings = RegretLuaInspector.compare_against_siblings(
                    old_code, file_path.name, sibling_sources
                )
            elif file_path.suffix == ".py":
                findings = RegretPythonInspector.compare(old_code, "", file_name=file_path.name)

            origin_label += " (SPLIT/DELETED MODE)"
            RegretReporter.render_file_report(
                file_path,
                origin_label,
                findings,
                origin_meta=origin_meta,      # <-- ATIVA A LINHAGEM E O COMMIT!
                verbose=verbose,
                show_snippets=show_snippets   # <-- ATIVA O SNIPPET COMPLETO COM -s!
            )
            return findings, origin_meta

        # Leitura da versão de trabalho atual
        try:
            new_code = file_path.read_text(encoding="utf-8", errors="replace")
        except (PermissionError, OSError):
            return [], origin_meta

        # 1. Análise Diferencial Tradicional
        if old_code is not None:
            if file_path.suffix == ".lua":
                findings.extend(RegretLuaInspector.compare(old_code, new_code, file_name=file_path.name))
            elif file_path.suffix == ".py":
                findings.extend(RegretPythonInspector.compare(old_code, new_code, file_name=file_path.name))
        else:
            origin_label = "working-tree (pure scan)"

        # 2. Auditoria de Funcionalidades Órfãs
        if check_orphans:
            if file_path.suffix == ".lua":
                inv = RegretLuaInspector.extract_inventory(new_code, file_name=file_path.name)
                orphan_findings = RegretLuaInspector.audit_orphans(
                    inventory=inv,
                    source_code=new_code,
                    file_name=file_path.name,
                    external_inventories=external_lua_inventories,
                )
                findings.extend(orphan_findings)
            elif file_path.suffix == ".py":
                py_inv = RegretPythonInspector.extract_inventory(new_code)
                if py_inv:
                    orphan_findings = RegretPythonInspector.audit_orphans(
                        inventory=py_inv,
                        source_code=new_code,
                        file_name=file_path.name,
                    )
                    findings.extend(orphan_findings)

        RegretReporter.render_file_report(file_path, origin_label, findings, verbose=verbose)
        return findings, origin_meta

    @classmethod
    def dump_findings_to_dumppot(
        cls, all_findings: Dict[str, List[RegretFinding]], project_root: Optional[Path] = None
    ) -> Optional[Path]:
        root = project_root or Path.cwd()
        dox_dir = root / ".doxoade"
        dox_dir.mkdir(parents=True, exist_ok=True)
        dumppot_file = dox_dir / "dumppot.txt"
        lines = [
            "\n" + "=" * 80,
            f"📋 DOXOADE REGRET RECOVERY DUMP — {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80 + "\n",
        ]
        total_dumped = 0
        for fname, findings in all_findings.items():
            for f in findings:
                if f.snippet_lost and f.severity in ("critical", "high", "medium"):
                    total_dumped += 1
                    lines.append(f"### [{f.category}] {fname}:{f.old_line_approx} — {f.identifier}")
                    lines.append(f"> {f.impact_description}")
                    lines.append(f"Mitigação: {f.mitigation_hint}")
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
        check_orphans: bool = True,
        check_provenance: bool = False,
        show_snippets: bool = False,
        dump_to_pot: bool = False,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Executa a suíte completa de auditoria com regressões, orfandade e proveniência."""
        revision = RegretGitReader.resolve_best_base_revision(
            requested_base=base_revision,
            commits_back=commits_back,
        )
        targets: List[Path] = []
        deep_scan = check_orphans or check_provenance

        if target_path:
            p = Path(target_path)
            if not p.is_absolute():
                p = (Path.cwd() / p).resolve()
            if not p.exists():
                print(f"\n{Fore.RED}✖ Alvo não encontrado: {p}{Fore.RESET}\n")
                return {
                    "total_files": 0, "total_regressions": 0, "total_relocations": 0,
                    "total_volatiles": 0, "total_ux": 0, "total_orphans": 0,
                    "total_ancestral_leaks": 0, "results": {},
                }

            if p.is_file():
                targets.append(p)
            elif p.is_dir():
                targets = cls.collect_directory_targets(
                    p,
                    revision=revision,
                    use_backup=use_backup,
                    backup_id=backup_id,
                    all_files=deep_scan,
                )
        else:
            targets = RegretGitReader.get_uncommitted_files()
            if not targets and deep_scan:
                targets = cls.collect_directory_targets(Path.cwd(), all_files=True)

        if not targets:
            alvo_nome = Path(target_path).name if target_path else "working tree"
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Nenhum arquivo para análise em [{alvo_nome}] contra [{revision}].{Style.RESET_ALL}\n")
            return {
                "total_files": 0, "total_regressions": 0, "total_relocations": 0,
                "total_volatiles": 0, "total_ux": 0, "total_orphans": 0,
                "total_ancestral_leaks": 0, "results": {},
            }

        # Pré-carrega inventários de templates Lua irmãos para visão sistêmica
        external_inventories: List[LuaCapabilityInventory] = []
        for t in targets:
            if t.suffix == ".lua" and t.exists():
                try:
                    c = t.read_text(encoding="utf-8", errors="replace")
                    external_inventories.append(RegretLuaInspector.extract_inventory(c, file_name=t.name))
                except Exception:
                    pass

        total_real_regressions = 0
        total_relocations = 0
        total_volatiles = 0
        total_ux = 0
        total_orphans = 0
        total_ancestral_leaks = 0
        results: Dict[str, List[RegretFinding]] = {}
        provenance_results: Dict[str, Optional[FileOriginMeta]] = {}

        for target in targets:
            findings, origin_meta = cls.analyze_file(
                file_path=target,
                revision=revision,
                use_backup=use_backup,
                backup_id=backup_id,
                check_orphans=check_orphans,
                check_provenance=check_provenance,
                show_snippets=show_snippets,
                external_lua_inventories=external_inventories,
                verbose=verbose,
            )
            results[target.name] = findings
            provenance_results[target.name] = origin_meta

            for f in findings:
                if f.category in ("SPLIT_CAPABILITY_LEAK", "CONTRACT_ORPHANED_ON_SPLIT"):
                    total_ancestral_leaks += 1
                    if f.severity in ("critical", "high"):
                        total_real_regressions += 1
                elif f.category in ("ORPHAN_COMMAND", "DEAD_KEYMAP", "ORPHAN_LOCAL_FUNCTION", "ORPHAN_PYTHON_FUNCTION"):
                    total_orphans += 1
                    if f.severity in ("critical", "high"):
                        total_real_regressions += 1
                elif f.severity in ("critical", "high"):
                    total_real_regressions += 1
                elif f.severity == "medium" and f.category == "VOLATILE_MUTATION":
                    total_volatiles += 1
                elif f.category in ("UX_BUTTON_LOST", "UX_DEFAULT_CHANGED", "MODIFIED_MODERATE"):
                    total_ux += 1
                elif f.severity in ("info", "low"):
                    total_relocations += 1

        if verbose:
            RegretReporter.render_summary(
                total_files=len(targets),
                total_real_regressions=total_real_regressions,
                total_relocations=total_relocations,
                total_volatiles=total_volatiles,
                total_ux=total_ux,
                total_orphans=total_orphans,
            )

        if dump_to_pot:
            pot_path = cls.dump_findings_to_dumppot(results)
            if pot_path and verbose:
                print(f"  {Fore.CYAN}📋 Trechos recuperados gravados em:{Fore.RESET} {pot_path}\n")

        return {
            "total_files": len(targets),
            "total_regressions": total_real_regressions,
            "total_relocations": total_relocations,
            "total_volatiles": total_volatiles,
            "total_ux": total_ux,
            "total_orphans": total_orphans,
            "total_ancestral_leaks": total_ancestral_leaks,
            "results": results,
            "provenance": provenance_results,
        }
