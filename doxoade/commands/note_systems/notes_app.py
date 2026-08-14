# -*- coding: utf-8 -*-
# doxoade\doxoade\commands\note_systems\notes_app.py
"""SOFTCLUB NOTES — Fase 1: janela viva, render fora da thread de UI.
Ma'at: nenhuma janela zumbi — buffer pronto ANTES da janela; quit no finally."""
import os
import hashlib
from pathlib import Path
from .renderer import SoftRenderer
from .bg_gen import render_background
from .palette import THEMES
from doxoade.tools.filesystem import _find_project_root

VK_BACK, VK_RETURN = 0x08, 0x0D
VK_ESCAPE, VK_F5 = 0x1B, 0x74
VK_UP, VK_DOWN = 0x26, 0x28


def _cache_path(theme_name, w, h, seed, key):
    d = Path(_find_project_root(os.getcwd())) / '.doxoade' / 'benzaiten' / 'softclub'
    d.mkdir(parents=True, exist_ok=True)
    return d / f'scb_{theme_name}_{w}x{h}_{seed}_{key}.raw'


def _load_or_render(theme_name, w, h, seed):
    theme = THEMES[theme_name if theme_name in THEMES else 'night']
    key = hashlib.sha256(repr(theme).encode()).hexdigest()[:8]
    p = _cache_path(theme_name, w, h, seed, key)
    need = w * h * 4
    if p.exists() and p.stat().st_size == need:
        return p.read_bytes()                      # ⚡ cache hit
    bgra = render_background(theme, w, h, seed, bgra=True)
    try:
        p.write_bytes(bgra)
    except OSError:
        pass
    return bgra


def run_notes_gui(root, theme_name='night', seed=7, width=800, height=600):
    if os.environ.get('DXGUI_VERBOSE') == '1':
        print(f'[SOFTCLUB] run_notes_gui pid={os.getpid()} theme={theme_name}')
    
    root_dir = Path(_find_project_root(os.getcwd()))
    r = SoftRenderer('SoftClub Notes', width, height)

    try:
        try:
            cw, ch = r.client_size()
        except Exception:
            cw, ch = width, height
            
        # NOVA MÁQUINA DE ESTADOS
        state = {
            'theme': theme_name if theme_name in THEMES else 'night',
            'seed': seed, 
            'size': (cw or width, ch or height),
            'notes': [], 
            'sel': 0,
            'mode': 'nav',        # 'nav' (Navegação) ou 'edit' (Edição)
            'edit_lines': [],     # Buffer de texto da nota atual
            'cursor_blink': True  # Para animação (futuro)
        }

        def load_notes():
            from doxoade.commands.note_systems.note_api import api_list_notes
            state['notes'] = api_list_notes(str(root_dir))
            if state['sel'] >= len(state['notes']) and state['notes']:
                state['sel'] = 0

        load_notes()

        def draw_ui():
            from doxoade.commands.note_systems.note_api import api_get_note, api_agenda
            th = THEMES[state['theme']]
            W, H = state['size']
            notes = state['notes']

            # TOPBAR
            kit.panel(r, 0, 0, W, TOPBAR_H, th.panel, th.panel_edge)
            kit.draw_text(r, 10, 8, 'softclub notes', th.accent2, 15, 2)
            
            status_text = f"[{state['mode'].upper()}] | {state['theme']}"
            kit.draw_text(r, W - 150, 9, status_text, th.ink_muted if state['mode'] == 'nav' else th.accent, 12, 1)

            # SIDEBAR (Lista de Notas)
            kit.panel(r, 0, TOPBAR_H, SIDE_W, H - TOPBAR_H - STATUS_H, th.panel, th.panel_edge)
            for i, n in enumerate(notes[:24]):
                y = TOPBAR_H + 10 + i * 20
                if i == state['sel']:
                    kit.fill_rect(r, 2, y - 4, SIDE_W - 4, 18, th.panel_edge)
                    kit.draw_text(r, 10, y - 1, n['name'], th.ink, 13, 1)
                else:
                    kit.draw_text(r, 10, y - 1, n['name'], th.ink_muted, 13, 1)

            # MAIN AREA (Preview ou Edição)
            x0 = SIDE_W + 14
            if notes:
                y = TOPBAR_H + 12
                note_name = notes[state['sel']]['name']
                kit.draw_text(r, x0, y, note_name, th.accent, 15, 1)
                y += 24

                if state['mode'] == 'nav':
                    # MODO NAVEGAÇÃO: Mostra Preview e Agenda
                    det = api_get_note(str(root_dir), note_name)
                    for line in (det.get('lines') or [])[:20]:
                        kit.draw_text(r, x0, y, line[:92], th.ink, 13, 1)
                        y += 17
                    
                    ag = api_agenda(str(root_dir))
                    y += 12
                    kit.draw_text(r, x0, y, 'agenda', th.accent2, 13, 2)
                    y += 18
                    for t in ag['tasks'][:5]:
                        kit.draw_text(r, x0, y, f"{t['mark']} {t['when']}  {t['text'][:58]}", th.ink_muted, 12, 1)
                        y += 16
                
                elif state['mode'] == 'edit':
                    # MODO EDIÇÃO: Mostra o buffer de texto atual e o cursor
                    # Vamos renderizar as últimas N linhas para não ultrapassar a tela
                    max_lines = (H - TOPBAR_H - STATUS_H - 40) // 17
                    display_lines = state['edit_lines'][-max_lines:] if len(state['edit_lines']) > max_lines else state['edit_lines']
                    
                    for i, line in enumerate(display_lines):
                        # Se for a última linha, desenha o cursor visualmente (um bloco ou underscore)
                        is_last = (i == len(display_lines) - 1)
                        txt_to_draw = line + ("_" if is_last else "")
                        kit.draw_text(r, x0, y, txt_to_draw, th.ink, 13, 1)
                        y += 17

            # STATUS BAR
            kit.panel(r, 0, H - STATUS_H, W, STATUS_H, th.panel, th.panel_edge)
            if state['mode'] == 'nav':
                hints = '↑/↓ notas · ENTER editar · t tema · r seed · q sair'
            else:
                hints = 'ESC salvar e voltar · BACKSPACE apagar · DIGITE livremente'
            kit.draw_text(r, 10, H - STATUS_H + 6, hints, th.ink_muted, 12, 1)

        def repaint():
            w, h = state['size']
            r.present(_load_or_render(state['theme'], w, h, state['seed']), w, h)
            draw_ui()

        def on_key(vk, text):
            # ===== MODO NAVEGAÇÃO =====
            if state['mode'] == 'nav':
                if text in ('q', 'Q') or vk == VK_ESCAPE:
                    r.quit()
                elif text in ('t', 'T'):
                    state['theme'] = 'day' if state['theme'] == 'night' else 'night'
                    repaint()
                elif text in ('r', 'R') or vk == VK_F5:
                    state['seed'] = (state['seed'] + 1) % 1000
                    repaint()
                elif vk == VK_DOWN and state['notes']:
                    state['sel'] = (state['sel'] + 1) % len(state['notes'])
                    repaint()
                elif vk == VK_UP and state['notes']:
                    state['sel'] = (state['sel'] - 1) % len(state['notes'])
                    repaint()
                elif vk == VK_RETURN and state['notes']:
                    # ENTRAR NO MODO DE EDIÇÃO
                    from doxoade.commands.note_systems.note_api import api_get_note
                    note_name = state['notes'][state['sel']]['name']
                    det = api_get_note(str(root_dir), note_name)
                    state['edit_lines'] = det.get('lines', [])
                    if not state['edit_lines']:
                        state['edit_lines'] = [""] # Garante pelo menos uma linha vazia
                    state['mode'] = 'edit'
                    repaint()
            
            # ===== MODO EDIÇÃO =====
            elif state['mode'] == 'edit':
                if vk == VK_ESCAPE:
                    # SALVAR E SAIR DO MODO DE EDIÇÃO
                    from doxoade.commands.note_systems.note_api import api_save_note
                    note_name = state['notes'][state['sel']]['name']
                    api_save_note(str(root_dir), note_name, '\n'.join(state['edit_lines']))
                    state['mode'] = 'nav'
                    load_notes() # Atualiza metadata (como o número de linhas na lista)
                    repaint()
                
                elif vk == VK_BACK:
                    # Apagar caractere ou linha
                    if state['edit_lines']:
                        if len(state['edit_lines'][-1]) > 0:
                            state['edit_lines'][-1] = state['edit_lines'][-1][:-1]
                        elif len(state['edit_lines']) > 1:
                            state['edit_lines'].pop() # Remove a linha atual se estiver vazia
                    repaint()
                
                elif vk == VK_RETURN:
                    # Nova linha
                    state['edit_lines'].append("")
                    repaint()
                
                elif text:
                    # Digitação de texto normal
                    if not state['edit_lines']:
                        state['edit_lines'].append("")
                    # Impede quebras de linha acidentais via string crua da DLL
                    clean_text = text.replace('\n', '').replace('\r', '')
                    if clean_text:
                        state['edit_lines'][-1] += clean_text
                    repaint()

        if hasattr(r, 'on_resize'):
            def handle_resize(w, h):
                state['size'] = (w, h)
                repaint()
            r.on_resize(handle_resize)

        r.on_key(on_key)
        repaint() # Chamada inicial para desenhar
        r.run()

    finally:
        try:
            r.quit()
        except Exception:
            pass