# doxoade/commands/lite_xl_systems/cmd_ghost_trace.py
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.lite_xl_systems.typhon_deploy import TyphonDeployEngine

@click.command("trace-ghost", help="Rastreia travamentos (Ghost Windows) no deploy de teste.")
def cmd_trace_ghost():
    test_dir = TyphonDeployEngine._get_deploy_dir("test")
    trace_log = test_dir / ".doxoade" / "diagnostics" / "ghost_trace.txt"
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}👻 GHOST TRACER ANALYSIS{Style.RESET_ALL}")
    
    if not trace_log.exists():
        click.echo(f"{Fore.GREEN}✔ Nenhum travamento de frame (>50ms) detectado no último teste.{Fore.RESET}")
        return
        
    click.echo(f"{Fore.RED}⚠ TRAVAMENTOS DETECTADOS:{Fore.RESET}")
    lines = trace_log.read_text(encoding="utf-8").splitlines()
    for line in lines[-10:]: # Últimos 10 eventos
        click.echo(f"  {Fore.YELLOW}↳{Fore.RESET} {line}")
        
    click.echo(f"\n{Fore.LIGHTBLACK_EX}Dica: O módulo listado é o provável causador do congelamento.{Fore.RESET}")
