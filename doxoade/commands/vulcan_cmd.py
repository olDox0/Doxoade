# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
"""
Módulo de Comando Vulcan - v82.1 Omega.
Interface de Ignição para Otimização Nativa (C/Cython).
"""

import os
import sys
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _find_project_root
# [DOX-UNUSED] from .run_systems.run_vulcan import apply_vulcan_turbo

__version__ = "82.1 Omega (Forge-Core)"

# Certifique-se de que o grupo e o comando estão aqui
@click.group('vulcan')
def vulcan_group():
    """🔥 Projeto Vulcano: Alta Performance Nativa (C/Cython)."""
    pass

#@vulcan_group.command('auto') # O registro acontece AQUI, dentro do módulo
#def vulcan_auto():
#    """Otimização Autônoma baseada em Telemetria (PASC-6.4)."""
#    from ..tools.vulcan.autopilot import vulcan_autopilot
#    vulcan_autopilot.scan_and_optimize()

@vulcan_group.command('ignite')
@click.option('--force', is_flag=True, help="Força a re-compilação de todos os Hot-Paths.")
@click.pass_context
def ignite(ctx, force):
    """Transforma Hot-Paths detectados em binários de alta velocidade."""
    root = _find_project_root(os.getcwd())
    
    with ExecutionLogger('vulcan_ignite', root, ctx.params) as _:
        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔥 [VULCAN-IGNITION] Iniciando Ciclo de Forja v{__version__}...{Fore.RESET}")
        
        # 1. Diagnóstico de Ambiente (PASC 8.1)
        from ..tools.vulcan.diagnostic import VulcanDiagnostic
        diag = VulcanDiagnostic(root)
        ok, report = diag.check_environment()
        
        if not ok:
            diag.render_report()
            click.echo(f"\n{Fore.RED}✘ [BLOQUEIO] Ambiente insuficiente para ignição nativa.{Fore.RESET}")
            sys.exit(1)

        # 2. Orquestração de Otimização (Vulcan Autopilot)
        # O Autopilot lê o Advisor (8.833 hits) e chama o Forge + Compiler
        from ..tools.vulcan.autopilot import VulcanAutopilot
        autopilot = VulcanAutopilot(root)
        
        try:
            click.echo(f"{Fore.CYAN}   > Analisando rastro do Chronos (Lookup: Hot-Paths)...{Fore.RESET}")
            autopilot.scan_and_optimize()
            
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ [VULCAN] Forja concluída com sucesso.{Fore.RESET}")
            click.echo("   > Próxima execução com 'doxoade run' usará modo turbo.")
            
        except Exception as e:
            _print_vulcan_forensic("IGNITE", e)
            sys.exit(1)

@vulcan_group.command('status')
def vulcan_status():
    """Lista módulos otimizados e ganhos de performance."""
    root = _find_project_root(os.getcwd())
    bin_dir = os.path.join(root, ".doxoade", "vulcan", "bin")
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🛡  ESTADO DA FOUNDRY VULCAN:{Style.RESET_ALL}")
    
    if not os.path.exists(bin_dir):
        click.echo("   Nenhum módulo forjado para este projeto.")
        return

    binaries = [f for f in os.listdir(bin_dir) if f.endswith(('.pyd', '.so'))]
    if not binaries:
        click.echo("   Nenhum binário ativo encontrado.")
    else:
        for b in binaries:
            size = os.path.getsize(os.path.join(bin_dir, b)) / 1024
            click.echo(f"   {Fore.GREEN}● {b:<25} {Fore.WHITE}| {size:>6.1f} KB {Fore.YELLOW}[ATIVO]")

@vulcan_group.command('purge')
def vulcan_purge():
    """Remove todos os binários e códigos temporários da forja."""
    root = _find_project_root(os.getcwd())
    from ..tools.vulcan.environment import VulcanEnvironment
    env = VulcanEnvironment(root)
    
    if click.confirm(f"{Fore.RED}Deseja realmente limpar a foundry Vulcano?{Fore.RESET}"):
        env.purge_unstable()
        click.echo(f"{Fore.GREEN}Foundry purificada.{Fore.RESET}")

def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    import sys as _sys, os as _os
    _, _, exc_tb = _sys.exc_info()
    f_name = _os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0
    
    click.echo(f"\n\033[1;34m[ FORENSIC:VULCAN:{scope} ]\033[0m \033[1mFile: {f_name} | L: {line_n}\033[0m")
    click.echo(f"\033[31m    ■ Tipo : {type(e).__name__}\n    ■ Valor: {e}\033[0m")