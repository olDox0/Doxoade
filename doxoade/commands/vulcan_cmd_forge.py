# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd_forge.py
"""
Subcomandos de compilação/forja do Vulcan.

  ignite      → compila arquivos Python em binários .pyd/.so
  regression  → gerencia histórico de regressões de performance
  lib         → compila bibliotecas do venv
  benchmark   → mede speedup Python vs Cython
  pitstop     → controle do PitStop Engine
"""

import os
import sys
import signal
import site
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger, _find_project_root
from .vulcan_cmd import (
    _sigint_handler, _print_vulcan_forensic, _patch_vulcan_forge,
    _simd_context_or_none, _NullContext,
    _SIMD_AVAILABLE, _OBJREDUCE_AVAILABLE,
)

try:
    from doxoade.tools.vulcan.simd_compiler import (
        SIMDContext, SIMDForge, SIMDEnvironment, estimate_gain,
    )
except ImportError:
    pass

try:
    from doxoade.tools.vulcan.object_reduction import reduce_source
except ImportError:
    pass


# ── Helpers internos ──────────────────────────────────────────────────────────

def _load_registry_for_ignite(root, no_registry=False):
    """Carrega o RegressionRegistry. Retorna None se falhar ou --no-registry."""
    if no_registry:
        return None
    try:
        from ..tools.vulcan.regression_registry import RegressionRegistry
        return RegressionRegistry(root)
    except Exception:
        return None


def _site_packages_dirs_for_listing() -> list[str]:
    """Resolve diretórios de libs priorizando o venv ativo no terminal."""
    dirs: list[str] = []

    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        venv_path = Path(venv)
        win_site = venv_path / "Lib" / "site-packages"
        if win_site.is_dir():
            dirs.append(str(win_site))

        lib_path = venv_path / "lib"
        if lib_path.is_dir():
            for p in sorted(lib_path.glob("python*/site-packages")):
                if p.is_dir():
                    dirs.append(str(p))

    if dirs:
        return dirs

    try:
        dirs.extend(site.getsitepackages())
    except AttributeError:
        pass

    try:
        user_sp = site.getusersitepackages()
        if user_sp:
            dirs.append(user_sp)
    except AttributeError:
        pass

    for p in sys.path:
        if "site-packages" in p or "dist-packages" in p:
            dirs.append(p)

    seen = set()
    return [d for d in dirs if d and not (d in seen or seen.add(d))]


def _lib_compile_with_simd(
    target: str,
    root: str,
    simd_ctx: "SIMDContext | None",
    run_optimizer: bool = True,
) -> tuple[bool, str]:
    """
    Ponto de entrada único para compilação de libs.

    Sempre usa LibForge — que aplica optimizer + SIMD de forma integrada:
      1. LibOptimizer nos fontes da cópia  (se run_optimizer=True)
      2. HybridIgnite paralelo com SIMD flags  (se simd_ctx não for None)

    O SIMDForge foi removido deste fluxo: LibForge já injeta os flags
    diretamente no _compile de cada módulo via extra_cflags.
    """
    _patch_vulcan_forge()
    from doxoade.tools.vulcan.lib_forge import LibForge
    forge = LibForge(root)
    return forge.compile_library(target, run_optimizer=run_optimizer, simd_ctx=simd_ctx)


