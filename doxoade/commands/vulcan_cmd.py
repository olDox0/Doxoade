# doxoade/doxoade/commands/vulcan_cmd.py
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
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root
__version__ = '86.0 Omega (modular split)'
try:
    pass  # [DOX-UNUSED] from doxoade.tools.vulcan.simd_detector import detect
    from doxoade.tools.vulcan.simd_compiler import SIMDContext
    _SIMD_AVAILABLE = True
except ImportError:
    _SIMD_AVAILABLE = False
try:
# [DOX-UNUSED]  from doxoade.tools.vulcan.object_allocation_scanner import ModuleAllocReport
# [DOX-UNUSED]  from doxoade.tools.vulcan.object_reduction import TransformResult
    _OBJREDUCE_AVAILABLE = True
except ImportError:
    _OBJREDUCE_AVAILABLE = False

def _simd_context_or_none(simd: bool, simd_level: str) -> 'SIMDContext | None':
    """Cria SIMDContext se --simd ativo e módulos disponíveis."""
    if not simd or not _SIMD_AVAILABLE:
        return None
    return SIMDContext(level_cap=simd_level)

class _NullContext:
    """Context manager inerte — substitui SIMDEnvironment quando --simd não ativo."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

def _sigint_handler(signum, frame):
    click.echo(f'\n{Fore.RED}Comando interrompido.{Style.RESET_ALL}')
    sys.exit(130)

def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense Dual: Python Traceback + Sotéria Native Rescue (PASC 8.19)."""
    # 1. TENTA O RESGATE NATIVO (Sotéria Mode)
    # PASC 6.6: Importação localizada para economizar RAM no N2808
    try:
        from doxoade.tools.vulcan.soteria_engine import SoteriaForensic
        forensic = SoteriaForensic()
    except ImportError:
        # Fallback se o motor não estiver no path
        click.echo(f"{Fore.RED}[!] Erro Crítico: Motor Sotéria não localizado.{Style.RESET_ALL}")
        forensic = None
        
    # Captura saída de erro se o processo crashou (ex: CalledProcessError)
    output = ""
    if hasattr(e, 'stdout') and e.stdout: output += e.stdout
    if hasattr(e, 'stderr') and e.stderr: output += e.stderr
    
    # Se a Sotéria encontrar suas marcas no log, ela gera o relatório e encerra
    if output and forensic.process_pipe(output):
        return

    # 2. FALLBACK: RELATÓRIO DE ERRO PADRÃO (Python Mode)
    _, exc_obj, exc_tb = sys.exc_info()
    f_name = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else 'vulcan_cmd.py'
    line_n = exc_tb.tb_lineno if exc_tb else 0
    
    click.echo(f'\n\x1b[1;34m\n[ ■ FORENSIC:VULCAN:{scope} ]\x1b[0m \x1b[1m\n ■ File: {f_name} | L: {line_n}\x1b[0m')
    
    # PASC 6.3: Sanitização contra Unicode Plague
    exc_value = '\n  >>>   '.join(str(exc_obj).split("'"))
    click.echo(f'\x1b[31m\n ■ Tipo: {type(e).__name__} \n ■ Exception value: {exc_value} \n ■ Valor: {e}\n\x1b[0m')

def _patch_vulcan_forge():
    """Garante que VulcanForge possua o atributo is_self_referential."""
    for mod in list(sys.modules.values()):
        if hasattr(mod, 'VulcanForge'):
            vf = getattr(mod, 'VulcanForge')
            if isinstance(vf, type) and (not hasattr(vf, 'is_self_referential')):
                setattr(vf, 'is_self_referential', staticmethod(lambda p: _is_doxoade_project(Path(p))))

def _is_doxoade_project(path: Path) -> bool:
    """
    Retorna True se o caminho alvo é o próprio projeto doxoade.
    O doxoade já possui MetaFinder nativo — injetar bootstrap seria redundante.
    """
    markers = [path / 'doxoade' / 'tools' / 'vulcan' / 'meta_finder.py', path / 'doxoade' / 'tools' / 'vulcan' / 'runtime.py']
    return any((m.exists() for m in markers))

