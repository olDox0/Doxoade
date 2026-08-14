# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/prefs.py
"""SOFTCLUB PREFS — memória persistente da GUI (FASE 1).
Storage: <projeto>/.doxoade/note/gui_prefs.json (mesmo silo das notas).
Doutrina: fail-graceful absoluto; write-through nas mudanças.
Prioridade do fundo (Q1): drop (sessão) > env SOFTCLUB_BG > prefs.
"""
from __future__ import annotations
import json
from pathlib import Path

_DEFAULTS = {'theme': 'night', 'seed': 7, 'bg_path': None,
             'bg_extras': [], 'rotation_min': 10}

def _prefs_path(root) -> Path:
    return Path(root) / '.doxoade' / 'note' / 'gui_prefs.json'

def load_prefs(root) -> dict:
    data = dict(_DEFAULTS)
    try:
        p = _prefs_path(root)
        if p.exists():
            data.update(json.loads(p.read_text(encoding='utf-8')))
    except Exception:
        pass
    return data

def save_prefs(root, prefs: dict) -> bool:
    """Merge + write-atômico (tmp→replace). Nunca levanta."""
    try:
        p = _prefs_path(root)
        p.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(_DEFAULTS)
        try:
            if p.exists():
                merged.update(json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            pass
        merged.update(prefs)
        tmp = p.with_suffix('.tmp')
        tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                       encoding='utf-8')
        tmp.replace(p)
        return True
    except Exception:
        return False
