# doxoade/doxoade/commands/venvkeeper_systems/dump.py
from __future__ import annotations

import os
import shutil
import click
from pathlib import Path

from .constants import BASE, DUMP_DIR_NAMES, DUMP_FILE_SUFFIXES
from .manifest import load_manifest
from .ops import scan_venvs
from .utils import fmt_size, is_venv, manifest_key

from .constants import DUMP_DIR_NAMES, DUMP_FILE_SUFFIXES

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _dir_size(path: Path) -> int:
    """
    Calcula o tamanho total de um diretório recursivamente.
    Compatível com Python 3.8+ (não usa follow_symlinks em is_file).
    """
    total = 0
    try:
        for entry in path.rglob("*"):
            # Evita contar symlinks como arquivos reais (py 3.8-compat)
            if not entry.is_symlink() and entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _resolve_real_path(src: Path) -> list[Path]:
    """
    Retorna a(s) pasta(s) real(is) onde os arquivos do venv estão de fato.

    Lógica de resolução (em ordem):
    1. Se `src` for um venv registrado no manifest → retorna [stored].
    2. Se `src` for um venv válido não registrado → retorna [src].
    3. Se `src` for um diretório qualquer → escaneia venvs dentro dele
       e resolve cada um recursivamente (combina casos 1 e 2).
    4. Nada encontrado → levanta RuntimeError.
    """
    src = src.absolute()
    data  = load_manifest()
    items = data["items"]

    # Caso 1: venv registrado
    key = manifest_key(src)
    if key in items:
        stored = Path(items[key]["stored"])
        if not stored.exists():
            raise RuntimeError(f"Armazenamento não encontrado: {stored}")
        return [stored]

    # Caso 2: venv válido não gerenciado
    if is_venv(src):
        return [src]

    # Caso 3: diretório raiz → scan interno
    if src.is_dir():
        venvs = scan_venvs(src)
        if not venvs:
            raise RuntimeError(f"Nenhum venv encontrado em: {src}")

        resolved: list[Path] = []
        for venv in venvs:
            vkey = manifest_key(venv)
            if vkey in items:
                stored = Path(items[vkey]["stored"])
                if stored.exists():
                    resolved.append(stored)
                else:
                    click.secho(f"[SKIP] {venv}: armazenamento perdido ({stored})", fg="yellow")
            else:
                resolved.append(venv)

        return resolved

    raise RuntimeError(f"Caminho inválido (não é venv nem diretório): {src}")


# ---------------------------------------------------------------------------
# Coleta de alvos
# ---------------------------------------------------------------------------

DumpTargets = tuple[list[tuple[Path, int]], list[tuple[Path, int]]]

def collect_dump_targets(venv_path: Path) -> DumpTargets:
    """
    Percorre o venv e coleta resíduos sem dupla contagem.

    Diretórios listados em DUMP_DIR_NAMES são coletados por inteiro e
    o walk NÃO desce neles (dirs[:] = keep_dirs).

    Retorna:
        dirs_targets  : [(path, size_bytes), ...]
        files_targets : [(path, size_bytes), ...]
    """
    dirs_targets:  list[tuple[Path, int]] = []
    files_targets: list[tuple[Path, int]] = []

    for current, dirs, files in os.walk(venv_path):
        current_path = Path(current)

        residual_dirs = [d for d in dirs if d in DUMP_DIR_NAMES]
        dirs[:] = [d for d in dirs if d not in DUMP_DIR_NAMES]

        for d in residual_dirs:
            dp = current_path / d
            dirs_targets.append((dp, _dir_size(dp)))

        for f in files:
            fp = current_path / f
            if fp.suffix in DUMP_FILE_SUFFIXES:
                try:
                    size = fp.stat().st_size
                except OSError:
                    size = 0
                files_targets.append((fp, size))

    return dirs_targets, files_targets


