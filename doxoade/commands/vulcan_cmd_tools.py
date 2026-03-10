# -*- coding: utf-8 -*-
# doxoade/commands/vulcan_cmd_tools.py
"""
Subcomandos de análise e otimização do Vulcan.

  alloc    → detecta e reduz criação de objetos temporários
  simd     → informações e benchmark SIMD
  opt      → gera camada de Python Otimizado (Tier 2)
  opt-bench → benchmark Tier 3 vs Tier 2
"""

import os
import sys
import re
import click
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import _find_project_root
from .vulcan_cmd import (
    _print_vulcan_forensic,
    _SIMD_AVAILABLE, _OBJREDUCE_AVAILABLE,
)

try:
    from doxoade.tools.vulcan.object_allocation_scanner import (
        scan_source, scan_pyx, render_report as _render_alloc_report,
    )
    from doxoade.tools.vulcan.object_reduction import reduce_source
except ImportError:
    pass


# ── Helpers internos ──────────────────────────────────────────────────────────

def _simd_debug_report():
    """Executa cada estratégia de detecção individualmente e mostra resultados."""
    import shutil
    from doxoade.tools.vulcan import simd_detector as _sd

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN SIMD — DIAGNÓSTICO DE DETECÇÃO{Style.RESET_ALL}")
    click.echo(f"  {'-' * 55}")

    strategies = [
        ("py-cpuinfo",    _sd._detect_cpuinfo),
        ("/proc/cpuinfo", _sd._detect_proc_cpuinfo),
        ("kernel32",      _sd._detect_windows_kernel32),
        ("sysctl",        _sd._detect_sysctl),
        ("cpuid-probe",   _sd._detect_cpuid),
        ("model-string",  lambda: (
            _sd._refine_via_model_string(_sd._detect_fallback())
            if hasattr(_sd, '_refine_via_model_string') else None
        )),
    ]

    results = []
    for name, fn in strategies:
        try:
            caps = fn()
            if caps is not None:
                level   = caps.best.upper()
                avx_str = (
                    f"avx={caps.avx} avx2={caps.avx2} avx512={caps.avx512f} fma={caps.fma}"
                )
                color = (
                    Fore.GREEN  if caps.level >= 4 else
                    Fore.YELLOW if caps.level >= 2 else
                    Fore.WHITE
                )
                click.echo(
                    f"  {Fore.CYAN}{name:<20}{Style.RESET_ALL} "
                    f"{color}{level:<10}{Style.RESET_ALL} "
                    f"{Style.DIM}{avx_str}{Style.RESET_ALL}"
                )
                results.append((name, caps))
            else:
                click.echo(f"  {Fore.CYAN}{name:<20}{Style.RESET_ALL} {Fore.RED}N/A{Style.RESET_ALL}")
        except Exception as e:
            click.echo(
                f"  {Fore.CYAN}{name:<20}{Style.RESET_ALL} "
                f"{Fore.RED}ERRO: {str(e)[:50]}{Style.RESET_ALL}"
            )

    click.echo(f"\n  {Fore.CYAN}Compiladores no PATH:{Style.RESET_ALL}")
    for compiler in ["gcc", "x86_64-w64-mingw32-gcc", "cl", "clang"]:
        path = shutil.which(compiler)
        if path:
            click.echo(f"  {Fore.GREEN}[OK]{Style.RESET_ALL} {compiler:<35} {Style.DIM}{path}{Style.RESET_ALL}")
        else:
            click.echo(f"  {Fore.RED}[--]{Style.RESET_ALL} {compiler}")

    try:
        model = _sd._get_cpu_model_name()
        click.echo(f"\n  {Fore.CYAN}Model string:{Style.RESET_ALL} {model}")
    except Exception:
        pass

    if results:
        best = max(results, key=lambda x: x[1].level)
        click.echo(
            f"\n  {Fore.GREEN}{Style.BRIGHT}Melhor resultado: {best[0]} → {best[1].best.upper()}{Style.RESET_ALL}"
        )
    click.echo()


