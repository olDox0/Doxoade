# -*- coding: utf-8 -*-
# doxoade/commands/note_systems/note_api.py
"""
📝 NOTES API v2.0 — Contrato Hera entre Terminal, GUI e Malha P2P.
Toda operação de notas passa por aqui, garantindo flush atômico e disparo do Watchdog.
Retorna apenas dicts JSON-serializáveis (portabilidade Win/Linux).
Compliance: ProDeNov 1.2.1 | PASC-6.1 | Limite < 50KB.
"""
from __future__ import annotations
import os
import json as _json
import shutil as _shutil
from pathlib import Path
from datetime import datetime
from .note_cmd import _note_dir, _load, _all_notes, _preview, _slug
from .agenda import (
    all_tasks, scan_note_tasks, classify_when,
    reminder_items, complete_task, add_item, parse_when, _MARK
)


def _atomic_write(target_path: Path, content: str):
    """Gravação atômica com garantia de flush e atualização de mtime no NTFS/ext4."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(f".tmp_{os.getpid()}")
    try:
        with open(temp_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


def api_list_notes(root: str | Path) -> list:
    """Lista todas as notas de projeto com contagem de tarefas e previews."""
    d = _note_dir(Path(root))
    notes = []
    for p in _all_notes(d):
        try:
            lines = _load(p)
            notes.append({
                "name": p.stem,
                "lines": len(lines),
                "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "preview": _preview(lines),
                "tasks": scan_note_tasks(p),
            })
        except Exception:
            continue
    return notes


def api_get_note(root: str | Path, name: str) -> dict:
    """Carrega nota específica com extração estruturada de tarefas."""
    target = _note_dir(Path(root)) / f"{_slug(name)}.md"
    if not target.exists():
        return {"error": "nota não encontrada", "name": name}
    lines = _load(target)
    return {
        "name": target.stem,
        "raw": "\n".join(lines),
        "lines": lines,
        "tasks": scan_note_tasks(target)
    }


def api_save_note(root: str | Path, name: str, raw: str) -> dict:
    """Salva nota do projeto com gravação atômica."""
    target = _note_dir(Path(root)) / f"{_slug(name)}.md"
    _atomic_write(target, raw + ("\n" if not raw.endswith("\n") else ""))
    return {"ok": True, "name": target.stem, "lines": len(raw.splitlines())}


def api_append(root: str | Path, name: str, text: str, when: str = None) -> dict:
    """Anexa linha à nota e registra agendamento opcional."""
    target = _note_dir(Path(root)) / f"{_slug(name)}.md"
    lines = _load(target)
    lines.append(text)
    _atomic_write(target, "\n".join(lines) + "\n")
    rec = add_item(Path(root), target.stem, text, parse_when(when)) if when else None
    return {"ok": True, "lines": len(lines), "agenda": rec}


def api_done_task(root: str | Path, ref: str) -> dict:
    """Conclui tarefa in-place por ID."""
    rec = complete_task(Path(root), ref)
    return {"ok": True, "id": rec["id"], "already": rec.get("already", False)} if rec \
        else {"ok": False, "error": f"não encontrado: {ref}"}


def api_agenda(root: str | Path) -> dict:
    """Consolida tarefas pendentes e lembretes da agenda."""
    r_path = Path(root)
    table = all_tasks(r_path / ".doxoade" / "note")
    for t in table:
        t["mark"] = _MARK[classify_when(t["when"], t.get("done"))]
    return {"reminders": reminder_items(r_path), "tasks": table}


def _trash_dir(root: Path) -> Path:
    t = Path(root) / ".doxoade" / "note" / ".trash"
    t.mkdir(parents=True, exist_ok=True)
    return t


def api_new_note(root: str | Path, name: str) -> dict:
    """Cria nova nota de projeto formatada com timestamp."""
    d = _note_dir(Path(root))
    slug = _slug((name or "").strip() or "nota")
    target = d / f"{slug}.md"
    n = 1
    while target.exists():
        n += 1
        target = d / f"{slug}_{n}.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    initial_content = f"# 📝 {target.stem}\n\nCriado em: {now_str}\n\n"
    _atomic_write(target, initial_content)
    return {"ok": True, "name": target.stem}


def api_delete_note(root: str | Path, name: str) -> dict:
    """Move nota para a lixeira preservando metadados de histórico."""
    d = _note_dir(Path(root))
    src = d / f"{_slug(name)}.md"
    if not src.exists():
        return {"ok": False, "error": "nota não encontrada"}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = _trash_dir(Path(root)) / f"{ts}_{src.name}"
    _shutil.move(str(src), str(dst))
    dst.with_suffix(".meta.json").write_text(
        _json.dumps({"name": src.stem, "when": ts}, ensure_ascii=False),
        encoding="utf-8"
    )
    return {"ok": True, "trashed": dst.name}


def api_list_trash(root: str | Path) -> list:
    """Lista itens retidos na lixeira."""
    t = _trash_dir(Path(root))
    out = []
    for p in sorted(t.glob("*.md"), reverse=True):
        meta = {}
        mj = p.with_suffix(".meta.json")
        if mj.exists():
            try:
                meta = _json.loads(mj.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        out.append({
            "ref": p.stem,
            "name": meta.get("name", p.stem),
            "when": meta.get("when", ""),
            "lines": len(_load(p))
        })
    return out


def api_restore_note(root: str | Path, ref: str) -> dict:
    """Restaura nota da lixeira para a pasta ativa de notas."""
    t = _trash_dir(Path(root))
    src = t / (ref if ref.endswith(".md") else ref + ".md")
    if not src.exists():
        return {"ok": False, "error": f"não encontrado na lixeira: {ref}"}
    name = None
    mj = src.with_suffix(".meta.json")
    if mj.exists():
        try:
            name = _json.loads(mj.read_text(encoding="utf-8")).get("name")
        except Exception:
            name = None
    if not name:
        parts = src.name.split("_")
        name = "_".join(parts[2:]) if len(parts) >= 3 else src.name
    d = _note_dir(Path(root))
    dst = d / f"{_slug(name)}.md"
    n = 1
    while dst.exists():
        n += 1
        dst = d / f"{_slug(name)}_{n}.md"
    _shutil.move(str(src), str(dst))
    mj.unlink(missing_ok=True)
    return {"ok": True, "name": dst.stem}


def api_purge_trash(root: str | Path, ref: str) -> dict:
    """Purga definitiva manual da lixeira."""
    t = _trash_dir(Path(root))
    src = t / (ref if ref.endswith(".md") else ref + ".md")
    if not src.exists():
        return {"ok": False, "error": f"não encontrado: {ref}"}
    src.unlink(missing_ok=True)
    src.with_suffix(".meta.json").unlink(missing_ok=True)
    return {"ok": True}
