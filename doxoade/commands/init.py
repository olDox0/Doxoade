# -*- coding: utf-8 -*-
# doxoade/commands/init.py
"""
Nexus Project Genesis v2.2 - Provisionador de Silos Soberanos.
Responsável por forjar a infraestrutura base (Hefesto) e injetar o DNA do Doxoade.
Compliance: OSL-4, PASC-6.1, PASC-8.4.
"""
import os
import sys
import re
import json
import click
import ast
import difflib
import shutil
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

# Caminho raiz da instalação do Doxoade (para buscar os Core Tools)
DOXOADE_ROOT = Path(__file__).resolve().parents[2]

# 🧬 DNA DOXOADE: Módulos essenciais que serão injetados no Silo (pasta utils/)
CORE_TOOLS = {
    'doxcolors.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'doxcolors.py',
    'error_info.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'error_info.py',
    'rescue.py':        DOXOADE_ROOT / 'doxoade' / 'rescue.py',
    'telemetry.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'telemetry_tools' / 'logger.py',
    'db_utils.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'db_utils.py',
    'core_database.py': DOXOADE_ROOT / 'doxoade' / 'core_database.py',
    'nexus_db.py':      DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'nexus_db.py',
    'aegis_core.py':    DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'aegis_core.py',
    'warden.py':        DOXOADE_ROOT / 'doxoade' / 'tools' / 'aegis' / 'warden.py',
    'nexus.py':         DOXOADE_ROOT / 'doxoade' / 'tools' / 'templates' / 'embedded' / 'nexus.py',
    'runtime.py':       DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'runtime.py',
    'meta_finder.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'meta_finder.py',
    'opt_cache.py':     DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'opt_cache.py',
    'lib_optimizer.py': DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'lib_optimizer.py',
    'safe_loader.py':   DOXOADE_ROOT / 'doxoade' / 'tools' / 'vulcan' / 'vulcan_safe_loader.py',
}

DNA_MANIFEST_REL = Path(".doxoade") / "dna_manifest.json"

DOX_BRIDGE_TEMPLATE = '''# utils/doxoade_bridge.py
# Gerado/auditado por Doxoade Init --commands
# Objetivo: expor comandos Doxoade dentro do CLI do Silo.

import importlib
import click


_CANDIDATES = (
    ("doxoade.cli.main", "cli"),
    ("doxoade.cli", "cli"),
    ("doxoade", "cli"),
)


def _load_doxoade_cli():
    errors = []

    for module_name, attr_name in _CANDIDATES:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr_name)
        except Exception as e:
            errors.append(f"{module_name}:{attr_name} -> {type(e).__name__}: {e}")

    @click.group()
    def _fallback():
        click.secho("[DOX BRIDGE] CLI do Doxoade não disponível.", fg="red", bold=True)
        for err in errors:
            click.echo(err)

    return _fallback


def load_command(name: str):
    base_cli = _load_doxoade_cli()

    try:
        ctx = click.Context(base_cli, info_name="doxoade")
        cmd = base_cli.get_command(ctx, name)
    except Exception:
        cmd = None

    if cmd is None:
        @click.command(name=name)
        def _missing():
            click.secho(
                f"[DOX BRIDGE] Comando '{name}' não encontrado no Doxoade.",
                fg="red",
                bold=True
            )
        return _missing

    return cmd
'''


def _inject_metalcraft_existing(root: Path, apply_changes: bool = False) -> None:
    root = Path(root).resolve()
    project_name = root.name
    
    click.echo()
    click.secho("[HEFESTO] Injeção do Metalcraft em projeto existente", fg="cyan", bold=True)
    click.echo(f"Silo: {root}")
    click.echo("=" * 80)
    
    if not apply_changes:
        click.secho("[MA'AT] DRY-RUN é o padrão. Nada será escrito sem --apply.", fg="yellow", bold=True)
    
    toml_path = root / 'metalcraft.toml'
    main_c_path = root / 'src' / 'native' / 'main.c'
    include_dir = root / 'src' / 'native' / 'include'
    bin_dir = root / 'bin'
    
    toml_content = _generate_metalcraft_toml(project_name)
    main_c_content = _generate_main_c(project_name)
    
    files_to_create = [
        (toml_path, toml_content, "metalcraft.toml"),
        (main_c_path, main_c_content, "src/native/main.c"),
    ]
    
    dirs_to_create = [include_dir, bin_dir]
    
    for path, content, desc in files_to_create:
        if path.exists():
            click.secho(f"  [SKIP] {desc} já existe.", fg="yellow")
        else:
            click.secho(f"  [PLANNED] {desc}", fg="green")
            if apply_changes:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                click.secho(f"  [APPLIED] {desc}", fg="green")
    
    for d in dirs_to_create:
        if d.exists():
            click.secho(f"  [SKIP] {d.relative_to(root)}/ já existe.", fg="yellow")
        else:
            click.secho(f"  [PLANNED] {d.relative_to(root)}/", fg="green")
            if apply_changes:
                d.mkdir(parents=True, exist_ok=True)
                click.secho(f"  [APPLIED] {d.relative_to(root)}/", fg="green")
    
    gitignore_path = root / '.gitignore'
    metalcraft_gitignore_rules = """
# ====== C/C++ (Metalcraft & Native) ======
*.o
*.obj
*.exe
*.dll
*.dylib
*.lib
*.out
*.app
bin/
obj/
*.gch
*.pch
*.nm
*.map
"""
    if gitignore_path.exists():
        current_content = gitignore_path.read_text(encoding="utf-8", errors="ignore")
        if "Metalcraft" in current_content or "*.obj" in current_content:
            click.secho("  [SKIP] .gitignore já contém regras do Metalcraft.", fg="yellow")
        else:
            click.secho("  [PLANNED] Adicionar regras do Metalcraft ao .gitignore", fg="green")
            if apply_changes:
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write("\n" + metalcraft_gitignore_rules)
                click.secho("  [APPLIED] .gitignore atualizado.", fg="green")
    else:
        click.secho("  [PLANNED] Criar .gitignore com regras do Metalcraft", fg="green")
        if apply_changes:
            gitignore_path.write_text(metalcraft_gitignore_rules, encoding="utf-8")
            click.secho("  [APPLIED] .gitignore criado.", fg="green")
    
    click.echo("=" * 80)
    if apply_changes:
        click.secho("✅ Metalcraft injetado com sucesso no Silo existente.", fg="green", bold=True)
    else:
        click.secho("Simulação concluída. Rode com --apply para escrever.", fg="yellow", bold=True)