def _run_hybrid_with_optimizer(target, root, force, registry=None):
    """
    Compilação híbrida com optimizer integrado e suporte ao RegressionRegistry.

    Com registry:
      • Funções 'excluded'         → removidas antes de compilar
      • Funções 'retry_aggressive' → compiladas com header Cython agressivo
      • Após compilação bem-sucedida → PerformanceWatcher mede e atualiza registry
    """
    from ..tools.vulcan.hybrid_forge     import HybridIgnite
    from ..tools.vulcan.hybrid_optimizer import optimize_pyx_file
    _patch_vulcan_forge()

    ignite = HybridIgnite(root)
    files  = HybridIgnite._collect_files(Path(target).resolve())

    opt_summary        = []
    obj_reduce_summary = []
    total_excluded     = 0
    total_aggressive   = 0
    total_regressions  = 0
    total_promoted     = 0

    for py_file in files:
        scan = ignite._scanner.scan(str(py_file))
        if not scan.candidates:
            continue

        aggressive_funcs = frozenset()

        if registry is not None:
            excluded_names   = registry.excluded_funcs_for_file(str(py_file))
            aggressive_funcs = registry.aggressive_funcs_for_file(str(py_file))

            before          = len(scan.candidates)
            scan.candidates = [c for c in scan.candidates if c.name not in excluded_names]
            excl_n          = before - len(scan.candidates)
            total_excluded += excl_n

            agg_active        = aggressive_funcs & {c.name for c in scan.candidates}
            total_aggressive += len(agg_active)

            if excl_n:
                click.echo(
                    f"   {Fore.RED}↷ {py_file.name}: "
                    f"{excl_n} função(ões) excluída(s) pelo registry{Style.RESET_ALL}"
                )
            if agg_active:
                click.echo(
                    f"   {Fore.MAGENTA}⬡ {py_file.name}: "
                    f"retry-agressivo → {', '.join(sorted(agg_active))}{Style.RESET_ALL}"
                )

        if not scan.candidates:
            continue

        fname = py_file.name
        click.echo(
            f"   {Fore.YELLOW}[HYBRID]{Style.RESET_ALL} {fname} — "
            f"{len(scan.candidates)} candidato(s):"
        )
        for f in scan.candidates:
            tag = f"{Fore.MAGENTA}[AGG]{Style.RESET_ALL}" if f.name in aggressive_funcs else "     "
            click.echo(
                f"     {tag} • {f.name:<35} score={f.score:>2}  "
                f"({', '.join(f.reasons[:3])})"
            )

        # 1. Gera .pyx
        pyx_path = ignite._forge.generate(scan, aggressive_funcs=aggressive_funcs)
        if not pyx_path:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {fname}: forge falhou")
            continue

        # 2. Redução de objetos temporários (AST pura)
        if _OBJREDUCE_AVAILABLE and pyx_path.exists():
            try:
                source = pyx_path.read_text(encoding='utf-8')
                red_result = reduce_source(source, pyx_path, level=1, is_pyx=False)
                if red_result.has_changes:
                    pyx_path.write_text(red_result.transformed, encoding='utf-8')
                    obj_reduce_summary.append(red_result)
                    click.echo(
                        f"   {Fore.CYAN}  ⬡ obj-reduce{Style.RESET_ALL}: "
                        f"{len(red_result.changes)} transformação(ões), "
                        f"~{red_result.allocs_removed} alloc(s) eliminada(s)"
                    )
            except Exception:
                pass

        # 3. Enriquece com optimizer (injeta sintaxe Cython)
        try:
            pyx_path, opt_report = optimize_pyx_file(pyx_path)
            if opt_report.transformations and not opt_report.transformations[0].startswith('revertido'):
                opt_summary.append(opt_report)
                n_cdefs = len(opt_report.transformations)
                click.echo(
                    f"   {Fore.MAGENTA}  ⬡ optimizer{Style.RESET_ALL}: "
                    f"{n_cdefs} cdef(s) injetados → "
                    f"{Fore.GREEN}{opt_report.estimated_gain}{Style.RESET_ALL}"
                )
        except Exception:
            pass

        # 4. Compila
        module_name = pyx_path.stem
        ok, err = ignite._compile(module_name)

        if ok:
            click.echo(
                f"   {Fore.GREEN}✔{Style.RESET_ALL} {fname} → {module_name} "
                f"({len(scan.candidates)} funcs, score={scan.total_score})"
            )
            if registry is not None:
                try:
                    from ..tools.vulcan.performance_watcher import PerformanceWatcher
                    watcher = PerformanceWatcher(
                        project_root=root,
                        foundry=ignite.foundry,
                        bin_dir=ignite.bin_dir,
                    )
                    wr = watcher.evaluate(py_file, module_name, update_registry=True)
                    wr.render_cli()
                    total_regressions += len(wr.regressions)
                    total_promoted    += wr.registry_summary.get("promoted", 0)
                except Exception:
                    pass
        else:
            click.echo(f"   {Fore.RED}✘{Style.RESET_ALL} {fname} falhou na compilação:")
            click.echo(f"{Fore.YELLOW}{str(err)}{Style.RESET_ALL}")

    # Resumo registry
    if registry is not None and (total_excluded or total_aggressive or total_regressions):
        click.echo(f"\n{Fore.MAGENTA}  ⬡ REGRESSION REGISTRY — resumo desta compilação:{Style.RESET_ALL}")
        if total_excluded:
            click.echo(f"    {Fore.RED}Funções excluídas (permanente)  : {total_excluded}{Style.RESET_ALL}")
        if total_aggressive:
            click.echo(f"    {Fore.YELLOW}Funções retry-agressivo         : {total_aggressive}{Style.RESET_ALL}")
        if total_regressions:
            click.echo(f"    {Fore.RED}Novas regressões detectadas     : {total_regressions}{Style.RESET_ALL}")
        if total_promoted:
            click.echo(f"    {Fore.GREEN}Funções promovidas (recuperadas): {total_promoted}{Style.RESET_ALL}")
        click.echo(f"    {Fore.CYAN}Gerencie com: doxoade vulcan regression{Style.RESET_ALL}")

    # Resumo optimizer
    if opt_summary:
        total_cdefs = sum(len(r.transformations) for r in opt_summary)
        click.echo(
            f"\n{Fore.MAGENTA}"
            f"  ⬡ OPTIMIZER: {total_cdefs} cdef(s) em {len(opt_summary)} módulo(s)"
            f"{Style.RESET_ALL}"
        )
        for r in opt_summary:
            click.echo(f"    {r.module_name:<30} → {Fore.GREEN}{r.estimated_gain}{Style.RESET_ALL}")

    # Resumo obj-reduce
    if obj_reduce_summary:
        total_allocs  = sum(r.allocs_removed for r in obj_reduce_summary)
        total_changes = sum(len(r.changes) for r in obj_reduce_summary)
        click.echo(
            f"\n{Fore.CYAN}"
            f"  ⬡ OBJ-REDUCE: {total_changes} transformação(ões) em "
            f"{len(obj_reduce_summary)} módulo(s), "
            f"~{total_allocs} alloc(s) eliminada(s)"
            f"{Style.RESET_ALL}"
        )