def _execute_dump(real_path: Path, display_label: str, dry_run: bool) -> int:
    """
    Executa (ou simula) a limpeza de `real_path`.
    Retorna o total de bytes liberados/estimados.
    """
    dirs_targets, files_targets = collect_dump_targets(real_path)

    total_dirs  = len(dirs_targets)
    total_files = len(files_targets)
    total_bytes = sum(s for _, s in dirs_targets) + sum(s for _, s in files_targets)

    if not dirs_targets and not files_targets:
        click.secho(f"[DUMP] {display_label} — nenhum resíduo encontrado.", fg="green")
        return 0

    if dry_run:
        click.secho(f"[DRY-RUN] {display_label}", fg="yellow", bold=True)
        click.echo(f"  {total_dirs} dir(s), {total_files} arquivo(s) — {fmt_size(total_bytes)} a liberar")
        for dp, size in dirs_targets:
            click.echo(f"  [DIR ] {dp}  ({fmt_size(size)})")
        for fp, size in files_targets:
            click.echo(f"  [FILE] {fp}  ({fmt_size(size)})")
    else:
        # --- EXECUÇÃO REAL DA LIMPEZA ---
        click.secho(f"[DUMP] {display_label} — Limpando...", fg="cyan")
        
        # Remove diretórios inteiros (ex: __pycache__)
        for dp, _ in dirs_targets:
            try:
                shutil.rmtree(dp, ignore_errors=True)
            except Exception as e:
                click.secho(f"  [ERRO] Falha ao remover dir {dp.name}: {e}", fg="red")
        
        # Remove arquivos isolados (ex: *.pyc, *.log)
        for fp, _ in files_targets:
            try:
                fp.unlink(missing_ok=True)
            except Exception as e:
                click.secho(f"  [ERRO] Falha ao remover arquivo {fp.name}: {e}", fg="red")

        click.secho(f"  [OK] {fmt_size(total_bytes)} liberados com sucesso!\n", fg="green", bold=True)

    return total_bytes


def dump_venv(src: Path, dry_run: bool = False) -> None:
    """
    Ponto de entrada para --dump.

    `src` pode ser:
    - Um venv registrado no manifest (usa o caminho stored).
    - Um venv válido não registrado (usa src diretamente).
    - Um diretório raiz (escaneia e limpa todos os venvs encontrados).
    """
    src = src.absolute()
    real_paths = _resolve_real_path(src)

    total_freed = 0
    for real_path in real_paths:
        # Label amigável: mostra src (original) se diferente do real
        label = str(src) if real_path == src else f"{src}  (real: {real_path})"
        total_freed += _execute_dump(real_path, label, dry_run)

    if len(real_paths) > 1:
        prefix = "[DRY-RUN] " if dry_run else ""
        click.echo(f"\n{prefix}Total: {fmt_size(total_freed)} em {len(real_paths)} venv(s)")


# ---------------------------------------------------------------------------
# Batch dump (todos os registrados no manifest)
# ---------------------------------------------------------------------------

def batch_dump_venvs(root: Path | None, dry_run: bool = False) -> None:
    """
    Limpa resíduos de todos os venvs registrados no manifest.
    Se `root` for informado, filtra apenas os que estão sob aquela árvore.
    """
    data  = load_manifest()
    items = data["items"]

    if not items:
        click.echo("[BATCH-DUMP] Nenhum venv registrado.")
        return

    if root is not None:
        root = root.absolute()
        targets = {
            k: v for k, v in items.items()
            if Path(v["source"]).absolute().is_relative_to(root)
        }
    else:
        targets = items

    if not targets:
        click.echo("[BATCH-DUMP] Nenhum venv encontrado para o filtro informado.")
        return

    total_freed = 0
    processed   = 0
    failures    = 0

    for key, info in targets.items():
        src    = Path(info["source"])
        stored = Path(info["stored"])

        if not stored.exists():
            click.secho(
                f"[SKIP] {src}: armazenamento não encontrado ({stored})",
                fg="yellow",
            )
            failures += 1
            continue

        freed = _execute_dump(stored, str(src), dry_run)
        total_freed += freed
        processed   += 1

    # Resumo
    prefix = "[DRY-RUN] " if dry_run else ""
    click.echo("")
    click.echo(
        f"{prefix}[BATCH-DUMP] {processed} venv(s) processados"
        f" — {fmt_size(total_freed)} liberados"
    )
    if failures:
        click.secho(f"             {failures} falha(s)", fg="yellow")