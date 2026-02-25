# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
import os
import sys
import click
import signal

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.vulcan.diagnostic import VulcanDiagnostic
from doxoade.tools.vulcan.auto_repair import auto_repair_module
from ..shared_tools import ExecutionLogger, _find_project_root

__version__ = "83.1 Omega (Pitstop-Ready)"

def _sigint_handler(signum, frame):
    click.echo(f"\n{Fore.RED}Comando interrompido. Saindo...{Style.RESET_ALL}")
    sys.exit(130)

@click.group('vulcan')
def vulcan_group():
    """🔥 Projeto Vulcano: Alta Performance Nativa (C/Cython)."""
    pass

@vulcan_group.command('doctor')
@click.option('--module', help='Nome do m?dulo Python a tentar reparar (ex: doxoade.tools.streamer)')
@click.option('--srcdir', help='Caminho para o c?digo-fonte do m?dulo (opcional)')
@click.option('--retries', default=1, type=int)
def doctor(module, srcdir, retries):
    """Executa diagn?stico Vulcan + tenta reparo autom?tico de um m?dulo."""
    project_root = '.'  # ou calc via shared_tools._find_project_root
    diag = VulcanDiagnostic(project_root)
    ok, results = diag.check_environment()
    click.echo(f"Diagnostic: compiler_ok={results.get('compiler')} cython={results.get('cython')}")
    # Run ABI gate first
    from doxoade.tools.vulcan.abi_gate import run_abi_gate
    run_abi_gate(project_root)
    if module:
        res = auto_repair_module(project_root, module, module_src_dir=srcdir, retries=retries)
        click.echo(res)
    else:
        click.echo("Use --module to attempt to repair a specific module.")

@vulcan_group.command('ignite')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help="Força a re-compilação de todos os alvos.")
@click.pass_context
def ignite(ctx, path, force):
    """Transforma código Python em binários de alta velocidade."""
    signal.signal(signal.SIGINT, _sigint_handler)
    root = _find_project_root(os.getcwd())
    
    with ExecutionLogger('vulcan_ignite', root, ctx.params) as _:
        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔥 [VULCAN-IGNITION] v{__version__}...{Style.RESET_ALL}")
        
        from ..tools.vulcan.diagnostic import VulcanDiagnostic
        diag = VulcanDiagnostic(root)
        ok, _ = diag.check_environment()
        
        if not ok:
            diag.render_report(); sys.exit(1)
            
        from ..tools.vulcan.autopilot import VulcanAutopilot
        autopilot = VulcanAutopilot(root)
        
        candidates, mode = [], "AUTOMÁTICO (baseado em telemetria)"
        
        if path:
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                mode = f"MANUAL (arquivo: {os.path.basename(abs_path)})"
                candidates.append({'file': abs_path})
            elif os.path.isdir(abs_path):
                mode = f"MANUAL (diretório: {os.path.basename(abs_path)})"
                from ..dnm import DNM
                dnm = DNM(abs_path)
                py_files = dnm.scan(extensions=['py'])
                candidates = [{'file': f} for f in py_files]
        
        click.echo(f"{Fore.CYAN}   > Modo de Operação: {mode}{Style.RESET_ALL}")

        try:
            autopilot.scan_and_optimize(candidates=candidates, force_recompile=force)
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ [VULCAN] Forja concluída.{Style.RESET_ALL}")
        except KeyboardInterrupt:
            _sigint_handler(None, None)
        except Exception as e:
            _print_vulcan_forensic("IGNITE", e)
            sys.exit(1)

@vulcan_group.command('status')
def vulcan_status():
    """Lista m?dulos otimizados e ganhos de performance."""
    root = _find_project_root(os.getcwd())
    bin_dir = os.path.join(root, ".doxoade", "vulcan", "bin")
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ESTADO DA FOUNDRY VULCAN:{Style.RESET_ALL}")
    
    if not os.path.exists(bin_dir):
        click.echo("   Nenhum m?dulo forjado para este projeto.")
        return

    binaries = [f for f in os.listdir(bin_dir) if f.endswith(('.pyd', '.so'))]
    if not binaries:
        click.echo("   Nenhum bin?rio ativo encontrado.")
    else:
        for b in binaries:
            size = os.path.getsize(os.path.join(bin_dir, b)) / 1024
            click.echo(f"   {Fore.GREEN}{b:<25} {Fore.WHITE}| {size:>6.1f} KB {Fore.YELLOW}[ATIVO]")

@vulcan_group.command('purge')
def vulcan_purge():
    """Remove todos os bin?rios e c?digos tempor?rios da forja."""
    root = _find_project_root(os.getcwd())
    from ..tools.vulcan.environment import VulcanEnvironment
    env = VulcanEnvironment(root)
    
    if click.confirm(f"{Fore.RED}Deseja realmente limpar a foundry Vulcano?{Fore.RESET}"):
        env.purge_unstable()
        click.echo(f"{Fore.GREEN}Foundry purificada.{Fore.RESET}")

def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    import sys as exc_sys, os as exc_os
    _, exc_obj, exc_tb = exc_sys.exc_info()
    f_name = exc_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0
    
    click.echo(f"\n\033[1;34m\n[ ■ FORENSIC:VULCAN:{scope} ]\033[0m \033[1m\n ■ File: {f_name} | L: {line_n}\033[0m")
    click.echo(f"\033[31m\n ■ Tipo: {type(e).__name__} \n ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))} \n ■ Valor: {e}\n\033[0m")