# -*- coding: utf-8 -*-
# doxoade/commands/backup_systems/backup_cmd.py
"""
Comando `doxoade backup` — Cria backups manuais com SAP/Strap.
"""

import asyncio
import difflib
import json
import click
import os
import tarfile
from pathlib import Path
from collections import defaultdict

from .backup_engine import (
    BackupEngineStrap,
    HARDCODED_IGNORE,
    _compile_patterns,
    _is_excluded,
    _load_toml_ignores,
)
from .backup_metadata import BackupMetadata, compute_file_hash
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.source_profile import is_source_path


SUMMARY_TOKEN = "__DOX_BACKUP_DIFF_SUMMARY__"


# ---------------------------------------------------------------------------
# Storage Guard (Ma'at): estado local NÃO é fonte.
# Isso evita que banco, locks, caches e relatórios gerados inflem backups.
# ---------------------------------------------------------------------------

STORAGE_GUARD_IGNORE = [
    # SQLite / bancos locais
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite3",
    "*.sqlite-shm",
    "*.sqlite-wal",
    "*.sqlite-journal",

    # caches / lixo
    "*.bak",
    "*.old",
    "*.tmp",
    "*.temp",
    "*.cache",

    # relatórios / sondas geradas
    "chief_dossier_*.xml",
    "*_dossier_*.xml",
    "probe_*.py",
]

HARDCODED_IGNORE += STORAGE_GUARD_IGNORE


@click.command("backup")
@click.option(
    "--backup-dir",
    type=click.Path(),
    help="Diretório de backups (padrão: .doxoade/backups)",
)
@click.option(
    "--delta", "-d", is_flag=True, help="Cria backup delta (apenas mudanças)"
)
@click.option(
    "--list", "-l", "show_list", is_flag=True, help="Lista todos os backups disponíveis"
)
@click.option(
    "--analyze-compression",
    "analyze_compression",
    is_flag=True,
    help="Analisa a eficiência da compressão do último backup (ou de um específico com -b).",
)
@click.option(
    "--backup", "-b", "backup_id", default=None, help="ID do backup (usado com --diff)."
)
@click.option(
    "--all",
    "include_all",
    is_flag=True,
    help=(
        "Snapshot completo (inclui binários/db/zim). "
        "Padrão = só fonte, ideal para rewind de regressão."
    ),
)
@click.option(
    "--diff",
    "diff_target",
    is_flag=False,
    flag_value=SUMMARY_TOKEN,
    default=None,
    metavar="[ARQUIVO]",
    help="Sem arquivo: resumo desde o último backup; com arquivo: diff completo.",
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    help="Simula o backup sem gravar; mostra escopo, tipos e contagens.",
)
@click.option(
    "--compress",
    "compress_mode",
    type=click.Choice(["auto", "plain", "static", "learned", "hybrid"]),
    default="auto",
    help="Modo de compressão.",
)
@click.option(
    "--compress-level",
    type=click.IntRange(1, 22),
    default=19,
    help="Nível Zstd.",
)
@click.option(
    "--dict-top",
    type=int,
    default=3,
    help="Treina dicionários para as N maiores extensões.",
)
@click.option(
    "--dict-size",
    default="auto",
    help="Tamanho do dicionário: auto, 32768, 64k, 112k.",
)
@click.option(
    "--retrain-dict",
    is_flag=True,
    help="Força retreino de dicionários.",
)
@click.option(
    "--dict-roi-guard/--no-dict-roi-guard",
    "dict_roi_guard",
    default=True,
    help="Só usa dicionário se pagar o overhead.",
)
def backup(
    delta,
    show_list,
    backup_dir,
    include_all,
    diff_target,
    backup_id,
    dry_run,
    analyze_compression,
    compress_mode,
    compress_level,
    dict_top,
    dict_size,
    retrain_dict,
    dict_roi_guard,
):
    """
    Cria backup manual com arquitetura SAP/Strap (assíncrono + pitstop).

    Exemplos:

       doxoade backup

       doxoade backup --delta

       doxoade backup --list

       doxoade backup --diff

       doxoade backup --diff doxoade/cli.py

       doxoade backup --diff -b backup_20260731_180759

       doxoade backup --diff doxoade/cli.py -b backup_20260731_180759
    """
    project_root = Path.cwd()
    backup_path = (
        Path(backup_dir) if backup_dir else project_root / ".doxoade" / "backups"
    )

    engine = BackupEngineStrap(project_root, backup_path)

    if analyze_compression:
        if delta or show_list or diff_target is not None:
            raise click.UsageError(
                "--analyze-compression não pode ser combinado com --delta, --list ou --diff."
            )

        backup_id = (
            _resolve_backup_id(engine, backup_id)
            if backup_id
            else _latest_backup_id(engine)
        )
        _run_analyze_compression(backup_path, backup_id)
        return

    if dry_run:
        if show_list or diff_target is not None or backup_id:
            raise click.UsageError(
                "--dry-run não pode ser combinado com --list, --diff ou -b."
            )

        if delta:
            click.echo(
                f"{Fore.YELLOW}Nota: --dry-run ainda simula escopo cheio, não delta.{Style.RESET_ALL}"
            )

        _run_backup_dry_run(project_root, include_all)
        return

    # Modo diff: prioridade máxima e NÃO cria backup.
    if diff_target is not None:
        if delta or show_list or include_all:
            raise click.UsageError("--diff não pode ser combinado com -d, -l ou --all.")

        backup_id = (
            _resolve_backup_id(engine, backup_id)
            if backup_id
            else _latest_backup_id(engine)
        )

        if diff_target == SUMMARY_TOKEN or diff_target == "":
            _run_backup_summary(project_root, backup_path, backup_id)
        else:
            _run_backup_diff(project_root, backup_path, backup_id, diff_target)
        return

    if backup_id:
        raise click.UsageError("-b/--backup atualmente só é usado com --diff.")

    if show_list:
        backups = engine.list_backups()
        if not backups:
            click.echo(
                f"{Fore.YELLOW}Nenhum backup encontrado em {backup_path}{Style.RESET_ALL}"
            )
            return

        click.echo(f"{Fore.CYAN}═══ Backups Disponíveis ═══{Style.RESET_ALL}")
        for meta in backups:
            backup_type = (
                Fore.GREEN + "FULL"
                if meta.backup_type == "full"
                else Fore.YELLOW + "DELTA"
            )
            click.echo(
                f"{backup_type}{Style.RESET_ALL} | {meta.backup_id} | "
                f"{meta.included_files}/{meta.total_files} arquivos | "
                f"{meta.compressed_size_bytes / 1024 / 1024:.2f} MB | "
                f"ratio: {meta.compression_ratio:.2%}"
            )
        return

    try:
        asyncio.run(
            engine.create_backup(
                delta=delta,
                include_all=include_all,
                compress_mode=compress_mode,
                compress_level=compress_level,
                dict_top=dict_top,
                dict_size=dict_size,
                retrain_dict=retrain_dict,
                roi_guard=dict_roi_guard,
            )
        )
    except KeyboardInterrupt:
        click.echo(
            f"\n{Fore.YELLOW}⚠️  Backup interrompido pelo usuário{Style.RESET_ALL}"
        )
    except Exception as e:
        click.echo(f"{Fore.RED}❌ Erro ao criar backup: {e}{Style.RESET_ALL}")
        raise


# ---------------------------------------------------------------------------
# Backup diff helpers
# ---------------------------------------------------------------------------

def _normalize_rel_path(project_root: Path, file_path: str) -> str:
    """
    Normaliza o caminho para relativo ao projeto e bloqueia path traversal.
    """
    base = project_root.resolve()
    candidate = Path(file_path)

    if not candidate.is_absolute():
        candidate = base / candidate

    candidate = candidate.resolve()

    try:
        return candidate.relative_to(base).as_posix()
    except ValueError:
        raise click.UsageError(
            f"'{file_path}' está fora do projeto atual ({base})."
        )