def _resolve_command_spec(spec: str, prefix: str = None):
    if not spec:
        return {}

    entries = [x.strip() for x in spec.split(",") if x.strip()]
    result = {}

    for entry in entries:
        if ":" in entry:
            cmd_name, alias = entry.split(":", 1)
            cmd_name = cmd_name.strip().lower()
            alias = alias.strip().lower()
            result[cmd_name] = {"alias": alias}
        else:
            cmd_name = entry.strip().lower()
            result[cmd_name] = {}

    if "all" in result:
        del result["all"]
        all_names = _list_doxoade_commands()
        for name in all_names:
            if name not in result:
                result[name] = {}

    if prefix:
        for cmd_name in result:
            if "alias" not in result[cmd_name]:
                result[cmd_name]["alias"] = f"{prefix}{cmd_name}"

    return result


def _list_doxoade_commands():
    import importlib

    candidates = [
        ("doxoade.cli", "cli"),
        ("doxoade.cli.main", "cli"),
        ("doxoade.__main__", "cli"),
        ("doxoade", "cli"),
    ]

    for mod_name, attr_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
            base_cli = getattr(mod, attr_name)
            ctx = click.Context(base_cli, info_name="doxoade")
            return sorted(base_cli.list_commands(ctx))
        except Exception:
            continue

    return ["backup", "doctor", "flow", "horus", "intelligence", "search"]


def _load_port_manifest(root: Path):
    manifest_path = root / ".doxoade" / "port_commands.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "commands": {},
        "priority": "local_first",
        "bridge": "utils/doxoade_bridge.py",
        "generated_by": "doxoade init --commands",
        "dry_run_default": True
    }


def _save_port_manifest(root: Path, commands: dict):
    manifest_path = root / ".doxoade" / "port_commands.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "commands": commands,
        "priority": "local_first",
        "bridge": "utils/doxoade_bridge.py",
        "generated_by": "doxoade init --commands",
        "dry_run_default": True
    }

    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _render_json_snippet(old_data, new_data, title):
    click.echo()
    click.secho(f"[SNIPPET] {title}", fg="cyan", bold=True)

    click.secho("  --- ORIGINAL ---", fg="red", bold=True)
    for line in json.dumps(old_data, indent=2, ensure_ascii=False).splitlines():
        click.secho(f"  {line}", fg="red")

    click.secho("  +++ ALTERADO +++", fg="green", bold=True)
    for line in json.dumps(new_data, indent=2, ensure_ascii=False).splitlines():
        click.secho(f"  {line}", fg="green")


def _port_doxoade_commands(root: Path, commands: dict, apply_changes: bool = False, show_snippets: bool = True):
    root = Path(root).resolve()
    if not commands:
        click.secho("[AVISO] Nenhum comando para portar.", fg="yellow")
        return

    manifest_path = root / ".doxoade" / "port_commands.json"
    bridge_path = root / "utils" / "doxoade_bridge.py"
    main_path = root / "cli" / "main.py"

    old_manifest = _load_port_manifest(root)
    old_commands = old_manifest.get("commands", {})

    if isinstance(old_commands, list):
        old_commands = {name: {} for name in old_commands}

    new_commands = dict(old_commands)
    for cmd_name in commands:
        if cmd_name not in new_commands:
            new_commands[cmd_name] = {}

    new_manifest = dict(old_manifest)
    new_manifest["commands"] = new_commands

    click.echo()
    click.secho("[HERMES] Porte de comandos Doxoade para o Silo", fg="cyan", bold=True)
    click.echo(f"Silo: {root}")
    click.echo("=" * 80)

    if not apply_changes:
        click.secho("[MA'AT] DRY-RUN é o padrão. Nada será escrito sem --apply.", fg="yellow", bold=True)

    if show_snippets:
        _render_json_snippet(old_manifest, new_manifest, ".doxoade/port_commands.json")

    if apply_changes:
        _save_port_manifest(root, new_commands)
        click.secho("  [APPLIED] .doxoade/port_commands.json", fg="green")

    if not bridge_path.exists():
        click.echo()
        click.secho("[SNIPPET] utils/doxoade_bridge.py (novo arquivo)", fg="cyan", bold=True)

        if show_snippets:
            for i, line in enumerate(DOX_BRIDGE_TEMPLATE.splitlines()[:40], 1):
                click.secho(f"  {i:4d} | {line}", fg="green")

        if apply_changes:
            bridge_path.parent.mkdir(parents=True, exist_ok=True)
            bridge_path.write_text(DOX_BRIDGE_TEMPLATE, encoding="utf-8")
            click.secho("  [APPLIED] utils/doxoade_bridge.py", fg="green")
    else:
        click.secho("  [OK] utils/doxoade_bridge.py já existe.", fg="green")

    click.echo("=" * 80)
    if apply_changes:
        click.secho("Comandos portados com sucesso.", fg="green", bold=True)
    else:
        click.secho("Simulação concluída. Rode com --apply para escrever.", fg="yellow", bold=True)


def _render_snippet_diff(actual: str, expected: str, max_blocks: int = 50, context: int = 1):
    a = (actual or "").splitlines()
    b = (expected or "").splitlines()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    printed = 0

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue

        if printed >= max_blocks:
            click.secho("  ... blocos restantes omitidos ...", fg="yellow")
            break

        click.echo()
        click.secho(f"  [BLOCO {tag.upper()}]", fg="cyan", bold=True)

        if i1 > 0:
            start = max(0, i1 - context)
            for n in range(start, i1):
                click.secho(f"  {n + 1:4d} | {a[n]}", fg="cyan")

        if i2 > i1:
            click.secho("  --- ORIGINAL ---", fg="red", bold=True)
            for n in range(i1, i2):
                click.secho(f"  {n + 1:4d} | {a[n]}", fg="red")
        else:
            click.secho("  --- ORIGINAL --- (não existia)", fg="yellow")

        if j2 > j1:
            click.secho("  +++ ALTERADO +++", fg="green", bold=True)
            for n in range(j1, j2):
                click.secho(f"  {n + 1:4d} | {b[n]}", fg="green")
        else:
            click.secho("  +++ ALTERADO +++ (removido)", fg="yellow")

        click.echo("  " + "-" * 70)
        printed += 1


