# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
"""
Módulo de Comando Vulcan - v82.1 Omega.
Interface de Ignição para Otimização Nativa (C/Cython).
"""

import os
import sys
import signal
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _find_project_root
from ..tools.vulcan.module_generator import generate_local_vulcan_module
# [DOX-UNUSED] from .run_systems.run_vulcan import apply_vulcan_turbo

__version__ = "82.1 Omega (Forge-Core)"


def _sigint_handler(signum, frame):
    click.echo(f"\n{Fore.RED}Comando interrompido. Saindo...{Style.RESET_ALL}")
    sys.exit(130)


@click.group('vulcan')
def vulcan_group():
    """🔥 Projeto Vulcano: Alta Performance Nativa (C/Cython)."""
    pass


@vulcan_group.command('doctor')
@click.option('--module', 'module_name', help='Nome do módulo Python a tentar reparar (ex: pacote.modulo).')
@click.option('--srcdir', help='Caminho para o código-fonte do módulo (opcional).')
@click.option('--retries', default=1, type=int, show_default=True)
def vulcan_doctor(module_name, srcdir, retries):
    """Executa diagnóstico Vulcan e tenta autorreparo quando disponível."""
    project_root = _find_project_root(os.getcwd())
    from ..tools.vulcan.diagnostic import VulcanDiagnostic

    diag = VulcanDiagnostic(project_root)
    ok, results = diag.check_environment()
    compiler_ok = results.get('compiler') if isinstance(results, dict) else None
    cython_ok = results.get('cython') if isinstance(results, dict) else None
    click.echo(f"Diagnostic: compiler_ok={compiler_ok} cython={cython_ok}")

    if not module_name:
        click.echo("Use --module para tentar reparo automático de um alvo específico.")
        return

    try:
        from ..tools.vulcan.auto_repair import auto_repair_module
    except Exception:
        click.echo(f"{Fore.YELLOW}[VULCAN-DOCTOR]{Fore.RESET} Auto-repair não disponível nesta build.")
        return

    try:
        result = auto_repair_module(project_root, module_name, module_src_dir=srcdir, retries=retries)
        click.echo(result)
    except Exception as e:
        _print_vulcan_forensic("DOCTOR", e)
        sys.exit(1)

#@vulcan_group.command('auto') # O registro acontece AQUI, dentro do módulo
#def vulcan_auto():
#    """Otimização Autônoma baseada em Telemetria (PASC-6.4)."""
#    from ..tools.vulcan.autopilot import vulcan_autopilot
#    vulcan_autopilot.scan_and_optimize()

@vulcan_group.command('ignite')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help="Força a re-compilação de todos os Hot-Paths.")
@click.pass_context
def ignite(ctx, path, force):
    """Transforma Hot-Paths detectados em binários de alta velocidade."""
    signal.signal(signal.SIGINT, _sigint_handler)
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

        candidates = []
        mode = "AUTOMÁTICO (baseado em telemetria)"
        if path:
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                mode = f"MANUAL (arquivo: {os.path.basename(abs_path)})"
                candidates = [{'file': abs_path}]
            elif os.path.isdir(abs_path):
                mode = f"MANUAL (diretório: {os.path.basename(abs_path)})"
                for root_dir, _, files in os.walk(abs_path):
                    for filename in files:
                        if filename.endswith('.py'):
                            candidates.append({'file': os.path.join(root_dir, filename)})

        try:
            click.echo(f"{Fore.CYAN}   > Modo de operação: {mode}{Fore.RESET}")
            autopilot.scan_and_optimize(candidates=candidates, force_recompile=force)
            
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ [VULCAN] Forja concluída com sucesso.{Fore.RESET}")
            click.echo("   > Próxima execução com 'doxoade run' usará modo turbo.")
            
        except KeyboardInterrupt:
            _sigint_handler(None, None)
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


@vulcan_group.command('module')
@click.option('--path', 'project_path', default='.', type=click.Path(file_okay=False, resolve_path=True),
              help="Raiz do projeto alvo (onde será criado .doxoade/vulcan/runtime.py).")
@click.option('--force', is_flag=True, help="Sobrescreve o módulo local caso já exista.")
def vulcan_module(project_path, force):
    """Gera módulo local de runtime Vulcan para projetos externos ao `doxoade run`."""
    root = _find_project_root(project_path)
    created, runtime_path = generate_local_vulcan_module(root, force=force)
    if not created:
        click.echo(f"{Fore.YELLOW}[SKIP]{Fore.RESET} Módulo já existe: {runtime_path}")
        click.echo("       Use --force para sobrescrever.")
        return

    click.echo(f"{Fore.GREEN}✅ [VULCAN] Módulo local criado:{Fore.RESET} {runtime_path}")
    click.echo("   > No seu __main__.py use:")
    click.echo("     import sys")
    click.echo("     from pathlib import Path")
    click.echo("     ROOT = Path(__file__).resolve().parents[1]")
    click.echo("     LOCAL_DOXOADE = ROOT / '.doxoade'")
    click.echo("     if LOCAL_DOXOADE.exists() and str(LOCAL_DOXOADE) not in sys.path:")
    click.echo("         sys.path.insert(0, str(LOCAL_DOXOADE))")
    click.echo("     from vulcan.runtime import activate_vulcan")
    click.echo("     activate_vulcan(globals(), __file__)")

def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    import sys as _sys, os as _os
    _, _, exc_tb = _sys.exc_info()
    f_name = _os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0
    
    click.echo(f"\n\033[1;34m[ FORENSIC:VULCAN:{scope} ]\033[0m \033[1mFile: {f_name} | L: {line_n}\033[0m")
    click.echo(f"\033[31m    ■ Tipo : {type(e).__name__}\n    ■ Valor: {e}\033[0m")
