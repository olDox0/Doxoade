# -*- coding: utf-8 -*-
# doxoade/commands/engine_cmd.py
"""
⚙️  ZEUS — Gerenciamento Central dos Motores de Background.
Permite inspecionar, ligar e desligar módulos legados do arranque.
"""
from __future__ import annotations

import os
import sys
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from doxoade.tools.filesystem import _find_project_root
from doxoade.boot import (
    load_engine_config,
    save_engine_config,
    DEFAULT_ENGINES,
    get_engine_config_path
)


@click.group('engine')
def engine_group():
    """⚙️  Gerenciamento Central dos Motores de Background."""
    pass


@engine_group.command('status')
def engine_status():
    """Exibe o estado de cada motor de boot e o sys.meta_path."""
    root = _find_project_root(os.getcwd())
    cfg = load_engine_config(root)
    console = Console()

    table = Table(
        title="⚙️  PAINEL DE MOTORES DE BACKGROUND (DOXOADE BOOT)",
        header_style="bold cyan",
        border_style="dim cyan"
    )
    table.add_column("Motor ID", style="bold white", width=18)
    table.add_column("Status", width=12)
    table.add_column("Finalidade / Papel", style="dim white")

    descriptions = {
        "hermes_init": "Bootstrap nativo C de módulos críticos",
        "metalcraft": "Compilação de alvos C (metalcraft.toml)",
        "hermes_diag": "Diagnostic Hooks e Logger Assíncrono",
        "abi_gate": "Auditor de arquitetura de binários .pyd/.so",
        "vulcan_meta": "Interceptador Tier 1 de imports nativos",
        "shadow_runtime": "Vigilância NSR e injeção de vacinas AST",
        "horus": "Observabilidade de incepção",
        "lazarus": "Escudo de resgate global (sys.excepthook)",
        "hermes_bridge": "Bridge C SSE 4.2 compilado",
        "hbc6": "Carregador de bytecode comprimido HBC6",
    }

    for engine_id, is_active in cfg.items():
        status_badge = "[bold green]🟢 ATIVO[/bold green]" if is_active else "[bold red]🔴 DESLIGADO[/bold red]"
        desc = descriptions.get(engine_id, "Subsistema interno")
        table.add_row(engine_id, status_badge, desc)

    console.print("\n")
    console.print(table)

    # Detalhe do MetaPath
    console.print("[bold yellow]Topologia sys.meta_path ativa:[/bold yellow]")
    for i, finder in enumerate(sys.meta_path):
        name = getattr(finder, '__name__', type(finder).__name__)
        name = finder.__name__ if hasattr(finder, '__name__') else type(finder).__name__
        console.print(f"  {i}. [cyan]{name}[/cyan]")
    
    conf_path = get_engine_config_path(root)
    console.print(f"\n[dim]Arquivo de configuração: {conf_path}[/dim]\n")


@engine_group.command('enable')
@click.argument('engine_name')
def engine_enable(engine_name: str):
    """Ativa um motor específico de inicialização."""
    root = _find_project_root(os.getcwd())
    cfg = load_engine_config(root)
    key = engine_name.lower().strip()

    if key not in DEFAULT_ENGINES:
        click.secho(f"Motor '{key}' não reconhecido.", fg="red")
        click.echo(f"Opções válidas: {', '.join(DEFAULT_ENGINES.keys())}")
        return

    cfg[key] = True
    save_engine_config(root, cfg)
    click.secho(f"✔ Motor '{key}' ATIVADO com sucesso.", fg="green", bold=True)


@engine_group.command('disable')
@click.argument('engine_name')
def engine_disable(engine_name: str):
    """Desativa um motor específico do arranque."""
    root = _find_project_root(os.getcwd())
    cfg = load_engine_config(root)
    key = engine_name.lower().strip()

    if key not in DEFAULT_ENGINES:
        click.secho(f"Motor '{key}' não reconhecido.", fg="red")
        click.echo(f"Opções válidas: {', '.join(DEFAULT_ENGINES.keys())}")
        return

    cfg[key] = False
    save_engine_config(root, cfg)
    click.secho(f"✔ Motor '{key}' DESATIVADO.", fg="yellow", bold=True)


@engine_group.command('reset')
def engine_reset():
    """Restaura todos os motores para a configuração padrão."""
    root = _find_project_root(os.getcwd())
    save_engine_config(root, DEFAULT_ENGINES)
    click.secho("✔ Todos os motores de boot foram restaurados para a configuração padrão.", fg="green", bold=True)