# ── Comandos ──────────────────────────────────────────────────────────────────

@click.command('ignite')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force',        is_flag=True,  help="Força a re-compilação de todos os alvos.")
@click.option('--jobs',         type=int, default=None, help="Número de workers (sobrescreve auto).")
@click.option('--no-pitstop',   is_flag=True,  help="Usa compilação legada (1 processo por módulo).")
@click.option('--streaming',    is_flag=True,  help="Forge e compilação em paralelo (melhor para > 15 módulos).")
@click.option('--hybrid',       is_flag=True,  help="Compilação seletiva por função (HybridForge).")
@click.option('--scan-only',    is_flag=True,  help="Com --hybrid: mostra candidatos sem compilar.")
@click.option('--simd',         is_flag=True,  help="Ativa otimizações SIMD (AVX/SSE) na compilação.")
@click.option('--simd-level',   default="auto",
              type=click.Choice(["auto", "native", "sse2", "avx", "avx2", "avx512f"]),
              show_default=True, help="Nível SIMD máximo (padrão: auto-detecta).")
@click.pass_context
def ignite(ctx, path, force, jobs, no_pitstop, streaming, hybrid, scan_only, simd, simd_level):
    """Transforma código Python em binários de alta velocidade.

    Modos:
      padrão   → PitStop Engine
      --hybrid → HybridForge (seletivo por função)
      --simd   → injeta flags AVX/SSE2/NEON na compilação

    Exemplos::

    \b
      doxoade vulcan ignite --simd
      doxoade vulcan ignite --hybrid --simd --simd-level avx2
    """
    signal.signal(signal.SIGINT, _sigint_handler)
    root   = _find_project_root(os.getcwd())
    target = path or root

    simd_ctx = _simd_context_or_none(simd, simd_level)

    if simd_ctx and _SIMD_AVAILABLE:
        eff = simd_ctx.effective_caps()
        click.echo(
            f"\n  {Fore.MAGENTA}⬡ SIMD:{Style.RESET_ALL} "
            f"{Fore.GREEN}{eff.best.upper()}{Style.RESET_ALL}  "
            f"{Fore.CYAN}est. {estimate_gain(eff)}{Style.RESET_ALL}"
        )
        click.echo(
            f"  {Fore.MAGENTA}  flags:{Style.RESET_ALL} "
            f"{Style.DIM}{' '.join(eff.cflags)}{Style.RESET_ALL}\n"
        )
    elif simd and not _SIMD_AVAILABLE:
        click.echo(f"  {Fore.YELLOW}⚠ --simd ignorado: módulos SIMD não disponíveis.{Style.RESET_ALL}")

    if hybrid:
        from doxoade.tools.vulcan.hybrid_forge import hybrid_ignite
        _patch_vulcan_forge()
        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}⬡ [VULCAN-HYBRID] ...{Style.RESET_ALL}")

        registry = None
        try:
            from doxoade.tools.vulcan.regression_registry import RegressionRegistry
            registry = RegressionRegistry(root)
            r = registry.report()
            if r["total"]:
                click.echo(
                    f"{Fore.MAGENTA}   > Registry: "
                    f"{Fore.RED}{r['excluded']} excluída(s){Style.RESET_ALL}  "
                    f"{Fore.YELLOW}{r['retry_aggressive']} retry-agressivo{Style.RESET_ALL}"
                )
        except Exception:
            registry = None

        if scan_only:
            click.echo(f"{Fore.CYAN}   > Modo: SCAN ONLY (sem compilação){Style.RESET_ALL}")
            _run_hybrid_with_optimizer(target, root, force, registry=registry)
            return

        click.echo(f"{Fore.CYAN}   > Alvo : {target}{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   > Modo : HÍBRIDO{Style.RESET_ALL}")

        _env_ctx = SIMDEnvironment(simd_ctx) if simd_ctx else _NullContext()

        with ExecutionLogger("vulcan_hybrid", root, ctx.params) as _:
            try:
                with _env_ctx:
                    _run_hybrid_with_optimizer(target=target, root=root, force=force, registry=registry)
            except KeyboardInterrupt:
                _sigint_handler(None, None)
            except Exception as e:
                _print_vulcan_forensic("HYBRID", e)
                sys.exit(1)
        return

    # Modo Padrão (PitStop)
    with ExecutionLogger("vulcan_ignite", root, ctx.params) as _:
        click.echo(f"{Fore.YELLOW}{Style.BRIGHT}🔥 [VULCAN-IGNITION] ...{Style.RESET_ALL}")

        from doxoade.tools.vulcan.diagnostic import VulcanDiagnostic
        diag = VulcanDiagnostic(root)
        ok, _ = diag.check_environment()
        if not ok:
            diag.render_report()
            sys.exit(1)

        from doxoade.tools.vulcan.autopilot import VulcanAutopilot
        _patch_vulcan_forge()
        autopilot = VulcanAutopilot(root)

        candidates, mode = [], "AUTOMÁTICO"

        if path:
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                mode = f"MANUAL (arquivo: {os.path.basename(abs_path)})"
                candidates.append({"file": abs_path})
            elif os.path.isdir(abs_path):
                mode = f"MANUAL (diretório: {os.path.basename(abs_path)})"
                from doxoade.dnm import DNM
                dnm = DNM(abs_path)
                py_files = dnm.scan(extensions=["py"])
                candidates = [{"file": f} for f in py_files]

        engine_label = (
            f"{Fore.YELLOW}LEGADO{Style.RESET_ALL}"
            if no_pitstop
            else f"{Fore.GREEN}PITSTOP{Style.RESET_ALL}"
            + (f" {Fore.CYAN}+streaming{Style.RESET_ALL}" if streaming else "")
        )
        click.echo(f"{Fore.CYAN}   > Modo  : {mode}{Style.RESET_ALL}")
        click.echo(f"{Fore.CYAN}   > Engine: {engine_label}{Style.RESET_ALL}")

        _env_ctx = SIMDEnvironment(simd_ctx) if simd_ctx else _NullContext()

        try:
            with _env_ctx:
                autopilot.scan_and_optimize(
                    candidates      = candidates,
                    force_recompile = force,
                    max_workers     = jobs,
                    use_pitstop     = not no_pitstop,
                    streaming       = streaming,
                )
            click.echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [VULCAN] Forja concluída.{Style.RESET_ALL}")
            if simd_ctx:
                click.echo(
                    f"   {Fore.MAGENTA}⬡ SIMD {simd_ctx.effective_caps().best.upper()} "
                    f"aplicado.{Style.RESET_ALL}"
                )
        except KeyboardInterrupt:
            _sigint_handler(None, None)
        except Exception as e:
            _print_vulcan_forensic("IGNITE", e)
            sys.exit(1)


