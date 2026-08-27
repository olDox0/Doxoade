# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/timeline_cli.py
""" Timeline Nexus - Sistema de Visualização Cronológica.
Comando principal para análise temporal de dados do Doxoade. """

import click
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.timeline_systems.tml_engine.tml_cmd_history import (
    cmd_history,
    heatmap_data,
)


@click.group('timeline')
def timeline_group():
    """📊 Timeline Nexus: Visualização e Análise Temporal de Dados."""
    pass


timeline_group.add_command(cmd_history)
timeline_group.add_command(heatmap_data)


@timeline_group.command('heatmap')
@click.option('--scale', type=click.Choice(['hour', 'week', 'day', 'month']),
              default='day', help='Escala temporal (day=12x31 anual, hour=7x24, week=semanasx24)')
@click.option('--year', '-y', type=int, default=None, help='Ano alvo (padrão: ano atual)')
@click.option('--month', '-m', type=int, default=None, help='Mês específico (1-12) para detalhe mensal')
@click.option('--command', '-c', default=None, help='Filtra por comando específico')
@click.option('--search', help='Busca termo na linha de comando')
@click.option('--theme', type=click.Choice(['cyberpunk', 'mono']),
              default='cyberpunk', help='Tema visual')
@click.option('--raw', is_flag=True, help='Usa renderização textual simples (sem Rich)')
def heatmap_cmd(scale, year, month, command, search, theme, raw):
    """Exibe heatmap de atividade temporal compacto e limpo."""
    from doxoade.commands.timeline_systems.tml_engine.activity_heatmap import ActivityHeatmap
    
    orch = ActivityHeatmap()
    month_idx = (month - 1) if month is not None else None

    if scale == 'week':
        models = orch.build_week_stack(year=year, command=command, search=search, month=month_idx)
        if raw:
            for mdl in models:
                click.echo(mdl.preview())
        else:
            from doxoade.commands.timeline_systems.tml_display.heatmap_renderer import get_renderer
            renderer = get_renderer(theme)
            for mdl in models:
                renderer.render(mdl)
    else:
        model = orch.build(scale=scale, year=year, command=command,
                           search=search, month=month_idx)
        if raw:
            click.echo(model.preview())
        else:
            from doxoade.commands.timeline_systems.tml_display.heatmap_renderer import get_renderer
            get_renderer(theme).render(model)


@timeline_group.command('view')
@click.option('--date', '-d', help='Data específica (YYYY-MM-DD)')
@click.option('--hour', '-h', type=int, help='Hora específica (0-23)')
@click.option('--command', '-c', help='Filtra por comando')
def view_cmd(date, hour, command):
    """Visualiza detalhes de um período específico."""
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [TIMELINE] View Detalhado ---{Style.RESET_ALL}")
    if date:
        click.echo(f"📅 Data: {date}")
    if hour is not None:
        click.echo(f"🕐 Hora: {hour:02d}:00")
    if command:
        click.echo(f" Comando: {command}")


@timeline_group.command('explore')
@click.option('--scale', type=click.Choice(['hour', 'day', 'month']),
              default='day', help='Escala inicial da navegação')
@click.option('--year', '-y', type=int, default=None, help='Ano alvo')
@click.option('--theme', type=click.Choice(['cyberpunk', 'mono']),
              default='cyberpunk', help='Tema visual')
def explore_cmd(scale, year, theme):
    """Modo interativo de navegação temporal (TUI)."""
    from doxoade.commands.timeline_systems.tml_display.tml_navigation import launch_explorer
    launch_explorer(scale=scale, year=year, theme=theme)


@timeline_group.command('projects')
@click.option('--year', '-y', type=int, default=None, help='Ano alvo (padrão: ano atual)')
@click.option('--limit', '-n', default=20, help='Quantidade máxima de projetos exibidos')
@click.option('--theme', type=click.Choice(['cyberpunk', 'mono']),
              default='cyberpunk', help='Tema visual')
@click.option('--raw', is_flag=True, help='Usa renderização textual simples')
def projects_cmd(year, limit, theme, raw):
    """Exibe a distribuição temporal de uso do Doxoade por projeto hospedeiro."""
    from doxoade.commands.timeline_systems.tml_engine.activity_heatmap import ActivityHeatmap
    from doxoade.commands.timeline_systems.tml_display.heatmap_renderer import get_renderer

    orch = ActivityHeatmap()
    model = orch.build_projects_model(year=year, limit=limit)
    get_renderer(theme).render_projects(model)

timeline = timeline_group
