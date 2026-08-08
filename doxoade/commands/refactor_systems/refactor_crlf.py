# doxoade/doxoade/commands/refactor_systems/refactor_crlf.py
# -*- coding: utf-8 -*-
"""CRLF-FIX — Cirurgião de EOL (Anti LF-Apocalypse). Lossless + fail-graceful."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Iterator, Optional, Tuple

TEXT_EXTS = {'.py', '.c', '.cpp', '.h', '.hpp', '.toml', '.md', '.txt', '.json',
             '.xml', '.yml', '.yaml', '.sh', '.s', '.html', '.css', '.js', '.ts',
             '.ini', '.cfg', '.gitattributes'}
SKIP_DIRS = {'venv', '.venv', '.git', '__pycache__', 'build', 'dist', '.doxoade',
             '.doxoade_cache', 'node_modules', 'nppbackup', 'pytest_temp_dir',
             'tests', 'regression_tests', 'thirdparty', 'w64devkit', 'recovery_zone'}
OS_JUNK = {'desktop.ini', 'thumbs.db', '.ds_store'}
CRLF_LOCKED = {'.bat', '.cmd', '.ps1'}   # scripts Windows: CRLF é o contrato

def detect_dominant_eol(raw: bytes) -> str:
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    return 'crlf' if crlf > lf else 'lf'

def normalize_eol(raw: bytes, target: str) -> bytes:
    canon = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return canon.replace(b'\n', b'\r\n') if target == 'crlf' else canon

def _build_snippet(raw: bytes, target: str, max_lines: int = 3) -> str:
    """⚖️ Prova de Ma'at: primeiras linhas com ␍ visível p/ auditoria a olho nu."""
    lines = raw.decode('utf-8', errors='replace').splitlines()
    out, shown = [], 0
    for i, ln in enumerate(lines):
        if shown >= max_lines:
            break
        had_cr = ln.endswith('\r')
        clean = ln.rstrip('\r')
        if target == 'lf' and had_cr:
            out.append(f"        L{i + 1:>4} - {clean}␍")
            out.append(f"             + {clean}")
            shown += 1
        elif target == 'crlf' and not had_cr and clean:
            out.append(f"        L{i + 1:>4} - {clean}")
            out.append(f"             + {clean}␍")
            shown += 1
    return '\n'.join(out)

def fix_file_eol(path: Path, target: str, dry_run: bool = False,
                 verbose: bool = False) -> Tuple[str, str, Optional[str]]:
    """status: 'fixed' | 'clean' | 'skipped'. NUNCA levanta em arquivo protegido."""
    if path.name.lower() in OS_JUNK:
        return 'skipped', 'os-junk', None
    if target == 'lf' and path.suffix.lower() in CRLF_LOCKED:
        return 'skipped', 'crlf-locked', None
    try:
        raw = path.read_bytes()
    except (PermissionError, OSError):
        return 'skipped', 'read-denied', None
    if b'\0' in raw[:8192]:
        return 'skipped', 'binary', None
    if target == 'auto':
        target = detect_dominant_eol(raw)
    new = normalize_eol(raw, target)
    if new == raw:
        return 'clean', target, None
    snippet = _build_snippet(raw, target) if verbose else None
    if not dry_run:
        try:
            path.write_bytes(new)
        except (PermissionError, OSError):
            return 'skipped', 'write-denied', None   # ← desktop.ini não mata a run
    n = raw.count(b'\r\n') if target == 'lf' else (raw.count(b'\n') - raw.count(b'\r\n'))
    return 'fixed', f"{detect_dominant_eol(raw)}({n})->{target}", snippet

def iter_candidate_files(root: Path, paths: tuple = ()) -> Iterator[Path]:
    root = root.resolve()
    seeds = [Path(p).resolve() for p in paths] or [root]
    for seed in seeds:
        if seed.is_file():
            if seed.suffix.lower() in TEXT_EXTS:
                yield seed
            continue
        for dirpath, dirnames, filenames in os.walk(seed, topdown=True):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith('.')]
            for name in filenames:
                if Path(name).suffix.lower() in TEXT_EXTS:
                    yield Path(dirpath) / name