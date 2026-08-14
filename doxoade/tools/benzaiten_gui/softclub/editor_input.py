# -*- coding: utf-8 -*-
# doxoade/doxoade/tools/benzaiten_gui/softclub/editor_input.py
"""SOFTCLUB INPUT — todo o teclado do editor/pote, isolado do render."""
import ctypes

VK_ESCAPE, VK_F5 = 0x1B, 0x74
VK_UP, VK_DOWN = 0x26, 0x28
VK_LEFT, VK_RIGHT = 0x25, 0x27
VK_RETURN = 0x0D
VK_BACK = 0x08
VK_DELETE = 0x2E
VK_HOME = 0x24
VK_END = 0x23
VK_TAB = 0x09
VK_SHIFT = 0x10


def _shift_held():
    try:
        return bool(ctypes.windll.user32.GetKeyState(VK_SHIFT) & 0x8000)
    except Exception:
        return False


# ── Clipboard (PowerShell, fail-graceful) ────────────────────────────────────
def _get_clipboard():
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        if not user32.OpenClipboard(None):
            return ''
        try:
            h = user32.GetClipboardData(13)  # CF_UNICODETEXT
            if not h:
                return ''
            p = kernel32.GlobalLock(h)
            if not p:
                return ''
            try:
                text = ctypes.wstring_at(p)
            finally:
                kernel32.GlobalUnlock(h)
            return text.replace('\r', '').rstrip('\n')
        finally:
            user32.CloseClipboard()
    except Exception:
        return ''

def _set_clipboard(text):
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        data = text.encode('utf-16-le') + b'\x00\x00'
        h = kernel32.GlobalAlloc(0x0042, len(data))  # GMEM_MOVEABLE|ZEROINIT
        if not h:
            return
        p = kernel32.GlobalLock(h)
        if not p:
            return
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if user32.OpenClipboard(None):
            user32.EmptyClipboard()
            user32.SetClipboardData(13, h)
            user32.CloseClipboard()
    except Exception:
        pass


# ── Seleção (apenas no editor) ───────────────────────────────────────────────
def _sel_range(state):
    a = state.get('edit_selection_start')
    if a is None:
        return None
    c = (state['edit_cursor_line'], state['edit_cursor_col'])
    return (a, c) if a <= c else (c, a)


def _get_sel_text(state):
    rng = _sel_range(state)
    if not rng:
        return None
    (l1, c1), (l2, c2) = rng
    lines = state['edit_lines']
    if l1 == l2:
        return lines[l1][c1:c2]
    return '\n'.join([lines[l1][c1:]] + lines[l1 + 1:l2] + [lines[l2][:c2]])


def _del_sel(state):
    rng = _sel_range(state)
    if not rng:
        return False
    (l1, c1), (l2, c2) = rng
    lines = state['edit_lines']
    lines[l1] = lines[l1][:c1] + lines[l2][c2:]
    del lines[l1 + 1:l2 + 1]
    state['edit_cursor_line'], state['edit_cursor_col'] = l1, c1
    state['edit_selection_start'] = None
    return True

def _pote_sel_range(state):
    a = state.get('pote_selection_start')
    if a is None:
        return None
    c = (state['pote_cursor_line'], state['pote_cursor_col'])
    return (a, c) if a <= c else (c, a)

def _pote_get_sel_text(state):
    rng = _pote_sel_range(state)
    if not rng:
        return None
    (l1, c1), (l2, c2) = rng
    lines = state['pote_lines']
    if l1 == l2:
        return lines[l1][c1:c2]
    return '\n'.join([lines[l1][c1:]] + lines[l1 + 1:l2] + [lines[l2][:c2]])

def _pote_del_sel(state):
    rng = _pote_sel_range(state)
    if not rng:
        return False
    (l1, c1), (l2, c2) = rng
    lines = state['pote_lines']
    lines[l1] = lines[l1][:c1] + lines[l2][c2:]
    del lines[l1 + 1:l2 + 1]
    state['pote_cursor_line'], state['pote_cursor_col'] = l1, c1
    state['pote_selection_start'] = None
    return True

def save_note(root, state):
    from doxoade.commands.note_systems.note_api import api_save_note
    if state['notes']:
        name = state['notes'][state['sel']]['name']
        api_save_note(str(root), name, '\n'.join(state['edit_lines']))
        state['dirty'] = False


# ── Fábrica do callback ───────────────────────────────────────────────────────

