# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd.py
import os
import sys
import click
import signal
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _find_project_root

__version__ = "83.3 Omega (Module Bootstrap Fix)"

_BOOTSTRAP_START = "# --- DOXOADE_VULCAN_BOOTSTRAP:START ---"
_BOOTSTRAP_END = "# --- DOXOADE_VULCAN_BOOTSTRAP:END ---"
_BOOTSTRAP_BLOCK = f'''{_BOOTSTRAP_START}
from pathlib import Path as _doxo_path
import importlib.util as _doxo_importlib_util

_doxo_activate_vulcan = None
for _doxo_base in [_doxo_path(__file__).resolve(), *_doxo_path(__file__).resolve().parents]:
    _doxo_runtime_file = _doxo_base / ".doxoade" / "vulcan" / "runtime.py"
    if not _doxo_runtime_file.exists():
        continue
    _doxo_spec = _doxo_importlib_util.spec_from_file_location("_doxoade_vulcan_runtime", str(_doxo_runtime_file))
    if not (_doxo_spec and _doxo_spec.loader):
        continue
    _doxo_mod = _doxo_importlib_util.module_from_spec(_doxo_spec)
    _doxo_spec.loader.exec_module(_doxo_mod)
    _doxo_activate_vulcan = getattr(_doxo_mod, "activate_vulcan", None)
    break

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


# PATCH vulcan_cmd.py — adicionar ao comando ignite existente
# Substitua o decorador + função ignite atual por este bloco completo.

@vulcan_group.command('ignite')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force',        is_flag=True,  help="Força a re-compilação de todos os alvos.")
@click.option('--jobs',         type=int, default=None, help="Número de workers (sobrescreve auto).")
@click.option('--no-pitstop',   is_flag=True,  help="Usa compilação legada (1 processo por módulo).")
@click.option('--streaming',    is_flag=True,  help="Forge e compilação em paralelo (melhor para > 15 módulos).")
@click.option('--hybrid',       is_flag=True,  help="Compilação seletiva por função (HybridForge).")
@click.option('--scan-only',    is_flag=True,  help="Com --hybrid: mostra candidatos sem compilar.")
@click.pass_context
def ignite(ctx, path, force, jobs, no_pitstop, streaming, hybrid, scan_only):
    """Transforma código Python em binários de alta velocidade.

    Modos:
      padrão   → PitStop Engine (batch compile + warm-up cache)
      --hybrid → HybridForge (seletivo por função, arquivos impuros aceitos)

    Use --scan-only com --hybrid para ver candidatos antes de compilar.
    """
    signal.signal(signal.SIGINT, _sigint_handler)
    root = _find_project_root(os.getcwd())
    target = path or root

    # ── Modo Híbrido ──────────────────────────────────────────────────────────
    if hybrid:
        from ..tools.vulcan.hybrid_forge import hybrid_ignite, hybrid_scan_file

        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}⬡ [VULCAN-HYBRID] v{__version__}...{Style.RESET_ALL}")

        if scan_only:
            # Modo diagnóstico: só mostra o que seria compilado
            click.echo(f"{Fore.CYAN}   > Modo: SCAN ONLY (sem compilação){Style.RESET_ALL}")
            _run_hybrid_with_optimizer(target, root)
            return

        click.echo(f"{Fore.CYAN}   > Alvo : {target}{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   > Modo : HÍBRIDO (seletivo por função){Style.RESET_ALL}")

        with ExecutionLogger('vulcan_hybrid', root, ctx.params) as _:
            try:
                hybrid_ignite(
                    project_root = root,
                    target       = target,
                    force        = force,
                    on_progress  = click.echo,
                )
            except KeyboardInterrupt:
                _sigint_handler(None, None)
            except Exception as e:
                _print_vulcan_forensic("HYBRID", e)
                sys.exit(1)
        return

    # ── Modo Padrão (PitStop / Legado) — não alterado ─────────────────────────
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

        engine_label = (
            f"{Fore.YELLOW}LEGADO{Style.RESET_ALL}"
            if no_pitstop
            else f"{Fore.GREEN}PITSTOP{Style.RESET_ALL}"
            + (f" {Fore.CYAN}+streaming{Style.RESET_ALL}" if streaming else "")
        )
        click.echo(f"{Fore.CYAN}   > Modo de Operação : {mode}{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   > Engine          : {engine_label}{Style.RESET_ALL}")

        try:
            autopilot.scan_and_optimize(
                candidates    = candidates,
                force_recompile = force,
                max_workers   = jobs,
                use_pitstop   = not no_pitstop,
                streaming     = streaming,
            )
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✅ [VULCAN] Forja concluída.{Style.RESET_ALL}")
        except KeyboardInterrupt:
            _sigint_handler(None, None)
        except Exception as e:
            _print_vulcan_forensic("IGNITE", e)
            sys.exit(1)
            
            
def _run_hybrid_with_optimizer(target, root, force):
    """
    Versão atualizada do ignite --hybrid com optimizer integrado.
    Substitui o bloco interno do comando ignite quando --hybrid é passado.
    """
    from ..tools.vulcan.hybrid_forge     import HybridIgnite
    from ..tools.vulcan.hybrid_optimizer import optimize_pyx_file
    from pathlib import Path

    ignite = HybridIgnite(root)
    files  = HybridIgnite._collect_files(Path(target).resolve())

    opt_summary = []   # acumula relatórios do optimizer

    for py_file in files:
        scan = ignite._scanner.scan(str(py_file))
        if not scan.candidates:
            continue

        fname = py_file.name
        click.echo(
            f"   {Fore.YELLOW}[HYBRID]{Style.RESET_ALL} {fname} — "
            f"{len(scan.candidates)} candidato(s):"
        )
        for f in scan.candidates:
            click.echo(
                f"     • {f.name:<35} score={f.score:>2}  "
                f"({', '.join(f.reasons[:3])})"
            )

        # Gera .pyx raw
        pyx_path = ignite._forge.generate(scan)
        if not pyx_path:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {fname}: forge falhou")
            continue

        # Enriquece com optimizer
        pyx_path, opt_report = optimize_pyx_file(pyx_path)

        if opt_report.transformations and not opt_report.transformations[0].startswith('revertido'):
            opt_summary.append(opt_report)
            n_cdefs = len(opt_report.transformations)
            click.echo(
                f"   {Fore.MAGENTA}  ⬡ optimizer{Style.RESET_ALL}: "
                f"{n_cdefs} cdef(s) injetados → "
                f"{Fore.GREEN}{opt_report.estimated_gain}{Style.RESET_ALL}"
            )

        # Compila
        module_name = pyx_path.stem
        ok, err = ignite._compile(module_name)

        if ok:
            click.echo(
                f"   {Fore.GREEN}✔{Style.RESET_ALL} {fname} → {module_name} "
                f"({len(scan.candidates)} funcs, score={scan.total_score})"
            )
        else:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {fname}: {str(err)[:80]}")

    # Resumo do optimizer
    if opt_summary:
        total_cdefs = sum(len(r.transformations) for r in opt_summary)
        click.echo(
            f"\n{Fore.MAGENTA}"
            f"  ⬡ OPTIMIZER: {total_cdefs} cdef(s) em {len(opt_summary)} módulo(s)"
            f"{Style.RESET_ALL}"
        )
        for r in opt_summary:
            click.echo(
                f"    {r.module_name:<30} → {Fore.GREEN}{r.estimated_gain}{Style.RESET_ALL}"
            )
            for t in r.transformations[:5]:
                click.echo(f"      {Style.DIM}• {t}{Style.RESET_ALL}")
            if len(r.transformations) > 5:
                click.echo(f"      {Style.DIM}  (+{len(r.transformations)-5} mais){Style.RESET_ALL}")


@vulcan_group.command('pitstop')
@click.option('--clear-cache', is_flag=True, help="Apaga o WarmupCache (força recompilação total na próxima vez).")
def vulcan_pitstop(clear_cache):
    """Informações e controle do PitStop Engine (cache + warm-up)."""
    root = _find_project_root(os.getcwd())

    from ..tools.vulcan.environment import VulcanEnvironment
    from ..tools.vulcan.pitstop import PitstopEngine

    env = VulcanEnvironment(root)
    engine = PitstopEngine(env)
    info = engine.warmup_info()

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  PITSTOP ENGINE INFO:{Style.RESET_ALL}")
    click.echo(f"   Python    : {info['python_exe']}")
    click.echo(f"   Foundry   : {info['foundry']}")
    click.echo(f"   Bin       : {info['bin_dir']}")
    click.echo(f"   Workers   : {info['workers']} processos GCC paralelos")
    click.echo(f"   Estratégia: {info['parallel_strategy']}")
    click.echo(f"   Batch size: {info['batch_size']}")
    click.echo(f"   Cache     : {info['cache']['entries']} entrada(s) em {info['cache']['path']}")

    if info['build_env_keys']:
        click.echo(f"   Env extras: {', '.join(info['build_env_keys'])}")

    if clear_cache:
        cache_path = Path(info['cache']['path'])
        if cache_path.exists():
            cache_path.unlink()
            click.echo(f"\n{Fore.GREEN}[OK]{Fore.RESET} WarmupCache apagado. Próximo ignite recompila tudo.")
        else:
            click.echo(f"\n{Fore.YELLOW}[INFO]{Fore.RESET} Cache já estava vazio.")
            
            
@vulcan_group.command('lib')
@click.option('--analyze', is_flag=True, help="Lista dependências 'quentes' candidatas à compilação.")
@click.option('--target', help="Compila uma biblioteca específica de requirements.txt.")
@click.option('--auto', is_flag=True, help="Compila automaticamente os melhores candidatos da análise.")
@click.option('--run-tests', is_flag=True, default=True, help="Executa a suíte de testes após a compilação para validar.")
@click.pass_context
def vulcan_lib(ctx, analyze, target, auto, run_tests):
    """Compila dependências de terceiros para performance nativa."""
    root = _find_project_root(os.getcwd())
    
    with ExecutionLogger('vulcan_lib', root, ctx.params) as logger:
        
        # --- Fase 1: Análise e Identificação ---
        if analyze:
            click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Analisando Telemetria de Dependências ---{Style.RESET_ALL}")
            from ..tools.vulcan.advisor import VulcanAdvisor
            advisor = VulcanAdvisor(root)
            
            # Precisamos de um novo método no Advisor para isso
            hot_deps = advisor.get_hot_dependencies()
            
            if not hot_deps:
                click.echo(Fore.YELLOW + "Nenhuma dependência 'quente' encontrada na telemetria recente.")
                return

            click.echo(f"{'BIBLIOTECA':<25} | {'PONTOS DE CALOR (HITS)'}")
            click.echo("-" * 50)
            for dep, hits in hot_deps.items():
                click.echo(f"{Fore.WHITE}{dep:<25}{Style.RESET_ALL} | {Fore.RED}{hits}{Style.RESET_ALL}")
            return

        if target:
            click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Forjando: {target} ---{Style.RESET_ALL}")
            from ..tools.vulcan.lib_forge import LibForge
            
            forge = LibForge(root)
            success, result_message = forge.compile_library(target)
            
            if success:
                click.echo(f"{Fore.GREEN}{Style.BRIGHT}\n[SUCESSO] {result_message}{Style.RESET_ALL}")
            else:
                click.echo(f"{Fore.RED}{Style.BRIGHT}\n[FALHA] {result_message}{Style.RESET_ALL}")
            
            # TODO: Adicionar lógica para rodar testes e validar
            return

        elif auto:
            click.echo(f"{Fore.YELLOW}Funcionalidade '--auto' em desenvolvimento.{Style.RESET_ALL}")
            
        else:
            click.echo(ctx.get_help())


@vulcan_group.command('benchmark')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--runs',       default=200, type=int, show_default=True,
              help='Número de execuções por função para calcular média.')
@click.option('--json',       'output_json', is_flag=True,
              help='Saída em JSON (para integração com CI).')
@click.option('--min-speedup', default=1.1, type=float, show_default=True,
              help='Speedup mínimo para considerar ganho real (regressões abaixo são marcadas).')
@click.option('--save',       is_flag=True,
              help='Salva resultado em .doxoade/vulcan/bench_results.json (feedback loop).')
def vulcan_benchmark(path, runs, output_json, min_speedup, save):
    """Mede speedup real Python vs Cython das funções compiladas.

    Compara execução das funções originais Python com os binários
    gerados pelo --hybrid, exibindo speedup real por função.
    Funções com speedup < --min-speedup são marcadas como REGRESSÃO.

    Exemplos:
      doxoade vulcan benchmark doxoade/tools/
      doxoade vulcan benchmark doxoade/tools/analysis.py --runs 500
      doxoade vulcan benchmark doxoade/tools/ --json > bench.json
      doxoade vulcan benchmark doxoade/tools/ --save --min-speedup 1.2
    """
    root   = _find_project_root(os.getcwd())
    target = path or root

    if not output_json:
        click.echo(
            f"\n{Fore.CYAN}{Style.BRIGHT}"
            f"  ⚡ VULCAN BENCHMARK — {runs} execuções por função"
            f"{Style.RESET_ALL}"
        )
        click.echo(
            f"{Fore.CYAN}  Alvo: {target}{Style.RESET_ALL}\n"
        )

    try:
        from ..tools.vulcan.hybrid_benchmark import run_benchmark
        results = run_benchmark(
            project_root = root,
            target       = target,
            runs         = runs,
            output_json  = output_json,
            min_speedup  = min_speedup,
        )

        if save and results:
            import json as _json
            bench_path = (
                Path(_find_project_root(os.getcwd()))
                / ".doxoade" / "vulcan" / "bench_results.json"
            )
            bench_path.parent.mkdir(parents=True, exist_ok=True)
            # Serializa results (lista de FileBenchResult dataclasses)
            import dataclasses
            serializable = _json.loads(
                _json.dumps(results, default=lambda o: dataclasses.asdict(o) if dataclasses.is_dataclass(o) else str(o))
            )
            bench_path.write_text(_json.dumps(serializable, indent=2), encoding='utf-8')
            click.echo(
                f"\n{Fore.GREEN}  ✔ Resultados salvos em {bench_path}{Style.RESET_ALL}"
            )
            click.echo(
                f"{Fore.CYAN}  Dica: use estes dados para excluir regressões no próximo --hybrid{Style.RESET_ALL}"
            )

    except Exception as e:
        _print_vulcan_forensic("BENCHMARK", e)
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
    original = main_file.read_text(encoding="utf-8", errors="replace")
    content = original

    # Remove bootstrap anterior para permitir atualização de lógica sem duplicar bloco.
    if _BOOTSTRAP_START in content and _BOOTSTRAP_END in content:
        start = content.index(_BOOTSTRAP_START)
        end = content.index(_BOOTSTRAP_END) + len(_BOOTSTRAP_END)
        content = (content[:start] + content[end:]).lstrip("\n")

    # Remove legado quebrado inserido manualmente em alguns projetos externos.
    legacy_lines = {
        "from .doxoade.vulcan.runtime import activate_vulcan",
        "activate_vulcan(globals(), __file__)",
    }
    content_lines = [line for line in content.splitlines() if line.strip() not in legacy_lines]
    sanitized = "\n".join(content_lines).lstrip("\n")
    updated = f"{_BOOTSTRAP_BLOCK}\n{sanitized}"

    if updated == original:
        return False

    main_file.write_text(updated, encoding="utf-8")
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