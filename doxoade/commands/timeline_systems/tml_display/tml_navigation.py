# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_display/tml_navigation.py
"""
Timeline Nexus - Hermes (Navegador Interativo).
TUI de exploração: cursor, drill-down e painel de detalhes.
Teclas: setas/WASD movem · ENTER detalha · ESC volta/sai ·
        1/2/3 escala · -/= ano · T tema · Q sai
"""
from datetime import datetime
import click
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style

from doxoade.commands.timeline_systems.tml_engine.activity_heatmap import (
    ActivityHeatmap, MONTH_ABBR,
)
from doxoade.commands.timeline_systems.tml_data.tml_aggregator import TimelineAggregator
from doxoade.commands.timeline_systems.tml_display.heatmap_renderer import CYBER_BOX
from doxoade.commands.timeline_systems.tml_display.tml_themes import THEMES, get_theme

DAY_FULL = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

KEYS_UP = ('\xe0H', '\x00H', 'w')
KEYS_DOWN = ('\xe0P', '\x00P', 's')
KEYS_LEFT = ('\xe0K', '\x00K', 'a')
KEYS_RIGHT = ('\xe0M', '\x00M', 'd')
KEYS_ENTER = ('\r', '\n')
KEYS_ESC = ('\x1b',)


class TimelineExplorer:
    """Navegador TUI do Timeline Nexus."""

    def __init__(self, initial_scale='hour', year=None, theme='cyberpunk'):
        self.orch = ActivityHeatmap()
        self.aggregator = TimelineAggregator()
        self.scale = initial_scale
        self.year = year
        self.theme_name = theme
        self.theme = get_theme(theme)
        self.model = self.orch.build(scale=self.scale, year=self.year)
        self.cursor = [0, 0]
        self.drill = None
        self.message = ''

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------
    def run(self):
        console = Console()
        try:
            with Live(self._build_layout(), console=console, screen=True,
                      refresh_per_second=6) as live:
                while True:
                    key = click.getchar(echo=False)
                    if not self._handle_key(key):
                        break
                    live.update(self._build_layout())
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self.aggregator.close()

    # ------------------------------------------------------------------
    # Tratamento de teclas
    # ------------------------------------------------------------------
    def _handle_key(self, key):
        if key in ('q', 'Q'):
            return False
        if key in KEYS_ESC:
            if self.drill is not None:
                self.drill = None
            else:
                return False
        elif key in KEYS_UP:    self._move(-1, 0)
        elif key in KEYS_DOWN:  self._move(1, 0)
        elif key in KEYS_LEFT:  self._move(0, -1)
        elif key in KEYS_RIGHT: self._move(0, 1)
        elif key in KEYS_ENTER: self._drill()
        elif key in ('1', '2', '3'):
            self._switch_scale({'1': 'hour', '2': 'day', '3': 'month'}[key])
        elif key in ('-', '_'): self._shift_year(-1)
        elif key in ('=', '+'): self._shift_year(1)
        elif key in ('t', 'T'):
            names = list(THEMES.keys())
            i = names.index(self.theme_name) if self.theme_name in names else 0
            self.theme_name = names[(i + 1) % len(names)]
            self.theme = get_theme(self.theme_name)
        elif key in (',', '['): self._shift_month(-1)
        elif key in ('.', ']'): self._shift_month(1)
        return True

    def _move(self, dy, dx):
        self.cursor[0] = min(max(0, self.cursor[0] + dy), len(self.model.row_labels) - 1)
        self.cursor[1] = min(max(0, self.cursor[1] + dx), len(self.model.col_labels) - 1)
        self.drill = None
        self.message = ''

    def _drill(self):
        y, x = self.cursor
        if self.model.cells[y][x].count == 0:
            self.drill = None
            self.message = 'Célula vazia — nada para detalhar.'
            return
        self.message = ''
        self.drill = self.aggregator.drill_down(self.model, y, x, limit=8)

    def _switch_scale(self, scale):
        if scale == self.scale:
            return
        self.scale = scale
        self.model = self.orch.build(scale=scale, year=self.year)
        self.cursor = [0, 0]
        self.drill = None
        self.message = f'Escala: {scale.upper()}'

    def _shift_year(self, delta):
        if self.scale == 'month':
            self.message = 'Escala MONTH já cobre todos os anos.'
            return
        base = self.year or datetime.now().year
        self.year = base + delta
        self.model = self.orch.build(scale=self.scale, year=self.year)
        self.cursor = [min(self.cursor[0], len(self.model.row_labels) - 1),
                       min(self.cursor[1], len(self.model.col_labels) - 1)]
        self.drill = None
        self.message = f'Ano: {self.year}'

    # ------------------------------------------------------------------
    # Renderização do layout
    # ------------------------------------------------------------------
    def _build_layout(self):
        layout = Layout()
        layout.split_column(
            Layout(name='header', size=3),
            Layout(name='body'),
            Layout(name='footer', size=3),
        )
        layout['body'].split_row(
            Layout(name='grid', ratio=3),
            Layout(name='side', size=44),
        )
        layout['header'].update(self._render_header())
        layout['grid'].update(self._render_grid())
        layout['side'].update(self._render_side())
        layout['footer'].update(self._render_footer())
        return layout

    def _render_header(self):
        t = self.theme
        txt = Text()
        txt.append('◤ TIMELINE NEXUS ◢ ', Style(color=t['title'], bold=True))
        txt.append(f"scale={self.scale} ", Style(color=t['axis_fg']))
        txt.append(f"year={self.model.year or 'ALL'} ", Style(color=t['axis_fg']))
        txt.append(f"theme={self.theme_name}", Style(color=t['axis_fg']))
        if self.message:
            txt.append(f"  ⚠ {self.message}", Style(color='yellow'))
        return Panel(txt, box=CYBER_BOX, border_style=Style(color=t['border']))

    def _render_grid(self):
        t = self.theme
        table = Table(box=CYBER_BOX, border_style=Style(color=t['border']),
                      show_header=True, expand=False)
        table.add_column('', justify='right',
                         style=Style(color=t['label_fg'], bold=True))
        for i in range(len(self.model.col_labels)):
            mark = self.model.col_marks.get(i, '')
            table.add_column(
                Text(mark, style=Style(color=t['header_fg'], bold=True)) if mark else Text(''),
                justify='center', width=2)
        for y, rl in enumerate(self.model.row_labels):
            row = [Text(rl, style=Style(color=t['label_fg'],
                                        bold=(y == self.cursor[0])))]
            for x in range(len(self.model.col_labels)):
                c = self.model.cells[y][x]
                sd = t.get(c.color_key, t['idle'])
                if [y, x] == self.cursor:
                    style = Style(color='black', bgcolor='white', bold=True)
                else:
                    style = Style(color=sd['fg'], bgcolor=sd['bg'],
                                  bold=c.color_key in ('peak', 'alert'))
                row.append(Text(sd['glyph'], style=style))
            table.add_row(*row)
        return table

    def _cell_label(self):
        y, x = self.cursor
        m = self.model
        if m.scale == 'hour':
            return f"{DAY_FULL[y]} · {x:02d}h"
        if m.scale == 'day':
            return f"{MONTH_ABBR[y]} {x + 1:02d} · {m.year}"
        return f"{m.row_labels[y]} · {MONTH_ABBR[x]}"

    def _render_side(self):
        t = self.theme
        y, x = self.cursor
        cell = self.model.cells[y][x]
        txt = Text()
        txt.append(self._cell_label() + '\n', Style(color=t['title'], bold=True))
        txt.append('─' * 34 + '\n', Style(color=t['axis_fg']))
        txt.append(f"Comandos : {cell.count}\n")
        txt.append(f"Erros    : {cell.errors} ({round(cell.error_ratio * 100, 1)}%)\n")
        txt.append(f"Nível    : {cell.intensity} ({cell.color_key})\n")
        if cell.commands:
            txt.append(f"Presentes: {', '.join(cell.commands[:5])}\n")
        if self.drill is not None:
            txt.append('\n[TOP COMANDOS NA CÉLULA]\n',
                       Style(color=t['header_fg'], bold=True))
            for i, d in enumerate(self.drill, 1):
                txt.append(f" {i}. {d['command']:<14} {d['total']:>4}",
                           Style(color=t['label_fg']))
                if d['errors']:
                    txt.append(f" ({d['errors']} err)", Style(color='red'))
                txt.append('\n')
        elif self.message:
            txt.append('\n' + self.message, Style(color='yellow'))
        else:
            txt.append('\nENTER para detalhar a célula.',
                       Style(color=t['axis_fg'], dim=True))
        return Panel(txt, title='DETALHES', box=CYBER_BOX,
                     border_style=Style(color=t['border']))

    def _render_footer(self):
        t = self.theme
        help_txt = ('↑↓←→/WASD navegar · ENTER detalhar · ESC voltar/sai · '
                    '1/2/3 escala · -/= ano · T tema · Q sair')
        return Panel(Text(help_txt, style=Style(color=t['axis_fg'])),
                     box=CYBER_BOX, border_style=Style(color=t['border']))

    def _shift_month(self, delta):
        if self.scale != 'hour':
            self.message = 'Paging mensal disponível na escala HOUR (tecla 1).'
            return
        seq = [None] + list(range(12))
        i = seq.index(self.month) if self.month in seq else 0
        self.month = seq[(i + delta) % len(seq)]
        self._rebuild_model()

    def _rebuild_model(self):
        self.model = self.orch.build(scale=self.scale, year=self.year, month=self.month)
        self.cursor = [min(self.cursor[0], len(self.model.row_labels) - 1),
                       min(self.cursor[1], len(self.model.col_labels) - 1)]
        self.drill = None
        self.message = ''

def launch_explorer(scale='hour', year=None, theme='cyberpunk'):
    """Facade para o CLI invocar o navegador."""
    TimelineExplorer(initial_scale=scale, year=year, theme=theme).run()