def _restore_trash_sel(state, root, load_notes):
    from doxoade.commands.note_systems.note_api import api_list_trash, api_restore_note
    tr = state.get('trash') or api_list_trash(str(root))
    state['trash'] = tr
    if tr:
        sel = min(state.get('trash_sel', 0), len(tr) - 1)
        api_restore_note(str(root), tr[sel]['ref'])
        state['trash_sel'] = 0
        load_notes()

def _purge_trash_sel(state, root):
    from doxoade.commands.note_systems.note_api import api_purge_trash
    tr = state.get('trash') or []
    if tr:
        sel = min(state.get('trash_sel', 0), len(tr) - 1)
        api_purge_trash(str(root), tr[sel]['ref'])
        state['trash_sel'] = 0

def make_on_key(state, r, root, paint, load_notes):
    """Devolve o on_key completo; editor e pote compartilham a mesma máquina."""

    def on_key(vk, text):
        is_ctrl_s = (text == '\x13'); is_ctrl_l = (text == '\x0c')
        is_ctrl_c = (text == '\x03'); is_ctrl_v = (text == '\x16')
        is_ctrl_x = (text == '\x18'); is_ctrl_d = (text == '\x04')
        is_ctrl_w = (text == '\x17')
        is_ctrl_z = (text == '\x1a'); is_ctrl_y = (text == '\x19')
        is_ctrl_a = (text == '\x01')
        is_ctrl_n = (text == '\x0e'); is_ctrl_r = (text == '\x12')

        shift = _shift_held()
        if vk == 0x70:  # F1 → abre/fecha a ajuda
                
            if state.get('show_help'):
                if vk == VK_LEFT:
                    state['help_page'] = max(0, state.get('help_page', 0) - 1)
                    paint(); return
                if vk == VK_RIGHT:
                    n = state.get('help_pages', 1)
                    state['help_page'] = min(n - 1, state.get('help_page', 0) + 1)
                    paint(); return
            
            state['show_help'] = not state.get('show_help', False)
            paint()
            return
        # ── F2 / c → abre/fecha calendário (SEMPRE antes do bloco de navegação) ──
        if vk == 0x71 or (text in ('c', 'C') and state['mode'] == 'nav'):
            state['show_cal'] = not state.get('show_cal', False)
            if state['show_cal']:
                state['focus'] = 'cal'
                if not state.get('cal_sel'):
                    from datetime import date as _d
                    state['cal_sel'] = _d.today().isoformat()
            elif state.get('focus') == 'cal':
                state['focus'] = 'editor'
            paint(); return
        if state.get('focus') == 'cal' and state.get('show_cal') \
                and state['mode'] != 'new':
            from datetime import date as _d, timedelta as _td
            d0 = _d.fromisoformat(state.get('cal_sel') or _d.today().isoformat())
            if text in ('c', 'C'):                      # c fecha também no edit
                state['show_cal'] = False
                state['focus'] = 'editor'
                paint(); return
            if vk == VK_LEFT:
                d0 -= _td(days=1)
            elif vk == VK_RIGHT:
                d0 += _td(days=1)
            elif vk == VK_UP:
                d0 -= _td(days=7)
            elif vk == VK_DOWN:
                d0 += _td(days=7)
            elif text == '[':
                yy, mm = state.get('cal_month') or (d0.year, d0.month)
                mm -= 1
                if mm < 1:
                    mm, yy = 12, yy - 1
                state['cal_month'] = (yy, mm); paint(); return
            elif text == ']':
                yy, mm = state.get('cal_month') or (d0.year, d0.month)
                mm += 1
                if mm > 12:
                    mm, yy = 1, yy + 1
                state['cal_month'] = (yy, mm); paint(); return
            elif vk == VK_TAB:
                state['focus'] = 'editor'; paint(); return
            elif vk == VK_RETURN:
                from doxoade.commands.note_systems.note_api import api_agenda, api_get_note
                ag = api_agenda(str(root))
                hit = next((t for t in ag.get('tasks', [])
                            if t.get('when') == d0.isoformat()), None)
                if hit and state['notes']:
                    names = [n['name'] for n in state['notes']]
                    if hit['note'] in names:
                        state['sel'] = names.index(hit['note'])
                        det = api_get_note(str(root), hit['note'])
                        state['edit_lines'] = det.get('lines') or ['']
                        state['mode'] = 'edit'
                        state['focus'] = 'editor'
                        state['edit_cursor_line'] = 0
                        state['edit_cursor_col'] = 0
                paint(); return
            elif state['mode'] == 'edit' and text and len(text) == 1:
                paint(); return    # não digita no editor com o cal focado
            else:
                return             # q/t/h caem no handler do nav
            state['cal_sel'] = d0.isoformat()
            state['cal_month'] = (d0.year, d0.month)
            paint(); return

        if vk == 0x70:  # F1 → abre/fecha a ajuda
            state['show_help'] = not state.get('show_help', False)
            paint()
            return

        if is_ctrl_n and state['mode'] in ('nav', 'edit'):
            if state['mode'] == 'edit' and state.get('dirty'):
                save_note(root, state)
            state['mode'] = 'new'
            state['new_buffer'] = ''
            paint()
            return

        # ===== MODO NAV =====
        if state['mode'] == 'new':
            if vk == VK_ESCAPE:
                state['mode'] = 'nav'; paint(); return
            if vk == VK_RETURN:
                from doxoade.commands.note_systems.note_api import api_new_note, api_get_note
                nm = (state.get('new_buffer') or '').strip()
                if nm:
                    rec = api_new_note(str(root), nm)
                    load_notes()
                    names = [n['name'] for n in state['notes']]
                    if rec.get('name') in names:
                        state['sel'] = names.index(rec['name'])
                        det = api_get_note(str(root), rec['name'])
                        state['edit_lines'] = det.get('lines') or ['']
                        state['mode'] = 'edit'
                        state['focus'] = 'editor'
                        state['edit_cursor_line'] = 0
                        state['edit_cursor_col'] = 0
                else:
                    state['mode'] = 'nav'
                paint(); return
            if vk == VK_BACK:
                state['new_buffer'] = state.get('new_buffer', '')[:-1]
                paint(); return
            if text and len(text) == 1 and text.isprintable():
                state['new_buffer'] = state.get('new_buffer', '') + text
                paint(); return
            return
        if state['mode'] == 'nav':
            if text in ('q', 'Q') or vk == VK_ESCAPE:
                r.quit()
            elif text in ('t', 'T'):
                state['theme'] = 'day' if state['theme'] == 'night' else 'night'
                paint()
            elif text in ('r', 'R') or vk == VK_F5:
                state['seed'] = (state['seed'] + 1) % 1000
                paint()
            elif text in ('h', 'H', '?'):
                state['show_help'] = not state.get('show_help', False)
                paint()
            elif text in ('b', 'B'):
                if state.get('on_next_bg'):
                    state['on_next_bg']()
                paint()

            elif vk == VK_TAB:
                state['focus'] = 'trash' if state.get('focus') != 'trash' else 'editor'
                paint()
            elif vk == VK_DOWN:
                if state.get('focus') == 'trash':
                    n = len(state.get('trash') or [])
                    if n:
                        state['trash_sel'] = min(state.get('trash_sel', 0) + 1, n - 1)
                elif state['notes'] and state['sel'] < len(state['notes']) - 1:
                    state['sel'] += 1
                elif state.get('trash'):
                    state['focus'] = 'trash'
                    state['trash_sel'] = 0
                paint()
            elif vk == VK_UP:
                if state.get('focus') == 'trash':
                    if state.get('trash_sel', 0) > 0:
                        state['trash_sel'] -= 1
                    else:
                        state['focus'] = 'editor'
                        state['sel'] = max(0, len(state['notes']) - 1)
                elif state['notes'] and state['sel'] > 0:
                    state['sel'] -= 1
                paint()
            elif vk == VK_RETURN:
                if state.get('focus') == 'trash':
                    _restore_trash_sel(state, root, load_notes)
                    if not state.get('trash'):
                        state['focus'] = 'editor'
                elif state['notes']:
                    from doxoade.commands.note_systems.note_api import api_get_note
                    det = api_get_note(str(root), state['notes'][state['sel']]['name'])
                    state['edit_lines'] = det.get('lines') or ['']
                    state['mode'] = 'edit'
                    state['edit_cursor_line'] = 0
                    state['edit_cursor_col'] = 0
                    state['edit_selection_start'] = None
                    state['focus'] = 'editor'
                paint()
            elif vk == VK_DELETE and _shift_held() and state.get('focus') == 'trash':
                _purge_trash_sel(state, root)
                load_notes()
                if not state.get('trash'):
                    state['focus'] = 'editor'
                paint()
            return
        if is_ctrl_w and state['mode'] == 'edit' and state.get('focus') == 'editor' and state['notes']:
#        if is_ctrl_w and state['mode'] == 'edit' and state['notes']:
            if state.get('dirty'):
                save_note(root, state)          # Q6: salva antes de lixeirar
            from doxoade.commands.note_systems.note_api import api_delete_note
            api_delete_note(str(root), state['notes'][state['sel']]['name'])
            state['mode'] = 'nav'; state['dirty'] = False
            load_notes(); paint(); return
        if is_ctrl_r:
            _restore_trash_sel(state, root, load_notes)
            paint(); return
        if vk == VK_TAB and state['mode'] == 'edit':
            order = ['editor', 'pote', 'trash'] + (['cal'] if state.get('show_cal') else [])
#            order = ['editor', 'pote', 'trash']
            cur = state.get('focus', 'editor')
            state['focus'] = (order[(order.index(cur) + 1) % len(order)]
                              if cur in order else 'editor')
            paint(); return
        if state.get('focus') == 'trash' and state['mode'] == 'edit':
            if vk == VK_TAB:
                state['focus'] = 'editor'
                paint(); return
            if vk == VK_DELETE and _shift_held():
                _purge_trash_sel(state, root)
                load_notes()
                if not state.get('trash'):
                    state['focus'] = 'editor'
                paint(); return
            paint(); return
        pote = (state.get('focus') == 'pote')
        lines = state['pote_lines'] if pote else state['edit_lines']
        kl = 'pote_cursor_line' if pote else 'edit_cursor_line'
        kc = 'pote_cursor_col' if pote else 'edit_cursor_col'

        def mark_dirty():
            if pote:
                state['pote_dirty'] = True
            else:
                state['dirty'] = True

        state.setdefault(kl, 0); state.setdefault(kc, 0)
        cl, cc = state[kl], state[kc]

        if not lines:
            lines.append('')
        cl = min(cl, len(lines) - 1)
        cc = min(cc, len(lines[cl]))
        state[kl], state[kc] = cl, cc
        state.setdefault('undo_stack', []); state.setdefault('redo_stack', [])
        state.setdefault('pote_undo', []); state.setdefault('pote_redo', [])
        def mark_dirty():
            if pote:
                state['pote_dirty'] = True
            else:
                state['dirty'] = True
        _mutating = (vk in (VK_BACK, VK_DELETE, VK_RETURN) or is_ctrl_l or
                     is_ctrl_v or is_ctrl_d or is_ctrl_x or
                     (text and vk == 0 and len(text) == 1 and text.isprintable()))
        if _mutating:
            stk = state['pote_undo'] if pote else state['undo_stack']
            stk.append((lines.copy(), cl, cc))
            if len(stk) > 100:
                stk.pop(0)
            (state['pote_redo'] if pote else state['redo_stack']).clear()

        if vk == VK_ESCAPE:
            if pote:
                state['focus'] = 'editor'
            else:
                save_note(root, state)
                state['mode'] = 'nav'
                load_notes()
            paint(); return
        if vk == VK_TAB:
            state['focus'] = 'pote' if not pote else 'editor'
            paint(); return
        if is_ctrl_s and not pote:
            save_note(root, state); paint(); return
        if is_ctrl_z or is_ctrl_y:
            if is_ctrl_z:
                stk = state['pote_undo'] if pote else state['undo_stack']
                ostk = state['pote_redo'] if pote else state['redo_stack']
            else:
                stk = state['pote_redo'] if pote else state['redo_stack']
                ostk = state['pote_undo'] if pote else state['undo_stack']
            if stk:
                snap, sl, sc = stk.pop()
                ostk.append((lines.copy(), cl, cc))
                lines[:] = snap
                nl = min(sl, max(0, len(lines) - 1))
                state[kl], state[kc] = nl, min(sc, len(lines[nl]))
                mark_dirty()
            paint(); return
        if is_ctrl_a:
            if pote:
                state['pote_selection_start'] = (0, 0)
            else:
                state['edit_selection_start'] = (0, 0)
            state[kl] = len(lines) - 1 if lines else 0
            state[kc] = len(lines[-1]) if lines else 0
            paint(); return
        if is_ctrl_l:
            lines.insert(cl + 1, ''); state[kl], state[kc] = cl + 1, 0
            state['dirty'] = True; paint(); return
        if is_ctrl_c or is_ctrl_x:
            sel = _pote_get_sel_text(state) if pote else _get_sel_text(state)
            if sel is None:
                sel = lines[cl] if lines else ''
            _set_clipboard(sel)
            if is_ctrl_x:
                if pote and _pote_sel_range(state):
                    _pote_del_sel(state)
                elif not pote and _sel_range(state):
                    _del_sel(state)
                elif lines:
                    lines.pop(cl)
                    if not lines: lines.append('')
                    cl = min(cl, len(lines) - 1)
                    cc = min(cc, len(lines[cl]))
                    state[kl], state[kc] = cl, cc
                mark_dirty()
            paint(); return
        if is_ctrl_v:
            clip = _get_clipboard()
            if clip:
                if not pote and _sel_range(state):
                    _del_sel(state); cl, cc = state[kl], state[kc]
                parts = clip.split('\n')
                if len(parts) == 1:
                    lines[cl] = lines[cl][:cc] + parts[0] + lines[cl][cc:]
                    state[kc] = cc + len(parts[0])
                else:
                    head = lines[cl][:cc] + parts[0]
                    tail = parts[-1] + lines[cl][cc:]
                    lines[cl:cl + 1] = [head] + parts[1:-1] + [tail]
                    state[kl] = cl + len(parts) - 1
                    state[kc] = len(tail)
                state['dirty'] = True
            paint(); return
        if is_ctrl_d:
            if pote and _pote_sel_range(state):
                _pote_del_sel(state); cl, cc = state[kl], state[kc]
            elif not pote and _sel_range(state):
                _del_sel(state); cl, cc = state[kl], state[kc]
            elif lines:
                lines.pop(cl)
                if not lines: lines.append('')
                state[kl] = min(cl, len(lines) - 1)
                state[kc] = min(cc, len(lines[state[kl]]))
            state['dirty'] = True; paint(); return

        if is_ctrl_w:
            state['wrap'] = not state.get('wrap', True)
            paint(); return

        # setas + seleção com Shift (só no editor)
        if vk in (VK_DOWN, VK_UP, VK_LEFT, VK_RIGHT, VK_HOME, VK_END):
            if shift:
                if pote:
                    if state.get('pote_selection_start') is None:
                        state['pote_selection_start'] = (cl, cc)
                elif state.get('edit_selection_start') is None:
                    state['edit_selection_start'] = (cl, cc)
            if vk == VK_DOWN and cl < len(lines) - 1:
                state[kl] = cl + 1; state[kc] = min(cc, len(lines[cl + 1]))
            elif vk == VK_UP and cl > 0:
                state[kl] = cl - 1; state[kc] = min(cc, len(lines[cl - 1]))
            elif vk == VK_RIGHT and cc < len(lines[cl]):
                state[kc] = cc + 1
            elif vk == VK_LEFT and cc > 0:
                state[kc] = cc - 1
            elif vk == VK_HOME:
                state[kc] = 0
            elif vk == VK_END:
                state[kc] = len(lines[cl])
            if not shift:
                state['edit_selection_start'] = None
                state['pote_selection_start'] = None
            paint(); return
        if vk == VK_BACK:
            if not pote and _sel_range(state):
                _del_sel(state)
            elif cc > 0:
                lines[cl] = lines[cl][:cc - 1] + lines[cl][cc:]
                state[kc] = cc - 1
            elif cl > 0:
                prev_len = len(lines[cl - 1])
                lines[cl - 1] += lines.pop(cl)
                state[kl] = state[kl] - 1; state[kc] = prev_len
            state['dirty'] = True; paint(); return
        if vk == VK_DELETE:
            if not pote and _sel_range(state):
                _del_sel(state)
            elif cc < len(lines[cl]):
                lines[cl] = lines[cl][:cc] + lines[cl][cc + 1:]
            elif cl < len(lines) - 1:
                lines[cl] += lines.pop(cl + 1)
            state['dirty'] = True; paint(); return
        if vk == VK_RETURN:
            if not pote and _sel_range(state):
                _del_sel(state); cl, cc = state[kl], state[kc]
            line = lines[cl]
            lines.insert(cl + 1, line[cc:])
            lines[cl] = line[:cc]
            state[kl], state[kc] = cl + 1, 0
            state['dirty'] = True; paint(); return
        if text and vk == 0 and len(text) == 1 and text.isprintable():
            if not pote and _sel_range(state):
                _del_sel(state); cl, cc = state[kl], state[kc]
            lines[cl] = lines[cl][:cc] + text + lines[cl][cc:]
            state[kc] = cc + 1
            state['dirty'] = True; paint(); return

    return on_key
    
sel_range = _sel_range   # alias público p/ o draw_ui do notes_app