@click.command('regression')
@click.option('--reset',         is_flag=True, help='Remove funções excluídas (nova tentativa).')
@click.option('--reset-all',     is_flag=True, help='Limpa todo o registry.')
@click.option('--purge-missing', is_flag=True, help='Remove arquivos que não existem mais.')
@click.option('--json', 'output_json', is_flag=True, help='Saída em JSON.')
def vulcan_regression(reset, reset_all, purge_missing, output_json):
    """Gerencia o RegressionRegistry — histórico de regressões de performance."""
    root = _find_project_root(os.getcwd())
    try:
        from ..tools.vulcan.regression_registry import RegressionRegistry
        registry = RegressionRegistry(root)

        if reset_all:
            n = registry.clear_all()
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Registry limpo ({n} entrada(s)).")
            return

        if reset:
            n = registry.clear_excluded()
            click.echo(
                f"{Fore.GREEN}[OK]{Style.RESET_ALL} {n} função(ões) excluída(s) removida(s).\n"
                f"{Fore.CYAN}[INFO] Serão recompiladas no próximo ignite.{Style.RESET_ALL}"
            )
            return

        if purge_missing:
            n = registry.purge_missing_files()
            click.echo(f"{Fore.GREEN}[OK]{Style.RESET_ALL} {n} entrada(s) de arquivos inexistentes removidas.")
            return

        if output_json:
            import json as _json
            click.echo(_json.dumps(registry.report(), indent=2, ensure_ascii=False))
        else:
            registry.render_cli()

    except Exception as e:
        _print_vulcan_forensic("REGRESSION", e)
        sys.exit(1)


