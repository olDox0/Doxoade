# doxoade/doxoade/commands/vulcan_cmd/vulcan_cmd_tools.py
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
from doxoade.commands.vulcan_cmd.vulcan_command import _SIMD_AVAILABLE, _OBJREDUCE_AVAILABLE
from doxoade.tools.filesystem import _find_project_root
from doxoade.commands.vulcan_cmd.vulcan_command import _print_vulcan_forensic
try:
    from doxoade.tools.vulcan.object_allocation_scanner import scan_source, scan_pyx, render_report as _render_alloc_report
    from doxoade.tools.vulcan.object_reduction import reduce_source
except ImportError:
    pass

def _simd_debug_report():
    """Executa cada estratégia de detecção individualmente e mostra resultados."""
    import shutil
    from doxoade.tools.vulcan import simd_detector as _sd
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN SIMD — DIAGNÓSTICO DE DETECÇÃO{Style.RESET_ALL}')
    click.echo(f"  {'-' * 55}")
    strategies = [('py-cpuinfo', _sd._detect_cpuinfo), ('/proc/cpuinfo', _sd._detect_proc_cpuinfo), ('kernel32', _sd._detect_windows_kernel32), ('sysctl', _sd._detect_sysctl), ('cpuid-probe', _sd._detect_cpuid), ('model-string', lambda: _sd._refine_via_model_string(_sd._detect_fallback()) if hasattr(_sd, '_refine_via_model_string') else None)]
    results = []
    for name, fn in strategies:
        try:
            caps = fn()
            if caps is not None:
                level = caps.best.upper()
                avx_str = f'avx={caps.avx} avx2={caps.avx2} avx512={caps.avx512f} fma={caps.fma}'
                color = Fore.GREEN if caps.level >= 4 else Fore.YELLOW if caps.level >= 2 else Fore.WHITE
                click.echo(f'  {Fore.CYAN}{name:<20}{Style.RESET_ALL} {color}{level:<10}{Style.RESET_ALL} {Style.DIM}{avx_str}{Style.RESET_ALL}')
                results.append((name, caps))
            else:
                click.echo(f'  {Fore.CYAN}{name:<20}{Style.RESET_ALL} {Fore.RED}N/A{Style.RESET_ALL}')
        except Exception as e:
            click.echo(f'  {Fore.CYAN}{name:<20}{Style.RESET_ALL} {Fore.RED}ERRO: {str(e)[:50]}{Style.RESET_ALL}')
    click.echo(f'\n  {Fore.CYAN}Compiladores no PATH:{Style.RESET_ALL}')
    for compiler in ['gcc', 'x86_64-w64-mingw32-gcc', 'cl', 'clang']:
        path = shutil.which(compiler)
        if path:
            click.echo(f'  {Fore.GREEN}[OK]{Style.RESET_ALL} {compiler:<35} {Style.DIM}{path}{Style.RESET_ALL}')
        else:
            click.echo(f'  {Fore.RED}[--]{Style.RESET_ALL} {compiler}')
    try:
        model = _sd._get_cpu_model_name()
        click.echo(f'\n  {Fore.CYAN}Model string:{Style.RESET_ALL} {model}')
    except Exception:
        pass
    if results:
        best = max(results, key=lambda x: x[1].level)
        click.echo(f'\n  {Fore.GREEN}{Style.BRIGHT}Melhor resultado: {best[0]} → {best[1].best.upper()}{Style.RESET_ALL}')
    click.echo()