def _validate_dna_content(name: str, content: str):
    if name.endswith(".py"):
        ast.parse(content)
    return True


def _atomic_write_text(dest: Path, content: str):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".dox_tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dest)


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _rollback_entries(entries, backup_dir: Path):
    for e in entries:
        try:
            backup_file = backup_dir / e["name"] if backup_dir else None
            if backup_file and backup_file.exists():
                os.replace(backup_file, e["dest"])
                click.secho(f"  [ROLLBACK] {e['dest_rel']} restaurado.", fg="yellow")
            elif e.get("existed_before") is False and e["dest"].exists():
                e["dest"].unlink()
                click.secho(f"  [ROLLBACK] {e['dest_rel']} removido.", fg="yellow")
        except Exception as exc:
            click.secho(f"  [ROLLBACK FAIL] {e['dest_rel']}: {exc}", fg="red")


def _verify_written_entries(entries):
    bad = []
    for e in entries:
        try:
            actual = _read_text_safe(e["dest"])
            if _sha256_text(actual) != e["expected_sha256"]:
                bad.append(e)
        except Exception:
            bad.append(e)
    return bad


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _relative_source(source_path: Path) -> str:
    try:
        return Path(source_path).resolve().relative_to(DOXOADE_ROOT).as_posix()
    except Exception:
        return str(source_path)


def _expected_dna_content(source_path: Path) -> str:
    raw = _read_text_safe(Path(source_path))
    return _refactor_to_silo(raw)


def _collect_dna_statuses(root: Path):
    root = Path(root).resolve()
    utils_dir = root / "utils"
    entries = []

    for dest_name, source_path in CORE_TOOLS.items():
        source_path = Path(source_path)
        dest_path = utils_dir / dest_name

        entry = {
            "name": dest_name,
            "source": source_path,
            "dest": dest_path,
            "source_rel": _relative_source(source_path),
            "dest_rel": f"utils/{dest_name}",
        }

        if not source_path.exists():
            entry["status"] = "SOURCE_MISSING"
            entries.append(entry)
            continue

        expected = _expected_dna_content(source_path)
        entry["expected"] = expected
        entry["expected_sha256"] = _sha256_text(expected)

        if not dest_path.exists():
            entry["status"] = "MISSING"
            entry["actual"] = None
            entries.append(entry)
            continue

        actual = _read_text_safe(dest_path)
        entry["actual"] = actual
        entry["actual_sha256"] = _sha256_text(actual)

        if actual == expected:
            entry["status"] = "OK"
        else:
            entry["status"] = "OUTDATED"

        entries.append(entry)

    return entries


def _print_dna_diff(root: Path, max_lines: int = 120):
    root = Path(root).resolve()
    entries = _collect_dna_statuses(root)

    click.echo()
    click.secho("[ANÚBIS] Auditoria de DNA Doxoade no Silo", fg="cyan", bold=True)
    click.echo(f"Silo: {root}")
    click.echo("=" * 80)

    ok = 0
    missing = 0
    outdated = 0
    source_missing = 0

    for e in entries:
        status = e["status"]

        if status == "OK":
            ok += 1
            click.secho(f"  [OK]       {e['dest_rel']}", fg="green")
            continue

        if status == "MISSING":
            missing += 1
            click.secho(f"  [MISSING]  {e['dest_rel']}", fg="yellow")
            continue

        if status == "SOURCE_MISSING":
            source_missing += 1
            click.secho(f"  [SOURCE]   {e['name']} não existe no Doxoade: {e['source_rel']}", fg="red")
            continue

        outdated += 1
        click.secho(f"  [OUTDATED] {e['dest_rel']}", fg="magenta", bold=True)
        actual_lines = (e.get("actual") or "").splitlines()
        expected_lines = (e.get("expected") or "").splitlines()
        diff = difflib.unified_diff(
            actual_lines, expected_lines,
            fromfile=f"a/{e['dest_rel']}", tofile=f"b/{e['dest_rel']} (Doxoade Nexus)",
            lineterm="",
        )

        printed = 0
        for line in diff:
            if printed >= max_lines:
                click.secho("  ... diff truncado ...", fg="yellow")
                break
            if line.startswith("+"):
                click.secho(f"  {line}", fg="green")
            elif line.startswith("-"):
                click.secho(f"  {line}", fg="red")
            elif line.startswith("@"):
                click.secho(f"  {line}", fg="cyan")
            else:
                click.echo(f"  {line}")
            printed += 1

        click.echo("-" * 80)

    click.echo("=" * 80)
    click.echo(f"Resumo: OK={ok} | OUTDATED={outdated} | MISSING={missing} | SOURCE_MISSING={source_missing}")
    return entries


