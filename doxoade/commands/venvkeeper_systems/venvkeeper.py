from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click


BASE = Path.home() / ".doxoade" / "venvkeeper"
MANIFEST = BASE / "manifest.json"
SUPPORTED_NAMES = {"venv", ".venv", "env"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def manifest_key(path: Path) -> str:
    return str(path.absolute())

def is_venv(path: Path) -> bool:
    return (path / "pyvenv.cfg").exists()

def is_link_like(path: Path) -> bool:
    try:
        return path.is_symlink() or path.is_junction()
    except AttributeError:
        return path.is_symlink()

def current_runtime_venv() -> Path | None:
    active = os.environ.get("VIRTUAL_ENV")
    if active:
        return Path(active).resolve()

    if sys.prefix != sys.base_prefix:
        return Path(sys.prefix).resolve()

    return None

def is_active_venv(src: Path) -> bool:
    active = current_runtime_venv()
    return active is not None and active == src.resolve()

def ensure_base() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["attrib", "+S", str(BASE)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

def empty_manifest() -> dict:
    return {"version": 2, "items": {}}

def load_manifest():
    if not MANIFEST.exists():
        return {"items": {}}

    raw = json.loads(MANIFEST.read_text())

    # Caso já seja formato novo
    if "items" in raw:
        items = raw["items"]
    else:
        # MIGRAÇÃO v1/v2 -> v3
        items = {}

        for k, v in raw.items():
            if isinstance(v, str):
                items[k] = {"stored": v}
            elif isinstance(v, dict):
                items[k] = v
            else:
                continue

        raw = {"items": items}
        save_manifest(raw)

    return raw

def save_manifest(data: dict) -> None:
    ensure_base()
    MANIFEST.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def make_link(src: Path, dst: Path):
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(src), str(dst)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Falha ao criar junction:\n{result.stderr.strip()}")

        # Protege o junction do Google Drive
        subprocess.run(
            ["attrib", "+S", str(src)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        os.symlink(dst, src, target_is_directory=True)

def protect_from_sync(path: Path) -> None:
    """Marca pasta com atributo sistema para sync clients ignorarem."""
    subprocess.run(
        ["attrib", "+S", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def remove_link(path: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            ["attrib", "-S", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["cmd", "/c", "rmdir", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        path.unlink()

def unique_storage_name(src: Path) -> str:
    key = manifest_key(src)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{src.name}_{digest}"

def record_item(src: Path, dst: Path) -> dict:
    return {
        "source": str(src),
        "stored": str(dst),
        "source_name": src.name,
        "created_at": now_iso(),
        "state": "moved",
    }

def scan_venvs(root: Path) -> list[Path]:
    root = root.absolute()
    found: list[Path] = []
    seen: set[str] = set()

    for current, dirs, files in os.walk(root):
        current_path = Path(current)

        if current_path == BASE or BASE in current_path.parents:
            dirs[:] = []
            continue

        if "pyvenv.cfg" in files and current_path.name in SUPPORTED_NAMES:
            key = str(current_path.absolute())
            if key not in seen:
                found.append(current_path)
                seen.add(key)

        keep_dirs = []
        for d in dirs:
            if d in {".git", "__pycache__", "node_modules"}:
                continue
            keep_dirs.append(d)
        dirs[:] = keep_dirs

    return found

def move_venv(src: Path, force: bool = False) -> None:
    src = src.absolute()

    if not src.exists():
        raise RuntimeError(f"Venv não existe: {src}")

    if not is_venv(src):
        raise RuntimeError(f"Não é um venv válido: {src}")

    if is_link_like(src):
        raise RuntimeError(f"Já está relocado por link/junction: {src}")

    # ✅ warn e abort apenas quando realmente ativo
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

    dst = BASE / unique_storage_name(src)
    if dst.exists():
        raise RuntimeError(f"Destino já existe: {dst}")

    shutil.move(str(src), str(dst))

    if not dst.exists() or not (dst / "pyvenv.cfg").exists():
        raise RuntimeError("Falha ao mover venv: destino inválido")

    try:
        make_link(src, dst)
    except Exception:
        shutil.move(str(dst), str(src))   # ← desfaz o move se o link falhar
        raise

    items[key] = record_item(src, dst)
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

    if isinstance(entry, str):
        stored = Path(entry)
    else:
        stored = Path(entry["stored"])

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

def show_status(root: Path | None = None) -> None:
    data = load_manifest()
    items = data["items"]

    if not items:
        click.echo("[STATUS] Nenhum venv registrado.")
        return

    if root is not None:
        root = root.absolute()
        filtered = {
            k: v
            for k, v in items.items()
            if Path(v["source"]).absolute().is_relative_to(root)
        }
    else:
        filtered = items

    if not filtered:
        click.echo("[STATUS] Nada encontrado para o filtro informado.")
        return

    for src, info in filtered.items():
        click.echo(f"- {src}")
        click.echo(f"  stored: {info['stored']}")
        click.echo(f"  state : {info.get('state', 'unknown')}")
        click.echo(f"  at    : {info.get('created_at', '-')}")

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

    targets: list[tuple[str, Path, Path]] = []
    for key, info in items.items():
        src = Path(info["source"]).absolute()
        if src.is_relative_to(root):
            targets.append((key, src, Path(info["stored"])))

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

@click.command()
@click.option("--move", "-m", "move_path", type=click.Path(path_type=Path), help="Mover um venv")
@click.option("--return", "-r", "return_path", type=click.Path(path_type=Path), help="Restaurar um venv")
@click.option("--scan", type=click.Path(path_type=Path), help="Procurar venvs em uma árvore")
@click.option("--batch-move", type=click.Path(path_type=Path), help="Mover todos os venvs encontrados em uma árvore")
@click.option("--batch-return", type=click.Path(path_type=Path), help="Restaurar todos os venvs registrados sob uma árvore")
@click.option("--status", is_flag=True, help="Mostrar manifest")
@click.option("--force", is_flag=True, help="Forçar operação mesmo com conflito")
@click.option("--dry-run", is_flag=True, help="Simular sem executar")
def venvkeeper(move_path, return_path, scan, batch_move, batch_return, status, force, dry_run):
    if status:
        show_status()
        return

    if scan is not None:
        found = scan_venvs(scan)
        if not found:
            click.echo("[SCAN] Nenhum venv encontrado.")
            return
        for p in found:
            click.echo(str(p))
        return

    if batch_move is not None:
        batch_move_venvs(batch_move, force=force, dry_run=dry_run)
        return

    if batch_return is not None:
        batch_return_venvs(batch_return, force=force)
        return

    if move_path is not None:
        move_venv(move_path, force=force)
        return

    if return_path is not None:
        return_venv(return_path, force=force)
        return

    raise click.UsageError(
        "Use --move, --return, --scan, --batch-move, --batch-return ou --status"
    )