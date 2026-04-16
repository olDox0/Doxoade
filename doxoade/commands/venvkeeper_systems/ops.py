# doxoade/doxoade/commands/venvkeeper_systems/ops.py
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import click

from .constants import BASE, SUPPORTED_NAMES
from .links import make_link, remove_link
from .manifest import ensure_base, load_manifest, save_manifest
from .utils import is_active_venv, is_link_like, is_venv, manifest_key, now_iso


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _unique_storage_name(src: Path) -> str:
    key = manifest_key(src)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{src.name}_{digest}"


def _record_item(src: Path, dst: Path) -> dict:
    return {
        "source": str(src),
        "stored": str(dst),
        "source_name": src.name,
        "created_at": now_iso(),
        "state": "moved",
    }


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def scan_venvs(root: Path) -> list[Path]:
    """Percorre a árvore e retorna todos os venvs encontrados."""
    root = root.absolute()
    found: list[Path] = []
    seen: set[str] = set()

    for current, dirs, files in os.walk(root):
        current_path = Path(current)

        # Ignora o próprio diretório de armazenamento
        if current_path == BASE or BASE in current_path.parents:
            dirs[:] = []
            continue

        if "pyvenv.cfg" in files and current_path.name in SUPPORTED_NAMES:
            key = str(current_path.absolute())
            if key not in seen:
                found.append(current_path)
                seen.add(key)

        dirs[:] = [
            d for d in dirs
            if d not in {".git", "__pycache__", "node_modules"}
        ]

    return found


# ---------------------------------------------------------------------------
# Move / Return
# ---------------------------------------------------------------------------

def move_venv(src: Path, force: bool = False) -> None:
    src = src.absolute()

    if not src.exists():
        raise RuntimeError(f"Venv não existe: {src}")
    if not is_venv(src):
        raise RuntimeError(f"Não é um venv válido: {src}")
    if is_link_like(src):
        raise RuntimeError(f"Já está relocado por link/junction: {src}")

    if is_active_venv(src):
        click.echo("[WARN] Venv ativo detectado")
        if not force:
            click.echo("Sugestão: execute 'deactivate' ou use --force")
            raise RuntimeError("Abortado por segurança")

    ensure_base()

    data = load_manifest()
    items = data["items"]
    key = manifest_key(src)

    if key in items and not force:
        raise RuntimeError("Já está registrado no manifest")

    dst = BASE / _unique_storage_name(src)
    if dst.exists():
        raise RuntimeError(f"Destino já existe: {dst}")

    shutil.move(str(src), str(dst))

    if not dst.exists() or not (dst / "pyvenv.cfg").exists():
        raise RuntimeError("Falha ao mover venv: destino inválido")

    try:
        make_link(src, dst)
    except Exception:
        shutil.move(str(dst), str(src))   # desfaz o move se o link falhar
        raise

    items[key] = _record_item(src, dst)
    save_manifest(data)

    click.echo(f"[OK] moved -> {dst}")
    click.echo(f"[LINK] {src} -> {dst}")


def return_venv(src: Path, force: bool = False) -> None:
    src = src.absolute()

    data = load_manifest()
    items = data.get("items", {})
    key = manifest_key(src)

    if key not in items:
        raise RuntimeError("Não registrado")

    entry = items[key]
    stored = Path(entry if isinstance(entry, str) else entry["stored"])

    if not stored.exists():
        raise RuntimeError(f"Destino perdido: {stored}")

    if src.exists():
        if is_link_like(src):
            remove_link(src)
        elif not force:
            raise RuntimeError(f"O caminho de origem já existe e não é link: {src}")

    shutil.move(str(stored), str(src))
    del items[key]
    save_manifest(data)

    click.echo(f"[OK] restored -> {src}")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def show_status(root: Path | None = None) -> None:
    data = load_manifest()
    items = data["items"]

    if not items:
        click.echo("[STATUS] Nenhum venv registrado.")
        return

    filtered = (
        {
            k: v for k, v in items.items()
            if Path(v["source"]).absolute().is_relative_to(root.absolute())
        }
        if root is not None else items
    )

    if not filtered:
        click.echo("[STATUS] Nada encontrado para o filtro informado.")
        return

    for src, info in filtered.items():
        click.echo(f"- {src}")
        click.echo(f"  stored: {info['stored']}")
        click.echo(f"  state : {info.get('state', 'unknown')}")
        click.echo(f"  at    : {info.get('created_at', '-')}")


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def batch_move_venvs(root: Path, force: bool = False, dry_run: bool = False) -> None:
    root = root.absolute()
    venvs = scan_venvs(root)

    if not venvs:
        click.echo("[BATCH] Nenhum venv encontrado.")
        return

    if dry_run:
        click.echo(f"[DRY-RUN] {len(venvs)} venv(s) seriam movidos:")
        for venv in venvs:
            click.echo(f"  {venv}")
        return

    for venv in venvs:
        try:
            move_venv(venv, force=force)
        except Exception as e:
            click.secho(f"[FAIL] {venv}: {e}", fg="red")


def batch_return_venvs(root: Path, force: bool = False) -> None:
    root = root.absolute()
    data = load_manifest()
    items = data["items"]

    targets = [
        (key, Path(info["source"]).absolute(), Path(info["stored"]))
        for key, info in items.items()
        if Path(info["source"]).absolute().is_relative_to(root)
    ]

    if not targets:
        click.echo("[BATCH] Nada para restaurar.")
        return

    for key, src, stored in targets:
        try:
            if not stored.exists():
                raise RuntimeError(f"Destino perdido: {stored}")
            if src.exists():
                if is_link_like(src):
                    remove_link(src)
                elif not force:
                    raise RuntimeError(f"Origem já existe e não é link: {src}")
            shutil.move(str(stored), str(src))
            del items[key]
            save_manifest(data)
            click.echo(f"[OK] restored -> {src}")
        except Exception as e:
            click.secho(f"[FAIL] {src}: {e}", fg="red")