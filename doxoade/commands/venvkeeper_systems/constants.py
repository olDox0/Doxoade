from __future__ import annotations

from pathlib import Path

BASE            = Path.home() / ".doxoade" / "venvkeeper"
MANIFEST        = BASE / "manifest.json"
SUPPORTED_NAMES = {"venv", ".venv", "env"}

# Diretórios inteiros considerados resíduos
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

# Extensões de arquivos avulsos considerados resíduos
DUMP_FILE_SUFFIXES: set[str] = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
}