def _save_dna_manifest(root: Path):
    root = Path(root).resolve()
    manifest_path = root / DNA_MANIFEST_REL

    manifest = {
        "project": root.name,
        "doxoade_root": str(DOXOADE_ROOT),
        "generated_at": datetime.now().isoformat(),
        "files": {},
    }

    for dest_name, source_path in CORE_TOOLS.items():
        source_path = Path(source_path)
        if not source_path.exists():
            continue
        expected = _expected_dna_content(source_path)
        manifest["files"][dest_name] = {
            "source": _relative_source(source_path),
            "dest": f"utils/{dest_name}",
            "sha256": _sha256_text(expected),
        }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def _update_dna(root: Path, apply_changes: bool = False, force: bool = False, backup: bool = True, snippets: bool = True):
    dry_run = not apply_changes
    root = Path(root).resolve()
    utils_dir = root / "utils"

    if not utils_dir.exists():
        click.secho(f"[AVISO] {utils_dir} não existe.", fg="yellow")
        if not click.confirm("Criar utils/ mesmo assim?", default=False):
            return

    entries = _collect_dna_statuses(root)
    planned = []
    unchanged = []
    failures = []

    for e in entries:
        if e["status"] == "SOURCE_MISSING":
            failures.append(e)
            continue
        should_write = force or e["status"] in ("MISSING", "OUTDATED")
        if not should_write:
            unchanged.append(e)
            continue
        if "expected" not in e or not e.get("expected"):
            failures.append(e)
            continue
        try:
            _validate_dna_content(e["name"], e["expected"])
            planned.append(e)
        except Exception as exc:
            click.secho(f"  [VALIDAÇÃO FALHOU] {e['dest_rel']}: {exc}", fg="red")
            failures.append(e)

    if dry_run:
        click.echo()
        click.secho("[ANÚBIS] Simulação de atualização de DNA", fg="cyan", bold=True)
        click.secho("[MA'AT] DRY-RUN é o padrão. Nada será escrito sem --apply.", fg="yellow", bold=True)
        
        for e in planned:
            click.secho(f"  [PLANNED] {e['dest_rel']}", fg="yellow")
            if snippets and e["status"] == "OUTDATED":
                click.secho(f"\n[SNIPPET] {e['dest_rel']}", fg="cyan", bold=True)
                _render_snippet_diff(e.get("actual") or "", e.get("expected") or "")
        
        for e in unchanged:
            click.secho(f"  [OK]      {e['dest_rel']}", fg="green")
        for e in failures:
            click.secho(f"  [FAIL]    {e['dest_rel']} -> {e.get('source_rel', '')}", fg="red")
        return

    if snippets:
        click.echo()
        click.secho("[ANÚBIS] Auditoria final antes da escrita", fg="cyan", bold=True)
        if not click.confirm("Aplicar as mudanças?", default=False):
            click.secho("[MA'AT] Operação cancelada.", fg="yellow")
            return

    backup_dir = None
    if backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = root / ".doxoade" / f"dna_backup_{ts}"

    applied = []
    abort = False

    for e in planned:
        try:
            e["existed_before"] = e["dest"].exists()
            if backup and e["existed_before"]:
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(e["dest"], backup_dir / e["name"])
            _atomic_write_text(e["dest"], e["expected"])
            applied.append(e)
        except Exception as exc:
            click.secho(f"  [FALHA] {e['dest_rel']}: {exc}", fg="red")
            failures.append(e)
            abort = True
            break

    if not abort:
        bad = _verify_written_entries(applied)
        if bad:
            abort = True
            for e in bad:
                click.secho(f"  [HASH FAIL] {e['dest_rel']}", fg="red")
                failures.append(e)

    if abort:
        click.secho("[MA'AT] Update abortado. Iniciando rollback.", fg="red", bold=True)
        _rollback_entries(applied, backup_dir)
        return

    _save_dna_manifest(root)
    click.secho("[HEFESTO] DNA atualizado com sucesso.", fg="green", bold=True)


def generate_silo_header(project_name: str) -> str:
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return (
        f"# {'=' * 70}\n"
        f"# SILO SOBERANO: {project_name.upper()}\n"
        f"# Forjado pelo Nexus Project Genesis v2.2 em {ts}\n"
        f"# DNA Doxoade Injetado e Refatorado para Autonomia Total.\n"
        f"# {'=' * 70}\n"
    )