@click.command('alloc')
@click.argument('target', default='.')
@click.option('--verbose', '-v', is_flag=True, help='Mostra snippet de código e estratégia detalhada.')
@click.option('--fix', is_flag=True, help='Aplica transformações automáticas nos arquivos.')
@click.option('--dry-run', is_flag=True, help='Com --fix: mostra mudanças sem sobrescrever.')
@click.option('--pyx', is_flag=True, help='Escaneia .pyx em vez de .py (foundry).')
@click.option('--clean-backups', is_flag=True, help='Remove todos os arquivos .bak_*.py gerados pelo --fix.')
def vulcan_alloc(target, verbose, fix, dry_run, pyx, clean_backups):
    """Detecta e reduz criação de objetos temporários."""
    if not _OBJREDUCE_AVAILABLE:
        click.echo(f'{Fore.RED}[ERRO] Módulos de redução de objetos não encontrados.{Style.RESET_ALL}\nVerifique: object_allocation_scanner.py e object_reduction.py')
        return
    root = Path(target).resolve()
    _bak_re = re.compile('\\.bak_\\d{8}_\\d{6}')
    if clean_backups:
        search_root = root if root.is_dir() else root.parent
        bak_files = [f for f in search_root.rglob('*.py') if _bak_re.search(f.stem)]
        if not bak_files:
            click.echo(f'{Fore.GREEN}Nenhum arquivo de backup encontrado em: {search_root}{Style.RESET_ALL}')
            return
        click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  Vulcan Alloc - Limpeza de Backups{Style.RESET_ALL}')
        click.echo(f"  {'─' * 55}")
        removed = 0
        for bak in sorted(bak_files):
            rel = bak.relative_to(search_root) if bak.is_relative_to(search_root) else bak.name
            click.echo(f'  {Fore.YELLOW}[del]{Style.RESET_ALL} {rel}')
            bak.unlink()
            removed += 1
        click.echo(f'\n  {Fore.GREEN}✔ {removed} arquivo(s) de backup removido(s).{Style.RESET_ALL}\n')
        return
    ext = '.pyx' if pyx else '.py'
    if root.is_file():
        files = [root] if root.suffix == ext else []
    else:
        files = [f for f in root.rglob(f'*{ext}') if not any((p in f.parts for p in ('__pycache__', '.git', 'venv', '.venv', 'node_modules'))) and (not _bak_re.search(f.stem))]
    if not files:
        click.echo(f'{Fore.YELLOW}Nenhum arquivo {ext} encontrado em: {root}{Style.RESET_ALL}')
        return
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN ALLOC — Detecção de Objetos Temporários{Style.RESET_ALL}')
    click.echo(f"  {'─' * 55}")
    click.echo(f"  Arquivos: {len(files)} {ext}  |  Modo: {('fix' if fix else 'scan')}\n")
    total_score = total_fixed = total_allocs = hot_files = 0
    for fpath in sorted(files):
        try:
            source = fpath.read_text(encoding='utf-8', errors='ignore')
            report = scan_pyx(source, fpath) if pyx else scan_source(source, fpath)
            if report.total_score == 0:
                continue
            hot_files += 1
            total_score += report.total_score
            rel = fpath.relative_to(root) if fpath.is_relative_to(root) else fpath.name
            color = Fore.RED if report.total_score >= 20 else Fore.YELLOW if report.total_score >= 8 else Fore.CYAN
            click.echo(f'  {color}{str(rel):<40}{Style.RESET_ALL} score={Style.BRIGHT}{report.total_score:<4}{Style.RESET_ALL} {Fore.GREEN}{len(report.all_auto_fixable)} auto{Style.RESET_ALL}')
            if verbose:
                _render_alloc_report(report, verbose=True)
            if fix:
                result = reduce_source(source, fpath, level=2, is_pyx=pyx)
                if result.has_changes:
                    if not dry_run:
                        import shutil, datetime as _dt
                        _ts = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
                        _bak = fpath.with_name(f'{fpath.stem}.bak_{_ts}{fpath.suffix}')
                        shutil.copy2(fpath, _bak)
                        fpath.write_text(result.transformed, encoding='utf-8')
                    for change in result.changes:
                        prefix = Fore.YELLOW + '  [dry]' if dry_run else Fore.GREEN + '  [fix]'
                        click.echo(f'{prefix}{Style.RESET_ALL} {change}')
                    total_fixed += len(result.changes)
                    total_allocs += result.allocs_removed
        except Exception as e:
            click.echo(f'  {Fore.RED}[ERRO]{Style.RESET_ALL} {fpath.name}: {e}')
    click.echo(f"\n  {'─' * 55}")
    click.echo(f'  Arquivos com alocações críticas : {hot_files}')
    click.echo(f'  Score total                     : {total_score}')
    if fix:
        action = 'simuladas' if dry_run else 'aplicadas'
        click.echo(f'  Transformações {action:<14}: {total_fixed}')
        click.echo(f'  Allocs eliminadas (estimativa)  : ~{total_allocs}')
    else:
        click.echo(f'\n  {Fore.GREEN}Dica:{Style.RESET_ALL} use {Fore.CYAN}--fix{Style.RESET_ALL} para aplicar transformações automáticas, ou {Fore.CYAN}--fix --dry-run{Style.RESET_ALL} para preview.')
    click.echo()