def _sanitize_backup_id(backup_id: str) -> str:
    """
    Remove sufixos e caminhos, extraindo apenas o ID do backup.

    Exemplos:
    backup_2026.tar.gz -> backup_2026
    .doxoade/backups/backup_2026.tar.gz -> backup_2026
    """
    name = Path(str(backup_id)).name

    for suffix in (".tar.gz", ".tgz", ".tar", ".meta.json"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    return name.strip()


def _ensure_nonempty_archive(archive: Path):
    if not archive.exists() or not archive.is_file():
        raise click.UsageError(f"Backup não encontrado: {archive}")

    if archive.stat().st_size == 0:
        raise click.UsageError(
            f"Backup '{archive.name}' está vazio (0 bytes). "
            f"Provavelmente snapshot descartado. Use 'doxoade backup -l'."
        )


def _latest_backup_id(engine) -> str:
    backups = sorted(engine.list_backups(), key=lambda m: m.backup_id, reverse=True)

    if not backups:
        raise click.UsageError(
            "Nenhum backup válido encontrado. Crie um com: doxoade backup"
        )

    return backups[0].backup_id


def _resolve_backup_id(engine, backup_id: str) -> str:
    """
    Resolve o ID canônico do backup a partir de:
    - ID exato
    - ID parcial
    - nome de arquivo .tar.gz
    - caminho direto para arquivo
    """
    raw = str(backup_id).strip()
    if not raw:
        return _latest_backup_id(engine)

    direct = Path(raw)
    direct_exists = direct.exists() and direct.is_file()

    search_name = direct.name if direct_exists else raw
    clean = _sanitize_backup_id(search_name)

    backups = sorted(engine.list_backups(), key=lambda m: m.backup_id, reverse=True)

    if not backups:
        raise click.UsageError(
            "Nenhum backup válido encontrado. Use: doxoade backup -l"
        )

    exact = [m.backup_id for m in backups if m.backup_id == clean]
    if exact:
        return exact[0]

    partial = [m.backup_id for m in backups if clean and clean in m.backup_id]
    if len(partial) == 1:
        return partial[0]

    if len(partial) > 1:
        names = ", ".join(partial[:8])
        raise click.UsageError(
            f"Mais de um backup corresponde a '{backup_id}': {names}. Use o ID completo."
        )

    # Fallback: permite arquivo de backup sem metadata (útil só para diff simples).
    return raw.strip() if direct_exists else clean


def _resolve_backup_archive(backup_dir: Path, backup_id: str) -> Path:
    """
    Resolve o arquivo de backup.

    Ordem:
    1. .tar.gz  (novo padrão)
    2. .tar     (backups antigos gerados pelo engine v3.0)
    3. arquivo direto informado pelo usuário
    """
    candidates = [
        backup_dir / f"{backup_id}.tar.gz",
        backup_dir / f"{backup_id}.tar",
    ]

    for candidate in candidates:
        if candidate.exists():
            if candidate.stat().st_size <= 0:
                raise click.UsageError(
                    f"Backup {backup_id} existe mas está vazio: {candidate}"
                )
            return candidate

    # Fallback: backup_id pode ser um path direto.
    raw = str(backup_id).strip()
    direct = Path(raw)

    if direct.exists() and direct.is_file():
        _ensure_nonempty_archive(direct)
        return direct.resolve()

    if not backup_dir.exists():
        raise click.UsageError(f"Diretório de backups não encontrado: {backup_dir}")

    clean = _sanitize_backup_id(raw)
    if not clean:
        raise click.UsageError("ID de backup inválido.")

    # ID exato com sufixos
    for suffix in (".tar.gz", ".tgz", ".tar"):
        candidate = backup_dir / f"{clean}{suffix}"
        if candidate.exists() and candidate.is_file():
            _ensure_nonempty_archive(candidate)
            return candidate

    # Partial match
    patterns = (
        f"*{clean}*.tar.gz",
        f"*{clean}*.tgz",
        f"*{clean}*.tar",
    )
    matches = []
    seen = set()

    for pattern in patterns:
        for m in backup_dir.glob(pattern):
            if m.is_file() and m.stat().st_size > 0 and m not in seen:
                seen.add(m)
                matches.append(m)

    matches.sort()

    if not matches:
        phantom = backup_dir / f"{clean}.tar.gz"
        if phantom.exists() and phantom.stat().st_size == 0:
            raise click.UsageError(
                f"Backup '{phantom.name}' existe, mas está vazio (0 bytes). "
                f"Use 'doxoade backup -l' para backups válidos."
            )

        raise click.UsageError(
            f"Backup '{backup_id}' não encontrado em {backup_dir}. "
            f"Use 'doxoade backup -l' para listar."
        )

    if len(matches) > 1:
        names = ", ".join(m.name for m in matches[:8])
        raise click.UsageError(
            f"Mais de um backup corresponde a '{backup_id}': {names}. "
            f"Use o ID completo."
        )

    _ensure_nonempty_archive(matches[0])
    return matches[0]


def _backup_id_from_archive(archive: Path) -> str:
    name = archive.name

    if name.endswith(".tar.gz"):
        return name[:-7]
    if name.endswith(".tgz"):
        return name[:-4]
    if name.endswith(".tar"):
        return name[:-4]

    return archive.stem


def _find_tar_member(tar: tarfile.TarFile, rel_posix: str):
    """
    Localiza um arquivo dentro do tar por caminho relativo.
    Tenta match exato e, como fallback, match por sufixo.
    """
    rel = rel_posix.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]

    exact = []
    suffix = []

    for member in tar.getmembers():
        if not member.isfile():
            continue

        name = member.name.replace("\\", "/")
        while name.startswith("./"):
            name = name[2:]

        if name == rel:
            exact.append(member)
        elif name.endswith("/" + rel):
            suffix.append(member)

    if exact:
        if len(exact) == 1:
            return exact[0]

        names = ", ".join(m.name for m in exact[:8])
        raise click.UsageError(
            f"Mais de um arquivo no backup casa exatamente com '{rel}': {names}"
        )

    if suffix:
        if len(suffix) == 1:
            return suffix[0]

        names = ", ".join(m.name for m in suffix[:8])
        raise click.UsageError(
            f"Mais de um arquivo no backup termina com '{rel}': {names}"
        )

    return None


