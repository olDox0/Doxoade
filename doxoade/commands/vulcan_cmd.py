# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
import os
import sys
import click
import signal
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _find_project_root

__version__ = "83.2 Omega (Module Bootstrap)"

_BOOTSTRAP_START = "# --- DOXOADE_VULCAN_BOOTSTRAP:START ---"
_BOOTSTRAP_END = "# --- DOXOADE_VULCAN_BOOTSTRAP:END ---"
_BOOTSTRAP_BLOCK = f'''{_BOOTSTRAP_START}
from pathlib import Path as _doxo_path
import importlib.util as _doxo_importlib_util

_doxo_runtime_file = _doxo_path(__file__).resolve().parents[1] / ".doxoade" / "vulcan" / "runtime.py"
_doxo_activate_vulcan = None
if _doxo_runtime_file.exists():
    _doxo_spec = _doxo_importlib_util.spec_from_file_location("_doxoade_vulcan_runtime", str(_doxo_runtime_file))
    if _doxo_spec and _doxo_spec.loader:
        _doxo_mod = _doxo_importlib_util.module_from_spec(_doxo_spec)
        _doxo_spec.loader.exec_module(_doxo_mod)
        _doxo_activate_vulcan = getattr(_doxo_mod, "activate_vulcan", None)

if callable(_doxo_activate_vulcan):
    _doxo_activate_vulcan(globals(), __file__)
{_BOOTSTRAP_END}
'''


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
            diag.render_report()
            sys.exit(1)

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


def _copy_runtime_module(project_root: Path) -> Path:
    runtime_src = Path(__file__).resolve().parents[1] / "tools" / "vulcan" / "runtime.py"
    vulcan_dir = project_root / ".doxoade" / "vulcan"
    vulcan_dir.mkdir(parents=True, exist_ok=True)
    runtime_dst = vulcan_dir / "runtime.py"
    runtime_dst.write_text(runtime_src.read_text(encoding="utf-8"), encoding="utf-8")

    init_dst = vulcan_dir / "__init__.py"
    init_dst.write_text(
        "# -*- coding: utf-8 -*-\n"
        "from .runtime import activate_vulcan, find_vulcan_project_root, load_vulcan_binary\n"
        "\n"
        "__all__ = [\"activate_vulcan\", \"find_vulcan_project_root\", \"load_vulcan_binary\"]\n",
        encoding="utf-8",
    )
    return runtime_dst


def _iter_project_main_files(project_root: Path):
    skip = {".git", "venv", ".venv", "__pycache__", "build", "dist", ".pytest_cache"}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        if "__main__.py" in files:
            yield Path(root) / "__main__.py"


def _inject_bootstrap(main_file: Path) -> bool:
    content = main_file.read_text(encoding="utf-8", errors="replace")
    if _BOOTSTRAP_START in content:
        return False
    main_file.write_text(f"{_BOOTSTRAP_BLOCK}\n{content}", encoding="utf-8")
    return True


@vulcan_group.command('module')
@click.option('--path', 'target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True), show_default=True,
              help='Projeto alvo que receberá o módulo de acionamento Vulcan.')
@click.option('--main', 'main_files', multiple=True, type=click.Path(exists=True, dir_okay=False),
              help='Arquivo __main__.py específico para injetar bootstrap (pode repetir).')
@click.option('--auto-main', is_flag=True, help='Detecta e injeta em todos os __main__.py do projeto alvo.')
def vulcan_module(target_path, main_files, auto_main):
    """Instala módulo de acionamento Vulcan em projetos externos."""
    project_root = Path(target_path).resolve()
    runtime_dst = _copy_runtime_module(project_root)
    click.echo(f"{Fore.GREEN}[OK]{Fore.RESET} Runtime instalado em: {runtime_dst}")

    changed = []
    if main_files:
        for item in main_files:
            p = Path(item).resolve()
            if _inject_bootstrap(p):
                changed.append(p)
    elif auto_main:
        for p in _iter_project_main_files(project_root):
            if _inject_bootstrap(p):
                changed.append(p)

    if changed:
        click.echo(f"{Fore.GREEN}[OK]{Fore.RESET} Bootstrap injetado em:")
        for p in changed:
            click.echo(f"  - {p}")
    elif main_files or auto_main:
        click.echo(f"{Fore.YELLOW}[INFO]{Fore.RESET} Nenhum __main__.py precisou de alteração.")
    else:
        click.echo(
            f"{Fore.CYAN}[DICA]{Fore.RESET} Use --auto-main para injetar automaticamente nos __main__.py do projeto, "
            "ou --main <arquivo> para alvo específico."
        )


def _print_vulcan_forensic(scope: str, e: Exception):
    """Interface Forense para falhas de metalurgia (MPoT-5.3)."""
    import sys as exc_sys, os as exc_os
    _, exc_obj, exc_tb = exc_sys.exc_info()
    f_name = exc_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "vulcan_cmd.py"
    line_n = exc_tb.tb_lineno if exc_tb else 0

    click.echo(f"\n\033[1;34m\n[ ■ FORENSIC:VULCAN:{scope} ]\033[0m \033[1m\n ■ File: {f_name} | L: {line_n}\033[0m")
    exc_value = '\n  >>>   '.join(str(exc_obj).split("'"))
    click.echo(f"\033[31m\n ■ Tipo: {type(e).__name__} \n ■ Exception value: {exc_value} \n ■ Valor: {e}\n\033[0m")