# ── Comandos ──────────────────────────────────────────────────────────────────

@click.command("alloc")
@click.argument("target", default=".")
@click.option("--verbose", "-v",   is_flag=True, help="Mostra snippet de código e estratégia detalhada.")
@click.option("--fix",             is_flag=True, help="Aplica transformações automáticas nos arquivos.")
@click.option("--dry-run",         is_flag=True, help="Com --fix: mostra mudanças sem sobrescrever.")
@click.option("--pyx",             is_flag=True, help="Escaneia .pyx em vez de .py (foundry).")
@click.option("--clean-backups",   is_flag=True, help="Remove todos os arquivos .bak_*.py gerados pelo --fix.")
def vulcan_alloc(target, verbose, fix, dry_run, pyx, clean_backups):
    """Detecta e reduz criação de objetos temporários."""
    if not _OBJREDUCE_AVAILABLE:
        click.echo(
            f"{Fore.RED}[ERRO] Módulos de redução de objetos não encontrados.{Style.RESET_ALL}\n"
            f"Verifique: object_allocation_scanner.py e object_reduction.py"
        )
        return

    root = Path(target).resolve()
    _bak_re = re.compile(r"\.bak_\d{8}_\d{6}")

    if clean_backups:
        search_root = root if root.is_dir() else root.parent
        bak_files = [f for f in search_root.rglob("*.py") if _bak_re.search(f.stem)]
        if not bak_files:
            click.echo(f"{Fore.GREEN}Nenhum arquivo de backup encontrado em: {search_root}{Style.RESET_ALL}")
            return
        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  Vulcan Alloc - Limpeza de Backups{Style.RESET_ALL}")
        click.echo(f"  {'─' * 55}")
        removed = 0
        for bak in sorted(bak_files):
            rel = bak.relative_to(search_root) if bak.is_relative_to(search_root) else bak.name
            click.echo(f"  {Fore.YELLOW}[del]{Style.RESET_ALL} {rel}")
            bak.unlink()
            removed += 1
        click.echo(f"\n  {Fore.GREEN}✔ {removed} arquivo(s) de backup removido(s).{Style.RESET_ALL}\n")
        return

    ext = ".pyx" if pyx else ".py"
    if root.is_file():
        files = [root] if root.suffix == ext else []
    else:
        files = [
            f for f in root.rglob(f"*{ext}")
            if not any(p in f.parts for p in ("__pycache__", ".git", "venv", ".venv", "node_modules"))
            and not _bak_re.search(f.stem)
        ]

    if not files:
        click.echo(f"{Fore.YELLOW}Nenhum arquivo {ext} encontrado em: {root}{Style.RESET_ALL}")
        return

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN ALLOC — Detecção de Objetos Temporários{Style.RESET_ALL}")
    click.echo(f"  {'─' * 55}")
    click.echo(f"  Arquivos: {len(files)} {ext}  |  Modo: {'fix' if fix else 'scan'}\n")

    total_score = total_fixed = total_allocs = hot_files = 0

    for fpath in sorted(files):
        try:
            source = fpath.read_text(encoding="utf-8", errors="ignore")
            report = scan_pyx(source, fpath) if pyx else scan_source(source, fpath)

            if report.total_score == 0:
                continue

            hot_files   += 1
            total_score += report.total_score

            rel   = fpath.relative_to(root) if fpath.is_relative_to(root) else fpath.name
            color = (
                Fore.RED    if report.total_score >= 20 else
                Fore.YELLOW if report.total_score >= 8  else
                Fore.CYAN
            )
            click.echo(
                f"  {color}{str(rel):<40}{Style.RESET_ALL} "
                f"score={Style.BRIGHT}{report.total_score:<4}{Style.RESET_ALL} "
                f"{Fore.GREEN}{len(report.all_auto_fixable)} auto{Style.RESET_ALL}"
            )

            if verbose:
                _render_alloc_report(report, verbose=True)

            if fix:
                result = reduce_source(source, fpath, level=2, is_pyx=pyx)
                if result.has_changes:
                    if not dry_run:
                        import shutil, datetime as _dt
                        _ts  = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                        _bak = fpath.with_name(f"{fpath.stem}.bak_{_ts}{fpath.suffix}")
                        shutil.copy2(fpath, _bak)
                        fpath.write_text(result.transformed, encoding="utf-8")
                    for change in result.changes:
                        prefix = Fore.YELLOW + "  [dry]" if dry_run else Fore.GREEN + "  [fix]"
                        click.echo(f"{prefix}{Style.RESET_ALL} {change}")
                    total_fixed  += len(result.changes)
                    total_allocs += result.allocs_removed

        except Exception as e:
            click.echo(f"  {Fore.RED}[ERRO]{Style.RESET_ALL} {fpath.name}: {e}")

    click.echo(f"\n  {'─' * 55}")
    click.echo(f"  Arquivos com alocações críticas : {hot_files}")
    click.echo(f"  Score total                     : {total_score}")
    if fix:
        action = "simuladas" if dry_run else "aplicadas"
        click.echo(f"  Transformações {action:<14}: {total_fixed}")
        click.echo(f"  Allocs eliminadas (estimativa)  : ~{total_allocs}")
    else:
        click.echo(
            f"\n  {Fore.GREEN}Dica:{Style.RESET_ALL} "
            f"use {Fore.CYAN}--fix{Style.RESET_ALL} para aplicar transformações automáticas, "
            f"ou {Fore.CYAN}--fix --dry-run{Style.RESET_ALL} para preview."
        )
    click.echo()