def _refactor_to_silo(content: str) -> str:
    replacements = {
        'import doxoade.tools.aegis.nexus_db as sqlite3': 'from . import nexus_db as sqlite3',
        'from doxoade.database import': 'from .database import',
        'from doxoade.tools.vulcan.runtime import': 'from .runtime import',
        'from doxoade.tools.vulcan.opt_cache import': 'from .opt_cache import',
        'from doxoade.tools.vulcan.vulcan_safe_loader import': 'from .safe_loader import',
        'from doxoade.tools.vulcan import': 'from . import',
        'from doxoade.tools.telemetry_tools.logger import': 'from .telemetry import',
        'from doxoade.rescue import': 'from .rescue import',
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    content = re.sub(r'from doxoade\.tools\.(\w+)', r'from .\1', content)
    content = re.sub(r'from doxoade\.tools import (\w+)', r'from . import \1', content)
    content = re.sub(r'(?m)^(\s*)import (doxcolors|error_info|telemetry|rescue|database|nexus_db|runtime|meta_finder|opt_cache|safe_loader)(\b)', r'\1from . import \2\3', content)
    
    return content


def _generate_pyproject_toml(project_name: str) -> str:
    return f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "Silo Soberano forjado pelo Doxoade."
requires-python = ">=3.10"

[tool.doxoade]
ignore = ["venv/", ".git/", "__pycache__/", ".doxoade/", "build/", "dist/"]
source_dir = "."
"""


def _generate_intelligence_toml(project_name: str) -> str:
    return f"""# intelligence.toml - Configuração de Blacklist do Motor Nexus
# Projeto: {project_name}
ignore = [
"*./experiments/",
"*/.doxoade/",
"*/__pycache__/",
".doxoade/",
".doxoade_cache/",
".git/",
".pytest_cache/",
"__pycache__/",
"build/",
"build_soteria_test/",
"Canone_Test/",
"commands_test/",
"dist/",
"dox_lab/",
"*.egg-info/",
"nppBackup/",
"pytest_temp_dir/",
"recovery_zone/",
"regression_tests/",
"tests/",
"tmp/",
"venv/",
"Vers/",
"w64devkit/",
"*.specpython",
"*.bat",
"*.sh",
"*.xml",
"*.pyd",
"*.txt",
"*.json",
"*.jsonl",
"*.hh",
"*.dll",
"*.exe",
"*.bkp",
"*.old",
"*.bak",
"*.tmp",
"*.temp",
"*.log",
"*.cache",
"*.nxa",
"*.conf",
"*.ini",
"*.whitelist_backup",
"*.hbc5_backup",
"*.final_backup",
"data/",
"*.db-journal",
"*.sqlite",
"*.sqlite3",
"*.sqlite-shm",
"*.sqlite-wal",
"*.sqlite-journal",
"*.db",
"*.db-shm",
"*.db-wal",
"chief_dossier_*.xml",
"*_dossier_*.xml",
]
"""


def _generate_main_py(project_name: str) -> str:
    return f'''# {project_name}/__main__.py
"""Entry point do {project_name}."""
import sys
import os

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from {project_name}.cli import main as cli_main
    cli_main()

if __name__ == '__main__':
    main()
'''


def _generate_cli_py(project_name: str) -> str:
    class_name = f"{project_name.title()}LazyGroup"
    
    return f'''# {project_name}/cli.py
"""
CLI do {project_name} - Nexus Edition.
Lazy loading, cores dinâmicas e ponte Doxoade.
"""
import sys
import os
import json
import click
import subprocess
from pathlib import Path
from importlib import import_module

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class _NoColor:
        def __getattr__(self, _): return ''
    Fore = _NoColor()
    Style = _NoColor()

class {class_name}(click.Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_path = Path(".doxoade/help_cache.json")
        self._help_cache = self._load_cache()
        
        self._local_commands = {{
            'main': '{project_name}.main:main',
        }}
        
        self._doxoade_commands = {{
            'check': 'doxoade.commands.check:check',
            'flow': 'doxoade.commands.run:flow_command',
            'horus': 'doxoade.commands.horus_cmd:horus_group',
            'save': 'doxoade.commands.save:save',
            'sync': 'doxoade.commands.git_systems.git_workflow:sync',
            'mk': 'doxoade.commands.utils:mk',
            'intelligence': 'doxoade.commands.intelligence_systems.intelligence:intelligence',
            'doctor': 'doxoade.commands.vulcan_systems.vulcan_cmd:doctor',
            'venv': 'doxoade.commands.venv_cmd:venv_cmd',
        }}
        
        self._lazy_map = {{**self._local_commands, **self._doxoade_commands}}
    
    def _load_cache(self):
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text())
            except Exception:
                return {{}}
        return {{}}
    
    def _rebuild_cache(self):
        self._help_cache = {{}}
        for name, path in self._lazy_map.items():
            try:
                mod_path, attr = path.split(':')
                mod = import_module(mod_path)
                cmd = getattr(mod, attr, None)
                if cmd:
                    doc = cmd.__doc__ or ""
                    self._help_cache[name] = doc.strip().split('\\n')[0][:80]
            except Exception:
                self._help_cache[name] = ""
        
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._help_cache, indent=2))
        except Exception:
            pass
    
    def list_commands(self, ctx):
        return sorted(self._lazy_map.keys())
    
    def get_command(self, ctx, name):
        if name not in self._lazy_map:
            return None
        
        if name in self._doxoade_commands:
            return self._create_doxoade_proxy(name)
        
        try:
            module_path, attr_name = self._lazy_map[name].split(':')
            mod = import_module(module_path)
            cmd = getattr(mod, attr_name)
            return cmd
        except Exception as e:
            click.echo(f"{{Fore.RED}}✘ Erro ao carregar comando '{{name}}': {{e}}{{Style.RESET_ALL}}")
            return None
    
    def _create_doxoade_proxy(self, cmd_name):
        @click.command(name=cmd_name, context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
        @click.pass_context
        def proxy(ctx):
            dox_python = self._find_doxoade_venv()
            if not dox_python:
                click.echo(f"{{Fore.RED}}❌ Doxoade não encontrado.{{Style.RESET_ALL}}")
                ctx.exit(1)
            cmd = [dox_python, "-m", "doxoade", cmd_name] + ctx.args
            result = subprocess.run(cmd, cwd=os.getcwd())
            ctx.exit(result.returncode)
        return proxy
    
    def _find_doxoade_venv(self):
        manifest_path = Path.home() / ".doxoade" / "core_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                core_root = Path(manifest.get("core_root", ""))
                if core_root.exists():
                    venv_python = core_root / "venv" / "Scripts" / "python.exe" if os.name == 'nt' else core_root / "venv" / "bin" / "python"
                    if venv_python.exists():
                        return str(venv_python)
            except Exception:
                pass
        return None

@click.group(cls={class_name}, invoke_without_command=True)
@click.option('--version', '-v', is_flag=True, help='Mostra versão')
@click.pass_context
def cli(ctx, version):
    if version:
        click.echo(f"{{Fore.GREEN}}{project_name} v1.0{{Style.RESET_ALL}}")
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

def main():
    try:
        cli(obj={{}})
    except KeyboardInterrupt:
        click.echo(f"\\n{{Fore.YELLOW}}[!] Operação cancelada.{{Style.RESET_ALL}}")
        sys.exit(130)
    except Exception as e:
        click.echo(f"{{Fore.RED}}✘ Erro: {{e}}{{Style.RESET_ALL}}")
        sys.exit(1)

if __name__ == '__main__':
    main()
'''


def _generate_setup_py(project_name: str) -> str:
    return f'''# setup.py - Setup tradicional para {project_name}
from setuptools import setup, find_packages

setup(
    name="{project_name}",
    version="1.0",
    packages=find_packages(),
    entry_points={{
        "console_scripts": [
            "{project_name} = {project_name}.__main__:main",
        ],
    }},
    install_requires=[
        "click>=8.1.0",
    ],
    python_requires=">=3.12",
)
'''


def _generate_metalcraft_toml(project_name: str) -> str:
    return f"""[project]
name = "{project_name}"
version = "1.0.0"
type = "executable"

[compiler]
engine = "gcc"
std = "c11"
opt = "O3"
shield = true
incremental = true

[paths]
sources = ["src/native/*.c"]
headers = ["src/native/include/"]
output  = "bin/"
"""


def _generate_main_c(project_name: str) -> str:
    return f"""// {'=' * 60}
// SILO NATIVE ENTRYPOINT: {project_name.upper()}
// Forjado pelo Nexus Metalcraft.
// {'=' * 60}

#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv) {{
    printf("🔥 [NEXUS METALCRAFT] Silo {project_name} operacional.\\n");
    printf("🛡️  [SOTERIA] Escudo de resgate ativo.\\n");
    return 0;
}}
"""


def _generate_gitignore(project_name: str) -> str:
    return f"""# ==========================================
# .gitignore - Silo Soberano: {project_name.upper()}
# Forjado pelo Nexus Project Genesis v2.2
# ==========================================

__pycache__/
*.py[cod]
*$py.class
*.so
*.pyd
*.egg-info/
dist/
build/
*.egg
.venv/
venv/
ENV/
env/

*.o
*.obj
*.exe
*.dll
*.dylib
*.lib
*.out
*.app
bin/
obj/
*.gch
*.pch

.doxoade/
.doxoade_cache/
.dox_agent_workspace/
.dox_lab/