@click.command('lib')
@click.option('--analyze',        is_flag=True, help="Lista dependências 'quentes' candidatas à compilação.")
@click.option('--target',         help="Nome da biblioteca instalada no venv a compilar.")
@click.option('--auto',           is_flag=True, help="Compila automaticamente os melhores candidatos.")
@click.option('--list-installed', is_flag=True, help="Lista libs instaladas no site-packages.")
@click.option('--optimize',       is_flag=True, help="Apenas otimiza os fontes (inspeciona sem compilar). Exige --target.")
@click.option('--no-optimize',    is_flag=True, help="Pula o LibOptimizer antes de compilar (debug/benchmarking).")
@click.option('--keep-temp',      is_flag=True, help="Mantém cópia temporária para inspeção/debug.")
@click.option('--simd',           is_flag=True, help="Ativa otimizações SIMD (AVX/SSE) na compilação.")
@click.option('--simd-level',     default="auto",
              type=click.Choice(["auto", "native", "sse2", "avx", "avx2", "avx512f"]),
              show_default=True, help="Nível SIMD máximo (padrão: auto-detecta).")
@click.pass_context
def vulcan_lib(ctx, analyze, target, auto, list_installed, optimize, no_optimize, keep_temp, simd, simd_level):
    """Compila funções elegíveis de dependências já instaladas no venv.

    Pipeline padrão (--target):
      1. Copia fontes isolados do venv
      2. LibOptimizer nos fontes (dead code, imports, docstrings, locals)
      3. HybridIgnite paralelo nos fontes otimizados [+ SIMD se --simd]
      4. Promove binários para lib_bin/

    Use --no-optimize para pular a etapa 2 (diagnóstico/benchmarking).
    Use --optimize sozinho para inspecionar fontes sem compilar.
    
    --target click                      | OPT → compile
    --target click --simd               | OPT → compile + SIMD
    --target click --no-optimize        | compile direto (sem OPT)
    --target click --no-optimize --simd | compile + SIMD (sem OPT)
    --target click --optimize           | OPT-only (inspeciona, sem compilar)
    
    """
    root = _find_project_root(os.getcwd())

    with ExecutionLogger('vulcan_lib', root, ctx.params) as logger:

        if list_installed:
            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Libs instaladas no site-packages ---"
                f"{Style.RESET_ALL}"
            )
            site_dirs = _site_packages_dirs_for_listing()
            rows = []
            for sp in site_dirs:
                sp_path = Path(sp)
                if not sp_path.is_dir():
                    continue
                for item in sorted(sp_path.iterdir()):
                    if not item.is_dir() or not (item / "__init__.py").exists():
                        continue
                    py_files = list(item.rglob("*.py"))
                    if py_files:
                        rows.append((item.name, len(py_files), str(item)))

            if not rows:
                click.echo(f"{Fore.YELLOW}Nenhum pacote encontrado.{Style.RESET_ALL}")
                return

            rows.sort(key=lambda r: r[1], reverse=True)
            click.echo(f"  {'BIBLIOTECA':<30} {'ARQUIVOS .PY':>14}")
            click.echo(f"  {'-'*30} {'-'*14}")
            for name, count, _ in rows[:40]:
                click.echo(
                    f"  {Fore.WHITE}{name:<30}{Style.RESET_ALL} "
                    f"{Fore.CYAN}{count:>14}{Style.RESET_ALL}"
                )
            if len(rows) > 40:
                click.echo(f"  {Style.DIM}... e mais {len(rows) - 40} pacote(s){Style.RESET_ALL}")
            return

        if analyze:
            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Analisando telemetria de dependências ---"
                f"{Style.RESET_ALL}"
            )
            from ..tools.vulcan.advisor import VulcanAdvisor
            advisor = VulcanAdvisor(root)
            hot_deps = advisor.get_hot_dependencies()

            if not hot_deps:
                click.echo(
                    f"{Fore.YELLOW}Nenhuma dependência 'quente' encontrada na telemetria recente.{Style.RESET_ALL}"
                )
                return

            click.echo(f"  {'BIBLIOTECA':<28} {'HITS':>8}  COMANDO")
            click.echo(f"  {'-'*28} {'-'*8}  {'-'*35}")
            for dep, hits in list(hot_deps.items())[:20]:
                click.echo(
                    f"  {Fore.WHITE}{dep:<28}{Style.RESET_ALL} "
                    f"{Fore.RED}{hits:>8}{Style.RESET_ALL}  "
                    f"{Style.DIM}doxoade vulcan lib --target {dep}{Style.RESET_ALL}"
                )
            return

        # FIX #5: validação antecipada de --optimize sem --target (era duplicada)
        if optimize and not target:
            click.echo(
                f"{Fore.YELLOW}[ERRO] --optimize exige --target.{Style.RESET_ALL}\n"
                f"{Fore.CYAN}Exemplo:{Style.RESET_ALL}\n"
                f"  doxoade vulcan lib --optimize --target click\n\n"
                f"{Fore.CYAN}Dica:{Style.RESET_ALL} use --list-installed para ver libs disponíveis."
            )
            return

        if optimize and target:
            click.echo(f"{Fore.CYAN}   > Modo: OPTIMIZE-ONLY (nenhuma compilação será executada){Style.RESET_ALL}")
            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Otimizando (apenas) a biblioteca: {target} ---"
                f"{Style.RESET_ALL}"
            )
            import importlib.util
            import shutil
            import tempfile

            try:
                spec = importlib.util.find_spec(target)
                if spec is None:
                    click.echo(f"{Fore.RED}[FALHA] Não foi possível localizar '{target}' no venv.{Style.RESET_ALL}")
                    click.echo(f"{Fore.YELLOW}[DICA] Verifique o nome ou use --list-installed.{Style.RESET_ALL}")
                    return

                if spec.submodule_search_locations:
                    pkg_path = Path(next(iter(spec.submodule_search_locations)))
                else:
                    if not spec.origin:
                        click.echo(f"{Fore.RED}[FALHA] Spec não contém origem para '{target}'.{Style.RESET_ALL}")
                        return
                    pkg_path = Path(spec.origin).parent

                if not pkg_path.exists():
                    click.echo(f"{Fore.RED}[FALHA] Caminho da lib não existe: {pkg_path}{Style.RESET_ALL}")
                    return

                tmp_ctx = tempfile.TemporaryDirectory(prefix=f"vulcan_opt_{target}_")
                tmp = tmp_ctx.name
                dest = Path(tmp) / pkg_path.name

                try:
                    shutil.copytree(pkg_path, dest, dirs_exist_ok=False)

                    from ..tools.vulcan.lib_optimizer import LibOptimizer
                    optimizer = LibOptimizer()
                    stats = optimizer.optimize_directory(dest)

                    # FIX #5: logger existe no escopo do `with ExecutionLogger` — uso correto
                    try:
                        logger.write_artifact(
                            name=f"vulcan_lib_opt_{target}.json",
                            data=stats
                        )
                    except Exception:
                        pass

                    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Resumo da Otimização ---{Style.RESET_ALL}")
                    click.echo(f"  Arquivos processados : {stats.get('files_processed', 0)}")
                    click.echo(f"  Arquivos otimizados  : {stats.get('files_optimized', 0)}")
                    click.echo(f"  Arquivos ignorados   : {stats.get('files_skipped', 0)}")
                    click.echo(f"  Docstrings removidas : {stats.get('docstrings_removed', 0)}")
                    click.echo(f"  Dead branches        : {stats.get('dead_branches', 0)}")
                    click.echo(f"  Imports removidos    : {stats.get('imports_removed', 0)}")
                    click.echo(f"  Locals minificados   : {stats.get('locals_minified', 0)}")
                    bytes_saved = stats.get('bytes_saved', 0)
                    click.echo(f"  Bytes economizados   : {bytes_saved} ({bytes_saved/1024:.1f} KiB)")
                    click.echo(f"\n{Fore.GREEN}[SUCESSO] Otimização concluída na cópia: {dest}{Style.RESET_ALL}")
                    click.echo(f"{Fore.CYAN}[DICA] Para compilar após otimizar: doxoade vulcan lib --target {target}{Style.RESET_ALL}")

                    # FIX #6: removido o bloco click.echo inacessível que ficava após return

                finally:
                    if keep_temp:
                        click.echo(
                            f"{Fore.YELLOW}[INFO] --keep-temp ativo. Diretório preservado:{Style.RESET_ALL}\n"
                            f"  {Path(tmp)}"
                        )
                    else:
                        try:
                            tmp_ctx.cleanup()
                        except Exception:
                            pass

                return

            except Exception as exc:
                click.echo(f"{Fore.RED}[FALHA] Erro durante otimização: {exc}{Style.RESET_ALL}")
                return

        if target:
            run_optimizer = not no_optimize
            simd_ctx      = _simd_context_or_none(simd, simd_level)

            mode_parts = []
            if run_optimizer:
                mode_parts.append("OPT")
            if simd_ctx and _SIMD_AVAILABLE:
                mode_parts.append(f"SIMD/{simd_level.upper()}")
            mode_label = " + ".join(mode_parts) if mode_parts else "PADRÃO"

            click.echo(
                f"{Fore.CYAN}{Style.BRIGHT}"
                f"--- [VULCAN LIB] Forjando: {target}  [{mode_label}] ---"
                f"{Style.RESET_ALL}"
            )
            click.echo(
                f"{Fore.CYAN}   > Modo: VENV LOCAL (sem download — cópia isolada dos fontes){Style.RESET_ALL}"
            )
            if not run_optimizer:
                click.echo(f"{Fore.YELLOW}   > --no-optimize: LibOptimizer desabilitado.{Style.RESET_ALL}")

            if simd_ctx and _SIMD_AVAILABLE:
                eff = simd_ctx.effective_caps()
                click.echo(f"  {Fore.MAGENTA}⬡ SIMD:{Style.RESET_ALL} {eff.best.upper()} — {estimate_gain(eff)}")
            elif simd and not _SIMD_AVAILABLE:
                click.echo(f"  {Fore.YELLOW}⚠ --simd ignorado: módulos SIMD não disponíveis.{Style.RESET_ALL}")

            success, result_message = _lib_compile_with_simd(
                target,
                root,
                simd_ctx,
                run_optimizer=run_optimizer,
            )

            if success:
                click.echo(f"{Fore.GREEN}{Style.BRIGHT}\n[SUCESSO] {result_message}{Style.RESET_ALL}")
                click.echo(f"{Fore.CYAN}[DICA] Use 'doxoade vulcan status' para ver os binários ativos.{Style.RESET_ALL}")
            else:
                click.echo(f"{Fore.RED}{Style.BRIGHT}\n[FALHA] {result_message}{Style.RESET_ALL}")
                click.echo(f"{Fore.YELLOW}[DICA] Use --list-installed para ver libs disponíveis no venv.{Style.RESET_ALL}")
            return

        elif auto:
            click.echo(f"{Fore.YELLOW}[INFO] --auto: compila as top-3 libs da telemetria automaticamente.{Style.RESET_ALL}")
            from ..tools.vulcan.advisor import VulcanAdvisor
            from ..tools.vulcan.lib_forge import LibForge
            _patch_vulcan_forge()

            advisor  = VulcanAdvisor(root)
            hot_deps = advisor.get_hot_dependencies()

            if not hot_deps:
                click.echo(f"{Fore.YELLOW}Sem dados de telemetria para --auto.{Style.RESET_ALL}")
                return

            forge = LibForge(root)
            for lib in list(hot_deps.keys())[:3]:
                click.echo(f"\n{Fore.CYAN}  → Compilando: {lib}{Style.RESET_ALL}")
                success, msg = forge.compile_library(lib)
                if success:
                    click.echo(f"{Fore.GREEN}  ✔ {msg}{Style.RESET_ALL}")
                else:
                    click.echo(f"{Fore.YELLOW}  ↷ {msg}{Style.RESET_ALL}")
            return

        else:
            click.echo(ctx.get_help())


