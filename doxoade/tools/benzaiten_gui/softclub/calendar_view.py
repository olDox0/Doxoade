# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/calendar_view.py
"""SOFTCLUB CALENDAR — painel extra (FASE 7).
Grade mensal + tarefas do dia; contraste adaptativo day/night.
Hoje = LARANJA | selecionado = ESMERALDA | dia c/ tarefa = âmbar.
"""
import calendar
from datetime import date
from . import kit

WD = ('D', 'S', 'T', 'Q', 'Q', 'S', 'S')
ORANGE  = (255, 155, 0)
EMERALD = (38, 188, 95)
AMBER   = (232, 170, 0)   # dia com tarefas
DOT = {'overdue': (232, 90, 90), 'today': ORANGE, 'suspect': AMBER,
       'upcoming': (90, 160, 255), 'future': (120, 130, 150),
       'done': (90, 95, 105)}
PRIO = ('overdue', 'today', 'suspect', 'upcoming', 'future', 'done')


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _lum(c):
    return (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000


def cal_rect(W, H, pote_w, topbar_h=30, status_h=24):
    x = W - pote_w - 16
    y = topbar_h + 8
    w = pote_w + 8
    h = H - status_h - y - 8
    return x, y, w, h


def draw_calendar(r, x, y, w, h, state, th, tasks_by_date):
    kit.panel_gradient(r, x, y, w, h, th, steps=8, solid=True)
    kit.double_bevel(r, x + 1, y + 1, w - 2, h - 2, th, t=1)
    light = _lum(th.panel) > 128          # tema claro? reforça contraste
    yy, mm = state.get('cal_month') or (date.today().year, date.today().month)
    sel = state.get('cal_sel') or date.today().isoformat()
    today = date.today().isoformat()
    kit.draw_text(r, x + 10, y + 8, f'{mm:02d}/{yy}', th.accent2, 14, 2)
    kit.draw_text(r, x + w - 128, y + 10, '[ ] mês · c fecha', th.ink_muted, 11, 1)
    cw = (w - 20) // 7
    gy = y + 34 + 14
    for i, wd in enumerate(WD):
        kit.draw_text(r, x + 10 + i * cw + 4, gy, wd, th.ink_muted, 11, 1)
    gy += 16
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(yy, mm)
    for wk in weeks:
        for i, d in enumerate(wk):
            if not d:
                continue
            iso = f'{yy:02d}-{mm:02d}-{d:02d}'
            cx = x + 10 + i * cw
            marks = [t.get('mark') for t in tasks_by_date.get(iso, [])]
            # 1) base amarelada p/ dia com tarefas
            if marks:
                kit.fill_rect(r, cx, gy - 2, cw - 2, 15,
                              _lerp(th.panel, AMBER, 0.38 if light else 0.20))
            # 2) hoje / selecionado por cima
            if iso == today:
                kit.fill_rect(r, cx, gy - 2, cw - 2, 15,
                              _lerp(th.panel, ORANGE, 0.50 if light else 0.28))
                ring_c = _lerp(ORANGE, (40, 25, 0), 0.35) if light else ORANGE
                kit.ring(r, cx, gy - 2, cw - 2, 15,
                         ring_c, _lerp(ring_c, th.bottom, 0.4))
                txt = _lerp(ORANGE, (35, 20, 0), 0.55) if light else ORANGE
            elif iso == sel:
                kit.fill_rect(r, cx, gy - 2, cw - 2, 15,
                              _lerp(th.panel, EMERALD, 0.45 if light else 0.25))
                ring_c = _lerp(EMERALD, (0, 30, 12), 0.35) if light else EMERALD
                kit.ring(r, cx, gy - 2, cw - 2, 15,
                         ring_c, _lerp(ring_c, th.bottom, 0.4))
                txt = (_lerp(EMERALD, (0, 30, 12), 0.55) if light
                       else _lerp(EMERALD, (255, 255, 255), 0.35))
            else:
                txt = th.ink
            kit.draw_text(r, cx + 4, gy, str(d), txt, 11, 1)
            if marks:
                m = next((p for p in PRIO if p in marks), marks[0])
                dot_c = DOT.get(m, (120, 130, 150))
                if light:
                    dot_c = _lerp(dot_c, (20, 20, 20), 0.25)
                kit.fill_rect(r, cx + cw - 8, gy + 9, 4, 4, dot_c)
        gy += 17
    gy += 4
    kit.draw_text(r, x + 10, gy, 'tarefas do dia', th.accent2, 12, 2)
    gy += 16
    for t in tasks_by_date.get(sel, [])[:8]:
        kit.draw_text(r, x + 10, gy,
                      f"{t.get('mark', '[ ]')} {t.get('text', '')[:24]}"
                      f" ({t.get('note', '')[:10]})", th.ink, 11, 1)
        gy += 14


def hit_day(x, y, w, mx, my, state):
    yy, mm = state.get('cal_month') or (date.today().year, date.today().month)
    cw = (w - 20) // 7
    gy = y + 34 + 14 + 16
    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(yy, mm)
    for wk in weeks:
        for i, d in enumerate(wk):
            if not d:
                continue
            cx = x + 10 + i * cw
            if cx <= mx < cx + cw - 2 and gy - 2 <= my < gy + 13:
                return f'{yy:02d}-{mm:02d}-{d:02d}'
        gy += 17
    return None