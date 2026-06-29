# doxoade/commands/engine_cmd.py
import sys
import os
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

@click.group('engine')
def engine_group():
    """⚙️  Gerenciamento Central dos Motores de Background."""
    pass

@engine_group.command('status')
def engine_status():
    """Exibe o estado atual dos interceptadores no MetaPath."""
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}╔════════════════════════════════════════╗")
    click.echo(f"║     NEXUS BACKGROUND ENGINE STATUS     ║")
    click.echo(f"╚════════════════════════════════════════╝{Style.RESET_ALL}\n")
    
    click.echo(f"{Fore.WHITE}■ Variáveis de Ambiente:{Style.RESET_ALL}")
    click.echo(f"  DOXOADE_QUIET_BOOT : {os.environ.get('DOXOADE_QUIET_BOOT', '0')}")
    click.echo(f"  DOXOADE_SHADOW     : {os.environ.get('DOXOADE_SHADOW', '1')}")
    click.echo(f"  DOXOADE_RESCUE     : {os.environ.get('DOXOADE_RESCUE', '1')}")
    click.echo(f"  VULCAN_VERBOSE     : {os.environ.get('VULCAN_VERBOSE', '0')}")

    click.echo(f"\n{Fore.WHITE}■ Topologia sys.meta_path:{Style.RESET_ALL}")
    vulcan_ok = False
    shadow_ok = False
    
    for i, finder in enumerate(sys.meta_path):
        # Tenta extrair o nome real, caso seja uma classe nativa do Python
        name = getattr(finder, '__name__', type(finder).__name__)
        
        if "VulcanMetaFinder" in name:
            if isinstance(finder, type):
                click.echo(f"  {i}. {Fore.RED}{name:<20}{Style.RESET_ALL} [!] AVISO: CLASSE INVÁLIDA (LIXO)")
            else:
                vulcan_ok = True
                click.echo(f"  {i}. {Fore.GREEN}{name:<20}{Style.RESET_ALL} [TIER 1 - Redirecionamento Ativo]")
        elif "ShadowFinder" in name:
            if isinstance(finder, type):
                click.echo(f"  {i}. {Fore.RED}{name:<20}{Style.RESET_ALL} [!] AVISO: CLASSE INVÁLIDA (LIXO)")
            else:
                shadow_ok = True
                click.echo(f"  {i}. {Fore.YELLOW}{name:<20}{Style.RESET_ALL} [VIGILÂNCIA - Vacinação AST]")
        elif isinstance(finder, type):
            # Motores nativos do Python (PathFinder, BuiltinImporter, etc)
            click.echo(f"  {i}. {Fore.WHITE}{name:<20}{Style.RESET_ALL} 🔒 [Nativo Python (Built-in)]")
        else:
            click.echo(f"  {i}. {Style.DIM}{name:<20}{Style.RESET_ALL} 🔹 [Nativo Python (Instância)]")
            
        cwd_root = Path.cwd()
        opt_dir = cwd_root / '.doxoade' / 'vulcan' / 'opt_py'
        opt_count = len(list(opt_dir.glob('opt_*.py'))) if opt_dir.exists() else 0

        click.echo(f"\n{Fore.WHITE}■ Tier 2 (Python Otimizado):{Style.RESET_ALL}")
        if opt_count > 0:
            click.echo(f"  {Fore.CYAN}opt_py: {opt_count} arquivo(s) em {opt_dir}{Style.RESET_ALL}")
            tier2_ok = True
        else:
            click.echo(f"  {Fore.RED}opt_py: Nenhum arquivo encontrado em {opt_dir}{Style.RESET_ALL}")
            tier2_ok = False

        # Atualizar o diagnóstico geral para incluir tier2_ok
        if vulcan_ok and shadow_ok and tier2_ok:
            click.echo(f"  {Fore.GREEN}✔ SISTEMA GOLD: Todos os tiers operacionais.{Style.RESET_ALL}")
        elif vulcan_ok and shadow_ok:
            click.echo(f"  {Fore.YELLOW}⚠ SISTEMA SILVER: Tier 1 ativo, Tier 2 ausente.{Style.RESET_ALL}")
            
    click.echo(f"\n{Fore.WHITE}■ Diagnóstico Geral:{Style.RESET_ALL}")
    if vulcan_ok and shadow_ok:
        click.echo(f"  {Fore.GREEN}✔ SISTEMA GOLD: Motores alinhados perfeitamente.{Style.RESET_ALL}")
    else:
        click.echo(f"  {Fore.RED}✘ SISTEMA DEGRADADO: Motores ausentes ou corrompidos.{Style.RESET_ALL}")
    print()