@click.command('simd')
@click.option('--bench', is_flag=True, help='Executa micro-benchmark SIMD no numpy.')
@click.option('--json', 'out_json', is_flag=True, help='Saída em JSON.')
@click.option('--level', 'cap_level', default='auto', type=click.Choice(['auto', 'native', 'sse2', 'avx', 'avx2', 'avx512f']), show_default=True, help='Nível SIMD máximo a considerar.')
@click.option('--debug', is_flag=True, help='Mostra resultado de cada estratégia de detecção.')
def vulcan_simd(bench, out_json, cap_level, debug):
    """Detecta suporte SIMD da CPU e exibe relatório de capacidades."""
    if not _SIMD_AVAILABLE:
        click.echo(f'{Fore.RED}[ERRO] Módulos SIMD não disponíveis.{Style.RESET_ALL}')
        return
    from doxoade.tools.vulcan.simd_compiler import SIMDContext, estimate_gain, get_simd_report
    if debug:
        _simd_debug_report()
        return
    ctx = SIMDContext(level_cap=cap_level)
    caps = ctx.effective_caps()
    if out_json:
        import json as _json
        click.echo(_json.dumps(get_simd_report(caps), indent=2))
        return
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN SIMD — CPU Capabilities{Style.RESET_ALL}')
    click.echo(f"  {'-' * 55}")
    click.echo(f'  Nível         : {Fore.GREEN}{caps.best.upper()}{Style.RESET_ALL}')
    click.echo(f'  AVX           : {(Fore.GREEN if caps.avx else Fore.RED)}{caps.avx}{Style.RESET_ALL}')
    click.echo(f'  AVX2          : {(Fore.GREEN if caps.avx2 else Fore.RED)}{caps.avx2}{Style.RESET_ALL}')
    click.echo(f'  AVX-512F      : {(Fore.GREEN if caps.avx512f else Fore.RED)}{caps.avx512f}{Style.RESET_ALL}')
    click.echo(f'  FMA           : {(Fore.GREEN if caps.fma else Fore.RED)}{caps.fma}{Style.RESET_ALL}')
    click.echo(f"  CFLAGS        : {Style.DIM}{' '.join(caps.cflags)}{Style.RESET_ALL}")
    click.echo(f'  Ganho estimado: {Fore.CYAN}{estimate_gain(caps)}{Style.RESET_ALL}')
    if bench:
        click.echo(f'\n{Fore.CYAN}  ⬡ Micro-benchmark (numpy){Style.RESET_ALL}')
        try:
            import numpy as np, time
            N = 10000000
            a = np.random.rand(N)
            b = np.random.rand(N)
            benchmarks = [('add', lambda: np.add(a, b, out=np.empty(N))), ('mul', lambda: np.multiply(a, b, out=np.empty(N))), ('sqrt', lambda: np.sqrt(a, out=np.empty(N)))]
            click.echo(f"\n  {'Operação':<20} {'N':>12}  {'Média':>12}  {'GB/s':>8}")
            click.echo(f"  {'-' * 20} {'-' * 12}  {'-' * 12}  {'-' * 8}")
            for name, fn in benchmarks:
                fn()
                REPS = 10
                t0 = time.perf_counter()
                for _ in range(REPS):
                    fn()
                elapsed_ms = (time.perf_counter() - t0) / REPS * 1000
                bytes_xfr = N * 8 * 2
                gbs = bytes_xfr / (elapsed_ms / 1000) / 1000000000.0
                click.echo(f'  {Fore.WHITE}{name:<20}{Style.RESET_ALL} {N:>12,}  {Fore.GREEN}{elapsed_ms:>10.2f} ms{Style.RESET_ALL}  {Fore.CYAN}{gbs:>6.1f} GB/s{Style.RESET_ALL}')
        except ImportError:
            click.echo(f'  {Fore.YELLOW}NumPy não instalado — benchmark pulado.{Style.RESET_ALL}')
        except Exception as e:
            click.echo(f'  {Fore.RED}Benchmark falhou: {e}{Style.RESET_ALL}')

