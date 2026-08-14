# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/benzaiten_gui/softclub/notes_app.py
"""SOFTCLUB NOTES — Fase 3: render + layout. O teclado vive em editor_input.py."""
import os
import sys
import hashlib
import traceback
import threading
import time

from pathlib import Path
from .renderer import SoftRenderer
from .bg_gen import render_background
from .palette import THEMES, photo_theme_for
from . import kit
from .editor_input import make_on_key, sel_range, save_note
from . import bg_image
from . import bg_rotator
from . import calendar_view as calv
from .events import EventBus
from doxoade.tools.filesystem import _find_project_root

_MEM_CACHE = {}


def _mem_put(name, data):
    _MEM_CACHE[name] = data
    while len(_MEM_CACHE) > 3:
        _MEM_CACHE.pop(next(iter(_MEM_CACHE)))


TOPBAR_H, STATUS_H = 30, 24
SIDE_W = 230
POTE_W = 250
LINE_H = 20

OLD_HELP_LINES = [
    ('SOFTCLUB — GUIA RÁPIDO', 'title'),
    ('NAV    ↑/↓ notas · ENTER editar · h/? ajuda', ''),
    ('       t tema · r seed · q sair', ''),
    ('EDIT   setas movem · digitar edita a linha', ''),
    ('       ENTER nova linha · CTRL+L linha abaixo', ''),
    ('       CTRL+S salvar · ESC sair (pergunta se sujo)', ''),
    ('       SHIFT+setas seleciona', ''),
    ('       CTRL+C copiar · CTRL+X cortar · CTRL+V colar', ''),
    ('       CTRL+D apagar seleção/linha · TAB foca o pote', ''),
    ('POTE   digitar/BACKSPACE edita · CTRL+V cola · TAB volta', ''),
    ('F1     abre/fecha esta ajuda', ''),
    ('NOTAS  CTRL+N nova · CTRL+W p/ lixeira (salva antes)', ''),
    ('       CTRL+R restaura · TAB editor→pote→lixeira', ''),
    ('       SHIFT+DEL purga (manual — preservação)', ''),
    ('STATUS ● não salvo · ↻ mudou fora (CTRL+S vence)', ''),
    ('FUNDO  b próximo fundo · drop adota + persiste', ''),
    ('       rotação auto 10 min de wallpaper/ (prefs: rotation_min)', ''),
    ('CAL    c/F2 abre/fecha · setas dia · [ ] mês', ''),
    ('       ENTER abre nota da tarefa · clique seleciona', ''),
    ('TBAR   prefs titlebar: title c/ {nota}/{tema} · border/caption/dark', ''),
]

HELP_PAGES = [
    [
        ('SOFTCLUB — GUIA RÁPIDO (1/4)', 'title'),
        ('NAV    ↑/↓ notas · ENTER editar · q sair', ''),
        ('       t tema · r seed · h/? ajuda · F1 páginas', ''),
        ('EDIT   setas movem · digitar edita a linha', ''),
        ('       ENTER nova linha · CTRL+L linha abaixo', ''),
        ('       CTRL+S salvar · ESC sair (pergunta se sujo)', ''),
        ('MOUSE  clique foca painel · posiciona cursor', ''),
        ('       arrastar seleciona · clique simples limpa', ''),
    ],
    [
        ('SELEÇÃO & CLIPBOARD (2/4)', 'title'),
        ('SHIFT+setas seleciona · CTRL+A tudo', ''),
        ('CTRL+C copiar · CTRL+X cortar · CTRL+V colar', ''),
        ('CTRL+D apaga seleção/linha', ''),
        ('CTRL+Z undo · CTRL+Y redo (editor e pote)', ''),
        ('POTE   TAB foca · digitar edita · CTRL+V cola', ''),
        ('       persiste sozinho em .doxoade/note/.pote.md', ''),
    ],
    [
        ('NOTAS & LIXEIRA (3/4)', 'title'),
        ('CTRL+N nova nota (input na statusbar)', ''),
        ('CTRL+W manda p/ lixeira (salva antes)', ''),
        ('CTRL+R restaura · TAB editor→pote→lixeira', ''),
        ('SHIFT+DEL purga (manual — preservação)', ''),
        ('STATUS ● não salvo · ↻ mudou fora (CTRL+S vence)', ''),
    ],
    [
        ('FUNDO & CALENDÁRIO (4/4)', 'title'),
        ('FUNDO  drop adota + persiste · b próximo', ''),
        ('       rotação auto 10 min de wallpaper/', ''),
        ('CAL    F2 abre/fecha · setas dia · [ ] mês', ''),
        ('       ENTER abre nota da tarefa · clique seleciona', ''),
        ('TBAR   arrastar move · 2x clique maximiza · – □ ✕', ''),
    ],
]
HELP_LINES = HELP_PAGES[0]   # compat

SOFTCLUB_DEBUG = os.environ.get("SOFTCLUB_DEBUG") == "1"


def _dbg(msg):
    if SOFTCLUB_DEBUG:
        sys.stderr.write(f"[SOFTCLUB-DEBUG] {msg}\n")
        sys.stderr.flush()