def _decode_bytes_to_text(data: bytes):
    """
    Retorna (status, texto).
    status: 'ok' | 'binary'
    """
    # Heurística simples de binário.
    if b"\0" in data[:8192]:
        return "binary", None

    # Tenta UTF-8 primeiro.
    try:
        return "ok", data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    # Fallback razoável para texto legado.
    try:
        return "ok", data.decode("latin-1", errors="replace")
    except Exception:
        return "binary", None


def _load_current_text(project_root: Path, rel_posix: str):
    path = project_root / rel_posix

    if path.is_dir():
        raise click.UsageError(f"'{rel_posix}' é um diretório, não um arquivo.")

    if not path.exists():
        return "missing", None

    try:
        data = path.read_bytes()
    except OSError as e:
        raise click.UsageError(f"Falha ao ler '{rel_posix}': {e}")

    status, text = _decode_bytes_to_text(data)
    return status, text


def _load_backup_text(archive: Path, rel_posix: str):
    try:
        mode = "r:gz" if archive.name.endswith(".tar.gz") else "r"
        with tarfile.open(archive, mode) as tar:
            member = _find_tar_member(tar, rel_posix)
            if member is None:
                return "missing", None

            extracted = tar.extractfile(member)
            if extracted is None:
                return "missing", None

            data = extracted.read()
    except tarfile.TarError as e:
        raise click.UsageError(f"Falha ao ler backup '{archive.name}': {e}")

    status, text = _decode_bytes_to_text(data)
    return status, text


def _load_parent_backup_id(backup_path: Path, backup_id: str):
    """
    Lê o parent_backup_id no .meta.json, se existir.
    """
    meta_path = backup_path / f"{backup_id}.meta.json"
    if not meta_path.exists():
        return None

    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return data.get("parent_backup_id")
    except Exception:
        return None


def _load_backup_text_chain(
    backup_path: Path,
    backup_id: str,
    rel_posix: str,
    depth: int = 0,
    visited: set = None,
):
    """
    Carrega o texto de um arquivo a partir de um backup.
    Se o backup for delta e o arquivo não estiver lá, tenta subir a cadeia
    via parent_backup_id.
    """
    if visited is None:
        visited = set()

    if backup_id in visited or depth > 16:
        return "missing", None

    visited.add(backup_id)

    archive = _resolve_backup_archive(backup_path, backup_id)
    resolved_id = _backup_id_from_archive(archive)

    status, text = _load_backup_text(archive, rel_posix)

    if status != "missing":
        return status, text

    parent = _load_parent_backup_id(backup_path, resolved_id)

    if parent:
        return _load_backup_text_chain(
            backup_path,
            parent,
            rel_posix,
            depth=depth + 1,
            visited=visited,
        )

    return "missing", None