@click.command("simd")
@click.option("--bench",              is_flag=True,   help="Executa micro-benchmark SIMD no numpy.")
@click.option("--json", "out_json",   is_flag=True,   help="Saída em JSON.")
@click.option("--level", "cap_level", default="auto",
              type=click.Choice(["auto", "native", "sse2", "avx", "avx2", "avx512f"]),
              show_default=True, help="Nível SIMD máximo a considerar.")
@click.option("--debug",              is_flag=True,   help="Mostra resultado de cada estratégia de detecção.")
def vulcan_simd(bench, out_json, cap_level, debug):
    """Detecta suporte SIMD da CPU e exibe relatório de capacidades."""
    if not _SIMD_AVAILABLE:
        click.echo(f"{Fore.RED}[ERRO] Módulos SIMD não disponíveis.{Style.RESET_ALL}")
        return

    from doxoade.tools.vulcan.simd_detector import detect as _detect_simd
    from doxoade.tools.vulcan.simd_compiler import SIMDContext, estimate_gain, get_simd_report

    if debug:
        _simd_debug_report()
        return

    ctx  = SIMDContext(level_cap=cap_level)
    caps = ctx.effective_caps()

    if out_json:
        import json as _json
        click.echo(_json.dumps(get_simd_report(caps), indent=2))
        return

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN SIMD — CPU Capabilities{Style.RESET_ALL}")
    click.echo(f"  {'-' * 55}")
    click.echo(f"  Nível         : {Fore.GREEN}{caps.best.upper()}{Style.RESET_ALL}")
    click.echo(f"  AVX           : {Fore.GREEN if caps.avx else Fore.RED}{caps.avx}{Style.RESET_ALL}")
    click.echo(f"  AVX2          : {Fore.GREEN if caps.avx2 else Fore.RED}{caps.avx2}{Style.RESET_ALL}")
    click.echo(f"  AVX-512F      : {Fore.GREEN if caps.avx512f else Fore.RED}{caps.avx512f}{Style.RESET_ALL}")
    click.echo(f"  FMA           : {Fore.GREEN if caps.fma else Fore.RED}{caps.fma}{Style.RESET_ALL}")
    click.echo(f"  CFLAGS        : {Style.DIM}{' '.join(caps.cflags)}{Style.RESET_ALL}")
    click.echo(f"  Ganho estimado: {Fore.CYAN}{estimate_gain(caps)}{Style.RESET_ALL}")

    if bench:
        click.echo(f"\n{Fore.CYAN}  ⬡ Micro-benchmark (numpy){Style.RESET_ALL}")
        try:
            import numpy as np, time
            N = 10_000_000
            a = np.random.rand(N)
            b = np.random.rand(N)

            benchmarks = [
                ("add",  lambda: np.add(a, b, out=np.empty(N))),
                ("mul",  lambda: np.multiply(a, b, out=np.empty(N))),
                ("sqrt", lambda: np.sqrt(a, out=np.empty(N))),
            ]
            click.echo(f"\n  {'Operação':<20} {'N':>12}  {'Média':>12}  {'GB/s':>8}")
            click.echo(f"  {'-'*20} {'-'*12}  {'-'*12}  {'-'*8}")
            for name, fn in benchmarks:
                fn()
                REPS = 10
                t0 = time.perf_counter()
                for _ in range(REPS):
                    fn()
                elapsed_ms     = (time.perf_counter() - t0) / REPS * 1000
                bytes_xfr      = N * 8 * 2
                gbs            = (bytes_xfr / (elapsed_ms / 1000)) / 1e9
                click.echo(
                    f"  {Fore.WHITE}{name:<20}{Style.RESET_ALL} "
                    f"{N:>12,}  "
                    f"{Fore.GREEN}{elapsed_ms:>10.2f} ms{Style.RESET_ALL}  "
                    f"{Fore.CYAN}{gbs:>6.1f} GB/s{Style.RESET_ALL}"
                )
        except ImportError:
            click.echo(f"  {Fore.YELLOW}NumPy não instalado — benchmark pulado.{Style.RESET_ALL}")
        except Exception as e:
            click.echo(f"  {Fore.RED}Benchmark falhou: {e}{Style.RESET_ALL}")


