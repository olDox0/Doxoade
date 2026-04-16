# doxoade/doxoade/commands/venvkeeper_systems/links.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def make_link(src: Path, dst: Path) -> None:
    """Cria junction (Windows) ou symlink (Unix) de src apontando para dst."""
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(src), str(dst)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Falha ao criar junction:\n{result.stderr.strip()}")
        # Protege o junction do Google Drive / OneDrive
        subprocess.run(
            ["attrib", "+S", str(src)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        os.symlink(dst, src, target_is_directory=True)


def remove_link(path: Path) -> None:
    """Remove junction (Windows) ou symlink (Unix) sem afetar o destino."""
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
    """Marca diretório com atributo sistema para sync clients ignorarem (Windows)."""
    subprocess.run(
        ["attrib", "+S", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )