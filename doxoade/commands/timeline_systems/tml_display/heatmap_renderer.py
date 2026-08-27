# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_display/heatmap_renderer.py
""" Timeline Nexus - Apolo (Renderer Rich).
Consome HeatmapModel e desenha no terminal com visual cyberpunk e compacto. """

from typing import Optional, List
from rich.console import Console
from rich.text import Text
from rich.style import Style
from doxoade.commands.timeline_systems.tml_display.tml_themes import (
    get_theme, TODAY_FG, TODAY_BG
)


class HeatmapRenderer:
    """Renderiza HeatmapModel em arte terminal elegante e compacta."""

    def __init__(self, theme: str = 'cyberpunk', console: Optional[Console] = None):
        self.theme = get_theme(theme)
        self.console = console or Console()

    def _paint_cell(self, cell, is_today=False) -> Text:
        """Converte uma HeatmapCell em Text Rich com estilo cyberpunk."""
        t = self.theme
        sd = t.get(cell.color_key, t['idle'])
        if is_today:
            style = Style(color=TODAY_FG, bgcolor=TODAY_BG, bold=True)
        else:
            style = Style(
                color=sd['fg'],
                bgcolor=sd['bg'],
                bold=(cell.color_key in ('peak', 'alert')),
            )
        return Text(sd['glyph'], style=style)

    def _render_day_matrix(self, model) -> Text:
        """Renderiza a matriz anual 12x31 compacta."""
        t = self.theme
        out = Text()

        # Cabeçalho dos dias: '    01 02 03 ... 31'
        header = Text("     ", style=Style(color=t['label_fg']))
        for d in range(1, 32):
            header.append(f"{d:02d} ", style=Style(color=t['header_fg'], dim=(d % 5 != 0 and d != 1)))
        out.append(header)
        out.append("\n")

        # Linhas dos Meses
        for m_idx, month_label in enumerate(model.row_labels):
            days_in_month = model.meta.get(m_idx, {}).get('days_in_month', 31)
            line = Text(f"{month_label:<4} ", style=Style(color=t['label_fg'], bold=True))

            for d_idx in range(31):
                if d_idx < days_in_month:
                    cell = model.cells[m_idx][d_idx]
                    is_today = (model.today_cell == (m_idx, d_idx))
                    line.append(self._paint_cell(cell, is_today=is_today))
                    line.append("  ")  # espaçamento proporcional ao '01 '
                else:
                    line.append("   ")  # dia inexistente no mês

            out.append(line)
            out.append("\n")

        return out

    def _render_calendar_matrix(self, model) -> Text:
        """Renderiza a matriz mensal de semanas (cal) compacta."""
        t = self.theme
        out = Text()

        # Cabeçalho dos dias da semana: '           D  S  T  Q  Q  S  S'
        header = Text("          ", style=Style(color=t['label_fg']))
        for day in model.col_labels:
            header.append(f"{day}  ", style=Style(color=t['header_fg'], bold=True))
        out.append(header)
        out.append("\n")

        # Linhas das Semanas
        for y, row_label in enumerate(model.row_labels):
            is_today_row = (model.today_row == y)
            row_style = Style(color=TODAY_FG, bold=True) if is_today_row else Style(color=t['label_fg'])
            line = Text(f"{row_label:<9} ", style=row_style)

            for x in range(len(model.col_labels)):
                cell = model.cells[y][x]
                is_today = (model.today_cell == (y, x))
                line.append(self._paint_cell(cell, is_today=is_today))
                line.append("  ")

            out.append(line)
            out.append("\n")

        return out

    def _build_legend(self) -> Text:
        t = self.theme
        legend = Text()
        items = [
            ('idle',  '0'),
            ('low',   'baixo'),
            ('mid',   'médio'),
            ('high',  'alto'),
            ('peak',  'pico'),
            ('alert', 'erro>30%'),
        ]
        for i, (key, label) in enumerate(items):
            s = t[key]
            style = Style(color=s['fg'], bgcolor=s['bg'], bold=(key in ('peak', 'alert')))
            legend.append(s['glyph'], style=style)
            legend.append(f" {label}", style=Style(color=t['axis_fg']))
            if i < len(items) - 1:
                legend.append("   ")
        return legend

    def _build_stats_line(self, stats: dict) -> Text:
        t = self.theme
        total = stats.get('total', 0)
        active = stats.get('active', 0)
        peak_lbl = stats.get('peak_label', '-')
        peak_cnt = stats.get('peak_count', 0)
        err_pct = stats.get('error_pct', 0.0)

        line = Text()
        line.append("Total: ", style=Style(color=t['axis_fg']))
        line.append(f"{total:,} cmds", style=Style(color=t['title'], bold=True))
        line.append(" · ", style=Style(color=t['axis_fg']))
        line.append(f"{active} dias ativos", style=Style(color=t['title']))
        line.append(" · Pico: ", style=Style(color=t['axis_fg']))
        line.append(f"{peak_lbl} ({peak_cnt})", style=Style(color=t['header_fg'], bold=True))
        line.append(" · Erros: ", style=Style(color=t['axis_fg']))

        err_style = Style(color='bright_red', bold=True) if err_pct > 0 else Style(color='green')
        line.append(f"{err_pct:.1f}%", style=err_style)
        return line

    def render(self, model) -> None:
        """Ponto de entrada: renderiza o modelo em modo compacto."""
        t = self.theme
        sub = f" · {model.subtitle}" if model.subtitle else ""
        title = f"◤ TIMELINE NEXUS ◢ {model.scale.upper()} · {model.year or 'ALL'}{sub}"

        self.console.print()
        self.console.print(Text(title, style=Style(color=t['title'], bold=True)))
        self.console.print()

        if model.scale == 'day':
            self.console.print(self._render_day_matrix(model))
        elif model.scale == 'cal':
            self.console.print(self._render_calendar_matrix(model))
        else:
            # Fallback genérico para outras escalas
            for y, row_label in enumerate(model.row_labels):
                line = Text(f"{row_label:>4} ", style=Style(color=t['label_fg']))
                for x in range(len(model.col_labels)):
                    line.append(self._paint_cell(model.cells[y][x]))
                    line.append(" ")
                self.console.print(line)

        self.console.print(self._build_legend())
        self.console.print(self._build_stats_line(model.stats))
        self.console.print()

    def render_projects(self, model) -> None:
        """Renderiza a matriz de Projetos x Meses no ano."""
        t = self.theme
        self.console.print()
        title = f"◤ TIMELINE NEXUS ◢ PROJETOS HOSPEDEIROS · {model.year}"
        self.console.print(Text(title, style=Style(color=t['title'], bold=True)))
        self.console.print()

        # Determina a largura máxima do nome do projeto
        max_name_len = max([len(p.name) for p in model.projects] + [12])
        max_name_len = min(max_name_len, 25)

        # Cabeçalho
        header = Text(f"{'PROJETO':<{max_name_len + 3}} ", style=Style(color=t['label_fg'], bold=True))
        months = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']
        for m in months:
            header.append(f"{m} ", style=Style(color=t['header_fg'], bold=True))
        header.append(f"  {'TOTAL':>8}   {'ERROS':>6}   {'ÚLTIMO USO':>10}", style=Style(color=t['header_fg'], bold=True))
        self.console.print(header)

        # Linhas dos Projetos
        for p in model.projects:
            marker = "● " if p.is_current else "  "
            marker_style = Style(color=TODAY_FG, bold=True) if p.is_current else Style(color=t['axis_fg'])
            name_style = Style(color=TODAY_FG, bold=True) if p.is_current else Style(color=t['title'])

            line = Text(marker, style=marker_style)
            line.append(f"{p.name[:max_name_len]:<{max_name_len}} ", style=name_style)

            # Glifos dos 12 meses
            for cell in p.cells:
                line.append(self._paint_cell(cell))
                line.append("   ")

            # Totais, erros e data
            line.append(f" {p.total_cmds:>8,}   ", style=Style(color=t['title']))
            err_style = Style(color='bright_red', bold=True) if p.error_pct > 1.0 else Style(color='green')
            line.append(f"{p.error_pct:>5.1f}%   ", style=err_style)
            line.append(f"{p.last_seen:>10}", style=Style(color=t['axis_fg']))

            self.console.print(line)

        self.console.print()
        self.console.print(self._build_legend())
        
        # Linha de sumário
        summary = Text()
        summary.append(f"Projetos catalogados: ", style=Style(color=t['axis_fg']))
        summary.append(f"{model.active_projects_count}", style=Style(color=t['title'], bold=True))
        summary.append(f" · Comandos no ano: ", style=Style(color=t['axis_fg']))
        summary.append(f"{model.total_cmds_global:,}", style=Style(color=t['title'], bold=True))
        summary.append(f" · Projeto ativo no terminal: ", style=Style(color=t['axis_fg']))
        summary.append(f"{model.current_project} (●)", style=Style(color=TODAY_FG, bold=True))
        self.console.print(summary)
        self.console.print()

def get_renderer(theme: str = 'cyberpunk') -> HeatmapRenderer:
    return HeatmapRenderer(theme=theme)