@click.command('benchmark')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--runs',       default=10, type=int, show_default=True)
@click.option('--json', 'output_json', is_flag=True)
@click.option('--min-speedup', default=1.1, type=float, show_default=True)
@click.option('--save',        is_flag=True)
@click.option('--learn/--no-learn', default=True)
def vulcan_benchmark(path, runs, output_json, min_speedup, save, learn):
    """Mede speedup real Python vs Cython das funções compiladas."""
    root   = _find_project_root(os.getcwd())
    target = path or root

    if not output_json:
        click.echo(
            f"\n{Fore.CYAN}{Style.BRIGHT}"
            f"  ⚡ VULCAN BENCHMARK — {runs} execuções por função"
            f"{Style.RESET_ALL}"
        )
        click.echo(f"{Fore.CYAN}  Alvo: {target}{Style.RESET_ALL}\n")

    try:
        from ..tools.vulcan.hybrid_benchmark import run_benchmark
        results = run_benchmark(
            project_root=root, target=target, runs=runs,
            output_json=output_json, min_speedup=min_speedup,
        )

        if save and results:
            import json as _json, dataclasses
            bench_path = Path(_find_project_root(os.getcwd())) / ".doxoade" / "vulcan" / "bench_results.json"
            bench_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = _json.loads(
                _json.dumps(results, default=lambda o: dataclasses.asdict(o) if dataclasses.is_dataclass(o) else str(o))
            )
            bench_path.write_text(_json.dumps(serializable, indent=2), encoding='utf-8')
            click.echo(f"\n{Fore.GREEN}  ✔ Resultados salvos em {bench_path}{Style.RESET_ALL}")

        if learn and results:
            from ..tools.vulcan.regression_registry import RegressionRegistry
            registry = RegressionRegistry(root)
            summary  = registry.update_from_benchmark(results, min_speedup=min_speedup)

            click.echo(f"\n{Fore.MAGENTA}{Style.BRIGHT}  ⬡ REGRESSION REGISTRY atualizado{Style.RESET_ALL}")
            click.echo(
                f"  {Fore.RED}Excluídas      : {summary['excluded']}{Style.RESET_ALL}  "
                f"{Fore.YELLOW}Retry-Agressivo: {summary['retry_aggressive']}{Style.RESET_ALL}  "
                f"{Fore.GREEN}Promovidas     : {summary['promoted']}{Style.RESET_ALL}"
            )
            if summary["excluded"]:
                click.echo(
                    f"\n  {Fore.RED}⚠ {summary['excluded']} função(ões) permanentemente excluída(s).{Style.RESET_ALL}"
                    f"\n  {Fore.CYAN}  Para resetar: doxoade vulcan regression --reset{Style.RESET_ALL}"
                )
            if summary["retry_aggressive"]:
                click.echo(
                    f"\n  {Fore.YELLOW}⬡ {summary['retry_aggressive']} função(ões) marcadas para retry-agressivo.{Style.RESET_ALL}"
                )

    except Exception as e:
        _print_vulcan_forensic("BENCHMARK", e)
        sys.exit(1)


@click.command('pitstop')
@click.option('--clear-cache', is_flag=True, help="Apaga o WarmupCache (força recompilação total).")
def vulcan_pitstop(clear_cache):
    """Informações e controle do PitStop Engine (cache + warm-up)."""
    root = _find_project_root(os.getcwd())

    from ..tools.vulcan.environment import VulcanEnvironment
    from ..tools.vulcan.pitstop import PitstopEngine

    env    = VulcanEnvironment(root)
    engine = PitstopEngine(env)
    info   = engine.warmup_info()

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
