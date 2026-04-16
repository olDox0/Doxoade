# doxoade/doxoade/experiments/optimizer_systems/optimizer_utils.py
import hashlib
from pathlib import Path

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()