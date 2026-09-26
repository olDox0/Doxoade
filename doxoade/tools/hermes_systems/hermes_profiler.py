# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_profiler.py
"""
☤ HERMES PROFILER — Raio-X de Precisão para o Pipeline HBC.
Compara o custo real em micro-segundos (µs) entre Python Puro, .pyc e Hermes C-Bridge.
"""
from __future__ import annotations

import sys
import os
import time
import importlib
import importlib.util
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from doxoade.tools.filesystem import _find_project_root


class HermesProfiler:
    def __init__(self, project_root: Path):
        self.root = project_root.resolve()
        self.build_dir = self.root / ".doxoade" / "hermes" / "build"
        self.console = Console()

    def _benchmark_import(self, module_name: str, mode: str) -> float:
        """
        Mede o tempo de importação em microssegundos isolando o sys.modules.
        mode: 'pure' | 'hermes'
        """
        # Limpa o módulo e submódulos da memória para forçar carga fria
        to_del = [m for m in sys.modules if m == module_name or m.startswith(module_name + ".")]
        for m in to_del:
            del sys.modules[m]

        t0 = time.perf_counter_ns()
        try:
            importlib.import_module(module_name)
            elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
            return elapsed_us
        except Exception as e:
            return -1.0

    def profile_module(self, module_name: str):
        """Executa a necropsia comparativa de um módulo."""
        self.console.print(f"\n[bold magenta]☤ HERMES COLD-START PROFILE: [cyan]{module_name}[/cyan][/bold magenta]\n")

        # 1. Mede custo do find_spec com e sem o Hermes no sys.meta_path
        hbc6_finder = next((f for f in sys.meta_path if "HBC6Finder" in type(f).__name__), None)
        
        find_spec_hermes_us = 0.0
        if hbc6_finder:
            t0 = time.perf_counter_ns()
            try:
                hbc6_finder.find_spec(module_name, None)
            except Exception:
                pass
            find_spec_hermes_us = (time.perf_counter_ns() - t0) / 1000.0

        # 2. Benchmark A/B de Importação Real
        # A: Modo Nativo Hermes
        time_hermes_us = self._benchmark_import(module_name, mode="hermes")

        # B: Modo Python Puro (Desinstalando temporariamente os finders)
        saved_finders = [f for f in sys.meta_path if "HBC6Finder" in type(f).__name__ or "Vulcan" in type(f).__name__]
        for f in saved_finders:
            sys.meta_path.remove(f)

        time_python_us = self._benchmark_import(module_name, mode="pure")

        # Restaura os finders
        for f in saved_finders:
            sys.meta_path.insert(0, f)

        # 3. Tabela Comparativa de Resultados
        table = Table(
            title=f"📊 Desempenho Real de Carga: {module_name}",
            header_style="bold cyan",
            border_style="dim cyan"
        )
        table.add_column("Cenário de Execução", style="white", width=26)
        table.add_column("Tempo Total (µs)", justify="right", style="bold yellow")
        table.add_column("Tempo (ms)", justify="right", style="dim white")
        table.add_column("Veredito", style="white")

        if time_python_us > 0:
            table.add_row("1. Python Puro (Disco/.py)", f"{time_python_us:,.1f} µs", f"{time_python_us/1000:.2f} ms", "[cyan]Baseline Padrão[/cyan]")
        
        if time_hermes_us > 0:
            diff = time_hermes_us - time_python_us
            if time_hermes_us < time_python_us:
                speedup = time_python_us / time_hermes_us
                verdict = f"[bold green]✔ {speedup:.2f}× mais rápido[/bold green]"
            else:
                slower = time_hermes_us / time_python_us if time_python_us > 0 else 1.0
                verdict = f"[bold red]✘ {slower:.2f}× mais LENTO (Overhead)[/bold red]"

            table.add_row("2. Hermes (HBC6 / Motor C)", f"{time_hermes_us:,.1f} µs", f"{time_hermes_us/1000:.2f} ms", verdict)

        self.console.print(table)

        # 4. Detalhamento do Overhead do MetaPath
        breakdown_text = (
            f"  • [bold yellow]Tempo gasto apenas no find_spec (Checagem de Hash SHA-256):[/bold yellow] "
            f"[bold red]{find_spec_hermes_us:,.1f} µs[/bold red] ({find_spec_hermes_us/1000:.3f} ms)\n"
            f"  • [dim]Se o find_spec for maior que 1.000 µs (1ms), o overhead do disco anula qualquer ganho do C.[/dim]"
        )
        self.console.print(Panel(breakdown_text, title="[bold blue]🔬 Análise Forense de Atrito[/bold blue]", border_style="blue"))
        self.console.print("\n")
