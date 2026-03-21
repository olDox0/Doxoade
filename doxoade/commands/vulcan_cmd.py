# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
"""
Grupo CLI principal do Vulcan.

Estrutura modular:
  vulcan_cmd.py           → este arquivo: grupo, utilitários, doctor, status, purge
  vulcan_cmd_forge.py     → ignite, regression, lib, benchmark, pitstop
  vulcan_cmd_tools.py     → alloc, simd, opt, opt-bench
  vulcan_cmd_bootstrap.py → module, probe, verify, bootstrap helpers
"""

import sys
import os
import re                       # FIX #4: movido do meio do arquivo para o topo
import signal
import subprocess               # FIX #3: era marcado [DOX-UNUSED] mas é usado em vulcan_verify
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _find_project_root

__version__ = "86.0 Omega (modular split)"

# ── Imports SIMD (opcionais) ──────────────────────────────────────────────────

try:
    from doxoade.tools.vulcan.simd_detector import detect as _detect_simd
    from doxoade.tools.vulcan.simd_compiler import (
        SIMDContext,
        SIMDForge,
        SIMDEnvironment,
        estimate_gain,
        get_simd_report,
    )
    _SIMD_AVAILABLE = True
except ImportError:
    _SIMD_AVAILABLE = False

try:
    from doxoade.tools.vulcan.object_allocation_scanner import (
        scan_source, scan_pyx, render_report as _render_alloc_report,
        ModuleAllocReport,
    )
    from doxoade.tools.vulcan.object_reduction import (
        reduce_source, reduce_pyx_file, TransformResult,
    )
    _OBJREDUCE_AVAILABLE = True
except ImportError:
    _OBJREDUCE_AVAILABLE = False


# ── Utilitários compartilhados ────────────────────────────────────────────────

def _simd_context_or_none(simd: bool, simd_level: str) -> "SIMDContext | None":
    """Cria SIMDContext se --simd ativo e módulos disponíveis."""
    if not simd or not _SIMD_AVAILABLE:
        return None
    return SIMDContext(level_cap=simd_level)


class _NullContext:
    """Context manager inerte — substitui SIMDEnvironment quando --simd não ativo."""
    def __enter__(self): return self
    def __exit__(self, *_): pass


# FIX #2: _sigint_handler definida UMA única vez (havia duplicata em linha 2566)
def _sigint_handler(signum, frame):
    click.echo(f"\n{Fore.RED}Comando interrompido.{Style.RESET_ALL}")
    sys.exit(130)


# FIX #1: _print_vulcan_forensic definida UMA única vez (havia duplicata em linha 2571)
# Mantida a versão mais completa (segunda definição do original)
def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    _, exc_obj, exc_tb = sys.exc_info()
    f_name = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0

    click.echo(f"\n\033[1;34m\n[ ■ FORENSIC:VULCAN:{scope} ]\033[0m \033[1m\n ■ File: {f_name} | L: {line_n}\033[0m")
    exc_value = '\n  >>>   '.join(str(exc_obj).split("'"))
    click.echo(f"\033[31m\n ■ Tipo: {type(e).__name__} \n ■ Exception value: {exc_value} \n ■ Valor: {e}\n\033[0m")


def _patch_vulcan_forge():
    """Garante que VulcanForge possua o atributo is_self_referential."""
    for mod in list(sys.modules.values()):
        if hasattr(mod, 'VulcanForge'):
            vf = getattr(mod, 'VulcanForge')
            if isinstance(vf, type) and not hasattr(vf, 'is_self_referential'):
                setattr(vf, 'is_self_referential', staticmethod(
                    lambda p: _is_doxoade_project(Path(p))
                ))


def _is_doxoade_project(path: Path) -> bool:
    """
    Retorna True se o caminho alvo é o próprio projeto doxoade.
    O doxoade já possui MetaFinder nativo — injetar bootstrap seria redundante.
    """
    markers = [
        path / "doxoade" / "tools" / "vulcan" / "meta_finder.py",
        path / "doxoade" / "tools" / "vulcan" / "runtime.py",
    ]
    return any(m.exists() for m in markers)


# ── Grupo CLI ─────────────────────────────────────────────────────────────────

@click.group('vulcan')
def vulcan_group():
    """🔥 Projeto Vulcano: Alta Performance Nativa (C/Cython)."""
    pass


# Registra subcomandos dos módulos filhos
def _register_subcommands():
    from .vulcan_cmd_forge     import (
        ignite, vulcan_regression, vulcan_lib, vulcan_benchmark,
        vulcan_pitstop,
    )
    from .vulcan_cmd_tools     import (
        vulcan_alloc, vulcan_simd, vulcan_opt, opt_bench,
    )
    from .vulcan_cmd_bootstrap import (
        vulcan_module, vulcan_probe, vulcan_verify,
        vulcan_telemetry_bridge,          # ← NOVO
    )

    for cmd in (
        ignite, vulcan_regression, vulcan_lib, vulcan_benchmark, vulcan_pitstop,
        vulcan_alloc, vulcan_simd, vulcan_opt, opt_bench,
        vulcan_module, vulcan_probe, vulcan_verify,
        vulcan_telemetry_bridge,          # ← NOVO
    ):
        vulcan_group.add_command(cmd)