def _run_backup_diff(
    project_root: Path,
    backup_path: Path,
    backup_id: str,
    file_path: str,
):
    """
    Compara o arquivo atual com a versão armazenada em um backup.
    """
    rel = _normalize_rel_path(project_root, file_path)

    current_status, current_text = _load_current_text(project_root, rel)
    backup_status, backup_text = _load_backup_text_chain(
        backup_path, backup_id, rel
    )

    if current_status == "binary" or backup_status == "binary":
        click.echo(
            f"{Fore.YELLOW}⚠️  '{rel}' é binário. "
            f"Diff textual não é suportado.{Style.RESET_ALL}"
        )
        return

    if current_status == "missing" and backup_status == "missing":
        raise click.UsageError(
            f"'{rel}' não existe nem no backup '{backup_id}' "
            f"(nem na cadeia de pais) nem no disco atual."
        )

    if backup_status == "missing":
        backup_text = ""

    if current_status == "missing":
        current_text = ""

    diff_lines = list(
        difflib.unified_diff(
            backup_text.splitlines(),
            current_text.splitlines(),
            fromfile=f"backup/{backup_id}/{rel}",
            tofile=f"atual/{rel}",
            lineterm="",
        )
    )

    if not diff_lines:
        click.echo(
            f"{Fore.GREEN}✔ Nenhuma diferença entre o backup "
            f"'{backup_id}' e '{rel}'.{Style.RESET_ALL}"
        )
        return

    output = "\n".join(diff_lines)

    # Reaproveita o apresentador de diff do Doxoade, se disponível.
    try:
        from doxoade.tools.display import _present_diff_output
        _present_diff_output(output)
    except Exception:
        click.echo(output)


# --- Resume helpers ---------------------------------------------------------