*.db
*.sqlite
*.sqlite3
!data/acervo/
!data/acervo/bricks/
!data/acervo/bricks/*.py

*.log
*.trace
*.dump
*.bak
*.bkp
*.old
*.tmp
*.temp
chief_dossier*.json
chief_dossier*.xml
doxoade_report.json
.env

.vscode/
.idea/
*.swp
*.swo
.nppBackup/

.DS_Store
Thumbs.db
desktop.ini

pytest_temp_dir/
regression_tests/canon/
htmlcov/
.coverage

!requirements.txt
!PipelineHelp.txt
!*.dox
"""


def _forge_docs(project_path: Path, project_name: str, desc: str) -> list[str]:
    docs_dir = project_path / 'docs'
    docs_dir.mkdir(exist_ok=True)

    identity_content = f"""# 📄 Relatório Universal de Delimitação de Escopo e Decisão
# Projeto: {project_name}

## 1️⃣ Existência do Projeto (POR QUÊ?)
**Objetivo:** {desc}
"""
    (docs_dir / 'identity.md').write_text(identity_content, encoding='utf-8')

    readme = f"""# {project_name}
{desc}

## Instalação
```bash
python install_setup.py
```
"""
    (project_path / 'README.md').write_text(readme, encoding='utf-8')
    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Docs gerados (identity.md, README.md).")
    return [str(docs_dir / 'identity.md'), str(project_path / 'README.md')]


def _generate_pyproject_toml_v2(project_name: str, description: str, dependencies: list[str], aliases: list[str]) -> str:
    required_deps = ['click>=8.1.0', 'colorama>=0.4.6']
    all_deps = required_deps.copy()
    for dep in dependencies:
        dep_name = dep.split('>=')[0].split('==')[0].split('<')[0].strip()
        if not any(dep_name in d for d in all_deps):
            all_deps.append(dep)
    
    deps_str = ",\n".join(f'    "{d}"' for d in all_deps)

    scripts_lines = [f'{project_name} = "{project_name}.__main__:main"']
    for alias in aliases:
        scripts_lines.append(f'{alias} = "{project_name}.__main__:main"')
    scripts_str = "\n".join(scripts_lines)

    return f"""[project]
name = "{project_name}"
version = "1.0"
description = "{description}"
requires-python = ">=3.12"
dependencies = [
{deps_str}
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["{project_name}"]

[tool.setuptools.packages.find]
where = ["."]
include = ["{project_name}*"]
namespaces = false

[project.scripts]
{scripts_str}

[tool.doxoade]
source_dir = "."
shadow_runtime = true
shadow_targets = ["{project_name}"]
soteria_active = true
soteria_mode = "direct"
vulcan_turbo = true
shadow_vacuum_check = ["scan", "find", "resolve", "parse"]

[tool.doxoade.lan_git]
enabled = true
silo_name = "{project_name}"
default_port = 9418
smart_http_port = 8080

ignore = [
    "*./experiments/",
    "*/.doxoade/",
    "*/__pycache__/",
    ".doxoade/",
    ".doxoade_cache/",
    ".git/",
    ".pytest_cache/",
    "__pycache__/",
    "build/",
    "dist/",
    "*.egg-info/",
    "venv/",
    "data/",
    "*.db",
    "*.sqlite",
    "*.log",
    "*.bak",
]

exclude_categories = ["STYLE", "DOCS"]