_register_subcommands()


# ── Comandos do core ──────────────────────────────────────────────────────────

@vulcan_group.command('doctor')
@click.option('--module', help='Nome do módulo Python a tentar reparar (ex: doxoade.tools.streamer)')
@click.option('--srcdir', help='Caminho para o código-fonte do módulo (opcional)')
@click.option('--retries', default=1, type=int)
def doctor(module, srcdir, retries):
    """Executa diagnóstico Vulcan + tenta reparo automático de um módulo."""
    project_root = '.'
    from doxoade.tools.vulcan.diagnostic import VulcanDiagnostic
    diag = VulcanDiagnostic(project_root)
    ok, results = diag.check_environment()
    click.echo(f"Diagnostic: compiler_ok={results.get('compiler')} cython={results.get('cython')}")
    from doxoade.tools.vulcan.abi_gate import run_abi_gate
    run_abi_gate(project_root)
    if module:
        from doxoade.tools.vulcan.auto_repair import auto_repair_module
        res = auto_repair_module(project_root, module, module_src_dir=srcdir, retries=retries)
        click.echo(res)
    else:
        click.echo("Use --module to attempt to repair a specific module.")


@vulcan_group.command('status')
def vulcan_status():
    """Lista módulos otimizados e camadas ativas (binário + opt_py)."""
    root        = _find_project_root(os.getcwd())
    bin_dir     = os.path.join(root, ".doxoade", "vulcan", "bin")
    lib_bin_dir = os.path.join(root, ".doxoade", "vulcan", "lib_bin")
    opt_py_dir  = os.path.join(root, ".doxoade", "vulcan", "opt_py")

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ESTADO DA FOUNDRY VULCAN:{Style.RESET_ALL}")

    for label, directory in [("Projeto (Tier 1)", bin_dir), ("Libs (Tier 1)", lib_bin_dir)]:
        if not os.path.exists(directory):
            continue
        binaries = [f for f in os.listdir(directory) if f.endswith(('.pyd', '.so'))]
        if binaries:
            click.echo(f"\n  {Fore.YELLOW}[{label}]{Style.RESET_ALL}")
            for b in binaries:
                size = os.path.getsize(os.path.join(directory, b)) / 1024
                click.echo(
                    f"   {Fore.GREEN}{b:<40} "
                    f"{Fore.WHITE}| {size:>6.1f} KB {Fore.YELLOW}[ATIVO]{Style.RESET_ALL}"
                )

    if os.path.exists(opt_py_dir):
        opt_files = [f for f in os.listdir(opt_py_dir) if f.endswith('.py')]
        if opt_files:
            click.echo(f"\n  {Fore.MAGENTA}[Python Otimizado (Tier 2)]{Style.RESET_ALL}")
            for f in opt_files:
                size = os.path.getsize(os.path.join(opt_py_dir, f)) / 1024
                click.echo(
                    f"   {Fore.MAGENTA}{f:<40} "
                    f"{Fore.WHITE}| {size:>6.1f} KB {Fore.CYAN}[OPT]{Style.RESET_ALL}"
                )

    all_bins = []
    for d in [bin_dir, lib_bin_dir]:
        if os.path.exists(d):
            all_bins += [f for f in os.listdir(d) if f.endswith(('.pyd', '.so'))]

    all_opts = []
    if os.path.exists(opt_py_dir):
        all_opts = [f for f in os.listdir(opt_py_dir) if f.endswith('.py')]

    if not all_bins and not all_opts:
        click.echo(
            f"   {Fore.YELLOW}Nenhum módulo ativo. "
            f"Execute 'doxoade vulcan ignite' ou 'doxoade vulcan opt'.{Style.RESET_ALL}"
        )
    else:
        click.echo(f"\n  {Fore.CYAN}Resumo:{Style.RESET_ALL}")
        click.echo(f"   {Fore.GREEN}Tier 1 (Binários)  : {len(all_bins)} módulo(s){Style.RESET_ALL}")
        click.echo(f"   {Fore.MAGENTA}Tier 2 (Opt Python): {len(all_opts)} módulo(s){Style.RESET_ALL}")
        click.echo(f"   {Fore.WHITE}Tier 3 (Python Puro): sempre disponível{Style.RESET_ALL}")


@vulcan_group.command('purge')
def vulcan_purge():
    """Remove todos os binários e códigos temporários da forja."""
    root = _find_project_root(os.getcwd())
    from ..tools.vulcan.environment import VulcanEnvironment
    env = VulcanEnvironment(root)
    if click.confirm(f"{Fore.RED}Deseja realmente limpar a foundry Vulcano?{Fore.RESET}"):
        env.purge_unstable()
        click.echo(f"{Fore.GREEN}Foundry purificada.{Fore.RESET}")