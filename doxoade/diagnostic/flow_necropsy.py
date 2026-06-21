# doxoade/doxoade/diagnostic/flow_necropsy.py
import os
import sys
# [DOX-UNUSED] import time
import click
# [DOX-UNUSED] from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
# [DOX-UNUSED] from doxoade.database import get_db_connection
# [DOX-UNUSED] from doxoade.tools.telemetry_tools.logger import chief_heartbeat
try:
    from doxoade.tools.engine_control import NexusEngineGuard # <-- VITAL
except Exception as e:
    import sys as exc_sys
    from traceback import print_tb as exc_trace
    _, exc_obj, exc_tb = exc_sys.exc_info()
    exc_trace(exc_tb)
    from doxoade.rescue import activate_protocol
    import traceback
    activate_protocol(traceback.format_exc())

@click.command('flow-diag')
def run_flow_necropsy():
    """Painel de Controle de Motores Nexus."""
    click.secho("\n╔══════════════════════════════════════════════════════╗", fg='cyan')
    click.secho("║       NEXUS SYSTEMS STATUS (VIGILÂNCIA ATIVA)        ║", fg='cyan', bold=True)
    click.secho("╚══════════════════════════════════════════════════════╝", fg='cyan')

    # 1. Mapeamento de MetaPath (Quem manda na importação)
    click.echo(f"\n{Fore.WHITE}■ BUS DE IMPORTAÇÃO (MetaPath):{Style.RESET_ALL}")
    for i, finder in enumerate(sys.meta_path):
        name = type(finder).__name__
        status = f"{Fore.GREEN}[ATIVO]{Fore.RESET}" if "Shadow" in name or "Vulcan" in name else f"{Style.DIM}[STD]"
        click.echo(f"  {i:02d}. {name:<25} {status}")

    # 2. Configurações de Força (Onde a verdade reside)
    from doxoade.tools.filesystem import _get_project_config
    config = _get_project_config(start_path=os.getcwd())
    
    click.echo(f"\n{Fore.WHITE}■ ESTADO DOS MOTORES (Memória vs TOML):{Style.RESET_ALL}")
    
    def check_motor(name, env_var):
        # Verifica se o Finder está fisicamente no sys.meta_path
        is_in_path = any(name in str(f) for f in sys.meta_path)
        toml_val = config.get(name.lower().replace('finder', '_runtime'), 'False')
        env_val = os.environ.get(env_var, 'Not Set')
        
        color = Fore.GREEN if is_in_path else Fore.RED
        status = "ON" if is_in_path else "OFF"
        click.echo(f"  • {name:<15} : {color}{status}{Style.RESET_ALL} (TOML: {toml_val} | ENV: {env_val})")

    check_motor('ShadowFinder', 'DOXOADE_SHADOW')
    check_motor('VulcanFinder', 'VULCAN_TURBO')
    
    def get_status(key, env_var):
        val = os.environ.get(env_var)
        if val is not None:
            return f"{Fore.YELLOW}{val} (via ENV)"
        return f"{Fore.CYAN}{config.get(key, 'False')} (via TOML)"

    click.echo(f"  • Shadow Runtime : {get_status('shadow_runtime', 'DOXOADE_SHADOW')}")
    click.echo(f"  • Sotéria Rescue : {get_status('soteria_active', 'DOXOADE_RESCUE')}")
    click.echo(f"  • Vulcan Turbo   : {get_status('vulcan_turbo', 'VULCAN_TURBO')}")

    # 3. Verificador de Interferência
    click.echo(f"\n{Fore.WHITE}■ DIAGNÓSTICO DE PUREZA:{Style.RESET_ALL}")
    active_interference = [m for m in sys.modules if 'pytest' in m or 'unittest' in m]
    if active_interference:
        click.secho(f"  ⚠  AMBIENTE POLUÍDO: {len(active_interference)} módulos de teste pré-carregados.", fg='yellow')
    else:
        click.secho("  ✔  AMBIENTE PURO: Sem interferência externa.", fg='green')
    
    states = NexusEngineGuard.get_engine_states(os.getcwd())
    
    click.echo(f"\n{Fore.WHITE}■ AUDITORIA DE MOTORES DE BACKGROUND:{Style.RESET_ALL}")
    for s in states:
        color = Fore.GREEN if s.integrity == "OK" and s.active else Fore.RED
        if s.integrity == "DIVERGENT": color = Fore.YELLOW
        
        click.echo(f"  • {s.name:<10} : {color}{'ONLINE' if s.active else 'OFFLINE':<8}{Style.RESET_ALL} "
                   f"| Integridade: {s.integrity:<10} | Alvo: {s.mode}")
    
    click.echo("")

if __name__ == "__main__":
    run_flow_necropsy()