def _cache_path(theme_name, w, h, seed, key):
    d = Path(_find_project_root(os.getcwd())) / '.doxoade' / 'benzaiten' / 'softclub'
    d.mkdir(parents=True, exist_ok=True)
    return d / f'scb_{theme_name}_{w}x{h}_{seed}_{key}.raw'


def _load_or_render(theme_name, w, h, seed):
    """BGRA pronto: cache em disco (instantâneo) ou render único (e grava)."""
    theme = THEMES[theme_name if theme_name in THEMES else 'night']
    key = hashlib.sha256(repr(theme).encode()).hexdigest()[:8]
    p = _cache_path(theme_name, w, h, seed, key)
    need = w * h * 4
#    from .bg_image import try_image_background
#    _img = try_image_background(w, h)
#    if _img is not None and len(_img) == need:
#        return _img
    hit = _MEM_CACHE.get(p.name)
    if hit is not None and len(hit) == need:
        return hit
    if p.exists() and p.stat().st_size == need:
        _dbg(f"cache hit: {p.name}")
        _mem_put(p.name, p.read_bytes())
        return _MEM_CACHE[p.name]
    _dbg(f"rendering {w}x{h} seed={seed}")
    bgra = render_background(theme, w, h, seed, bgra=True)
    _mem_put(p.name, bgra)
    try:
        p.write_bytes(bgra)
        _dbg(f"cached: {p.name}")
    except OSError as e:
        _dbg(f"cache write failed: {e}")
    return bgra


def _glass_rects(W, H):
    return [
        (0, 0, W, TOPBAR_H),
        (0, TOPBAR_H, SIDE_W, H - TOPBAR_H - STATUS_H),
        (W - POTE_W, TOPBAR_H, POTE_W, H - TOPBAR_H - STATUS_H),
        (0, H - STATUS_H, W, STATUS_H),
    ]


_DETAIL_CACHE = {}
_AGENDA_CACHE = {}

def _note_detail(root_s, name):
    """api_get_note com TTL 2s — hot-path do paint sem disco."""
    now = time.time()
    key = (root_s, name)
    hit = _DETAIL_CACHE.get(key)
    if hit is not None and now - hit[0] < 2.0:
        return hit[1]
    from doxoade.commands.note_systems.note_api import api_get_note
    val = api_get_note(root_s, name)
    _DETAIL_CACHE[key] = (now, val)
    return val

def _agenda_cached(root_s):
    """api_agenda com TTL 2s — scan de tarefas fora do paint."""
    now = time.time()
    hit = _AGENDA_CACHE.get(root_s)
    if hit is not None and now - hit[0] < 2.0:
        return hit[1]
    from doxoade.commands.note_systems.note_api import api_agenda
    val = api_agenda(root_s)
    _AGENDA_CACHE[root_s] = (now, val)
    return val

