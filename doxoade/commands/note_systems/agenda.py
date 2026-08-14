# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/note_systems/agenda.py
"""
⏰ AGENDA NEXUS — lembretes que avisam no uso normal do Doxoade.
Storage: <projeto>/.doxoade/note/.agenda.json + tarefas datadas nas notas.
Doutrina: fail-graceful absoluto; o lembrete NUNCA quebra o comando real.
"""
from __future__ import annotations
import json
import os
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

SUSPECT_DAYS = 90   # "vencida" há mais que isso = provável erro de ano (2025 vs 2026)
HORIZON_DAYS = 1    # aviso antecipado: hoje anuncia as tarefas de amanhã

_MARK = {'done': '[x]', 'suspect': '[?]', 'overdue': '[!]',
         'today': '[*]', 'upcoming': '[>]', 'future': '[ ]'}
_ORDER = {'today': 0, 'overdue': 1, 'upcoming': 2, 'suspect': 3, 'future': 4, 'done': 5}


def classify_when(when_iso: str, done: bool = False) -> str:
    """★ hoje | ! vencida real | > próxima (amanhã) | ? data suspeita | [ ] futuro."""
    if done:
        return 'done'
    try:
        w = date.fromisoformat(when_iso)
    except ValueError:
        return 'future'
    delta = (date.today() - w).days
    if delta < 0:
        return 'upcoming' if -delta <= HORIZON_DAYS else 'future'
    if delta == 0:
        return 'today'
    return 'overdue' if delta <= SUSPECT_DAYS else 'suspect'


def _find_root() -> Path:
    p = Path.cwd()
    for c in [p, *p.parents]:
        if (c / 'pyproject.toml').exists() or (c / '.git').exists():
            return c
    return p


def _agenda_path(root: Path) -> Path:
    return Path(root) / '.doxoade' / 'note' / '.agenda.json'


def _load(root: Path) -> dict:
    p = _agenda_path(root)
    if not p.exists():
        return {'items': []}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {'items': []}


def _save(root: Path, data: dict):
    p = _agenda_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_when(s: str):
    """Aceita: 2026-08-10 | +3d | +2w | amanha/tomorrow."""
    s = _norm_date((s or '').strip().lower())
