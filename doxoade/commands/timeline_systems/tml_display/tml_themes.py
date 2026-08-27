# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_display/tml_themes.py
""" Timeline Nexus - Nyx (Temas).
Paleta semântica cyberpunk. O renderer consulta isto, nunca cores hardcoded. """

from rich.box import Box

BOX_OPEN_DOUBLE = Box(
    "╔══╗\n" "║  ║\n" "╠══╣\n" "║  ║\n"
    "╠══╣\n" "╠══╣\n" "╚══╝\n" "    \n"
)
BOX_OPEN_SINGLE = Box(
    "┌──┐\n" "│  │\n" "├──┤\n" "│  │\n"
    "├──┤\n" "├──┤\n" "└──┘\n" "    \n"
)

THEMES = {
    'cyberpunk': {
        'idle':  {'fg': 'bright_black', 'bg': None,    'glyph': '░'},
        'low':   {'fg': 'cyan',         'bg': None,    'glyph': '▒'},
        'mid':   {'fg': 'bright_cyan',  'bg': None,    'glyph': '▓'},
        'high':  {'fg': 'green',        'bg': None,    'glyph': '█'},
        'peak':  {'fg': 'bright_green', 'bg': 'green', 'glyph': '█'},
        'alert': {'fg': 'bright_white', 'bg': 'red',   'glyph': '■'},
        # Cores de estrutura
        'header_fg': 'bright_cyan',
        'label_fg':  'cyan',
        'axis_fg':   'bright_black',
        'border':    'cyan',
        'title':     'bright_white',
    },
    'mono': {
        'idle':  {'fg': 'white', 'bg': None, 'glyph': '·'},
        'low':   {'fg': 'white', 'bg': None, 'glyph': '░'},
        'mid':   {'fg': 'white', 'bg': None, 'glyph': '▒'},
        'high':  {'fg': 'white', 'bg': None, 'glyph': '▓'},
        'peak':  {'fg': 'bright_white', 'bg': None, 'glyph': '█'},
        'alert': {'fg': 'bright_white', 'bg': None, 'glyph': 'X'},
        'header_fg': 'white',
        'label_fg':  'white',
        'axis_fg':   'bright_black',
        'border':    'white',
        'title':     'bright_white',
    },
}

TODAY_FG = '#FFA500'  # laranja
TODAY_BG = '#4B0082'  # anil

def get_theme(name: str = 'cyberpunk') -> dict:
    return THEMES.get(name, THEMES['cyberpunk'])