@click.command('opt')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help='Regenera mesmo arquivos já otimizados.')
@click.option('--stats', is_flag=True, help='Mostra estatísticas de economia por arquivo.')
def vulcan_opt(path, force, stats):
    """Gera camada de Python Otimizado (Tier 2) sem compilar."""
    root = _find_project_root(os.getcwd())
    target = Path(path).resolve() if path else Path(root)
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ [VULCAN OPT] Gerando camada de Python Otimizado (Tier 2)...{Style.RESET_ALL}')
    click.echo(f'{Fore.CYAN}   > Alvo   : {target}{Style.RESET_ALL}')
    click.echo(f'{Fore.CYAN}   > Raiz   : {root}{Style.RESET_ALL}')
    try:
        from doxoade.tools.vulcan.opt_cache import generate_opt_py, find_opt_py, opt_dir
        skip_dirs = frozenset({'.git', 'venv', '.venv', '__pycache__', 'build', 'dist', '.doxoade', 'tests'})
        skip_stems = frozenset({'__init__', '__main__', 'setup', 'forge', 'compiler', 'autopilot', 'bridge', 'advisor', 'environment', 'core', 'pitstop', 'diagnostic', 'guards', 'meta_finder', 'runtime', 'auto_repair', 'artifact_manager', 'compiler_safe', 'opt_cache'})
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
                    click.echo(f'   {Fore.BLUE}↷{Style.RESET_ALL} {(py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name)}  {Style.DIM}(cache){Style.RESET_ALL}')
                    continue
            result = generate_opt_py(Path(root), py_file)
            if result:
                ok_count += 1
                orig_size = py_file.stat().st_size
                saved = max(0, orig_size - result.stat().st_size)
                total_saved += saved
                rel = py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name
                if stats and saved > 0:
                    click.echo(f'   {Fore.GREEN}✔{Style.RESET_ALL} {rel}  {Fore.CYAN}{saved:>6} bytes{Style.RESET_ALL}')
                else:
                    click.echo(f'   {Fore.GREEN}✔{Style.RESET_ALL} {rel}')
            else:
                click.echo(f'   {Fore.YELLOW}↷{Style.RESET_ALL} {(py_file.relative_to(target) if py_file.is_relative_to(target) else py_file.name)}  {Style.DIM}(sem ganho){Style.RESET_ALL}')
        d = opt_dir(Path(root))
        opt_count = len(list(d.glob('opt_*.py')))
        click.echo(f"\n{Fore.CYAN}{'─' * 55}{Style.RESET_ALL}")
        click.echo(f'  {Fore.GREEN}✔ {ok_count} gerado(s){Style.RESET_ALL}  {Fore.BLUE}↷ {skip_count} cache(s){Style.RESET_ALL}  {Fore.CYAN}Total opt_py: {opt_count}{Style.RESET_ALL}')
        if total_saved > 0:
            click.echo(f'  {Fore.GREEN}⚡ {total_saved:,} bytes economizados ({total_saved / 1024:.1f} KiB){Style.RESET_ALL}')
        click.echo(f'\n{Fore.CYAN}[INFO] Tier 2 ativo. Quando binário falhar, o Python otimizado será usado automaticamente.{Style.RESET_ALL}')
        click.echo(f"{Fore.CYAN}{'─' * 55}{Style.RESET_ALL}")
    except Exception as e:
        _print_vulcan_forensic('OPT', e)
        sys.exit(1)