def _normalize_manifest_path(path: str) -> str:
    p = str(path).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _load_metadata_object(backup_path: Path, backup_id: str):
    meta_path = backup_path / f"{backup_id}.meta.json"
    if not meta_path.exists():
        return None

    try:
        return BackupMetadata.from_json(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _effective_manifest(
    backup_path: Path,
    backup_id: str,
    depth: int = 0,
    visited: set = None,
):
    """
    Monta o snapshot efetivo subindo a cadeia de backups.
    Retorna: {rel_path: sha256}
    """
    if visited is None:
        visited = set()

    if backup_id in visited or depth > 16:
        return {}

    visited.add(backup_id)

    meta = _load_metadata_object(backup_path, backup_id)
    if meta is None:
        return {}

    manifest = {}

    if meta.parent_backup_id:
        manifest.update(
            _effective_manifest(
                backup_path, meta.parent_backup_id, depth + 1, visited
            )
        )

    for f in meta.files:
        rel = _normalize_manifest_path(f.path)
        if f.included and f.sha256:
            manifest[rel] = f.sha256

    return manifest


def _iter_current_source_files(project_root: Path):
    """
    Itera arquivos fonte atuais respeitando o mesmo ignore do backup.
    """
    base = project_root.resolve()
    patterns = list(HARDCODED_IGNORE) + _load_toml_ignores(project_root)
    compiled = _compile_patterns(patterns)

    for root, dirs, files in os.walk(base, topdown=True):
        rel_root = Path(root).relative_to(base).as_posix()
        if rel_root == ".":
            rel_root = ""

        kept_dirs = []
        for d in dirs:
            rel_dir = f"{rel_root}/{d}" if rel_root else d
            comps = rel_dir.split("/")
            if not _is_excluded(rel_dir, comps, compiled):
                kept_dirs.append(d)
        dirs[:] = kept_dirs

        for name in files:
            rel_file = f"{rel_root}/{name}" if rel_root else name
            comps = rel_file.split("/")

            if _is_excluded(rel_file, comps, compiled):
                continue

            if not is_source_path(rel_file):
                continue

            yield rel_file, Path(root) / name


def _print_summary_section(title: str, items: list, color: str, limit: int = 20):
    if not items:
        return

    click.echo(f"\n{color}{title} ({len(items)}):{Style.RESET_ALL}")
    for item in items[:limit]:
        click.echo(f"  {item}")

    if len(items) > limit:
        click.echo(f"  ... +{len(items) - limit}")


def _run_backup_summary(project_root: Path, backup_path: Path, backup_id: str):
    """
    Resumo seguro: mostra apenas o que mudou, sem exibir código.
    """
    meta = _load_metadata_object(backup_path, backup_id)
    if meta is None:
        raise click.UsageError(
            f"Metadados do backup '{backup_id}' não encontrados. "
            f"Use 'doxoade backup -l' para escolher um backup válido."
        )

    effective = _effective_manifest(backup_path, backup_id)

    if not effective:
        raise click.UsageError(
            f"Não foi possível montar o snapshot efetivo de '{backup_id}'. "
            f"O backup pode estar vazio ou sem cadeia completa."
        )

    base = project_root.resolve()

    modified = []
    deleted = []
    unreadable = []

    # 1) Compara arquivos existentes no snapshot efetivo
    for rel, old_hash in effective.items():
        path = base / rel

        if not path.exists() or not path.is_file():
            deleted.append(rel)
            continue

        current_hash = compute_file_hash(path)

        if current_hash is None:
            unreadable.append(rel)
            continue

        if current_hash != old_hash:
            modified.append(rel)

    # 2) Detecta arquivos novos no projeto atual
    new = []
    for rel, full_path in _iter_current_source_files(project_root):
        if rel in effective:
            continue

        current_hash = compute_file_hash(full_path)
        if current_hash is None:
            unreadable.append(rel)
            continue

        new.append(rel)

    modified = sorted(set(modified))
    deleted = sorted(set(deleted))
    new = sorted(set(new))
    unreadable = sorted(set(unreadable))

    ts = (meta.timestamp or "")[:19]
    btype = (meta.backup_type or "?").upper()

    click.echo(
        f"{Fore.CYAN}═══ Resumo desde {meta.backup_id} ({btype}) {ts} ═══{Style.RESET_ALL}"
    )
    click.echo(f"Snapshot efetivo: {len(effective)} arquivos")
    click.echo(
        f"{Fore.GREEN}Novos: {len(new)}{Style.RESET_ALL} | "
        f"{Fore.YELLOW}Modificados: {len(modified)}{Style.RESET_ALL} | "
        f"{Fore.RED}Removidos: {len(deleted)}{Style.RESET_ALL} | "
        f"{Fore.LIGHTBLACK_EX}Ilegíveis: {len(unreadable)}{Style.RESET_ALL}"
    )

    if not (new or modified or deleted):
        click.echo(
            f"{Fore.GREEN}✔ Nenhuma alteração relevante desde o backup.{Style.RESET_ALL}"
        )
        return

    _print_summary_section("MODIFICADOS", modified, Fore.YELLOW)
    _print_summary_section("NOVOS", new, Fore.GREEN)
    _print_summary_section("REMOVIDOS", deleted, Fore.RED)

    if unreadable:
        _print_summary_section(
            "ILEGÍVEIS (pulados)", unreadable, Fore.LIGHTBLACK_EX, limit=10
        )


# --- Dry-run helpers --------------------------------------------------------

def _validate_pyproject_toml(project_root: Path):
    path = project_root / "pyproject.toml"
    if not path.exists():
        return True, None

    try:
        import tomllib
        with open(path, "rb") as f:
            tomllib.load(f)
        return True, None
    except Exception as e:
        return False, str(e)


def _run_backup_dry_run(project_root: Path, include_all: bool):
    from collections import Counter
    from doxoade.tools.source_profile import ext_of

    click.echo(f"{Fore.CYAN}═══ DRY-RUN BACKUP ═══{Style.RESET_ALL}")

    toml_ok, toml_err = _validate_pyproject_toml(project_root)
    if not toml_ok:
        click.echo(
            f"{Fore.RED}⚠️  pyproject.toml INVÁLIDO: {toml_err}{Style.RESET_ALL}"
        )
        click.echo(
            f"{Fore.YELLOW}   O ignore do TOML NÃO será aplicado até corrigir.{Style.RESET_ALL}"
        )
        toml_ignores = []
    else:
        toml_ignores = _load_toml_ignores(project_root)

    patterns = list(HARDCODED_IGNORE) + toml_ignores
    compiled = _compile_patterns(patterns)

    base = project_root.resolve()

    files_by_ext: "Counter[str]" = Counter()
    size_by_ext: "Counter[str]" = Counter()
    largest: list = []

    total_files = 0
    total_size = 0
    ignored_files = 0
    non_source_files = 0
    unreadable_files = 0
    skipped_dirs = 0

    for root, dirs, files in os.walk(base, topdown=True):
        rel_root = os.path.relpath(root, base).replace(os.sep, "/")
        if rel_root == ".":
            rel_root = ""

        kept_dirs = []
        for d in dirs:
            rel_dir = f"{rel_root}/{d}" if rel_root else d
            comps = rel_dir.split("/")
            if _is_excluded(rel_dir, comps, compiled):
                skipped_dirs += 1
            else:
                kept_dirs.append(d)
        dirs[:] = kept_dirs

        for name in files:
            rel_file = f"{rel_root}/{name}" if rel_root else name
            comps = rel_file.split("/")

            if _is_excluded(rel_file, comps, compiled):
                ignored_files += 1
                continue

            if not include_all and not is_source_path(rel_file):
                non_source_files += 1
                continue

            full_path = Path(root) / name

            try:
                st = full_path.stat()
            except OSError:
                unreadable_files += 1
                continue

            ext = ext_of(name) or "(sem extensão)"
            files_by_ext[ext] += 1
            size_by_ext[ext] += st.st_size
            total_files += 1
            total_size += st.st_size
            largest.append((st.st_size, rel_file))

    click.echo(f"Projeto: {base}")
    click.echo(f"Escopo: {'TUDO (include_all)' if include_all else 'SÓ FONTE'}")
    click.echo(
        f"Ignores ativos: {len(patterns)} ({len(toml_ignores)} do pyproject.toml)"
    )
    click.echo(f"Diretórios podados: {skipped_dirs}")
    click.echo(f"Arquivos ignorados por padrão: {ignored_files}")
    click.echo(f"Arquivos fora do escopo fonte: {non_source_files}")
    click.echo(f"Arquivos ilegíveis: {unreadable_files}")
    click.echo(f"Arquivos candidatos: {total_files}")
    click.echo(f"Tamanho estimado: {total_size / 1024 / 1024:.2f} MB")

    if total_files == 0:
        click.echo(
            f"{Fore.RED}⚠️  Nenhum arquivo entraria no backup.{Style.RESET_ALL}"
        )
        click.echo(
            f"{Fore.YELLOW}   Verifique ignore, source_profile e validade do pyproject.toml.{Style.RESET_ALL}"
        )
        return

    click.echo(f"\n{Fore.CYAN}Tipos de arquivo:{Style.RESET_ALL}")
    click.echo(f"{'EXT':<14} | {'QTD':>6} | {'TAMANHO':>12}")
    click.echo("-" * 42)

    for ext, count in sorted(
        files_by_ext.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        size = size_by_ext[ext]
        click.echo(f"{ext:<14} | {count:>6} | {size / 1024 / 1024:>9.2f} MB")

    largest.sort(reverse=True)
    click.echo(f"\n{Fore.CYAN}Maiores arquivos:{Style.RESET_ALL}")
    for size, rel in largest[:10]:
        click.echo(f"{size / 1024:>9.1f} KB | {rel}")


def _run_analyze_compression(backup_path: Path, backup_id: str):
    """
    Horus do Backup: telemetria avançada da compressão.
    """
    from doxoade.tools.compression import hybrid_codec
    from doxoade.tools.compression.dict_learner import calculate_entropy

    meta = _load_metadata_object(backup_path, backup_id)

    if meta is None:
        raise click.UsageError(
            f"Metadados do backup '{backup_id}' não encontrados. "
            f"Use 'doxoade backup -l' para escolher um backup válido."
        )

    click.echo(
        f"{Fore.CYAN}═══ Análise de Compressão: {meta.backup_id} ({meta.backup_type.upper()}) ═══{Style.RESET_ALL}"
    )
    click.echo(f"Timestamp: {meta.timestamp[:19]}")
    click.echo(f"Arquivos incluídos: {meta.included_files}")
    click.echo(
        f"Tamanho original (bruto): {meta.total_size_bytes / 1024 / 1024:.2f} MB"
    )
    click.echo(
        f"Tamanho comprimido: {meta.compressed_size_bytes / 1024 / 1024:.2f} MB"
    )
    click.echo(f"Ratio global: {meta.compression_ratio:.2%}")
    click.echo()

    # Análise por EXTENSÃO (não só perfil)
    ext_stats = defaultdict(lambda: {
        "count": 0,
        "original_bytes": 0,
        "with_dict": 0,
        "without_dict": 0,
        "entropies": [],
    })

    for f in meta.files:
        if not f.included:
            continue

        ext = Path(f.path).suffix.lower() or "<none>"
        ext_stats[ext]["count"] += 1
        ext_stats[ext]["original_bytes"] += f.size

        codec = (f.codec_meta or {}).get("codec", "unknown")
        if codec == "zstd+dict":
            ext_stats[ext]["with_dict"] += 1
        else:
            ext_stats[ext]["without_dict"] += 1

        # Calcula entropia do arquivo
        try:
            full_path = Path(meta.project_root) / f.path
            if full_path.exists():
                data = full_path.read_bytes()
                entropy = calculate_entropy(data)
                ext_stats[ext]["entropies"].append(entropy)
        except Exception:
            pass

    # Relatório por extensão
    click.echo(
        f"{Fore.CYAN}{'EXTENSÃO':<12} | {'ARQ':>5} | {'ORIGINAL':>10} | {'COM DICT':>9} | {'SEM DICT':>9} | {'ENTROPIA':>9}{Style.RESET_ALL}"
    )
    click.echo("-" * 80)

    sorted_exts = sorted(
        ext_stats.items(),
        key=lambda kv: kv[1]["original_bytes"],
        reverse=True,
    )

    for ext, stats in sorted_exts[:15]:  # Top 15 extensões
        count = stats["count"]
        original_mb = stats["original_bytes"] / 1024 / 1024
        with_dict = stats["with_dict"]
        without_dict = stats["without_dict"]
        
        avg_entropy = (
            sum(stats["entropies"]) / len(stats["entropies"])
            if stats["entropies"]
            else 0.0
        )

        # Cor baseada na entropia
        if avg_entropy > 7.5:
            color = Fore.RED  # Difícil de comprimir
        elif avg_entropy > 6.5:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN

        click.echo(
            f"{color}{ext:<12}{Style.RESET_ALL} | "
            f"{count:>5} | "
            f"{original_mb:>8.2f} MB | "
            f"{with_dict:>9} | "
            f"{without_dict:>9} | "
            f"{avg_entropy:>7.2f} b/B"
        )

    click.echo("-" * 80)
    click.echo()

    # Dicionários usados
    if hasattr(meta, "dictionaries") and meta.dictionaries:
        click.echo(f"{Fore.CYAN}Dicionários usados:{Style.RESET_ALL}")
        for d in meta.dictionaries:
            if d.get("decision") == "use":
                ext = d.get("ext", "?")
                stored_kb = float(d.get("stored_size", 0)) / 1024
                roi = d.get("roi", {})
                net_kb = float(roi.get("estimated_net_savings_bytes", 0)) / 1024
                payback = float(roi.get("payback_ratio", 0))
                avg_entropy = float(roi.get("avg_entropy", 0))

                click.echo(
                    f"  {ext:<8} | dict={stored_kb:>6.1f} KB | "
                    f"net={net_kb:>7.1f} KB | payback={payback:.1f}x | "
                    f"entropia={avg_entropy:.2f} b/B"
                )
        click.echo()

    # Top arquivos que não comprimem bem (entropia alta)
    high_entropy_files = []
    for f in meta.files:
        if not f.included:
            continue
        try:
            full_path = Path(meta.project_root) / f.path
            if full_path.exists():
                data = full_path.read_bytes()
                entropy = calculate_entropy(data)
                if entropy > 7.0:
                    high_entropy_files.append((f.path, entropy, f.size))
        except Exception:
            pass

    if high_entropy_files:
        high_entropy_files.sort(key=lambda x: x[1], reverse=True)
        click.echo(f"{Fore.YELLOW}Top arquivos com alta entropia (difíceis de comprimir):{Style.RESET_ALL}")
        for path, entropy, size in high_entropy_files[:10]:
            click.echo(
                f"  {entropy:.2f} b/B | {size / 1024:>7.1f} KB | {path}"
            )
        click.echo()

    # Top 5 maiores arquivos
    top_files = sorted(meta.files, key=lambda f: f.size, reverse=True)[:5]
    click.echo(f"{Fore.CYAN}Top 5 maiores arquivos incluídos:{Style.RESET_ALL}")
    for f in top_files:
        click.echo(f"  {f.size / 1024:>8.1f} KB  {f.path}")