def run_notes_gui(root, theme_name='night', seed=7, width=800, height=600):
    # ── FASE 1: prefs persistentes (Q1: drop > env > prefs) ──
    from . import prefs as _sc_prefs
    _pf = _sc_prefs.load_prefs(root)
    theme_name = _pf.get('theme', theme_name)
    seed = _pf.get('seed', seed)
    bg_image.set_prefs_bg(_pf.get('bg_path'))

    if os.environ.get('DXGUI_VERBOSE') == '1':
        print(f'[SOFTCLUB] run_notes_gui pid={os.getpid()} theme={theme_name}')
    _dbg("starting run_notes_gui")
    r = SoftRenderer('SoftClub Notes', width, height)
    _tb_cfg = _pf.get('titlebar') or {}
    _frameless = _tb_cfg.get('style', 'custom') != 'native'
    if _frameless:
        r.set_frameless(1)
    _dbg(f"renderer created: {r}")
    bg_image.set_repaint_fn(getattr(r, "request_repaint_safe", r.request_repaint))
    try:
        try:
            cw, ch = r.client_size()
            _dbg(f"client_size: {cw}x{ch}")
        except Exception as e:
            _dbg(f"client_size failed: {e}")
            cw, ch = width, height

        state = {
            'theme': theme_name if theme_name in THEMES else 'night',
            'seed': seed,
            'size': (cw or width, ch or height),
            'notes': [], 'sel': 0,
            'mode': 'nav',                                   # 'nav' | 'edit'
            'edit_lines': [],
            'edit_cursor_line': 0, 'edit_cursor_col': 0,
            'edit_selection_start': None,
            'dirty': False,
            'pote_lines': [], 'pote_w': POTE_W,
            'pote_cursor_line': 0, 'pote_cursor_col': 0,
            'focus': 'editor',                               # 'editor' | 'pote'
            '_frameless': _frameless, '_tb_cfg': _tb_cfg, '_tb_btns': {},
        }

        bus = EventBus()
        state['_paint_requested'] = False
        state['_paint_reason'] = 'init'

        def load_notes():
            from doxoade.commands.note_systems.note_api import api_list_notes
            try:
                state['notes'] = api_list_notes(str(root))
            except Exception as e:
                _dbg(f"load_notes failed: {e}")
                state['notes'] = []
            try:
                from doxoade.commands.note_systems.note_api import api_list_trash
                state['trash'] = api_list_trash(str(root))
            except Exception:
                state['trash'] = []
        if state['sel'] >= len(state['notes']) and state['notes']:
                state['sel'] = 0

        def paint(w=None, h=None):
            w = w or state['size'][0]
            h = h or state['size'][1]
            state['size'] = (w, h)

            # Tema: base + (se foto) foto-tema harmonizado
            th = THEMES[state['theme']]
            photo = False
            if bg_image.custom_active():
                pal = bg_image.get_image_palette()
                if pal:
                    _ = photo_theme_for(state['theme'], pal)  # aquece cache de temas
                    dom = pal.get('dominant') or [pal.get('avg', (128, 128, 128))]
                    kit.EDGE_TINT = tuple(int(c) for c in dom[0])
                else:
                    kit.EDGE_TINT = None

            if bg_image.custom_active():
                variant = 'night' if state['theme'] == 'night' else 'day'
                res = bg_image.render_full(w, h, variant)
                if res is None:
                    # fallback procedural imediato (variante ainda processando)
                    bgra = _load_or_render(state['theme'], w, h, state['seed'])
                    r.present(bgra, w, h)
                    bg_image.note_presented(bgra, w, h)
                else:
                    bgra, bw, bh = res
                    r.present(bgra, bw, bh)
                draw_ui()
                _sync_win_title()
                return
            bgra = _load_or_render(state['theme'], w, h, state['seed'])
            r.present(bgra, w, h)
            draw_ui()
            _sync_win_title()

        def request_paint(reason="ui"):
            state['_paint_requested'] = True
            state['_paint_reason'] = reason

        def flush_paint():
            if state.pop('_paint_requested', False):
                paint()
                bus.emit("paint:frame", state.get('_paint_reason', 'ui'))
        def _bg_pump():
            request_paint('bg')
            flush_paint()
        r.on_repaint(_bg_pump)

        def _sheen_tick():
            while True:
                time.sleep(0.1)
                r.request_repaint_safe()
        if kit.FX_ENABLED:
            threading.Thread(target=_sheen_tick, daemon=True).start()

        def draw_ui():
            from doxoade.commands.note_systems.note_api import api_get_note, api_agenda
            from doxoade.commands.note_systems.agenda import classify_when, _MARK
            th = THEMES[state['theme']]
            photo = False
            pal = None
            if bg_image.custom_active():
                pal = bg_image.get_image_palette()
                if pal:
                    th = photo_theme_for(state['theme'], pal)
                    photo = True
            W, H = state['size']
            kit.GLASS_PAL = pal if photo else None
            kit.GLASS_BORDERS_ONLY = photo
            notes = state['notes']
            focus = state.get('focus', 'editor')
            night = state['theme'] == 'night'
            tb_cfg = _pf.get('titlebar') or {}
            tb_dark = tb_cfg.get('dark')
            tb_border = tuple(tb_cfg['border']) if tb_cfg.get('border') else th.panel_edge
            tb_caption = tuple(tb_cfg['caption']) if tb_cfg.get('caption') else th.panel
            if tb_dark is None:
                tb_dark = night
            tb_key = (state['theme'], bool(photo), tb_border, tb_caption, bool(tb_dark))
            if state.get('_tb_key') != tb_key:
                state['_tb_key'] = tb_key
                r.style_titlebar(bool(tb_dark), tb_border, tb_caption)
            pivot_bg   = (100, 80, 100)  if night else (180, 200, 220)
            pivot_fg   = (235, 238, 246) if night else (34, 42, 54)
            sel_bg     = (70, 95, 130)   if night else (150, 175, 210)
            cursor_rgb = th.accent2 if night else th.accent

            # ── TOPBAR (frameless: o fundo faz parte do GUI) ──
            kit.panel_gradient(r, 0, 0, W, TOPBAR_H, th, steps=5)
            tb = state.get('_tb_cfg') or {}
            nota = notes[state['sel']]['name'] if notes else '—'
            tpl = tb.get('title') or 'softclub · {nota}'
            icon = tb.get('icon') or '✎'
            title = (tpl.replace('{nota}', nota).replace('{tema}', state['theme'])
                     + ('  ●' if state.get('dirty') else '')
                     + ('  ↻' if state.get('external') else ''))
            kit.draw_text(r, 10, 8, f'{icon} {title}',
                          th.ink if photo else th.accent2, 14, 2)
            if state.get('_frameless'):
                bw = 34
                btns = {'min':   (W - 3 * bw, 0, bw, TOPBAR_H),
                        'max':   (W - 2 * bw, 0, bw, TOPBAR_H),
                        'close': (W - bw,     0, bw, TOPBAR_H)}
                state['_tb_btns'] = btns
                hov = state.get('_tb_hover')
                for name, (bx, by, bw2, bh2) in btns.items():
                    if hov == name:
                        if name == 'close':
                            kit.fill_rect(r, bx, by + 1, bw2, bh2 - 1,
                                          (196, 72, 72) if night else (206, 84, 84))
                        else:
                            kit.fill_rect(r, bx, by + 1, bw2, bh2 - 1,
                                          kit.lerp_color(th.panel_edge, (250, 252, 255), 0.25))
                    kit.ring(r, bx, by + 1, bw2, bh2 - 2,
                             kit.lerp_color(th.panel, th.ink_muted, 0.30), th.bottom)
                kit.draw_text(r, W - 3 * bw + 12, 7, '–', th.ink, 14, 1)
                kit.draw_text(r, W - 2 * bw + 11, 7, '□', th.ink, 12, 1)
                kit.draw_text(r, W - bw + 11, 7, '✕',
                              (250, 240, 240) if hov == 'close' else (226, 106, 106), 13, 1)
            else:
                kit.draw_text(r, W - 110, 9,
                              state['theme'] + ('·foto' if photo else ''),
                              th.ink_muted, 12, 1)

            # ── SIDEBAR ──
            kit.panel_gradient(r, 0, TOPBAR_H, SIDE_W, H - TOPBAR_H - STATUS_H, th, steps=8)
            for i, n in enumerate(notes[:24]):
                y = TOPBAR_H + 10 + i * LINE_H
                if i == state['sel']:
                    kit.fill_rect(r, 2, y - 4, SIDE_W - 4, 18, th.panel_edge)
                    kit.draw_text(r, 10, y - 1, n['name'], th.ink, 13, 1)
                else:
                    kit.draw_text(r, 10, y - 1, n['name'], th.ink_muted, 13, 1)

            ty_tr = TOPBAR_H + 10 + min(len(notes), 24) * LINE_H + 8
            trash = state.get('trash') or []
            kit.draw_text(r, 10, ty_tr, f'lixeira ({len(trash)})',
                          th.accent2 if state.get('focus') == 'trash' else th.ink_muted, 12, 2)
            ty_tr += 16
            for i, t in enumerate(trash[:8]):
                if state.get('focus') == 'trash' and i == state.get('trash_sel', 0):
                    kit.fill_rect(r, 2, ty_tr - 3, SIDE_W - 4, 15, th.panel_edge)
                    kit.draw_text(r, 10, ty_tr, t['name'], th.ink, 12, 1)
                else:
                    kit.draw_text(r, 10, ty_tr, t['name'], th.ink_muted, 12, 1)
                ty_tr += 15
            # ── MAIN ─
            x0 = SIDE_W + 14
            pote_w = state.get('pote_w', POTE_W)
            band_w = W - pote_w - x0 + 5
            if notes and state['sel'] < len(notes):
                note_name = notes[state['sel']]['name']
                y = TOPBAR_H + 12
                kit.draw_text(r, x0, y, note_name, th.accent, 15, 1)
                y += 24
                if state['mode'] == 'nav':
                    det = _note_detail(str(root), note_name)
                    for line in (det.get('lines') or [])[:20]:
                        kit.draw_text(r, x0, y, line[:92], th.ink, 13, 1)
                        y += 17
                    ag = _agenda_cached(str(root))
                    y += 12
                    kit.draw_text(r, x0, y, 'agenda', th.accent2, 13, 2)
                    y += 18
                    for t in ag['tasks'][:5]:
                        mark = _MARK[classify_when(t['when'], t.get('done'))]
                        kit.draw_text(r, x0, y, f"{mark} {t['when']}  {t['text'][:58]}",
                                      th.ink_muted, 12, 1)
                        y += 16
                else:
                    edit_lines = state.get('edit_lines', [])
                    cur = state.get('edit_cursor_line', 0)
                    cur_col = state.get('edit_cursor_col', 0)
                    wrap = state.get('wrap', True)
                    wrap_w = max(24, (band_w - 16) // 7)
                    visual = []
                    for ali, line in enumerate(edit_lines):
                        if wrap and len(line) > wrap_w:
                            for s in range(0, len(line), wrap_w):
                                visual.append((ali, line[s:s + wrap_w], s))
                        else:
                            visual.append((ali, line, 0))
                    max_lines = (H - TOPBAR_H - STATUS_H - 40) // 17
                    cv = next((i for i, v in enumerate(visual) if v[0] == cur
                               and v[2] <= cur_col <= v[2] + len(v[1])), min(cur, len(visual) - 1))
                    scroll = state.get('scroll_v', 0)
                    if cv < scroll: scroll = cv
                    if cv >= scroll + max_lines: scroll = cv - max_lines + 1
                    state['scroll_v'] = max(0, scroll)
                    sel = sel_range(state)
                    for i, (ali, chunk, start_col) in enumerate(visual[scroll:scroll + max_lines]):
                        vi = scroll + i
                        row_y = y
                        chunk_end = start_col + len(chunk)
                        is_current = (ali == cur and focus != 'pote')
                        is_selected = bool(sel and sel[0][0] <= ali <= sel[1][0])
                        if is_current:
                            kit.line_gradient(r, x0 - 5, row_y - 3, band_w, 17, th, mode='active')
                        elif is_selected:
                            kit.fill_rect(r, x0 - 5, row_y - 3, band_w, 17, sel_bg)
                        if is_current:
                            kit.draw_text(r, x0, row_y, chunk, pivot_fg, 13, 1)
                            caret_here = (start_col <= cur_col < chunk_end
                                          or (cur_col == chunk_end and vi == len(visual) - 1))
                            if caret_here:
                                prefix = chunk[:max(0, cur_col - start_col)]
                                px_ = kit.measure_text(r, prefix, 13, 1)
                                kit.fill_rect(r, x0 + max(0, px_) + 1, row_y - 1, 2, 14, cursor_rgb)
                        else:
                            kit.draw_text(r, x0, row_y, chunk, th.ink, 13, 1)
                        y += 17

            # ── POTE ──
            pote_x = W - pote_w
            if focus == 'pote':
                kit.panel_gradient(r, pote_x, TOPBAR_H, pote_w, H - TOPBAR_H - STATUS_H,
                       th, steps=8, edge=th.accent)
                kit.draw_text(r, pote_x + 10, TOPBAR_H + 10, 'POTE (FOCO)', th.accent2, 14, 2)
            else:
                kit.panel_gradient(r, pote_x, TOPBAR_H, pote_w, H - TOPBAR_H - STATUS_H,
                       th, steps=8)
                kit.draw_text(r, pote_x + 10, TOPBAR_H + 10, 'pote', th.ink_muted, 14, 1)
            y = TOPBAR_H + 30
            pl = state.get('pote_lines', [])
            p_a = state.get('pote_selection_start')
            p_c = (state.get('pote_cursor_line', 0), state.get('pote_cursor_col', 0))
            p_lo, p_hi = (min(p_a, p_c), max(p_a, p_c)) if p_a else (None, None)
            for i, line in enumerate(pl[:20]):
                if p_lo is not None and p_lo[0] <= i <= p_hi[0]:
                    kit.fill_rect(r, pote_x + 5, y - 3, pote_w - 10, 15, sel_bg)
                    kit.draw_text(r, pote_x + 10, y, line[:30], th.ink, 12, 1)
                elif focus == 'pote' and i == state.get('pote_cursor_line', 0):
                    kit.fill_rect(r, pote_x + 5, y - 3, pote_w - 10, 15, pivot_bg)
                    kit.draw_text(r, pote_x + 10, y, line[:30], pivot_fg, 12, 1)
                else:
                    kit.draw_text(r, pote_x + 10, y, f"{i+1:>2}. {line[:30]}",
                                  th.ink_muted, 12, 1)
                y += 15

            # ── STATUSBAR ──
            kit.panel_gradient(r, 0, H - STATUS_H, W, STATUS_H, th, steps=4)
            if state['mode'] == 'edit':
                hints = (f"Ln {state.get('edit_cursor_line', 0)+1}, "
                         f"Col {state.get('edit_cursor_col', 0)+1} · ESC salvar · "
                         f"↑↓←→ · Tab pote · Ctrl+S/L/C/V/X/D")
            else:
                hints = '↑/↓ notas · ENTER editar · t tema · r seed · q sair'
            if state['mode'] == 'new':
                hints = f"nova nota: {state.get('new_buffer', '')}█  (ENTER cria · ESC cancela)"
            elif state.get('focus') == 'trash':
                hints = ('LIXEIRA ↑/↓ · ENTER/Ctrl+R restaura · '
                         'SHIFT+DEL purga · TAB volta')
            kit.draw_text(r, 10, H - STATUS_H + 6, hints, th.ink_muted, 12, 1)

            # ── OVERLAY DE AJUDA (F1 / h / ?) ──
            if state.get('mode') == 'confirm':
                kit.panel_gradient(r, W // 2 - 200, H // 2 - 46, 400, 92, th,
                                     solid=True, edge=th.panel_edge)
                kit.draw_text(r, W // 2 - 180, H // 2 - 28,
                                'salvar alterações?  y / N', (232, 170, 0), 15, 1)
                kit.draw_text(r, W // 2 - 180, H // 2 + 2,
                                'y salva · N descarta · ESC cancela',
                                th.ink_muted, 12, 1)
            if state.get('show_help'):
                pages = HELP_PAGES
                pg = max(0, min(state.get('help_page', 0), len(pages) - 1))
                hw = min(720, W - 60)
                hh = 300
                hx = (W - hw) // 2
                hy = (H - hh) // 2
                kit.panel_gradient(r, hx, hy, hw, hh, th, steps=8, edge=th.accent, solid=True)
                ty = hy + 12
                for txt, kind in pages[pg]:
                    if kind == 'title':
                        kit.draw_text(r, hx + 16, ty, txt, th.accent2, 15, 2)
                        ty += 26
                    else:
                        kit.draw_text(r, hx + 16, ty, txt, th.ink, 12, 1)
                        ty += 21
                kit.draw_text(r, hx + 16, hy + hh - 24,
                              f'←/→ página {pg + 1}/{len(pages)} · F1 fecha',
                              th.ink_muted, 11, 1)

            if state.get('show_cal'):
                ag = _agenda_cached(str(root))
                tbd = {}
                for t in ag.get('tasks', []):
                    tbd.setdefault(t.get('when'), []).append(t)
                cx, cy, cw2, ch2 = calv.cal_rect(W, H, state.get('pote_w', POTE_W))
                calv.draw_calendar(r, cx, cy, cw2, ch2, state, th, tbd)
                    
        # ── Teclado: domínio do editor_input (arquivo próprio) ──
        def _save_prefs_now():
            try:
                _sc_prefs.save_prefs(root, {
                    'theme': state['theme'], 'seed': state['seed'],
                    'bg_path': _pf.get('bg_path'),
                })
            except Exception as e:
                _dbg(f'prefs save falhou: {e}')

        def _sync_win_title():
            tb_cfg = _pf.get('titlebar') or {}
            tpl = tb_cfg.get('title') or '📝 softclub · {nota}'
            nota = state['notes'][state['sel']]['name'] if state['notes'] else '—'
            t = tpl.replace('{nota}', nota).replace('{tema}', state['theme'])
            if state.get('dirty'):
                t = '● ' + t
            if t != state.get('_win_title'):
                state['_win_title'] = t
                r.set_title(t)

        def _note_path():
            if not state.get('notes'):
                return None
            try:
                from doxoade.commands.note_systems.note_cmd import _note_dir, _slug
                name = state['notes'][state['sel']]['name']
                return _note_dir(Path(root)) / ('%s.md' % _slug(name))
            except Exception:
                return None

        def _sync_external():
            p = _note_path()
            if p is None:
                state['external'] = False
                return
            try:
                m = p.stat().st_mtime
            except OSError:
                state['external'] = False
                return
            if not state.get('dirty'):
                state['external'] = False
                state['note_mtime'] = m
            else:
                base = state.get('note_mtime')
                state['external'] = bool(base is not None and m != base)

        def _invalidate_detail():
            if state.get('notes'):
                _DETAIL_CACHE.pop((str(root), state['notes'][state['sel']]['name']), None)

        def _close_confirm(apply):
            act = state.get('confirm_action')
            state['confirm_action'] = None
            if act == 'exit_edit':
                state['mode'] = 'nav'
                state['edit_selection_start'] = None
                if not apply and state.get('notes'):
                    _invalidate_detail()
                    det = _note_detail(str(root), state['notes'][state['sel']]['name'])
                    state['edit_lines'] = det.get('lines') or ['']
            else:
                state['mode'] = 'edit'
            _sync_external()

        def _confirm_key(vk, text):
            if text in ('y', 'Y'):
                save_note(root, state)
                _close_confirm(apply=True)
            elif text in ('n', 'N'):
                state['dirty'] = False
                _close_confirm(apply=False)
            elif vk == 0x1B:
                state['confirm_action'] = None
                state['mode'] = 'edit'

        _last_pref = {'theme': state['theme'], 'seed': state['seed']}

        def _post_key():
            if (state['theme'] != _last_pref['theme']
                    or state['seed'] != _last_pref['seed']):
                _last_pref['theme'], _last_pref['seed'] = state['theme'], state['seed']
                _save_prefs_now()
            _sync_external()

        _raw_on_key = make_on_key(state, r, root, request_paint, load_notes)

        def on_key(vk, text):
            bus.emit("input:key", {"vk": vk, "text": text})
            state['_paint_requested'] = False
            try:
                if state.get('mode') == 'confirm':
                    _confirm_key(vk, text)
                    return
                if (state.get('mode') == 'edit' and state.get('dirty')
                        and state.get('focus') == 'editor' and vk == 0x1B):
                    state['confirm_action'] = 'exit_edit'
                    state['mode'] = 'confirm'
                    return
                _raw_on_key(vk, text)
            finally:
                _post_key()
                _sync_pote()
                flush_paint()

        def handle_resize(w, h):
            try:
                state['size'] = (w, h)
                request_paint("resize")
                flush_paint()
            except Exception as e:
                _dbg(f"resize paint failed: {e}")

        def handle_drop(path):
            _dbg(f'drop handle: {path!r}')
            _adopt_bg(path)
            bus.emit('bg:dropped', {'path': path})
            w, h = state['size']
            variant = 'night' if state['theme'] == 'night' else 'day'
            bg_image.fade_to_path(str(path), w, h, variant)
            request_paint('drop')

        def _open_current_note():
            if not state['notes']:
                return
            from doxoade.commands.note_systems.note_api import api_get_note
            det = api_get_note(str(root), state['notes'][state['sel']]['name'])
            state['edit_lines'] = det.get('lines') or ['']
            state['mode'] = 'edit'
            state['edit_cursor_line'] = 0
            state['edit_cursor_col'] = 0
            state['edit_selection_start'] = None
            state['focus'] = 'editor'

        def _in_editor(x, y):
            W, H = state['size']
            pote_x = W - state.get('pote_w', POTE_W)
            return (SIDE_W <= x < pote_x) and (TOPBAR_H <= y < H - STATUS_H)

        def _tb_hit(x, y):
            for name, (bx, by, bw2, bh2) in (state.get('_tb_btns') or {}).items():
                if bx <= x < bx + bw2 and by <= y < by + bh2:
                    return name
            return None

        def _editor_cell(x, y):
            y0 = TOPBAR_H + 36
            x0 = SIDE_W + 14
            visual = _visual_lines()
            if not visual:
                return 0, 0
            scroll = state.get('scroll_v', 0)
            vi = max(0, min((y - y0) // 17 + scroll, len(visual) - 1))
            ali, scol, clen = visual[vi]
            return ali, scol + max(0, min(clen, (x - x0) // 8))

        _md = {'cell': None}

        def handle_click(x, y):
            W, H = state['size']
            pote_x = W - state.get('pote_w', POTE_W)
            if y < TOPBAR_H and state.get('_frameless'):
                btns = state.get('_tb_btns') or {}
                def _in(rc):
                    return rc and rc[0] <= x < rc[0] + rc[2] and rc[1] <= y < rc[1] + rc[3]
                if _in(btns.get('close')):
                    r.win_close(); return
                if _in(btns.get('max')):
                    r.win_maximize(); return
                if _in(btns.get('min')):
                    r.win_minimize(); return
                now = time.time()
                last = state.get('_tb_last_click')
                if last and (now - last[0]) < 0.35 and abs(last[1] - x) < 8 \
                        and abs(last[2] - y) < 8:
                    state['_tb_last_click'] = None
                    r.win_maximize(); return
                state['_tb_last_click'] = (now, x, y)
                if y < TOPBAR_H:
                    hit = _tb_hit(x, y)
                    if hit == 'close':
                        r.win_close(); return
                    if hit == 'max':
                        r.win_maximize(); return
                    if hit == 'min':
                        r.win_minimize(); return
                r.start_drag(); return
            if state.get('show_cal'):
                cx, cy, cw2, ch2 = calv.cal_rect(W, H, state.get('pote_w', POTE_W))
                if cx <= x < cx + cw2 and cy <= y < cy + ch2:
                    iso = calv.hit_day(cx, cy, cw2, x, y, state)
                    if iso:
                        state['cal_sel'] = iso
                        state['focus'] = 'cal'
                    request_paint('cal'); flush_paint()
                    return
            if _in_editor(x, y) or y < TOPBAR_H or y >= H - STATUS_H:
                return
            if x < SIDE_W:
                ty_tr = TOPBAR_H + 10 + min(len(state['notes']), 24) * LINE_H + 8
                if y < ty_tr:
                    i = (y - (TOPBAR_H + 6)) // LINE_H
                    if 0 <= i < len(state['notes']):
                        state['sel'] = i
                        state['focus'] = 'editor'
                        if state['mode'] == 'edit':
                            _open_current_note()
                else:
                    ti = int((y - (ty_tr + 16)) // 15)
                    trash = state.get('trash') or []
                    if 0 <= ti < min(len(trash), 8):
                        state['focus'] = 'trash'
                        state['trash_sel'] = ti
                request_paint('click'); flush_paint()
                return
            if x >= pote_x:
                state['focus'] = 'pote'
                lines = state.get('pote_lines', [])
                i = (y - (TOPBAR_H + 30)) // 15
                state['pote_cursor_line'] = max(0, min(i, len(lines) - 1)) if lines else 0
                state['pote_cursor_col'] = min(max(0, (x - (pote_x + 10)) // 8),
                                               len(lines[state['pote_cursor_line']]) if lines else 0)
                state['pote_selection_start'] = None
                request_paint('click'); flush_paint()

        def handle_mouse(x, y, buttons):
            if buttons == 0 and _md['cell'] is None:
                hov = _tb_hit(x, y) if (x >= 0 and y >= 0 and y < TOPBAR_H) else None
                if state.get('_tb_hover') != hov:
                    state['_tb_hover'] = hov
                    request_paint('hover'); flush_paint()
                return
            if buttons == 1 and _md['cell'] is None and not _in_editor(x, y):
                return
            if buttons == 1 and _md['cell'] is None:
                state['focus'] = 'editor'
                if state['mode'] == 'nav':
                    _open_current_note()
                ali, col = _editor_cell(x, y)
                state['edit_cursor_line'], state['edit_cursor_col'] = ali, col
                state['edit_selection_start'] = (ali, col)
                _md['cell'] = (ali, col)
                request_paint('mouse'); flush_paint()
                return
            if buttons == 1 and _md['cell'] is not None:
                ali, col = _editor_cell(x, y)
                state['edit_cursor_line'], state['edit_cursor_col'] = ali, col
                if (ali, col) != _md['cell']:
                    state['edit_selection_start'] = _md['cell']
                request_paint('mouse'); flush_paint()
                return
            if buttons == 0 and _md['cell'] is not None:
                ali, col = _editor_cell(x, y)
                if (ali, col) == _md['cell']:
                    state['edit_selection_start'] = None
                _md['cell'] = None
                request_paint('mouse'); flush_paint()

        if hasattr(r, 'on_click'):
            r.on_click(handle_click)
        if hasattr(r, 'on_mouse'):
            r.on_mouse(handle_mouse)

        def _visual_lines():
            W, H = state['size']
            pote_w = state.get('pote_w', POTE_W)
            x0 = SIDE_W + 14
            band_w = W - pote_w - x0 + 5
            wrap_w = max(24, (band_w - 16) // 7)
            visual = []
            for ali, line in enumerate(state.get('edit_lines', [])):
                if state.get('wrap', True) and len(line) > wrap_w:
                    for s in range(0, len(line), wrap_w):
                        visual.append((ali, s, min(wrap_w, len(line) - s)))
                else:
                    visual.append((ali, 0, len(line)))
            return visual

        def _pote_path():
            return Path(root) / '.doxoade' / 'note' / '.pote.md'

        def load_pote():
            try:
                p = _pote_path()
                state['pote_lines'] = (p.read_text(encoding='utf-8', errors='replace').splitlines()
                                       if p.exists() else [])
            except Exception:
                state['pote_lines'] = []

        def _adopt_bg(path):
            p = str(path)
            _pf['bg_path'] = p
            try:
                wp = str(bg_rotator.wallpaper_dir())
                if not p.startswith(wp):
                    ex = _pf.get('bg_extras') or []
                    if p not in ex:
                        ex.append(p)
                        _pf['bg_extras'] = ex
            except Exception:
                pass
            _save_prefs_now()
        def _rot_pick():
            pl = bg_rotator.playlist(_pf.get('bg_extras') or [])
            if not pl:
                return None
            cur = _pf.get('bg_path')
            idx = 0
            if cur:
                for i, p in enumerate(pl):
                    if str(p) == str(cur):
                        idx = (i + 1) % len(pl)
                        break
            return pl[idx]
        def _bg_next(path):
            if path is None:
                return
            _adopt_bg(path)
            w, h = state['size']
            variant = 'night' if state['theme'] == 'night' else 'day'
            bg_image.fade_to_path(str(path), w, h, variant)
        state['on_next_bg'] = lambda: _bg_next(_rot_pick())
        bg_rotator.start(_bg_next,
                         lambda: (_pf.get('bg_path'), _pf.get('bg_extras') or []),
                         interval_min=_pf.get('rotation_min', 10))

        def save_pote():
            try:
                p = _pote_path()
                p.parent.mkdir(parents=True, exist_ok=True)
                pl = state.get('pote_lines', [])
                p.write_text('\n'.join(pl) + ('\n' if pl else ''), encoding='utf-8')
            except Exception as e:
                _dbg(f'pote save failed: {e}')

        _pote_last = {'s': None}
        def _sync_pote():
            s = '\n'.join(state.get('pote_lines', []))
            if _pote_last['s'] is None:
                _pote_last['s'] = s
                return
            if s != _pote_last['s']:
                save_pote()
                _pote_last['s'] = s

        load_pote()

        if hasattr(r, 'on_resize'):
            r.on_resize(handle_resize)
        if hasattr(r, 'on_drop'):
            _orig_drop = handle_drop
            def handle_drop(path):
                _orig_drop(path)
                _pf['bg_path'] = bg_image.wanted_bg_path()
                _save_prefs_now()
            r.on_drop(handle_drop)

        r.on_key(on_key)
        
        if hasattr(r, 'on_click'):
            r.on_click(handle_click)
        if hasattr(r, 'on_mouse'):
            r.on_mouse(handle_mouse)
        
        load_notes()

        if not _pf.get('tutorial_seen'):
            try:
                from datetime import date as _d
                from doxoade.commands.note_systems.note_api import api_save_note, api_get_note
                nome = 'bem-vindo'
                if api_get_note(str(root), nome).get('error'):
                    hoje = _d.today().isoformat()
                    api_save_note(str(root), nome, f"""# bem-vindo ao SoftClub
Tudo aqui é markdown puro em .doxoade/note/ — legível no Notepad++
e no terminal (doxoade note).

## essencial
[ ] {hoje} #welcome aperte F1 p/ o guia paginado (←/→ trocam)
- NAV: ↑/↓ escolhe nota · ENTER edita · q sai
- EDIT: digite à vontade · CTRL+S salva · ESC sai (pergunta se sujo)
- pote: TAB foca o rascunho rápido (persiste sozinho)

## notas & lixeira
- CTRL+N nova nota · CTRL+W lixeira (salva antes)
- CTRL+R restaura · SHIFT+DEL purga (só manual)

## fundo & calendário
- arraste uma imagem p/ janela (b troca · rotação auto de wallpaper/)
- F2 calendário · ENTER na tarefa abre a nota dona

## título
- arrastar a barra move · 2x clique maximiza
- prefs: titlebar.title com {{nota}}/{{tema}}

Apague esta nota quando quiser (CTRL+W). Boa! ✎
""")
                load_notes()
                names = [n['name'] for n in state['notes']]
                if nome in names:
                    state['sel'] = names.index(nome)
                state['show_help'] = True
                state['help_page'] = 0
                _sc_prefs.save_prefs(root, {'tutorial_seen': True})
            except Exception as e:
                _dbg(f'tutorial falhou: {e}')

        _dbg("calling startup paint")
        request_paint("startup")
        flush_paint()
        _dbg("startup paint ok (present+draw_ui)")
        bus.emit("app:start", {"theme": state["theme"], "seed": state["seed"]})
        _dbg("calling r.run()")
        r.run()
        _dbg("r.run() returned")

    except BaseException as e:
        _dbg(f"EXCEPTION ({type(e).__name__}): {e}")
        _dbg(traceback.format_exc())
        raise
    finally:
        _dbg("finally block")
        try:
            r.quit()
        except Exception as e:
            _dbg(f"quit failed: {e}")