@click.command('opt')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help='Regenera mesmo arquivos já otimizados.')
@click.option('--stats', is_flag=True, help='Mostra estatísticas de economia por arquivo.')
def vulcan_opt(path, force, stats):
    """Gera camada de Python Otimizado (Tier 2) sem compilar."""
    root   = _find_project_root(os.getcwd())
    target = Path(path).resolve() if path else Path(root)

    click.echo(
        f"\n{Fore.CYAN}{Style.BRIGHT}"
        f"  ⬡ [VULCAN OPT] Gerando camada de Python Otimizado (Tier 2)..."
        f"{Style.RESET_ALL}"
    )
    click.echo(f"{Fore.CYAN}   > Alvo   : {target}{Style.RESET_ALL}")
    click.echo(f"{Fore.CYAN}   > Raiz   : {root}{Style.RESET_ALL}")

    try:
        from doxoade.tools.vulcan.opt_cache import generate_opt_py, find_opt_py, opt_dir

        skip_dirs  = frozenset({'.git', 'venv', '.venv', '__pycache__', 'build', 'dist', '.doxoade', 'tests'})
        skip_stems = frozenset({
            '__init__', '__main__', 'setup',
            'forge', 'compiler', 'autopilot', 'bridge', 'advisor',
            'environment', 'core', 'pitstop', 'diagnostic', 'guards',
            'meta_finder', 'runtime', 'auto_repair', 'artifact_manager',
            'compiler_safe', 'opt_cache',
        })

        if target.is_file():
            py_files = [target] if target.suffix == '.py' else []
        else:
            py_files = []
            for r, dirs, files in os.walk(str(target)):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for f in files:
                    p = Path(r) / f
                    if p.suffix == '.py' and p.stem not in skip_stems:
                        py_files.append(p)

        total = ok_count = skip_count = total_saved = 0

        for py_file in py_files:
            total += 1
            if not force:
                cached = find_opt_py(Path(root), py_file)
                if cached:
                    skip_count += 1
                    click.echo(
                        f"   {Fore.BLUE}↷{Style.RESET_ALL} "
                        f"{py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name}"
                        f"  {Style.DIM}(cache){Style.RESET_ALL}"
                    )
                    continue

            result = generate_opt_py(Path(root), py_file)
            if result:
                ok_count  += 1
                orig_size  = py_file.stat().st_size
                saved      = max(0, orig_size - result.stat().st_size)
                total_saved += saved
                rel = py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name
                if stats and saved > 0:
                    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {rel}  {Fore.CYAN}{saved:>6} bytes{Style.RESET_ALL}")
                else:
                    click.echo(f"   {Fore.GREEN}✔{Style.RESET_ALL} {rel}")
            else:
                click.echo(
                    f"   {Fore.YELLOW}↷{Style.RESET_ALL} "
                    f"{py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name}"
                    f"  {Style.DIM}(sem ganho){Style.RESET_ALL}"
                )

        d         = opt_dir(Path(root))
        opt_count = len(list(d.glob("opt_*.py")))

        click.echo(f"\n{Fore.CYAN}{'─' * 55}{Style.RESET_ALL}")
        click.echo(
            f"  {Fore.GREEN}✔ {ok_count} gerado(s){Style.RESET_ALL}  "
            f"{Fore.BLUE}↷ {skip_count} cache(s){Style.RESET_ALL}  "
            f"{Fore.CYAN}Total opt_py: {opt_count}{Style.RESET_ALL}"
        )
        if total_saved > 0:
            click.echo(
                f"  {Fore.GREEN}⚡ {total_saved:,} bytes economizados ({total_saved / 1024:.1f} KiB){Style.RESET_ALL}"
            )
        click.echo(
            f"\n{Fore.CYAN}[INFO] Tier 2 ativo. Quando binário falhar, "
            f"o Python otimizado será usado automaticamente.{Style.RESET_ALL}"
        )
        click.echo(f"{Fore.CYAN}{'─' * 55}{Style.RESET_ALL}")

    except Exception as e:
        _print_vulcan_forensic("OPT", e)
        sys.exit(1)


