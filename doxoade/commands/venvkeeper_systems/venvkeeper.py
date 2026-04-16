# doxoade/doxoade/commands/venvkeeper_systems/venvkeeper.py

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BASE = Path.home() / ".doxoade" / "venvkeeper"
MANIFEST = BASE / "manifest.json"
SUPPORTED_NAMES = {"venv", ".venv", "env"}

DUMP_DIR_NAMES: set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "htmlcov",
    "tmp",
    "temp",
}

DUMP_FILE_SUFFIXES: set[str] = {".pyc", ".pyo", ".log", ".tmp"}


# ---------------------------------------------------------------------------
# Helpers gerais
# ---------------------------------------------------------------------------

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
        try:
            return Path(active).resolve()
        except Exception:
            return Path(active).absolute()

    if sys.prefix != sys.base_prefix:
        try:
            return Path(sys.prefix).resolve()
        except Exception:
            return Path(sys.prefix).absolute()

    return None


def is_active_venv(src: Path) -> bool:
    active = current_runtime_venv()
    return active is not None and active == src.resolve()


def fmt_size(n_bytes: int) -> str:
    value = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _is_relative_to(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    try:
        return child.is_relative_to(parent)
    except AttributeError:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False


def _remove_existing_path(path: Path) -> None:
    if not path.exists():
        return

    if is_link_like(path):
        remove_link(path)
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def ensure_base() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["attrib", "+S", str(BASE)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def save_manifest(data: dict) -> None:
    ensure_base()
    MANIFEST.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"items": {}}

    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if "items" in raw:
        if isinstance(raw["items"], dict):
            return raw
        return {"items": {}}

    # Migração v1/v2 → v3
    items: dict = {}
    for k, v in raw.items():
        if isinstance(v, str):
            items[k] = {"stored": v}
        elif isinstance(v, dict):
            items[k] = v

    migrated = {"items": items}
    save_manifest(migrated)
    return migrated


# ---------------------------------------------------------------------------
# Links / junctions
# ---------------------------------------------------------------------------

def make_link(src: Path, dst: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(src), str(dst)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Falha ao criar junction:\n{result.stderr.strip()}")
        subprocess.run(
            ["attrib", "+S", str(src)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        os.symlink(dst, src, target_is_directory=True)


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


def protect_from_sync(path: Path) -> None:
    subprocess.run(
        ["attrib", "+S", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Scan de venvs
# ---------------------------------------------------------------------------

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

        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]

    return found


# ---------------------------------------------------------------------------
# Move / Return
# ---------------------------------------------------------------------------

def unique_storage_name(src: Path) -> str:
    digest = hashlib.sha1(manifest_key(src).encode()).hexdigest()[:12]
    return f"{src.name}_{digest}"


def record_item(src: Path, dst: Path) -> dict:
    return {
        "source": str(src),
        "stored": str(dst),
        "source_name": src.name,
        "created_at": now_iso(),
        "state": "moved",
    }


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

    dst = BASE / unique_storage_name(src)
    if dst.exists():
        raise RuntimeError(f"Destino já existe: {dst}")

    shutil.move(str(src), str(dst))
    if not (dst / "pyvenv.cfg").exists():
        raise RuntimeError("Falha ao mover venv: destino inválido")

    try:
        make_link(src, dst)
    except Exception:
        shutil.move(str(dst), str(src))
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
    stored = Path(entry if isinstance(entry, str) else entry["stored"])

    if not stored.exists():
        raise RuntimeError(f"Destino perdido: {stored}")

    if src.exists():
        if is_link_like(src):
            remove_link(src)
        elif force:
            _remove_existing_path(src)
        else:
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

    if root is not None:
        root = root.absolute()
        filtered = {
            k: v for k, v in items.items()
            if _is_relative_to(Path(v["source"]).absolute(), root)
        }
    else:
        filtered = items

    if not filtered:
        msg = "[STATUS] Nenhum venv registrado." if not root else "[STATUS] Nada encontrado para o filtro informado."
        click.echo(msg)
        return

    for src, info in filtered.items():
        click.echo(f"- {src}")
        click.echo(f"  stored: {info['stored']}")
        click.echo(f"  state : {info.get('state', 'unknown')}")
        click.echo(f"  at    : {info.get('created_at', '-')}")


# ---------------------------------------------------------------------------
# Batch move / return
# ---------------------------------------------------------------------------

def batch_move_venvs(root: Path, force: bool = False, dry_run: bool = False) -> None:
    venvs = scan_venvs(root.absolute())
    if not venvs:
        click.echo("[BATCH] Nenhum venv encontrado.")
        return

    if dry_run:
        click.echo(f"[DRY-RUN] {len(venvs)} venv(s) seriam movidos:")
        for v in venvs:
            click.echo(f"  {v}")
        return

    for v in venvs:
        try:
            move_venv(v, force=force)
        except Exception as e:
            click.secho(f"[FAIL] {v}: {e}", fg="red")


def batch_return_venvs(root: Path, force: bool = False) -> None:
    root = root.absolute()
    data = load_manifest()
    items = data["items"]

    targets = [
        (key, Path(info["source"]).absolute(), Path(info["stored"]))
        for key, info in items.items()
        if _is_relative_to(Path(info["source"]).absolute(), root)
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
                elif force:
                    _remove_existing_path(src)
                else:
                    raise RuntimeError(f"Origem já existe e não é link: {src}")

            shutil.move(str(stored), str(src))
            del items[key]
            save_manifest(data)
            click.echo(f"[OK] restored -> {src}")
        except Exception as e:
            click.secho(f"[FAIL] {src}: {e}", fg="red")


# ---------------------------------------------------------------------------
# Dump — limpeza de resíduos
# ---------------------------------------------------------------------------

def _dir_size(path: Path) -> int:
    """Tamanho total de um diretório. Compatível com Python 3.8+."""
    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if not entry.is_symlink() and entry.is_file():
                    total += entry.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def _collect_dump_targets(
    venv_path: Path,
) -> tuple[list[tuple[Path, int]], list[tuple[Path, int]]]:
    """
    Coleta resíduos dentro de venv_path.
    Diretórios resíduos são coletados por inteiro — não percorridos (sem dupla contagem).
    """
    dirs_targets: list[tuple[Path, int]] = []
    files_targets: list[tuple[Path, int]] = []

    for current, dirs, files in os.walk(venv_path):
        current_path = Path(current)

        residual = [d for d in dirs if d in DUMP_DIR_NAMES]
        dirs[:] = [d for d in dirs if d not in DUMP_DIR_NAMES]

        for d in residual:
            dp = current_path / d
            dirs_targets.append((dp, _dir_size(dp)))

        for f in files:
            fp = current_path / f
            if fp.suffix in DUMP_FILE_SUFFIXES:
                try:
                    sz = fp.stat().st_size
                except OSError:
                    sz = 0
                files_targets.append((fp, sz))

    return dirs_targets, files_targets


def _resolve_real_paths(src: Path) -> list[Path]:
    """
    Resolve o(s) caminho(s) físico(s) onde os arquivos do venv estão.

    1. Venv registrado no manifest  → [stored]
    2. Venv válido não registrado   → [src]
    3. Diretório raiz               → scan + resolve cada venv encontrado
    """
    src = src.absolute()
    items = load_manifest()["items"]
    key = manifest_key(src)

    if key in items:
        stored = Path(items[key]["stored"])
        if not stored.exists():
            raise RuntimeError(f"Armazenamento não encontrado: {stored}")
        return [stored]

    if is_venv(src):
        return [src]

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
                    click.secho(f"[SKIP] {venv}: armazenamento perdido", fg="yellow")
            else:
                resolved.append(venv)
        return resolved

    raise RuntimeError(f"Caminho inválido (não é venv nem diretório): {src}")


def _execute_dump(real_path: Path, label: str, dry_run: bool) -> int:
    dirs_targets, files_targets = _collect_dump_targets(real_path)
    total_bytes = sum(s for _, s in dirs_targets) + sum(s for _, s in files_targets)

    if not dirs_targets and not files_targets:
        click.echo(f"[DUMP] {label} — nenhum resíduo encontrado.")
        return 0

    if dry_run:
        click.echo(f"[DRY-RUN] {label}")
        click.echo(
            f"  {len(dirs_targets)} dir(s), {len(files_targets)} arquivo(s)"
            f" — {fmt_size(total_bytes)} a liberar"
        )
        for dp, sz in dirs_targets:
            click.echo(f"  [DIR ] {dp}  ({fmt_size(sz)})")
        for fp, sz in files_targets:
            click.echo(f"  [FILE] {fp}  ({fmt_size(sz)})")
        return total_bytes

    rd = rf = errs = 0
    for dp, _ in dirs_targets:
        try:
            shutil.rmtree(dp)
            rd += 1
        except Exception as e:
            click.secho(f"  [FAIL] {dp}: {e}", fg="red")
            errs += 1

    for fp, _ in files_targets:
        try:
            fp.unlink()
            rf += 1
        except Exception as e:
            click.secho(f"  [FAIL] {fp}: {e}", fg="red")
            errs += 1

    click.echo(f"[DUMP] {label}")
    click.echo(f"  dirs     : {rd}/{len(dirs_targets)}")
    click.echo(f"  arquivos : {rf}/{len(files_targets)}")
    click.echo(f"  liberado : {fmt_size(total_bytes)}")
    if errs:
        click.secho(f"  erros    : {errs}", fg="yellow")
    return total_bytes


def dump_venv(src: Path, dry_run: bool = False) -> None:
    src = src.absolute()
    real_paths = _resolve_real_paths(src)
    total = 0
    for real in real_paths:
        label = str(src) if real == src else f"{src}  (real: {real})"
        total += _execute_dump(real, label, dry_run)
    if len(real_paths) > 1:
        prefix = "[DRY-RUN] " if dry_run else ""
        click.echo(f"\n{prefix}Total: {fmt_size(total)} em {len(real_paths)} venv(s)")


def batch_dump_venvs(root: Path | None, dry_run: bool = False) -> None:
    data = load_manifest()
    items = data["items"]

    if not items:
        click.echo("[BATCH-DUMP] Nenhum venv registrado.")
        return

    targets = (
        {
            k: v for k, v in items.items()
            if _is_relative_to(Path(v["source"]).absolute(), root.absolute())
        }
        if root else items
    )
    if not targets:
        click.echo("[BATCH-DUMP] Nenhum venv encontrado para o filtro informado.")
        return

    total_freed = processed = failures = 0
    for info in targets.values():
        stored = Path(info["stored"])
        if not stored.exists():
            click.secho(f"[SKIP] {info['source']}: armazenamento não encontrado", fg="yellow")
            failures += 1
            continue
        total_freed += _execute_dump(stored, info["source"], dry_run)
        processed += 1

    prefix = "[DRY-RUN] " if dry_run else ""
    click.echo(f"\n{prefix}[BATCH-DUMP] {processed} venv(s) — {fmt_size(total_freed)} liberados")
    if failures:
        click.secho(f"             {failures} falha(s)", fg="yellow")


# ---------------------------------------------------------------------------
# Inteligência AST e Análise de Libs
# ---------------------------------------------------------------------------

def _get_site_packages_path(venv_path: Path) -> Path | None:
    """Encontra a pasta site-packages dependendo do S.O."""
    if os.name == "nt":
        sp = venv_path / "Lib" / "site-packages"
    else:
        lib_dir = venv_path / "lib"
        if not lib_dir.exists():
            return None
        subdirs = [d for d in lib_dir.iterdir() if d.is_dir() and d.name.startswith("python")]
        if not subdirs:
            return None
        sp = subdirs[0] / "site-packages"

    return sp if sp.exists() else None


def _scan_project_imports(project_root: Path) -> set[str]:
    """Usa AST para ler todos os .py do projeto e extrair os módulos importados."""
    imported_modules = set()
    ignore_dirs = {".git", "__pycache__", "node_modules", "tmp", "temp"}

    for root, dirs, files in os.walk(project_root):
        current_path = Path(root)

        if is_venv(current_path) or current_path.name in ignore_dirs:
            dirs[:] = []
            continue

        for f in files:
            if f.endswith(".py"):
                file_path = current_path / f
                try:
                    tree = ast.parse(file_path.read_text(encoding="utf-8"))
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imported_modules.add(alias.name.split(".")[0].lower())
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            imported_modules.add(node.module.split(".")[0].lower())
                except Exception:
                    pass

    return imported_modules


def _analyze_libs(venv_path: Path) -> dict:
    """Calcula o tamanho real em disco de cada biblioteca instalada."""
    sp = _get_site_packages_path(venv_path)
    if not sp:
        click.secho(f"  [WARN] Pasta site-packages não encontrada em {venv_path}", fg="yellow")
        return {}

    lib_sizes: dict[str, int] = {}

    for item in sp.iterdir():
        if item.name in DUMP_DIR_NAMES or item.name.startswith("_"):
            continue

        base_name = item.name.split("-")[0].split(".")[0].lower()
        size = _dir_size(item) if item.is_dir() else (item.stat().st_size if item.is_file() else 0)
        lib_sizes[base_name] = lib_sizes.get(base_name, 0) + size

    sorted_libs = dict(sorted(lib_sizes.items(), key=lambda x: x[1], reverse=True))

    click.secho("\n>> Análise de Bibliotecas (Top 15 maiores)", fg="cyan", bold=True)
    click.secho(f"{'BIBLIOTECA':<30} | {'TAMANHO':<15}", fg="magenta")
    click.echo("-" * 48)

    count = 0
    total_size = 0
    for name, size in sorted_libs.items():
        total_size += size
        if count < 15:
            click.echo(f"{name:<30} | {fmt_size(size):<15}")
        count += 1

    click.echo("-" * 48)
    click.echo(f"Total na site-packages: {fmt_size(total_size)} em {len(sorted_libs)} pacotes primários.\n")
    return sorted_libs


def _optimize_conf(venv_path: Path, dry_run: bool) -> None:
    """
    Corrige o pyvenv.cfg caso o venv tenha sido movido e o caminho base
    do Python (home) tenha quebrado, algo muito comum no Windows.
    """
    cfg_file = venv_path / "pyvenv.cfg"
    if not cfg_file.exists():
        click.secho("  [SKIP] pyvenv.cfg não encontrado.", fg="yellow")
        return

    lines = cfg_file.read_text(encoding="utf-8").splitlines()
    modified = False
    new_lines = []

    for line in lines:
        if line.startswith("home = "):
            current_home = line.split("=", 1)[1].strip()
            if not Path(current_home).exists():
                new_home = sys.base_prefix
                if dry_run:
                    click.secho(
                        f"  [DRY-RUN] pyvenv.cfg quebrado! 'home' mudaria de {current_home} -> {new_home}",
                        fg="yellow",
                    )
                else:
                    line = f"home = {new_home}"
                    modified = True
                    click.secho(f"  [FIX] pyvenv.cfg corrigido: apontando para {new_home}", fg="green")
        new_lines.append(line)

    if modified and not dry_run:
        cfg_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    elif not modified and not dry_run:
        click.echo("  [OK] pyvenv.cfg está saudável.")


def _optimize_update(venv_path: Path, py_exe: Path, dry_run: bool) -> None:
    """Atualiza pacotes desatualizados de forma conservadora."""
    click.echo("  [1/2] Verificando pacotes desatualizados...")
    try:
        result = subprocess.run(
            [str(py_exe), "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            click.secho(f"  [WARN] pip list --outdated falhou:\n{result.stderr.strip()}", fg="yellow")
            return

        outdated_raw = json.loads(result.stdout or "[]")
        outdated = [pkg["name"] for pkg in outdated_raw if "name" in pkg]
    except Exception as e:
        click.secho(f"  [ERRO] Falha ao consultar pacotes desatualizados: {e}", fg="red")
        return

    if not outdated:
        click.secho("  [OK] Nenhum pacote desatualizado detectado.", fg="green")
        return

    safe_core = {"pip", "setuptools", "wheel"}
    candidates = [pkg for pkg in outdated if pkg.lower() not in safe_core]

    click.secho(f"  [INFO] {len(outdated)} pacote(s) desatualizado(s) detectado(s).", fg="cyan")
    if candidates:
        click.echo("    candidatos: " + ", ".join(candidates))
    else:
        click.echo("    apenas pacotes de base (pip/setuptools/wheel).")

    if dry_run:
        click.secho("  [DRY-RUN] Nenhum pacote foi atualizado.", fg="yellow")
        return

    if not click.confirm("  [?] Deseja atualizar os pacotes listados?", default=False):
        click.secho("  [SKIP] Atualização cancelada pelo usuário.", fg="magenta")
        return

    if candidates:
        cmd = [str(py_exe), "-m", "pip", "install", "-U"] + candidates
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            click.secho("  [OK] Pacotes atualizados.", fg="green")
        else:
            click.secho(f"  [WARN] Falha ao atualizar alguns pacotes:\n{result.stderr.strip()}", fg="yellow")
    else:
        click.secho("  [OK] Nenhum pacote adicional para atualizar.", fg="green")

    core_cmd = [str(py_exe), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"]
    result = subprocess.run(core_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        click.secho("  [OK] Ferramentas base atualizadas.", fg="green")
    else:
        click.secho(f"  [WARN] Falha ao atualizar ferramentas base:\n{result.stderr.strip()}", fg="yellow")


def _optimize_clean_lib(venv_path: Path, py_exe: Path, dry_run: bool) -> None:
    """Motor Nível 3: PIP check + Purga de Cache + AST Ghost Hunter com Resolução de Dependências."""
    click.echo("  [1/3] Verificando integridade das bibliotecas (pip check)...")
    try:
        result = subprocess.run([str(py_exe), "-m", "pip", "check"], capture_output=True, text=True)
        if result.returncode == 0:
            click.echo("  [OK] Nenhuma quebra de dependência detectada.")
        else:
            click.secho(f"  [WARN] Conflitos encontrados:\n{result.stdout.strip()}", fg="yellow")
    except Exception as e:
        click.secho(f"  [ERRO] Falha ao rodar pip check: {e}", fg="red")

    click.echo("  [2/3] Purgando cache residual do pip...")
    if not dry_run:
        subprocess.run(
            [str(py_exe), "-m", "pip", "cache", "purge"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    click.echo("  [OK] Cache de instalação avaliado/limpo.")

    click.echo("  [3/3] Caçador de Fantasmas (Cruzamento AST vs Árvore de Dependências)...")
    project_root = venv_path.parent

    imported_modules = _scan_project_imports(project_root)

    _PROBE_SCRIPT = r"""
import json
from importlib import metadata

results = {"package_deps": {}, "module_map": {}}

try:
    for dist in metadata.distributions():
        pkg_name = dist.metadata['name'].lower().replace('_', '-')
        results["package_deps"][pkg_name] = [
            req.split(';')[0].split(' ')[0].split('=')[0].split('>')[0].split('<')[0].lower().replace('_', '-')
            for req in (dist.requires or []) if 'extra ==' not in req
        ]
        provided = set()
        try:
            top_level = dist.read_text('top_level.txt')
            if top_level:
                provided.update(t.lower().replace('-', '_') for t in top_level.strip().split())
        except Exception:
            pass
        provided.add(pkg_name.replace('-', '_'))
        results["module_map"][pkg_name] = list(provided)
except Exception:
    pass

print(json.dumps(results))
"""

    try:
        result = subprocess.run([str(py_exe), "-c", _PROBE_SCRIPT], capture_output=True, text=True, check=True)
        probe_results = json.loads(result.stdout)

        module_to_pkg: dict[str, str] = {}
        for pkg, mods in probe_results.get("module_map", {}).items():
            for mod in mods:
                module_to_pkg[mod] = pkg

        root_used_pkgs = {module_to_pkg[mod] for mod in imported_modules if mod in module_to_pkg}

        fully_used = set(root_used_pkgs)
        to_process = list(root_used_pkgs)
        deps_map = probe_results.get("package_deps", {})

        while to_process:
            current = to_process.pop()
            for dep in deps_map.get(current, []):
                if dep and dep not in fully_used:
                    fully_used.add(dep)
                    to_process.append(dep)

        all_installed = set(deps_map.keys())
        safelist = {"pip", "setuptools", "wheel", "pytest", "coverage", "black", "bandit", "click", "rich"}

        ghosts = sorted(list(all_installed - fully_used - safelist))

        if not ghosts:
            click.secho("  [OK] Nenhum pacote ocioso/fantasma detectado.", fg="green")
        else:
            click.secho(f"  [ALERTA] {len(ghosts)} pacote(s) órfão(s) detectado(s):", fg="yellow")
            click.echo("    " + ", ".join(ghosts))

            if dry_run:
                click.secho("  [DRY-RUN] Os pacotes acima seriam desinstalados.", fg="yellow")
            else:
                if click.confirm(
                    f"\n  [?] Deseja remover permanentemente estes {len(ghosts)} pacotes para liberar espaço?",
                    default=False,
                ):
                    click.echo("  Iniciando desinstalação segura...")
                    subprocess.run(
                        [str(py_exe), "-m", "pip", "uninstall", "-y"] + ghosts,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    click.secho("  [OK] Fantasmas eliminados com sucesso!", fg="green")
                else:
                    click.secho("  [SKIP] Remoção cancelada pelo usuário.", fg="magenta")

    except Exception as e:
        click.secho(f"  [ERRO] Falha no Caçador de Fantasmas: {e}", fg="red")


def _optimize_alloc(venv_path: Path, dry_run: bool) -> None:
    """Injeta flags de alta performance de alocação e CPU nos scripts do venv."""
    scripts_dir = venv_path / "Scripts" if os.name == "nt" else venv_path / "bin"

    if not scripts_dir.exists():
        click.secho("  [ERRO] Pasta Scripts/bin não encontrada no Venv.", fg="red")
        return

    num_cores = os.cpu_count() or 4
    alloc_vars_bat = [
        "\n:: [DOXOADE ALLOC OPTIMIZATIONS]",
        "set PYTHONOPTIMIZE=1",
        "set PYTHONTRACEMALLOC=0",
        f"set OMP_NUM_THREADS={num_cores}",
        f"set MKL_NUM_THREADS={num_cores}\n",
    ]

    alloc_vars_ps1 = [
        "\n# [DOXOADE ALLOC OPTIMIZATIONS]",
        "$env:PYTHONOPTIMIZE=1",
        "$env:PYTHONTRACEMALLOC=0",
        f"$env:OMP_NUM_THREADS={num_cores}",
        f"$env:MKL_NUM_THREADS={num_cores}\n",
    ]

    patched = False

    bat_file = scripts_dir / "activate.bat"
    if bat_file.exists():
        content = bat_file.read_text(encoding="utf-8")
        if "DOXOADE ALLOC OPTIMIZATIONS" not in content:
            if dry_run:
                click.secho(f"  [DRY-RUN] Injetaria otimizações de Alocação no {bat_file.name}", fg="yellow")
            else:
                bat_file.write_text(content + "\n".join(alloc_vars_bat), encoding="utf-8")
                patched = True

    ps1_file = scripts_dir / "Activate.ps1"
    if ps1_file.exists():
        content = ps1_file.read_text(encoding="utf-8")
        if "DOXOADE ALLOC OPTIMIZATIONS" not in content:
            if dry_run:
                click.secho(f"  [DRY-RUN] Injetaria otimizações de Alocação no {ps1_file.name}", fg="yellow")
            else:
                ps1_file.write_text(content + "\n".join(alloc_vars_ps1), encoding="utf-8")
                patched = True

    if not dry_run:
        if patched:
            click.secho(
                f"  [OK] Scripts de ativação turbinados com sucesso! ({num_cores} cores alocados)",
                fg="green",
            )
            click.secho("       (Desative e ative o venv novamente para aplicar)", fg="cyan")
        else:
            click.echo("  [OK] O Venv já possui as otimizações de alocação ativas.")


def _batch_optimize_alloc(root: Path, dry_run: bool) -> None:
    venvs = scan_venvs(root.absolute())
    if not venvs:
        click.echo("[BATCH-ALLOC] Nenhum venv encontrado.")
        return

    for venv in venvs:
        try:
            real_paths = _resolve_real_paths(venv)
            for real in real_paths:
                click.secho(f"\n[BATCH-ALLOC] {real}", fg="cyan", bold=True)
                _optimize_alloc(real, dry_run)
        except Exception as e:
            click.secho(f"[FAIL] {venv}: {e}", fg="red")


def optimize_venv(
    venv_path: Path,
    clean_lib: bool,
    update: bool,
    conf: bool,
    alloc: bool,
    lib_analyze: bool,
    dry_run: bool,
) -> None:
    venv_path = venv_path.absolute()

    try:
        real_paths = _resolve_real_paths(venv_path)
    except Exception as e:
        click.secho(f"[ERRO] {e}", fg="red")
        return

    for real_venv in real_paths:
        click.secho(f"\n[OPTIMIZE] Iniciando em: {real_venv}", fg="cyan", bold=True)
        py_exe = real_venv / "Scripts" / "python.exe" if os.name == "nt" else real_venv / "bin" / "python"

        if lib_analyze:
            _analyze_libs(real_venv)

        if conf:
            click.secho("\n>> Restaurando Configurações (-c / --conf)", fg="magenta")
            _optimize_conf(real_venv, dry_run)

        if clean_lib:
            click.secho("\n>> Limpando Bibliotecas (-cl / --clean-lib)", fg="magenta")
            _optimize_clean_lib(real_venv, py_exe, dry_run)

        if update:
            click.secho("\n>> Atualizando Bibliotecas (-u / --update)", fg="magenta")
            _optimize_update(real_venv, py_exe, dry_run)

        if alloc:
            click.secho("\n>> Alocação de Recursos (-a / --alloc)", fg="magenta")
            _optimize_alloc(real_venv, dry_run)

        click.secho("\n>> Limpeza Final de Resíduos (--dump)", fg="magenta")
        _execute_dump(real_venv, str(real_venv), dry_run)

    click.secho("\n[OPTIMIZE] Orquestração concluída com sucesso!", fg="green", bold=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command("venvkeeper")
@click.option("--move", "-m", "move_path", type=click.Path(path_type=Path), help="Mover um venv")
@click.option("--return", "-r", "return_path", type=click.Path(path_type=Path), help="Restaurar um venv")
@click.option("--scan", type=click.Path(path_type=Path), help="Listar venvs em uma árvore")
@click.option("--batch-move", type=click.Path(path_type=Path), help="Mover todos os venvs em uma árvore")
@click.option("--batch-return", type=click.Path(path_type=Path), help="Restaurar todos os venvs sob uma árvore")

# ----------------- OPERAÇÕES DE DUMP -----------------
@click.option(
    "-d",
    "--dump",
    "dump_path",
    type=click.Path(path_type=Path),
    required=False,
    default=None,
    is_flag=False,
    flag_value=Path("."),
    help="Limpar resíduos (__pycache__, *.pyc, *.log…). Sem argumento usa '.'",
)
@click.option(
    "-bd",
    "--batch-dump",
    "batch_dump_root",
    type=click.Path(path_type=Path),
    default=None,
    is_flag=False,
    flag_value=Path("."),
    help="Limpar resíduos de todos os venvs na árvore atual.",
)

# ---------------- OPERAÇÕES DE OTIMIZAÇÃO ----------------
@click.option(
    "--optimize",
    "-o",
    "optimize_path",
    type=click.Path(path_type=Path),
    required=False,
    default=None,
    is_flag=False,
    flag_value=Path("."),
    help="Otimizar o venv (-cl, -u, -c, -a, -d)",
)
@click.option("--clean-lib", "-cl", is_flag=True, help="Remover pacotes excessivos não usados")
@click.option("--update", "-u", is_flag=True, help="Atualizar libs compatíveis")
@click.option("--conf", "-c", is_flag=True, help="Corrigir configurações de ambiente")
@click.option("--alloc", "-a", is_flag=True, help="Ajustar alocação de memória")
@click.option(
    "--batch-alloc",
    "-ba",
    "batch_alloc_root",
    type=click.Path(path_type=Path),
    default=None,
    is_flag=False,
    flag_value=Path("."),
    help="Ajustar alocação de memória em lote",
)

# ---------------- CONFIGURAÇÕES GERAIS ----------------
@click.option("--status", is_flag=True, help="Exibir manifest")
@click.option("--force", is_flag=True, help="Forçar operação mesmo com conflito")
@click.option("--dry-run", is_flag=True, help="Simular sem executar")

# ---------------- CONFIGURAÇÕES ANALISE ----------------
@click.option("--lib-analyze", "-la", is_flag=True, help="Analisar tamanho e uso das bibliotecas instaladas")
def venvkeeper(
    move_path,
    return_path,
    scan,
    batch_move,
    batch_return,
    dump_path,
    batch_dump_root,
    optimize_path,
    clean_lib,
    update,
    conf,
    alloc,
    batch_alloc_root,
    lib_analyze,
    status,
    force,
    dry_run,
):
    """Gerenciador de ambientes virtuais Python."""

    if status:
        show_status()
        return

    if scan is not None:
        found = scan_venvs(scan)
        if not found:
            click.echo("[SCAN] Nenhum venv encontrado.")
        else:
            for p in found:
                click.echo(str(p))
        return

    if batch_move is not None:
        batch_move_venvs(batch_move, force=force, dry_run=dry_run)
        return

    if batch_return is not None:
        batch_return_venvs(batch_return, force=force)
        return

    if dump_path is not None:
        try:
            dump_venv(Path(str(dump_path)), dry_run=dry_run)
        except Exception as e:
            click.secho(f"[ERRO] {e}", fg="red")
        return

    if batch_dump_root is not None:
        root = None if str(batch_dump_root) == "__ALL__" else Path(str(batch_dump_root))
        batch_dump_venvs(root, dry_run=dry_run)
        return

    if batch_alloc_root is not None:
        root = Path(str(batch_alloc_root))
        _batch_optimize_alloc(root, dry_run=dry_run)
        return

    if optimize_path is not None:
        if not any([clean_lib, update, conf, alloc, lib_analyze]):
            clean_lib = update = conf = lib_analyze = True

        target = Path(str(optimize_path))
        optimize_venv(target, clean_lib, update, conf, alloc, lib_analyze, dry_run)
        return

    if move_path is not None:
        try:
            move_venv(move_path, force=force)
        except Exception as e:
            click.secho(f"[ERRO] {e}", fg="red")
        return

    if return_path is not None:
        try:
            return_venv(return_path, force=force)
        except Exception as e:
            click.secho(f"[ERRO] {e}", fg="red")
        return

    raise click.UsageError(
        "Use --move, --return, --scan, --batch-move, --batch-return, "
        "--dump, --batch-dump, --optimize, --batch-alloc ou --status"
    )


if __name__ == "__main__":
    venvkeeper()