[tool.pytest.ini_options]
addopts = "-v"
filterwarnings = ["ignore::DeprecationWarning"]
"""


def _forge_admin_venv(project_path: Path, project_name: str) -> list[str]:
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'doxoade', 'venv', '--admin', '--title', project_name],
            cwd=str(project_path),
            capture_output=True, text=True, check=False, timeout=60
        )
        if result.returncode == 0:
            click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Venv admin configurado (--title {project_name})")
        else:
            click.echo(f"   {Fore.YELLOW}⚠{Style.RESET_ALL} venv --admin falhou. Execute manualmente.")
        return []
    except Exception as e:
        click.echo(f"   {Fore.YELLOW}⚠{Style.RESET_ALL} venv --admin erro: {e}")
        return []


def _validate_project_name(name: str) -> None:
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        click.secho("[ERRO] Nome inválido. Use apenas letras, números, '_' e '-'.", fg="red")
        sys.exit(1)


def _resolve_project_path(name: str, force: bool = False) -> Path:
    project_path = Path(os.getcwd()) / name
    if project_path.exists():
        if not force:
            click.secho(f"[ERRO] O diretório '{name}' já existe.", fg="red")
            sys.exit(1)
        click.echo(f"{Fore.YELLOW}⚠ Sobrescrevendo diretório existente...{Style.RESET_ALL}")
    return project_path


def _forge_foundation(project_path: Path, package_dir: Path, metalcraft: bool = False, macrothon: bool = False, house: bool = False) -> list[str]:
    dirs = [
        package_dir,
        project_path / 'utils',
        project_path / 'src',
        project_path / 'docs',
        project_path / 'data',
        project_path / 'tests',
        project_path / '.doxoade' / 'vulcan' / 'bin',
        project_path / '.doxoade' / 'vulcan' / 'foundry',
    ]
    if metalcraft:
        dirs += [project_path / 'src' / 'native' / 'include', project_path / 'bin']
    if macrothon or house:
        dirs.append(project_path / 'src' / 'houses')
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Estrutura criada.")
    return [str(d) for d in dirs]


def _forge_python_package(package_dir: Path, project_name: str, desc: str) -> list[str]:
    (package_dir / '__init__.py').write_text(f'"""{desc}"""\n__version__ = "1.0"\n', encoding='utf-8')
    (package_dir / '__main__.py').write_text(_generate_main_py(project_name), encoding='utf-8')
    (package_dir / 'cli.py').write_text(_generate_cli_py(project_name), encoding='utf-8')
    (package_dir / 'main.py').write_text(f'"""Lógica principal do {project_name}."""\n\ndef main():\n    print("Hello from {project_name}!")\n', encoding='utf-8')
    
    return [str(package_dir / '__init__.py'), str(package_dir / '__main__.py'), str(package_dir / 'cli.py'), str(package_dir / 'main.py')]


def _forge_contracts(project_path: Path, project_name: str, desc: str, dependencies: list[str], aliases: list[str]) -> list[str]:
    pyproject = project_path / 'pyproject.toml'
    pyproject.write_text(_generate_pyproject_toml_v2(project_name, desc, dependencies, aliases), encoding='utf-8')

    intel = project_path / 'intelligence.toml'
    intel.write_text(_generate_intelligence_toml(project_name), encoding='utf-8')

    gitignore = project_path / '.gitignore'
    gitignore.write_text(_generate_gitignore(project_name), encoding='utf-8')

    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Contratos selados (pyproject, intelligence, gitignore).")
    return [str(pyproject), str(intel), str(gitignore)]


def _inject_dna(project_path: Path, project_name: str) -> list[str]:
    utils_path = project_path / 'utils'
    affected = []
    injected = 0
    for target_name, source_path in CORE_TOOLS.items():
        if source_path.exists():
            content = source_path.read_text(encoding='utf-8', errors='ignore')
            dest = utils_path / target_name
            dest.write_text(_refactor_to_silo(content), encoding='utf-8')
            affected.append(str(dest))
            injected += 1
    (utils_path / '__init__.py').write_text(generate_silo_header(project_name), encoding='utf-8')
    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {injected} motores injetados.")
    return affected


def _forge_venv(project_path: Path, install_editable: bool = True, install_global: bool = True) -> list[str]:
    venv_path = project_path / 'venv'
    try:
        subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True, capture_output=True, text=True)
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Venv isolado criado em: {Fore.CYAN}venv/{Style.RESET_ALL}")
        time.sleep(1)

        if install_editable:
            pip_exe = venv_path / 'Scripts' / 'pip.exe' if os.name == 'nt' else venv_path / 'bin' / 'pip'
            if pip_exe.exists():
                result = subprocess.run([str(pip_exe), 'install', '-e', str(project_path)], capture_output=True, text=True, check=False, cwd=str(project_path))
                if result.returncode == 0:
                    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Projeto instalado no venv (pip install -e .)")

        if install_global:
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-e', str(project_path)], capture_output=True, text=True, check=False, cwd=str(project_path))
            if result.returncode == 0:
                click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Projeto instalado globalmente (comando disponível)")

        return [str(venv_path)]
    except Exception as e:
        click.echo(f"   {Fore.RED}✘ Erro ao criar venv: {e}{Style.RESET_ALL}")
        return []


def _forge_macrothon(project_path: Path, pyproject_path: Path, project_name: str) -> list[str]:
    toml_content = pyproject_path.read_text(encoding='utf-8')
    if '[tool.doxoade.macrothon]' not in toml_content:
        toml_content += f"""\n[tool.doxoade.macrothon]\nis_house = true\nhouse_name = "{project_name}"\nauto_sync = true\nrequires = []\n"""
        pyproject_path.write_text(toml_content, encoding='utf-8')

    manifest = {"house_name": project_name, "last_sync": None, "synced_systems": {}}
    manifest_path = project_path / '.doxoade' / 'house_manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=4), encoding='utf-8')
    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} DNA Macrothon injetado.")
    return [str(manifest_path)]


def _forge_metalcraft(project_path: Path, project_name: str) -> list[str]:
    toml_path = project_path / 'metalcraft.toml'
    toml_path.write_text(_generate_metalcraft_toml(project_name), encoding='utf-8')
    main_c = project_path / 'src' / 'native' / 'main.c'
    main_c.parent.mkdir(parents=True, exist_ok=True)
    main_c.write_text(_generate_main_c(project_name), encoding='utf-8')
    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} metalcraft.toml e main.c forjados.")
    return [str(toml_path), str(main_c)]


def _forge_architecture(project_path: Path, architecture: str) -> list[str]:
    from doxoade.commands.mk_systems.mk_engine import MkEngine
    engine = MkEngine(base_path=str(project_path))
    for path, kind in engine.parse_architecture_file(architecture):
        color = Fore.YELLOW if kind == 'Movido' else (Fore.BLUE if kind == 'Mantido' else Fore.GREEN)
        click.echo(f"   {color}[{kind.upper():<10}]{Style.RESET_ALL}: {path}")
    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Topologia '{Path(architecture).name}' erguida.")
    return engine.affected_files


def _consecrate_git(project_path: Path, no_git: bool = False) -> list[str]:
    if no_git:
        return []
    try:
        subprocess.run(['git', 'init', '-b', 'main'], cwd=str(project_path), capture_output=True, check=True)
        # Cria o marcador de segurança para LAN Git automaticamente
        marker = project_path / ".git" / "git-daemon-export-ok"
        marker.touch()
        click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} Repositório Git inicializado com marcador LAN Git.")
        return [str(project_path / '.git')]
    except Exception:
        click.echo(f"   {Fore.YELLOW}⚠{Style.RESET_ALL} Git não encontrado ou falha ao inicializar.")
        return []


def _awaken_up(affected_files: list[str]) -> None:
    from doxoade.commands.mk_systems.mk_utils import open_in_notepadpp
    files_to_open = [f for f in affected_files if os.path.isfile(f)]
    if files_to_open:
        from doxoade.tools.editor_dispatch import EditorDispatcher
        ok, editor_name = EditorDispatcher.open_files(files_to_open)
        badge_color = Fore.GREEN if ok else Fore.YELLOW
        click.echo(f"\n{Fore.CYAN}--- [UP] Abrindo {len(files_to_open)} arquivo(s) via {badge_color}{editor_name}{Fore.CYAN} ---{Style.RESET_ALL}")

# ═══════════════════════════════════════════════════════════════
# CLI ENTRYPOINT DO INIT
# ═══════════════════════════════════════════════════════════════
@click.command('init')
@click.argument('project_name', required=False)
@click.option('--remote', help="URL para publicação automática no GitHub.")
@click.option('--metalcraft', '-mc', is_flag=True, help="Embarca a Forja C (Metalcraft) no Silo.")
@click.option('--macrothon', '-mt', is_flag=True, help="Prepara o Silo para orquestração Macrothon (Houses).")
@click.option('--house', '-h', is_flag=True, help="Transforma o Silo em uma House Macrothon.")
@click.option('--architecture', '-a', type=click.Path(exists=True), help="Blueprint de topologia.")
@click.option('--no-venv', '-nv', is_flag=True, help="Pula a criação do venv.")
@click.option('--no-git', is_flag=True, help="Pula git init.")
@click.option('--up', is_flag=True, help="Abre arquivos no Notepad++.")
@click.option('--desc', '-d', default=None, help="Descrição do projeto")
@click.option('--deps', default=None, help="Dependências extras (ex: 'rich,httpx'). Click é obrigatório.")
@click.option('--alias', '-al', multiple=True, help="Aliases para o comando CLI")
@click.option('--no-global', is_flag=True, help="Não instala o comando globalmente (apenas no venv).")
@click.option('--force', is_flag=True, help="Sobrescrever se existir.")
@click.option('--diff', 'dna_diff', is_flag=True, help="Compara o DNA injetado em utils/ com o Doxoade atual.")
@click.option('--update', 'dna_update', is_flag=True, help="Atualiza o DNA injetado em utils/ para o Doxoade atual.")
@click.option('--dry-run', 'force_dry_run', is_flag=True, hidden=True, help="Força dry-run.")
@click.option('--apply', 'apply_changes', is_flag=True, help="Aplica as mudanças (sai do modo Dry-Run).")
@click.option('--snippets/--no-snippets', 'show_snippets', default=True, help="Mostra trechos ORIGINAL/ALTERADO.")
@click.option('--setup', 'setup_flag', is_flag=True, help="Injeta o instalador soberano 'install_setup.py' no projeto atual.")
@click.option('--lan-git', '-lg', 'lan_git_flag', is_flag=True, help="Injeta o DNA LAN Git e install_setup.py V4 no Silo.")
@click.option('--commands', 'port_commands', is_flag=False, flag_value='all', default=None, help="Porta comandos Doxoade para o Silo.")
@click.option('--prefix', 'cmd_prefix', default=None, help="Prefixo para todos os comandos portados.")
@click.pass_context
def init(ctx, project_name, desc, deps, alias, remote, metalcraft, macrothon, house, 
         architecture, no_venv, no_git, no_global, force, up, dna_diff, dna_update,
         port_commands, show_snippets, apply_changes, force_dry_run, cmd_prefix, setup_flag, lan_git_flag):
    """🚀 Nexus Project Genesis: Forja ou aprimora Silos Soberanos."""

    # 1. Caso Especial: Injeção do LAN Git em Silo existente
    if lan_git_flag and not project_name:
        from doxoade.commands.init_system.init_setup import inject_lan_git_silo
        target_root = Path.cwd().resolve()
        inject_lan_git_silo(target_root, apply_changes=apply_changes)
        return

    # 2. Caso Especial: Injeção do Metalcraft em Silo existente
    if metalcraft and not project_name:
        target_root = Path.cwd().resolve()
        _inject_metalcraft_existing(target_root, apply_changes=apply_changes)
        return

    # 3. Caso Especial: DNA Diff ou DNA Update
    if dna_diff or dna_update:
        target_root = Path(project_name).resolve() if project_name else Path.cwd().resolve()
        if dna_diff:
            _print_dna_diff(target_root)
        if dna_update:
            _update_dna(target_root, apply_changes, force=force, backup=True, snippets=show_snippets)
        return

    # 4. Caso Especial: Porte de Comandos
    if port_commands is not None:
        target_root = Path(project_name).resolve() if project_name else Path.cwd().resolve()
        apply_now = apply_changes and not force_dry_run
        resolved = _resolve_command_spec(port_commands, prefix=cmd_prefix)
        _port_doxoade_commands(target_root, resolved, apply_changes=apply_now, show_snippets=show_snippets)
        return

    # 5. Caso Especial: Injeção do install_setup.py legado
    if setup_flag:
        from doxoade.commands.init_system.init_setup import inject_setup_existing
        inject_setup_existing(Path.cwd(), apply_changes=apply_changes)
        return

    # ═══════════════════════════════════════════════════════════════
    # FLUXO PRINCIPAL: GENESIS DE NOVO SILO
    # ═══════════════════════════════════════════════════════════════
    if not project_name:
        project_name = click.prompt('Nome do novo projeto')

    _validate_project_name(project_name)
    project_path = _resolve_project_path(project_name)
    project_path.mkdir(parents=True, exist_ok=True)

    # Forja o instalador V4 soberano
    from doxoade.commands.init_system.init_setup import inject_setup_existing
    inject_setup_existing(project_path, apply_changes=True)

    if desc is None:
        desc = click.prompt(f"{Fore.CYAN}Descrição{Style.RESET_ALL}", default=f"Silo {project_name}")
    dependencies = ['click>=8.1.0']
    if deps:
        dependencies += [d.strip() for d in deps.split(',') if d.strip() and d.strip() != 'click']
    aliases = list(alias) if alias else []

    affected_files = []

    with ExecutionLogger('init', '.', ctx.params) as _:
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [NEXUS PROJECT GENESIS v3.0] ---{Style.RESET_ALL}")
        click.echo(f"[*] Forjando Silo: {Fore.YELLOW}{project_name}{Style.RESET_ALL}")

        package_dir = project_path / project_name

        affected_files += _forge_foundation(project_path, package_dir, metalcraft, macrothon, house)
        affected_files += _forge_python_package(package_dir, project_name, desc)

        pyproject_path = project_path / 'pyproject.toml'
        affected_files += _forge_contracts(project_path, project_name, desc, dependencies, aliases)

        setup_path = project_path / 'setup.py'
        setup_path.write_text(_generate_setup_py(project_name), encoding='utf-8')
        affected_files.append(str(setup_path))

        affected_files += _inject_dna(project_path, project_name)
        affected_files += _forge_docs(project_path, project_name, desc)

        if not no_venv:
            affected_files += _forge_venv(project_path, install_editable=True, install_global=not no_global)
            _forge_admin_venv(project_path, project_name)
        else:
            click.echo(f"[*] {Fore.DIM}Venv pulado (modo --no-venv).{Style.RESET_ALL}")

        if house or macrothon:
            affected_files += _forge_macrothon(project_path, pyproject_path, project_name)

        if metalcraft:
            affected_files += _forge_metalcraft(project_path, project_name)

        if architecture:
            affected_files += _forge_architecture(project_path, architecture)

        affected_files += _consecrate_git(project_path, no_git)

        if up:
            _awaken_up(affected_files)

        click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ Silo '{project_name}' forjado com sucesso!{Style.RESET_ALL}")
        click.echo(f"   🚀 Entre no Silo: {Fore.YELLOW}cd {project_name}{Style.RESET_ALL}")
