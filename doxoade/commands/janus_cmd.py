# -*- coding: utf-8 -*-
# doxoade/commands/janus_cmd.py
"""
🏛️ JANUS CLI — Painel de Controle de Compiladores C/C++.
Permite visualizar o compilador ativo, arquitetura, SIMD e forçar re-varredura.
"""
from __future__ import annotations

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from doxoade.tools.janus_systems import Janus
from doxoade.tools.janus_systems.janus_manifest import JanusManifest


@click.group('janus')
def janus_group():
    """🏛️ Janus Toolchain: Gestão e Descoberta de Compiladores C/C++."""
    pass


@janus_group.command('status')
def janus_status():
    """Exibe o compilador registrado e o status do ambiente."""
    info = Janus.get_info()
    console = Console()
    from doxoade.tools.janus_systems.janus_cpu import JanusCPU
    cpu = JanusCPU.profile()
    
    if not info:
        console.print("[bold red]✘ Nenhum compilador C/C++ detectado na máquina.[/bold red]")
        console.print("[yellow]💡 Instale o MinGW (Windows), WinLibs ou Clang (Termux: pkg install clang).[/yellow]")
        return

    table = Table(
        title="🏛️ JANUS TOOLCHAIN — STATUS DO COMPILADOR ATIVO",
        header_style="bold cyan",
        border_style="dim cyan"
    )
    table.add_column("Propriedade", style="bold white", width=22)
    table.add_column("Valor / Configuração", style="cyan")

    table.add_row("Processador (CPU)", f"[bold white]{cpu.model_name}[/bold white]")
    table.add_row("SIMD Tier Ativo", f"[bold magenta]{cpu.simd_tier}[/bold magenta]")
    table.add_row("Flags Otimizadas", f"[dim green]{' '.join(cpu.optimal_cflags)}[/dim green]")
    
    table.add_row("Compilador C (CC)", info.compiler_path)
    table.add_row("Compilador C++ (CXX)", info.gpp_path or "[dim]Não disponível[/dim]")
    table.add_row("Tipo de Compilador", f"[bold green]{info.compiler_type.upper()}[/bold green]")
    table.add_row("Versão", info.version)
    table.add_row("Arquitetura Alvo", info.target_machine)
    table.add_row("Suporte a SIMD", "[bold green]✔ SIM[/bold green]" if info.supports_simd else "[yellow]✘ NÃO[/yellow]")
    table.add_row("Provedor Detectado", f"[bold yellow]{info.provider}[/bold yellow]")

    manifest_path = Path.cwd() / ".doxoade" / "janus" / "compiler_manifest.json"
    table.add_row("Manifesto em Disco", str(manifest_path))

    console.print("\n")
    console.print(table)
    console.print("\n")


@janus_group.command('scan')
def janus_scan():
    """Força uma nova varredura no sistema operacional e atualiza o manifesto."""
    console = Console()
    console.print("[cyan]🔍 [JANUS] Executando varredura profunda de compiladores no sistema...[/cyan]")
    
    info = Janus.get_info(force_scan=True)
    if info:
        console.print(f"[bold green]✔ Compilador localizado e registrado com sucesso![/bold green]")
        console.print(f"  • Binário: [bold white]{info.compiler_path}[/bold white]")
        console.print(f"  • Tipo: [bold yellow]{info.compiler_type.upper()}[/bold yellow] ({info.provider})")
        console.print(f"  • Versão: {info.version}\n")
    else:
        console.print("[bold red]✘ Nenhum compilador localizado durante a varredura.[/bold red]\n")