#    s = (s or '').strip().lower()
    if not s:
        return None
    if s in ('amanha', 'amanhã', 'tomorrow', '+1d'):
        return (date.today() + timedelta(days=1)).isoformat()
    m = re.match(r'^\+(\d+)([dw])$', s)
    if m:
        n = int(m.group(1))
        return (date.today() + timedelta(days=n * 7 if m.group(2) == 'w' else n)).isoformat()
    m = re.match(r'^(\d{4})[-/](\d{2})[-/](\d{2})$', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def add_item(root: Path, note_name: str, text: str, when_iso: str) -> dict:
    data = _load(root)
    item = {'id': uuid.uuid4().hex[:4], 'note': note_name, 'text': (text or '').strip(),
            'when': when_iso, 'created': date.today().isoformat(), 'done': False}
    data.setdefault('items', []).append(item)
    _save(root, data)
    return item


def due_items(root: Path = None) -> list:
    root = root or _find_root()
    today = date.today().isoformat()
    return [i for i in _load(root).get('items', [])
            if not i.get('done') and i.get('when', '9999') <= today]


def mark_done(root: Path, ref: str):
    data = _load(root)
    hit = None
    for i in data.get('items', []):
        if i.get('id') == ref or i.get('note') == ref:
            i['done'] = True
            hit = i
    if hit:
        _save(root, data)
    return hit


# ─────────────────────────── TAREFAS DAS NOTAS ───────────────────────────
_TASK_RE = re.compile(
    r'^\s*\[(?P<done>[xX\s])\]\s*(?P<date>\d{4}[./-]\d{2}[./-]\d{2})\s*(?P<text>.*)$'
)


def _norm_date(s: str) -> str:
    return s.replace('.', '-').replace('/', '-')


def _new_id() -> str:
    """ID curto base36 (5 chars), estável e copiável da tabela."""
    n = uuid.uuid4().int
    s = ''
    while n and len(s) < 5:
        n, r = divmod(n, 36)
        s = '0123456789abcdefghijklmnopqrstuvwxyz'[r] + s
    return s

_TASK_RE = re.compile(
    r'^\s*\[(?P<done>[xX\s])\]\s*(?P<date>\d{4}[./-]\d{2}[./-]\d{2})'
    r'\s*(?:#(?P<tid>[a-z0-9]{4,8})\s*)?(?P<text>.*)$'
)

def scan_note_tasks(note_path: Path, assign_ids: bool = True) -> list:
    """Extrai tarefas; tarefas sem ID ganham um (write-through, doutrina do Note)."""
    tasks = []
    try:
        raw = Path(note_path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return tasks
    out_lines, changed = list(raw), False
    for i, line in enumerate(raw):
        m = _TASK_RE.match(line)
        if not m:
            continue
        tid = m.group('tid')
        if not tid and assign_ids:
            tid = _new_id()
            out_lines[i] = re.sub(
                r'^(\s*\[[xX\s]\]\s*\d{4}[./-]\d{2}[./-]\d{2})\s*',
                rf'\1 #{tid} ', line, count=1)
            changed = True
        tasks.append({
            'id': tid, 'note': Path(note_path).stem, 'line': i + 1,
            'done': m.group('done').strip().lower() == 'x',
            'when': _norm_date(m.group('date')), 'text': m.group('text').strip(),
        })
    if changed:
        Path(note_path).write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    return tasks

def _append_history(root: Path, rec: dict):
    p = Path(root) / '.doxoade' / 'note' / '.history.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')

def _history_path(root) -> Path:
    return Path(root) / '.doxoade' / 'note' / '.history.jsonl'

def _load_history_ids(root) -> set:
    ids = set()
    p = _history_path(root)
    if p.exists():
        for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                ids.add(json.loads(line).get('id'))
            except Exception:
                pass
    return ids

def sync_done_to_history(root, notes_dir=None) -> int:
    """🔄 Capta tarefas marcadas [x] FORA do Doxoade (Notepad/GUI) e registra no histórico."""
    notes_dir = Path(notes_dir) if notes_dir else Path(root) / '.doxoade' / 'note'
    known = _load_history_ids(root)
    added = 0
    for t in all_tasks(notes_dir):
        if t.get('done') and t['id'] not in known:
            _append_history(root, {
                'id': t['id'], 'note': t['note'], 'when': t['when'],
                'text': t['text'], 'done_at': date.today().isoformat(),
                'status': 'done', 'source': 'external',
            })
            known.add(t['id'])
            added += 1
    return added

def complete_task(root, ref, note_path=None):
    """⚖️ Conclui tarefa por ID — a linha NUNCA sai da nota:
    1. marca [x] in-place; 2. registra no histórico (idempotente)."""
    d = Path(root) / '.doxoade' / 'note'
    notes = [Path(note_path)] if note_path else sorted(d.glob('*.md'))
    hits = []
    for np in notes:
        if not np.exists():
            continue
        for i, l in enumerate(np.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            m = _TASK_RE.match(l)
            if m and m.group('tid') and (m.group('tid') == ref or m.group('tid').startswith(ref)):
                hits.append((np, i, m))
    if len(hits) != 1:
        return None
    np, idx, m = hits[0]
    already = (m.group('done') or '').strip().lower() == 'x'
    if not already:
        lines = np.read_text(encoding='utf-8', errors='replace').splitlines()
        lines[idx - 1] = re.sub(r'\[[xX\s]\]', '[x]', lines[idx - 1], count=1)
        np.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
        if m.group('tid') not in _load_history_ids(root):
            _append_history(root, {
                'id': m.group('tid'), 'note': np.stem, 'when': _norm_date(m.group('date')),
                'text': m.group('text').strip(), 'done_at': date.today().isoformat(),
                'status': 'done', 'source': 'cli',
            })
    return {'id': m.group('tid'), 'note': np.stem, 'already': already,
            'when': _norm_date(m.group('date')), 'text': m.group('text').strip()}

def all_tasks(notes_dir: Path) -> list:
    out = []
    for p in sorted(Path(notes_dir).glob('*.md')):
        out.extend(scan_note_tasks(p))
    return out


def due_tasks(notes_dir: Path) -> list:
    today = date.today().isoformat()
    return [t for t in all_tasks(notes_dir) if not t['done'] and t['when'] <= today]


def reminder_items(root) -> list:
    out = []
    for t in all_tasks(Path(root) / '.doxoade' / 'note'):
        st = classify_when(t['when'], t.get('done'))
        if st in ('today', 'overdue', 'upcoming', 'suspect'):
            t['status'] = st
            out.append(t)
    return out


def render_reminder(items: list) -> str:
    if not items:
        return ''
    tag = {'today': 'HOJE', 'overdue': 'VENCIDA', 'upcoming': 'AMANHÃ', 'suspect': 'DATA SUSPEITA'}
    lines = [f"\n⏰ [AGENDA NEXUS] {len(items)} aviso(s):"]
    for t in sorted(items, key=lambda x: (_ORDER[x['status']], x['when'])):
        lines.append(f"   {_MARK[t['status']]} {t['when']} | {t['note']}: {t['text'][:60]}  ({tag[t['status']]})")
        if t['status'] == 'suspect':
            lines.append(f"       ↳ 'vencida' há >{SUSPECT_DAYS} dias — provável erro de ANO. Revise: doxoade note {t['note']}")
    return '\n'.join(lines)


def render_task_table(tasks: list, title: str = 'TAREFAS AGENDADAS') -> str:
    if not tasks:
        return '⏰ Nenhuma tarefa agendada nas notas.'
    tasks = sorted(tasks, key=lambda t: (
        _ORDER[classify_when(t['when'], t.get('done'))], t['when'], t['note']))
    out = [f'⏰ {title} ({len(tasks)}):',
           f"   {'ST':<4} | {'ID':<6} | {'DATA':<10} | {'NOTA':<12} | TAREFA",
           '   ' + '-' * 80]
    for t in tasks:
        st = _MARK[classify_when(t['when'], t.get('done'))]
        out.append(f"   {st:<4} | {t.get('id') or '-----':<6} | {t['when']:<10} | "
                   f"{t['note'][:12]:<12} | {t['text'][:50]}")
    return '\n'.join(out)