# doxoade/doxoade/commands/venvkeeper_systems/manifest.py
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .constants import BASE, MANIFEST


def ensure_base() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["attrib", "+S", str(BASE)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"items": {}}

    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if "items" in raw:
        return raw

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


def save_manifest(data: dict) -> None:
    ensure_base()
    MANIFEST.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )