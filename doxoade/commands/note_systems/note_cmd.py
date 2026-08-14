# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/note_systems/note_cmd.py
r"""
📝 DOXOADE NOTE — notas no terminal (experimental).
Storage : <projeto>/.doxoade/note/<nome>.md (markdown puro = interop Notepad/Benzaiten)
Doutrina: write-through (toda mudança persiste na hora — crash-safe).
Editor  : texto livre = append | \q sair | \h ajuda | \when <data> [txt]
"""
from __future__ import annotations
import os
import re
import difflib
import subprocess
import click
from pathlib import Path
from datetime import datetime

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root


def _note_dir(root: Path) -> Path:
    d = Path(root) / '.doxoade' / 'note'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(name: str) -> str:
    s = re.sub(r'[^\w\-]+', '_', (name or '').strip(), flags=re.UNICODE)
    return s.strip('_') or 'nota'


def _load(p: Path) -> list:
    return p.read_text(encoding='utf-8', errors='replace').splitlines() if p.exists() else []


def _save(p: Path, lines: list):
    p.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')


def _all_notes(d: Path) -> list:
    return sorted(d.glob('*.md'))


def _preview(lines, n=52):
    for l in lines:
        if l.strip() and not l.startswith('#'):
            return l.strip()[:n]
    return '(vazia)'


def _render_list(d: Path):
    notes = _all_notes(d)
    if not notes:
        click.echo(f'{Fore.YELLOW}📭 Nenhuma nota ainda. Crie com: doxoade note <nome>{Style.RESET_ALL}')
        return
    click.echo(f'{Fore.CYAN}📚 Notas ({len(notes)}):{Style.RESET_ALL}')
    for p in notes:
        lines = _load(p)
        mt = datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        click.echo(f'  {Fore.GREEN}•{Style.RESET_ALL} {p.stem:<24} {Fore.DIM}{len(lines):>3} linhas | {mt}{Style.RESET_ALL}')
        click.echo(f'      {Fore.DIM}{_preview(lines)}{Style.RESET_ALL}')


def _render_search(d: Path, term: str):
    hits = 0
    for p in _all_notes(d):
        for i, l in enumerate(_load(p), 1):
            if term.lower() in l.lower():
                hits += 1
                click.echo(f'  {Fore.CYAN}{p.stem}{Style.RESET_ALL}:{i} {l.strip()[:80]}')
    if not hits:
        click.echo(f'{Fore.YELLOW}Nada encontrado para "{term}".{Style.RESET_ALL}')

CMD_PREFIX = '^'   # caminhos Windows nunca começam com '^' → refs coladas são sempre texto
_CMD_KNOWN = {'q', 'exit', 'sair', 'h', 'cat', 'l', 't', 'when', 'e', 'i', 'd', 'z', 'undo', 'y', 'p'}
#_CMD_KNOWN = {'q', 'exit', 'sair', 'h', 'cat', 'l', 't', 'when', 'e', 'i', 'd', 'undo'}

def _cmd_of(line: str):
    """'^q' => comando; qualquer outra coisa => texto livre (None)."""
    if line.startswith(CMD_PREFIX):
        return line[len(CMD_PREFIX):].strip()
    return None

def _editor_loop(note: Path, title: str, root: Path):
    from .agenda import add_item, parse_when
    lines = _load(note)
    undo_stack, redo_stack = [], []
    pivot = len(lines)                      # pivô 1-based (padrão: última linha)

    def _snap():
        undo_stack.append(lines.copy())
        redo_stack.clear()

    def _show_pivot():
        """Exibe a linha ACIMA do pivô + o pivô marcado (contexto p/ edição)."""
        if not lines:
            click.echo(f'  {Fore.DIM}(nota vazia — texto livre append){Style.RESET_ALL}')
            return
        p = min(max(pivot, 1), len(lines))
        if p > 1:
            click.echo(f'  {Fore.DIM}{p - 1:>3} | {lines[p - 2]}{Style.RESET_ALL}')
        click.echo(f'  {Fore.CYAN}>{p:>3} | {lines[p - 1]}{Style.RESET_ALL}')

    click.echo(f'{Fore.CYAN}📝 {title}{Style.RESET_ALL} {Fore.DIM}({len(lines)} linhas) — ^h ajuda, ^q sair{Style.RESET_ALL}')
    while True:
        _show_pivot()
        try:
            raw = input(f'{Fore.GREEN}note>{Style.RESET_ALL} ')
        except (EOFError, KeyboardInterrupt):
            break
        if not raw.strip():
            continue
        cmd = _cmd_of(raw)
        if cmd is None:                                   # texto livre = append
            _snap(); lines.append(raw.rstrip()); _save(note, lines)
            pivot = len(lines)
            click.echo(f'{Fore.DIM}+ linha {len(lines)} salva{Style.RESET_ALL}')
            continue
        verb = cmd.split(None, 1)[0] if cmd.split() else ''
        if verb not in _CMD_KNOWN:
            click.echo(f'{Fore.YELLOW}^{verb} não é comando (^h ajuda){Style.RESET_ALL}')
            continue
        if verb in ('q', 'exit', 'sair'):
            break
        if verb == 'h':
            click.echo('  texto livre         append no fim (pivô vai p/ ela)\n'
                       '  ^p N | ^p + | ^p -  move o pivô\n'
                       '  ^e [N] <txt>        substitui linha (pivô por padrão)\n'
                       '  ^i [N] <txt>        insere antes (pivô por padrão)\n'
                       '  ^d [N]              remove linha (pivô por padrão)\n'
                       '  ^z / ^y             undo / redo\n'
                       '  ^l [N] | ^cat       últimas N | tudo numerado\n'
                       '  ^t                  marcador de tempo | ^when <data> [txt] agenda\n'
                       '  ^q                  sair')
            continue
        if verb == 'p':
            arg = cmd.split(None, 1)[1].strip() if len(cmd.split(None, 1)) > 1 else ''
            if arg == '+': pivot = min(len(lines), pivot + 1)
            elif arg == '-': pivot = max(1, pivot - 1)
            elif arg.isdigit() and lines: pivot = min(max(1, int(arg)), len(lines))
            continue
        if verb in ('z', 'undo'):
            if undo_stack:
                redo_stack.append(lines.copy()); lines[:] = undo_stack.pop()
                _save(note, lines)
                pivot = min(max(1, pivot), len(lines)) if lines else 0
                click.echo(f'{Fore.GREEN}✔ undo{Style.RESET_ALL} {Fore.DIM}({len(lines)} linhas){Style.RESET_ALL}')
            else:
                click.echo(f'{Fore.YELLOW}nada para desfazer{Style.RESET_ALL}')
            continue
        if verb == 'y':
            if redo_stack:
                undo_stack.append(lines.copy()); lines[:] = redo_stack.pop()
                _save(note, lines)
                pivot = min(max(1, pivot), len(lines)) if lines else 0
                click.echo(f'{Fore.GREEN}✔ redo{Style.RESET_ALL} {Fore.DIM}({len(lines)} linhas){Style.RESET_ALL}')
            else:
                click.echo(f'{Fore.YELLOW}nada para refazer{Style.RESET_ALL}')
            continue
        if verb == 'cat':
            for i, l in enumerate(lines, 1):
                mark = '>' if i == pivot else ' '
                click.echo(f'  {Fore.DIM}{mark}{i:>3}{Style.RESET_ALL} {l}')
            continue
        if verb == 'l':
            parts = cmd.split()
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            for i, l in enumerate(lines[-n:], max(1, len(lines) - n + 1)):
                click.echo(f'  {Fore.DIM}{i:>3}{Style.RESET_ALL} {l}')
            continue
        if verb == 't':
            _snap(); lines.append(f'[{datetime.now():%Y-%m-%d %H:%M}]')
            _save(note, lines); pivot = len(lines)
            continue
        m = re.match(r'^when\s+(\S+)(?:\s+(.*))?$', cmd)
        if m:
            w = parse_when(m.group(1))
            if not w:
                click.echo(f'{Fore.RED}data inválida{Style.RESET_ALL}'); continue
            text = m.group(2) or (lines[pivot - 1] if 1 <= pivot <= len(lines) else title)
            item = add_item(root, title, text, w)
            click.echo(f'{Fore.CYAN}⏰ agendado [{item["id"]}] para {w}{Style.RESET_ALL}')
            continue
        m = re.match(r'^(e|i|d)(?:\s+(\d+))?(?:\s(.*))?$', cmd)
        if m:
            v2, num, text = m.group(1), m.group(2), (m.group(3) or '')
            idx = int(num) if num else pivot              # sem número = pivô
            limit = len(lines) + 1 if v2 == 'i' else len(lines)
            if not (1 <= idx <= limit):
                click.echo(f'{Fore.RED}linha inválida (1..{limit}){Style.RESET_ALL}'); continue
            if v2 == 'e' and not text:
                click.echo(f'{Fore.DIM}linha {idx}: {lines[idx - 1]}{Style.RESET_ALL}')
                click.echo(f'{Fore.YELLOW}uso: ^e {idx} <novo texto>{Style.RESET_ALL}')
                continue
            _snap()
            if v2 == 'd':
                removed = lines.pop(idx - 1)
                pivot = min(idx, len(lines)) if lines else 0
                click.echo(f'{Fore.YELLOW}- linha {idx} removida: {removed[:50]}{Style.RESET_ALL}')
            elif v2 == 'e':
                lines[idx - 1] = text; pivot = idx
                click.echo(f'{Fore.GREEN}✔ linha {idx} substituída{Style.RESET_ALL}')
            else:
                lines.insert(idx - 1, text); pivot = idx
                click.echo(f'{Fore.GREEN}✔ linha inserida em {idx}{Style.RESET_ALL}')
            _save(note, lines)
            continue
        click.echo(f'{Fore.YELLOW}comando desconhecido: ^{cmd}{Style.RESET_ALL}')

@click.command('note')
@click.argument('name', required=False)
@click.option('--list', '-l', 'show_list', is_flag=True, help='Lista todas as notas.')
@click.option('--search', '-s', 'term', default=None, help='Busca um termo em todas as notas.')
@click.option('--append', '-a', 'quick', default=None, help='Adiciona linha rápida sem abrir o editor.')
@click.option('--show', is_flag=True, help='Somente exibe a nota.')
@click.option('--npp', is_flag=True, help='Abre no Notepad++ (fuga tradicional).')
@click.option('--delete', '-rm', is_flag=True, help='Remove a nota.')
@click.option('--when', '-w', 'when_date', default=None, help='⏰ Agenda: 2026-08-10 | +3d | +2w | amanha.')
@click.option('--due', is_flag=True, help='⏰ Lista lembretes vencidos/pendentes.')
@click.option('--done', 'done_id', default=None, help='⏰ Conclui lembrete por id ou nome.')
@click.option('--tasks', '-t', is_flag=True, help='⏰ Tabela completa de tarefas agendadas (todas as notas).')
@click.option('--json', 'as_json', is_flag=True, help='📊 Saída JSON p/ cruzamento de dados futuro.')
@click.option('--gui', '-g', is_flag=True, help='📊 Interface grafica do usuario.')
def note(name, show_list, term, quick, show, npp, delete, when_date, due, done_id, tasks, as_json, gui):
    """📝 Notas de terminal (experimental). Guarda em .doxoade/note/."""
    from .agenda import add_item, due_items, mark_done, parse_when, render_reminder, complete_task
    root = Path(_find_project_root(os.getcwd()))
    d = _note_dir(root)

    from .agenda import sync_done_to_history
    sync_done_to_history(root, d)

    if gui:
        from .note_gui import launch_notes_gui
        launch_notes_gui(root)
        return

    if due or tasks:
        from .agenda import due_tasks, all_tasks, render_task_table
        items = due_tasks(d) if due else all_tasks(d)
        if as_json:
            import json as _json
            click.echo(_json.dumps(items, ensure_ascii=False, indent=2))
            return
        title = 'TAREFAS VENCIDAS' if due else 'TABELA DE TAREFAS AGENDADAS'
        click.echo(render_task_table(items, title=title))
        return
    if done_id:
        rec = complete_task(root, done_id)
        if rec:
            if rec.get('already'):
                click.echo(f'✔ tarefa #{rec["id"]} já estava concluída (histórico intacto).')
            else:
                click.echo(f'{Fore.GREEN}✔ tarefa #{rec["id"]} marcada [x] e registrada no histórico.{Style.RESET_ALL}')
        else:
            click.echo(f'✗ não encontrado: {done_id}')
        return
    if term:
        _render_search(d, term)
        return
    if show_list or not name:
        _render_list(d)
        return

    slug = _slug(name)
    target = d / f'{slug}.md'
    if not target.exists():
        close = difflib.get_close_matches(slug, [p.stem for p in _all_notes(d)], n=3, cutoff=0.6)
        if close:
            click.echo(f'{Fore.YELLOW} Ganesha: nome parecido com: {", ".join(close)}{Style.RESET_ALL}')
            if click.confirm(f'   Abrir "{close[0]}" em vez de criar "{slug}"?', default=False):
                slug, target = close[0], d / f'{close[0]}.md'

    if delete:
        if target.exists() and click.confirm(f'⚠️ Remover nota "{slug}"?'):
            target.unlink()
            click.echo(f'{Fore.GREEN}✔ nota removida{Style.RESET_ALL}')
        else:
            click.echo(f'{Fore.YELLOW}nota "{slug}" não existe{Style.RESET_ALL}')
        return

    if not target.exists():
        _save(target, [f'# {name}', ''])
        click.echo(f'{Fore.GREEN}📝 nota "{slug}" criada{Style.RESET_ALL}')

    if when_date:
        w = parse_when(when_date)
        if not w:
            click.echo(f'✗ data inválida: {when_date} (use 2026-08-10, +3d, +2w, amanha)')
            return
        item = add_item(root, slug, quick or name, w)
        click.echo(f'⏰ agendado [{item["id"]}] para {w}: {item["text"][:60]}')
        if quick is not None:
            lines = _load(target)
            lines.append(quick)
            _save(target, lines)
        return

    if npp:
        import subprocess
        subprocess.Popen(['notepad++', '-nosession', str(target)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if quick is not None:
        lines = _load(target)
        lines.append(quick)
        _save(target, lines)
        click.echo(f'{Fore.GREEN}+ linha adicionada{Style.RESET_ALL} {Fore.DIM}({len(lines)} linhas){Style.RESET_ALL}')
        return
    if show:
        for l in _load(target):
            click.echo(l)
        return
    _editor_loop(target, slug, root)
    