@click.command('opt-bench')
@click.argument('target', default='.')
@click.option('--rounds', '-r', default=3,   show_default=True, help='Repetições de benchmark por callable.')
@click.option('--calls',  '-c', default=100, show_default=True, help='Chamadas por round.')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--csv', '-o', default=None, metavar='ARQUIVO', help='Exporta resultado em CSV.')
@click.pass_context
def opt_bench(ctx, target, rounds, calls, verbose, csv):
    """Benchmark Tier 3 (Python Puro) vs Tier 2 (Python Otimizado)."""
    from ..tools.vulcan.opt_benchmark import run_opt_bench, render_results

    project_root = Path(os.getcwd()).resolve()
    target_path  = (project_root / target).resolve()

    if not target_path.exists():
        click.echo(f"\033[31m ■ Alvo não encontrado: {target_path}\033[0m")
        ctx.exit(1)
        return

    print(f"\n  \033[36m⬡\033[0m Alvo   : {target_path}")
    print(f"  \033[36m⬡\033[0m Raiz   : {project_root}")
    print(f"  \033[36m⬡\033[0m Rounds : {rounds} × {calls} chamadas por callable")
    print()

    try:
        results = run_opt_bench(target_path, project_root, rounds=rounds, calls=calls)
    except Exception as exc:
        click.echo(f"\033[31m ■ Erro ao executar benchmark: {exc}\033[0m")
        ctx.exit(1)
        return

    if not results:
        click.echo(
            "\033[33m ⚠ Nenhum arquivo .py encontrado no alvo.\033[0m\n"
            "   Dica: use 'doxoade vulcan opt <alvo>' para gerar Tier 2 primeiro."
        )
        return

    csv_path = Path(csv).resolve() if csv else None
    render_results(results, verbose=verbose, show_funcs=True, csv_out=csv_path)