@click.group('vulcan')
def vulcan_group():
    """🔥 Projeto Vulcano: Alta Performance Nativa (C/Cython).
    
    DEBUG DE REDIRECIONAMENTO:
      Para analisar o desvio de imports em tempo real, use:
      $ set VULCAN_VERBOSE=1 && python main.py (Windows)
      $ VULCAN_VERBOSE=1 python3 main.py      (Linux/Termux)
    """
    pass
    
@vulcan_group.command('inspect')
@click.argument('path')
@click.option('--c-code', is_flag=True, help='Mostra o código C gerado')
def vulcan_inspect(path, c_code):
    """Inspeciona a Pureza de Metal e o código gerado."""
    from doxoade.tools.vulcan.forge import BodyPurityScanner
    from doxoade.tools.vulcan.diagnostic import extract_c_snippet
    import ast
    
    click.echo(f"🔍 [INSPECT] Analisando metalurgia de: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
        tree = ast.parse(source)

    scanner = BodyPurityScanner()
    scanner.visit(tree)
    report = scanner.get_purity_report()

    # Exibe Score de Pureza
    click.echo(f"\nPureza de Metal: {report['color']}{report['score']}% - {report['rank']}\x1b[0m")
    for detail in report['details']:
        click.echo(detail)

    if c_code:
        # Tenta localizar o .c na foundry
        file_name = os.path.basename(path)
        # Lógica simplificada para achar o .c (pode usar o hash que já temos)
        foundry_dir = ".doxoade/vulcan/foundry/"
        c_files = [f for f in os.listdir(foundry_dir) if f.endswith('.c') and file_name.split('.')[0] in f]
        
        if c_files:
            latest_c = os.path.join(foundry_dir, c_files[0])
            click.echo(f"\n{Fore.YELLOW}--- AMOSTRA DE C (Core Implementation) ---{Style.RESET_ALL}")
            # Extrai a primeira função encontrada para exemplo
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            if functions:
                snippet = extract_c_snippet(latest_c, functions[0])
                click.echo(f"\x1b[2m{snippet}\x1b[0m")
        else:
            click.echo("\n[!] Arquivo .c não encontrado na foundry. Execute ignite primeiro.")

@vulcan_group.command('forge')
@click.argument('target', type=click.Path(exists=True))
@click.option('--view', '-v', is_flag=True, help='Exibe o código .pyx no terminal.')
@click.option('--save', '-s', is_flag=True, help='Salva os fontes .pyx e .c na pasta foundry.')
def vulcan_forge(target, view, save):
    """🛠️  Metalurgia: Gera e analisa a qualidade da tradução C."""
    from doxoade.tools.vulcan.forge import VulcanForge
    from rich.syntax import Syntax
    from rich.console import Console

    click.echo(f"{Fore.CYAN}--- [VULCAN FORGE] Analisando: {target} ---{Style.RESET_ALL}")
    
    forge = VulcanForge(target)
    pyx_code = forge.generate_source(target)
    
    if view:
        console = Console()
        syntax = Syntax(pyx_code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)
    
    if save:
        # Caminho para análise profunda em .doxoade/vulcan/foundry
        from doxoade.tools.vulcan.environment import VulcanEnvironment
        env = VulcanEnvironment('.')
        out_file = env.foundry / f"{Path(target).stem}.pyx"
        out_file.write_text(pyx_code, encoding='utf-8')
        click.echo(f"{Fore.GREEN}✅ Fonte Pyx guardado em: {out_file}{Style.RESET_ALL}")
        
    # Relatório de "Pureza de Metal"
    _analyze_forge_quality(pyx_code)

def _analyze_forge_quality(code):
    """Novo Laudo: Detecta Pureza C e Eficiência de Hardware."""
    cdefs = code.count("cdef ") + code.count("cpdef ")
    # Verifica se há o 'Passaporte C' (cdivision=True)
    fast_math = "cdivision=True" in code 
    
    click.echo(f"\n{Fore.WHITE}{Style.BRIGHT}Laudo de Metalurgia v2 (N2808 Optimized):{Style.RESET_ALL}")
    
    if cdefs > 0:
        click.echo(f"   {Fore.SUCCESS}✔ Pureza: {cdefs} variáveis tipadas no hardware.{Style.RESET_ALL}")
    else:
        click.echo(f"   {Fore.RED}✘ Impuro: Código 100% dependente do interpretador Python.{Style.RESET_ALL}")
        
    if fast_math:
        click.echo(f"   {Fore.SUCCESS}✔ Math: Branchless division bypass ativo.{Style.RESET_ALL}")
    else:
            click.echo(f"   {Fore.YELLOW}⚠ Math: Checagem de erro Python ativa (Lento).{Style.RESET_ALL}")

def _register_subcommands():
    from .vulcan_cmd_forge import ignite, vulcan_regression, vulcan_lib, vulcan_benchmark, vulcan_pitstop
    from .vulcan_cmd_tools import vulcan_alloc, vulcan_simd, vulcan_opt, opt_bench
    from .vulcan_cmd_bootstrap import vulcan_module, vulcan_probe, vulcan_verify, vulcan_telemetry_bridge
    from .vulcan_cmd_lazy import vulcan_lazy
    for cmd in (ignite, vulcan_regression, vulcan_lib, vulcan_benchmark, vulcan_pitstop, vulcan_alloc, vulcan_simd, vulcan_opt, opt_bench, vulcan_module, vulcan_probe, vulcan_verify, vulcan_telemetry_bridge, vulcan_lazy):
        vulcan_group.add_command(cmd)
_register_subcommands()

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
        click.echo('Use --module to attempt to repair a specific module.')

@vulcan_group.command('status')
def vulcan_status():
    """Dashboard de Sincronia: Original (Tier 3) vs Nativo (Tier 1)."""
    from pathlib import Path
    import hashlib, os

    root = Path(_find_project_root(os.getcwd()))
    bin_dir = root / '.doxoade' / 'vulcan' / 'bin'
    
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}📊 DASHBOARD DE INTEGRIDADE VULCAN{Style.RESET_ALL}")
    
    # Cabeçalho
    click.echo(f"{'MÓDULO':<35} │ {'TIER 1 (BIN)':<14} │ {'STATUS'}")
    click.echo("─" * 65)

    from doxoade.dnm import DNM
    py_files = DNM(str(root)).scan(extensions=['py'])

    for py_f in py_files:
        p = Path(py_f)
        if p.name.startswith('__') or 'tests' in str(p): continue
        
        # Calcula o hash de vinculação do binário
        path_hash = hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:6]
        v_pattern = f"v_{p.stem}_{path_hash}"
        binary = list(bin_dir.glob(f"{v_pattern}*.pyd")) or list(bin_dir.glob(f"{v_pattern}*.so"))
        
        rel_path = os.path.relpath(p, root)
        
        if not binary:
            click.echo(f"{Fore.WHITE}{rel_path[:35]:<35}{Style.RESET_ALL} │ {Style.DIM}{'no binary':<14}{Style.RESET_ALL} │ {Style.DIM}Tier 3")
            continue
            
        # Verifica se o binário é "Stale" (código mudou e binário é antigo)
        is_stale = p.stat().st_mtime > binary[0].stat().st_mtime
        status_txt = f"{Fore.RED}STALE (Re-ignite){Fore.RESET}" if is_stale else f"{Fore.GREEN}SYNCED (Nativo){Fore.RESET}"
        size = binary[0].stat().st_size / 1024
        
        click.echo(f"{Fore.CYAN}{rel_path[:35]:<35}{Style.RESET_ALL} │ {Fore.YELLOW}{size:>7.1f} KB{Style.RESET_ALL}    │ {status_txt}")

@vulcan_group.command('purge')
def vulcan_purge():
    """Remove todos os binários e códigos temporários da forja."""
    root = _find_project_root(os.getcwd())
    from doxoade.tools.vulcan.environment import VulcanEnvironment
    env = VulcanEnvironment(root)
    if click.confirm(f'{Fore.RED}Deseja realmente limpar a foundry Vulcano?{Fore.RESET}'):
        env.purge_unstable()
        click.echo(f'{Fore.GREEN}Foundry purificada.{Fore.RESET}')