@click.command('opt-bench')
@click.argument('target', default='.')
@click.option('--rounds', '-r', default=3, show_default=True, help='Repetições de benchmark por callable.')
@click.option('--calls', '-c', default=100, show_default=True, help='Chamadas por round.')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--csv', '-o', default=None, metavar='ARQUIVO', help='Exporta resultado em CSV.')
@click.pass_context
def opt_bench(ctx, target, rounds, calls, verbose, csv):
    """Benchmark Tier 3 (Python Puro) vs Tier 2 (Python Otimizado)."""
    from doxoade.tools.vulcan.opt_benchmark import run_opt_bench, render_results
    project_root = Path(os.getcwd()).resolve()
    target_path = (project_root / target).resolve()
    if not target_path.exists():
        click.echo(f'\x1b[31m ■ Alvo não encontrado: {target_path}\x1b[0m')
        ctx.exit(1)
        return
    print(f'\n  \x1b[36m⬡\x1b[0m Alvo   : {target_path}')
    print(f'  \x1b[36m⬡\x1b[0m Raiz   : {project_root}')
    print(f'  \x1b[36m⬡\x1b[0m Rounds : {rounds} × {calls} chamadas por callable')
    print()
    try:
        results = run_opt_bench(target_path, project_root, rounds=rounds, calls=calls)
    except Exception as exc:
        click.echo(f'\x1b[31m ■ Erro ao executar benchmark: {exc}\x1b[0m')
        ctx.exit(1)
        return
    if not results:
        click.echo("\x1b[33m ⚠ Nenhum arquivo .py encontrado no alvo.\x1b[0m\n   Dica: use 'doxoade vulcan opt <alvo>' para gerar Tier 2 primeiro.")
        return
    csv_path = Path(csv).resolve() if csv else None
    render_results(results, verbose=verbose, show_funcs=True, csv_out=csv_path)

