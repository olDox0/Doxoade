# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/note_systems/note_api.py
"""
📝 NOTES API — Contrato Hera entre terminal e GUI (Benzaiten).
Toda operação da GUI passa por aqui: a mesma verdade do terminal.
Retorna apenas dicts JSON-serializáveis (portabilidade Win/Linux).
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime

from .note_cmd import _note_dir, _load, _save, _all_notes, _preview, _slug
from .agenda import (all_tasks, scan_note_tasks, classify_when,
                     reminder_items, complete_task, add_item, parse_when, _MARK)


def api_list_notes(root) -> list:
    d = _note_dir(Path(root))
    return [{
        'name': p.stem,
        'lines': len(_load(p)),
        'mtime': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
        'preview': _preview(_load(p)),
        'tasks': scan_note_tasks(p),
    } for p in _all_notes(d)]


def api_get_note(root, name: str) -> dict:
    target = _note_dir(Path(root)) / f'{_slug(name)}.md'
    if not target.exists():
        return {'error': 'nota não encontrada', 'name': name}
    lines = _load(target)
    return {'name': target.stem, 'raw': '\n'.join(lines),
            'lines': lines, 'tasks': scan_note_tasks(target)}


def api_save_note(root, name: str, raw: str) -> dict:
    target = _note_dir(Path(root)) / f'{_slug(name)}.md'
    _save(target, raw.splitlines())
    return {'ok': True, 'name': target.stem, 'lines': len(raw.splitlines())}


def api_append(root, name: str, text: str, when: str = None) -> dict:
    target = _note_dir(Path(root)) / f'{_slug(name)}.md'
    lines = _load(target)
    lines.append(text)
    _save(target, lines)
    rec = add_item(Path(root), target.stem, text, parse_when(when)) if when else None
    return {'ok': True, 'lines': len(lines), 'agenda': rec}


def api_done_task(root, ref: str) -> dict:
    rec = complete_task(Path(root), ref)
    return {'ok': True, 'id': rec['id'], 'already': rec.get('already', False)} if rec \
        else {'ok': False, 'error': f'não encontrado: {ref}'}


def api_agenda(root) -> dict:
    root = Path(root)
    table = all_tasks(root / '.doxoade' / 'note')
    for t in table:
        t['mark'] = _MARK[classify_when(t['when'], t.get('done'))]
    return {'reminders': reminder_items(root), 'tasks': table}

# ── FASE 4: ciclo de vida (lixeira recuperável · purga só manual) ────
import json as _json
import shutil as _shutil

def _trash_dir(root: Path) -> Path:
    t = Path(root) / '.doxoade' / 'note' / '.trash'
    t.mkdir(parents=True, exist_ok=True)
    return t

def api_new_note(root, name: str) -> dict:
    d = _note_dir(Path(root))
    slug = _slug((name or '').strip() or 'nota')
    target = d / f'{slug}.md'
    n = 1
    while target.exists():
        n += 1
        target = d / f'{slug}_{n}.md'
    _save(target, [f'# {target.stem}', ''])
    return {'ok': True, 'name': target.stem}

def api_delete_note(root, name: str) -> dict:
    d = _note_dir(Path(root))
    src = d / f'{_slug(name)}.md'
    if not src.exists():
        return {'ok': False, 'error': 'nota não encontrada'}
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = _trash_dir(Path(root)) / f'{ts}_{src.name}'
    _shutil.move(str(src), str(dst))
    dst.with_suffix('.meta.json').write_text(
        _json.dumps({'name': src.stem, 'when': ts}, ensure_ascii=False),
        encoding='utf-8')
    return {'ok': True, 'trashed': dst.name}

def api_list_trash(root) -> list:
    t = _trash_dir(Path(root))
    out = []
    for p in sorted(t.glob('*.md'), reverse=True):
        meta = {}
        mj = p.with_suffix('.meta.json')
        if mj.exists():
            try:
                meta = _json.loads(mj.read_text(encoding='utf-8'))
            except Exception:
                meta = {}
        out.append({'ref': p.stem, 'name': meta.get('name', p.stem),
                    'when': meta.get('when', ''), 'lines': len(_load(p))})
    return out

def api_restore_note(root, ref: str) -> dict:
    t = _trash_dir(Path(root))
    src = t / (ref if ref.endswith('.md') else ref + '.md')
    if not src.exists():
        return {'ok': False, 'error': f'não encontrado na lixeira: {ref}'}
    name = None
    mj = src.with_suffix('.meta.json')
    if mj.exists():
        try:
            name = _json.loads(mj.read_text(encoding='utf-8')).get('name')
        except Exception:
            name = None
    if not name:
        parts = src.name.split('_')
        name = '_'.join(parts[2:]) if len(parts) >= 3 else src.name
    d = _note_dir(Path(root))
    dst = d / f'{_slug(name)}.md'
    n = 1
    while dst.exists():
        n += 1
        dst = d / f'{_slug(name)}_{n}.md'
    _shutil.move(str(src), str(dst))
    mj.unlink(missing_ok=True)
    return {'ok': True, 'name': dst.stem}

def api_purge_trash(root, ref: str) -> dict:
    """Purga MANUAL (doutrina de preservação: nunca automática)."""
    t = _trash_dir(Path(root))
    src = t / (ref if ref.endswith('.md') else ref + '.md')
    if not src.exists():
        return {'ok': False, 'error': f'não encontrado: {ref}'}
    src.unlink(missing_ok=True)
    src.with_suffix('.meta.json').unlink(missing_ok=True)
    return {'ok': True}