@click.command("headroom")
@click.argument("target", default=".", type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, help="Saída em JSON.")
@click.option("--apply-to", type=click.Path(), help="Salva JSON neste arquivo.")
@click.option("--min-score", default=0, type=int, help="Só mostra funções com score >= N.")
@click.option("--methods", is_flag=True, help="Também analisa métodos de classes.")
@click.option("--corpus", is_flag=True, help="Agrega estatísticas de todo o diretório alvo.")
@click.option("--verbose", "-v", is_flag=True, help="Detalhamento por função.")
@click.option("--analyze-calls", is_flag=True, help="Classifica chamadas Python em loop por tipo de refatoração.")
def vulcan_headroom(target, output_json, apply_to, min_score, methods, corpus, verbose, analyze_calls):
    """
    📊 Mede HEADROOM de otimização Cython por função.

    Diferente de 'vulcan inspect' (que mede pureza para nogil),
    'headroom' mede QUANTO CYTHON GANHARIA se a função fosse
    reescrita com tipagem explícita.

    Grades:
      ADAMANTIUM (80-100) → Reescrever vale muito a pena
      STEEL      (40-79)  → Ganho moderado, custo médio
      BRONZE     (15-39)  → Ganho baixo
      SLAG       (0-14)   → Não vale a pena Cython
    """
    from doxoade.tools.vulcan.purity_analyzer import (
        analyze_file, aggregate_corpus,
    )

    root = Path(target).resolve()

    # [FIX] Coleta de arquivos com variável sempre definida
    files: list[Path] = []

    if root.is_file():
        if root.suffix == ".py":
            files = [root]
        else:
            click.echo(f"{Fore.YELLOW}Alvo é arquivo, não diretório: {root}{Style.RESET_ALL}")
            return
    elif root.is_dir():
        skip = {".git", "venv", ".venv", "__pycache__", "build", "dist",
                ".doxoade", "thirdparty", "node_modules", "tests", "lixao",
                "vendor", "external", "old", "recycle"}
        for r, dirs, fs in os.walk(str(root)):
            dirs[:] = [d for d in dirs if d not in skip]
            for f in fs:
                if f.endswith(".py") and not f.startswith("__"):
                    files.append(Path(r) / f)
    else:
        click.echo(f"{Fore.RED}Alvo não encontrado: {root}{Style.RESET_ALL}")
        return

    if not files:
        click.echo(f"{Fore.YELLOW}Nenhum .py encontrado em: {root}{Style.RESET_ALL}")
        return

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN HEADROOM — {len(files)} arquivo(s){Style.RESET_ALL}")
    click.echo(f"  {'─' * 70}")

    # Coleta relatórios de headroom
    reports = []
    for f in files:
        try:
            r = analyze_file(str(f), include_methods=methods)
            if r.functions:
                reports.append(r)
        except Exception as e:
            if verbose:
                click.echo(f"  {Fore.RED}✘ {f.name}: {e}{Style.RESET_ALL}")

    if not reports:
        click.echo(f"  {Fore.YELLOW}Nenhuma função analisada.{Style.RESET_ALL}")
        return

    # [FASE 2] Classificação de calls em loop
    calls_data = None
    if analyze_calls:
        from doxoade.tools.vulcan.purity_analyzer import (
            classify_calls_in_file, aggregate_call_events,
        )
        all_events = []
        for f in files:
            try:
                all_events.extend(classify_calls_in_file(str(f)))
            except Exception as e:
                if verbose:
                    click.echo(f"  {Fore.RED}✘ calls {f.name}: {e}{Style.RESET_ALL}")
        if all_events:
            calls_data = aggregate_call_events(all_events)
            calls_data["raw_events"] = [e.to_dict() for e in all_events]

    # Saída JSON / arquivo
    if output_json or apply_to:
        import json as _json
        payload = {
            "files": [r.to_dict() for r in reports],
            "corpus": aggregate_corpus(reports),
        }
        if calls_data is not None:
            payload["calls_analysis"] = calls_data
        if apply_to:
            Path(apply_to).write_text(
                _json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            click.echo(f"  {Fore.GREEN}✔ JSON salvo em: {apply_to}{Style.RESET_ALL}")
        else:
            click.echo(_json.dumps(payload, indent=2, ensure_ascii=False))
        return

    # Sumário de corpus
    if corpus:
        _render_corpus_summary(reports)
        return

    # Sumário de calls
    if analyze_calls and calls_data:
        _render_calls_summary(calls_data)
        return

    # Renderização por arquivo
    for r in reports:
        display_funcs = [f for f in r.functions if f.score >= min_score]
        if not display_funcs:
            continue

        click.echo(f"\n  {Fore.CYAN}{Path(r.file).name}{Style.RESET_ALL}  "
                   f"({len(display_funcs)}/{r.total_functions} funções, "
                   f"avg={r.avg_score:.1f})")

        for f in display_funcs:
            c = f.color
            rst = Style.RESET_ALL
            click.echo(
                f"    {c}■{rst} L{f.lineno:<4} {f.name:<38} "
                f"{c}{f.score:>3} {f.grade:<10}{rst}"
                f"  ({f.n_nodes:>4} nodes, depth={f.max_loop_depth})"
            )
            if verbose:
                pos = []
                neg = []
                if f.numeric_loops:         pos.append(f"loops×{f.numeric_loops}")
                if f.indexed_access:        pos.append(f"idx×{f.indexed_access}")
                if f.local_arithmetic:      pos.append(f"arith×{f.local_arithmetic}")
                if f.branchless_candidates: pos.append(f"cmov×{f.branchless_candidates}")
                if f.native_kernels_used:   pos.append(f"nexus×{f.native_kernels_used}")
                if f.python_calls_in_loop:  neg.append(f"py-call×{f.python_calls_in_loop}")
                if f.dict_lookups_in_loop:  neg.append(f"dict×{f.dict_lookups_in_loop}")
                if f.string_ops_in_loop:    neg.append(f"str×{f.string_ops_in_loop}")
                if f.io_calls:              neg.append(f"io×{f.io_calls}")
                if f.dynamic_attrs:         neg.append(f"dyn×{f.dynamic_attrs}")
                if f.exceptions_in_loop:    neg.append(f"try×{f.exceptions_in_loop}")
                if pos:
                    click.echo(f"       {Fore.GREEN}+ {', '.join(pos)}{Style.RESET_ALL}")
                if neg:
                    click.echo(f"       {Fore.RED}- {', '.join(neg)}{Style.RESET_ALL}")
                if f.args_annotated:
                    click.echo(f"       {Fore.CYAN}✓ args anotados (confiança alta){Style.RESET_ALL}")

    click.echo()


def _render_corpus_summary(reports):
    """Renderiza o resumo agregado de corpus."""
    from doxoade.tools.vulcan.purity_analyzer import aggregate_corpus

    agg = aggregate_corpus(reports)

    click.echo(f"\n  {Fore.CYAN}{Style.BRIGHT}  ⬡ CORPUS SUMMARY — {agg['total_files']} arquivos, {agg['total_functions']} funções{Style.RESET_ALL}")
    click.echo(f"  {'─' * 70}")

    # Distribuição de grades
    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}Distribuição por grade:{Style.RESET_ALL}")
    grade_colors = {
        "ADAMANTIUM": "\x1b[35m",
        "STEEL": "\x1b[34m",
        "BRONZE": "\x1b[33m",
        "SLAG": "\x1b[31m",
    }
    for grade in ["ADAMANTIUM", "STEEL", "BRONZE", "SLAG"]:
        count = agg["grade_distribution"].get(grade, 0)
        pct = (count / agg["total_functions"] * 100) if agg["total_functions"] else 0
        bar_len = int(pct / 3)
        bar = "█" * bar_len
        c = grade_colors.get(grade, "")
        click.echo(f"    {c}{grade:<12}{Style.RESET_ALL} "
                   f"{c}{bar:<33}{Style.RESET_ALL} "
                   f"{count:>4} ({pct:>5.1f}%)")

    # Histograma de scores
    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}Histograma de scores:{Style.RESET_ALL}")
    for bucket, count in agg["score_histogram"].items():
        bar = "▆" * min(count, 60)
        click.echo(f"    {bucket:<6}  {bar:<60}  {count}")

    # Top fatores positivos
    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}Top fatores POSITIVOS (total no corpus):{Style.RESET_ALL}")
    pos_sorted = sorted(agg["positive_totals"].items(), key=lambda x: x[1], reverse=True)
    for attr, total in pos_sorted[:6]:
        click.echo(f"    {Fore.GREEN}●{Style.RESET_ALL} {attr:<25} {total:>5}")

    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}Top fatores NEGATIVOS (total no corpus):{Style.RESET_ALL}")
    neg_sorted = sorted(agg["negative_totals"].items(), key=lambda x: x[1], reverse=True)
    for attr, total in neg_sorted[:6]:
        click.echo(f"    {Fore.RED}●{Style.RESET_ALL} {attr:<25} {total:>5}")

    # Padrões em ADAMANTIUM
    high = agg["high_score_patterns"]
    if high["count"] > 0:
        click.echo(f"\n  {Fore.MAGENTA}{Style.BRIGHT}PADRÕES EM ADAMANTIUM ({high['count']} funções):{Style.RESET_ALL}")
        click.echo(f"    Fatores positivos mais comuns:")
        for attr, count in sorted(high["positive_factors"].items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = count / high["count"] * 100
            click.echo(f"      {Fore.GREEN}→{Style.RESET_ALL} {attr:<25} {count:>3} ({pct:>5.1f}%)")
        if high["negative_factors"]:
            click.echo(f"    Fatores negativos toleráveis:")
            for attr, count in sorted(high["negative_factors"].items(), key=lambda x: x[1], reverse=True)[:5]:
                pct = count / high["count"] * 100
                click.echo(f"      {Fore.YELLOW}→{Style.RESET_ALL} {attr:<25} {count:>3} ({pct:>5.1f}%)")

    # Padrões em SLAG
    low = agg["low_score_patterns"]
    if low["count"] > 0:
        click.echo(f"\n  {Fore.RED}{Style.BRIGHT}ANTIPADRÕES EM SLAG ({low['count']} funções):{Style.RESET_ALL}")
        for attr, count in sorted(low["negative_factors"].items(), key=lambda x: x[1], reverse=True)[:5]:
            pct = count / low["count"] * 100
            click.echo(f"    {Fore.RED}✘{Style.RESET_ALL} {attr:<25} {count:>3} ({pct:>5.1f}%)")

    click.echo()

def _render_calls_summary(calls_data):
    """Renderiza o sumário de classificação de calls em loop."""
    click.echo(f"\n  {Fore.CYAN}{Style.BRIGHT}  ⬡ CALLS-IN-LOOP ANALYSIS — {calls_data['total_calls']} calls{Style.RESET_ALL}")
    click.echo(f"  {'─' * 70}")

    by_cat = calls_data["by_category"]
    total = calls_data["total_calls"]

    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}Distribuição por categoria de refatoração:{Style.RESET_ALL}")
    category_colors = {
        "ADAMANTIUM_READY": "\x1b[35m",  # não usado, mas reservado
        "HOIST": "\x1b[32m",    # verde — fácil
        "SAFE": "\x1b[32m",     # verde — fácil
        "NATIVE": "\x1b[35m",   # magenta — já é nativo
        "BATCH": "\x1b[36m",    # ciano — médio
        "BUFFER": "\x1b[36m",   # ciano — médio
        "INLINE": "\x1b[33m",   # amarelo — requer análise
        "UNKNOWN": "\x1b[33m",  # amarelo
        "BLOCKED": "\x1b[31m",  # vermelho — não otimizável
    }
    order = ["HOIST", "SAFE", "BATCH", "BUFFER", "INLINE",
             "NATIVE", "UNKNOWN", "BLOCKED"]
    for cat in order:
        count = by_cat.get(cat, 0)
        if count == 0:
            continue
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        c = category_colors.get(cat, "")
        click.echo(f"    {c}{cat:<10}{Style.RESET_ALL} "
                   f"{c}{bar:<50}{Style.RESET_ALL} "
                   f"{count:>4} ({pct:>5.1f}%)")

    # ROI: funções com mais calls refatoráveis
    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}TOP 15 funções por ROI de refatoração:{Style.RESET_ALL}")
    click.echo(f"  {'─' * 70}")
    click.echo(f"  {'FUNÇÃO':<35} {'TOTAL':>6} {'REFAT':>6} {'BLOCK':>6} {'UNKN':>6}")
    click.echo(f"  {'─' * 35} {'─' * 6} {'─' * 6} {'─' * 6} {'─' * 6}")
    for f in calls_data["roi_by_function"][:15]:
        name = f["func_name"][:33]
        click.echo(
            f"  {Fore.CYAN}{name:<35}{Style.RESET_ALL} "
            f"{f['total_calls']:>6} "
            f"{Fore.GREEN}{f['refactorable']:>6}{Style.RESET_ALL} "
            f"{Fore.RED}{f['blocked']:>6}{Style.RESET_ALL} "
            f"{Fore.YELLOW}{f['unknown']:>6}{Style.RESET_ALL}"
        )

    # Top targets por categoria (só os mais úteis)
    click.echo(f"\n  {Fore.WHITE}{Style.BRIGHT}Top targets por categoria:{Style.RESET_ALL}")
    for cat in ["BLOCKED", "HOIST", "BATCH", "INLINE", "UNKNOWN"]:
        targets = calls_data["targets_per_category"].get(cat, {})
        if not targets:
            continue
        c = category_colors.get(cat, "")
        click.echo(f"\n  {c}{cat}{Style.RESET_ALL}:")
        for target, count in list(targets.items())[:5]:
            click.echo(f"    {c}→{Style.RESET_ALL} {target:<30} {count:>4}x")

    click.echo()

