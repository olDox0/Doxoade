# doxoade/doxoade/commands/vulcan_cmd_forge.py
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
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.vulcan.site_packages import site_packages_dirs_for_listing
from .vulcan_cmd import _sigint_handler, _print_vulcan_forensic, _patch_vulcan_forge, _simd_context_or_none, _NullContext, _SIMD_AVAILABLE, _OBJREDUCE_AVAILABLE
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
try:
    from doxoade.tools.vulcan.simd_compiler import SIMDContext, SIMDForge, SIMDEnvironment, estimate_gain
except ImportError:
    pass
try:
    from doxoade.tools.vulcan.object_reduction import reduce_source
except ImportError:
    pass

def _get_accelerator():
    """Tenta carregar o acelerador nativo do Doxoade."""
    try:
        import vulcan_accelerator
        return vulcan_accelerator
    except ImportError:
        return None

def _batch_is_critical_cli(file_paths):
    """Verifica múltiplos arquivos usando o acelerador em C (se disponível)."""
    acc = _get_accelerator()
    if acc:
        return set(acc.fast_scan(file_paths))
    skips = set()
    for p in file_paths:
        if _is_critical_cli_file(p):
            skips.add(p)
    return skips

def _load_registry_for_ignite(root, no_registry=False):
    """Carrega o RegressionRegistry. Retorna None se falhar ou --no-registry."""
    if no_registry:
        return None
    try:
        from doxoade.tools.vulcan.regression_registry import RegressionRegistry
        return RegressionRegistry(root)
    except Exception:
        return None

def _find_venv_python() -> 'str | None':
    """
    Retorna o executável Python do venv ativo no terminal.
    """
    from pathlib import Path as _P
    from doxoade.tools.vulcan.site_packages import _find_active_venv_site_packages
    sp_dirs = _find_active_venv_site_packages()
    if not sp_dirs:
        return None
    sp = _P(sp_dirs[0])
    scripts = sp.parent.parent / 'Scripts' / 'python.exe'
    if scripts.exists():
        return str(scripts)
    bin_py = sp.parent.parent.parent / 'bin' / 'python'
    if bin_py.exists():
        return str(bin_py)
    return None

def _ensure_gcc_in_path() -> 'str | None':
    """
    Garante que gcc está no PATH para compilação com --compiler=mingw32.

    Estratégia:
      1. Varre os.environ["PATH"] entrada por entrada procurando gcc.exe
         (mais confiável que shutil.which em Windows com caminhos com espaços)
      2. Busca w64devkit em caminhos relativos ao doxoade e ao projeto
      3. Tenta MinGW em caminhos padrão

    Retorna o diretório injetado (para log) ou None se já estava no PATH.
    """
    from pathlib import Path as _P
    for entry in os.environ.get('PATH', '').split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry:
            continue
        gcc_candidate = _P(entry) / 'gcc.exe'
        if gcc_candidate.exists():
            return None
    try:
        import doxoade
        doxoade_root = _P(doxoade.__file__).parent.parent
        relative_candidates = [doxoade_root / 'opt' / 'w64devkit' / 'bin', doxoade_root / 'thirdparty' / 'w64devkit' / 'bin', doxoade_root / 'tools' / 'w64devkit' / 'bin']
    except Exception:
        relative_candidates = []
    standard_candidates = [_P('C:\\w64devkit\\bin'), _P('C:\\mingw64\\bin'), _P('C:\\mingw32\\bin'), _P('C:\\MinGW\\bin'), _P('C:\\msys64\\mingw64\\bin'), _P('C:\\msys64\\ucrt64\\bin')]
    for candidate in relative_candidates + standard_candidates:
        if (candidate / 'gcc.exe').exists():
            injected = str(candidate)
            os.environ['PATH'] = injected + os.pathsep + os.environ.get('PATH', '')
            return injected
    return None

def _lib_compile_with_simd(target: str, root: str, simd_ctx: 'SIMDContext | None', run_optimizer: bool=True) -> tuple[bool, str]:
    """
    Ponto de entrada único para compilação de libs.

    Pré-voo:
      1. gcc: varre os.environ["PATH"] manualmente (robusto a caminhos com espaços)
         e injeta w64devkit se necessário.
      2. Python: LibForge pode capturar sys.executable no import. Para garantir
         que setup.py rode com o Python do venv ativo, usamos monkey-patching de
         subprocess — intercepta qualquer chamada que use o Python errado e
         substitui pelo Python correto do venv.

    Sempre usa LibForge — que aplica optimizer + SIMD de forma integrada.
    """
    import subprocess as _subprocess
    import sys as _sys
    gcc_injected = _ensure_gcc_in_path()
    if gcc_injected:
        click.echo(f'{Fore.YELLOW}  ⬡ gcc injetado no PATH: {gcc_injected}{Style.RESET_ALL}')
    venv_python = _find_venv_python()
    _orig_run = _subprocess.run
    _orig_popen = _subprocess.Popen
    _patched = False
    if venv_python and os.path.normcase(venv_python) != os.path.normcase(_sys.executable):
        click.echo(f'{Fore.CYAN}  ⬡ Python do venv: {os.path.basename(os.path.dirname(venv_python))}\\Scripts\\python.exe{Style.RESET_ALL}')
        _bad_python = os.path.normcase(_sys.executable)

        def _fix_args(args):
            """Substitui o Python errado pelo Python do venv em qualquer argv."""
            if isinstance(args, (list, tuple)) and args:
                first = os.path.normcase(str(args[0]))
                if first == _bad_python:
                    return [venv_python] + list(args[1:])
            return args

        def _patched_run(args=None, *a, **kw):
            return _orig_run(_fix_args(args), *a, **kw)

        def _patched_popen(args=None, *a, **kw):
            return _orig_popen(_fix_args(args), *a, **kw)
        _subprocess.run = _patched_run
        _subprocess.Popen = _patched_popen
        _patched = True
    try:
        _patch_vulcan_forge()
        from doxoade.tools.vulcan.lib_forge import LibForge
        forge = LibForge(root)
        return forge.compile_library(target, run_optimizer=run_optimizer, simd_ctx=simd_ctx)
    finally:
        if _patched:
            _subprocess.run = _orig_run
            _subprocess.Popen = _orig_popen

def _resolve_pkg_info(name: str) -> 'tuple[str, Path] | None':
    """
    Localiza o pacote `name` — robusto ao caso onde doxoade roda com Python
    global mas $VIRTUAL_ENV aponta para o venv ativo.

    Estratégia (em ordem):
      1. Filesystem direto via $VIRTUAL_ENV  — sem importlib, sem ambiguidade.
         Testa: <VIRTUAL_ENV>/Lib/site-packages/<name>  (Windows)
                <VIRTUAL_ENV>/lib/pythonX.Y/site-packages/<name>  (Linux/macOS)
         Aceita variantes de nome (hífen ↔ underscore).
      2. importlib.util.find_spec — funciona quando doxoade e o pacote estão
         no mesmo ambiente (ex: instalação com pip no venv).
      3. importlib.metadata alias pip→import  (ex: llama_cpp_python → llama_cpp)
      4. Scan por todos os site-packages de site_packages_dirs_for_listing()
         — fallback final para instalações não-convencionais.

    Efeito colateral: injeta o site-packages encontrado em sys.path para que
    LibForge também enxergue o pacote.
    """
    import importlib.util as _iutil
    from pathlib import Path as _P
    name_variants: list[str] = sorted({name, name.replace('-', '_'), name.replace('_', '-')})

    def _try_dir(pkg_candidate: '_P') -> 'tuple[str, _P] | None':
        """Valida um diretório candidato: precisa ter .py ou .pyd/.so."""
        if not pkg_candidate.is_dir():
            return None
        has_py = any(pkg_candidate.rglob('*.py'))
        has_ext = any(pkg_candidate.rglob('*.pyd')) or any(pkg_candidate.rglob('*.so'))
        if has_py or has_ext:
            return (pkg_candidate.name, pkg_candidate)
        return None

    def _inject(pkg_dir: '_P') -> None:
        """Injeta o site-packages pai em sys.path para que LibForge ache o pacote."""
        sp = str(pkg_dir.parent)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    from doxoade.tools.vulcan.site_packages import _find_active_venv_site_packages
    for sp_str in _find_active_venv_site_packages():
        sp = _P(sp_str)
        for variant in name_variants:
            result = _try_dir(sp / variant)
            if result:
                _inject(result[1])
                return result

    def _spec_to_path(spec) -> '_P | None':
        if spec is None:
            return None
        if spec.submodule_search_locations:
            locs = list(spec.submodule_search_locations)
            return _P(locs[0]) if locs else None
        if spec.origin:
            return _P(spec.origin).parent
        return None
    for variant in name_variants:
        try:
            pkg_dir = _spec_to_path(_iutil.find_spec(variant))
        except (ModuleNotFoundError, ValueError):
            pkg_dir = None
        if pkg_dir and pkg_dir.exists():
            _inject(pkg_dir)
            return (variant, pkg_dir)
    try:
        import importlib.metadata as _meta
        dist_map = _meta.packages_distributions()
        for import_name, dist_names in dist_map.items():
            if any((name.lower().replace('-', '_') == d.lower().replace('-', '_') for d in dist_names)):
                try:
                    pkg_dir = _spec_to_path(_iutil.find_spec(import_name))
                except (ModuleNotFoundError, ValueError):
                    pkg_dir = None
                if pkg_dir and pkg_dir.exists():
                    _inject(pkg_dir)
                    return (import_name, pkg_dir)
    except Exception:
        pass
    for sp_dir in site_packages_dirs_for_listing():
        sp_path = _P(sp_dir)
        if not sp_path.is_dir():
            continue
        for variant in name_variants:
            result = _try_dir(sp_path / variant)
            if result:
                if sp_dir not in sys.path:
                    sys.path.insert(0, sp_dir)
                return result
    return None

def _list_installed_importable() -> list[tuple[str, int, str]]:
    """
    Lista pacotes importáveis via importlib.metadata.packages_distributions.

    Apenas pacotes cujo diretório pai seja um diretório de site-packages
    (nome termina com 'site-packages' ou 'dist-packages') são incluídos.
    Isso evita capturar módulos stdlib ou outros paths espúrios em sys.path
    quando doxoade roda com Python global mas o venv já está em sys.path.
    """
    try:
        import importlib.metadata as _meta
        import importlib.util as _iutil
        known_sp = {p for p in sys.path if p.endswith('site-packages') or p.endswith('dist-packages')}
        pkg_dist = _meta.packages_distributions()
        rows: list[tuple[str, int, str]] = []
        seen: set[str] = set()
        for import_name in sorted(pkg_dist.keys()):
            if import_name in seen or import_name.startswith('_'):
                continue
            try:
                spec = _iutil.find_spec(import_name)
            except (ModuleNotFoundError, ValueError):
                continue
            if spec is None:
                continue
            if spec.submodule_search_locations:
                locs = list(spec.submodule_search_locations)
                pkg_dir = Path(locs[0]) if locs else None
            elif spec.origin:
                pkg_dir = Path(spec.origin).parent
            else:
                continue
            if pkg_dir is None or not pkg_dir.is_dir():
                continue
            parent_str = str(pkg_dir.parent)
            if parent_str not in known_sp:
                continue
            py_count = len(list(pkg_dir.rglob('*.py')))
            rows.append((import_name, py_count, str(pkg_dir)))
            seen.add(import_name)
        return rows
    except Exception:
        return []

def _run_hybrid_with_optimizer(target, root, force, registry=None):
    """
    Compilação híbrida com optimizer integrado e suporte ao RegressionRegistry.

    Com registry:
      • Funções 'excluded'         → removidas antes de compilar
      • Funções 'retry_aggressive' → compiladas com header Cython agressivo
      • Após compilação bem-sucedida → PerformanceWatcher mede e atualiza registry
    """
    from doxoade.tools.vulcan.hybrid_forge import HybridIgnite
    from doxoade.tools.vulcan.hybrid_optimizer import optimize_pyx_file
    _patch_vulcan_forge()
    ignite = HybridIgnite(root)
    files = HybridIgnite._collect_files(Path(target).resolve())
    opt_summary = []
    obj_reduce_summary = []
    total_excluded = 0
    total_aggressive = 0
    total_regressions = 0
    total_promoted = 0
    for py_file in files:
        scan = ignite._scanner.scan(str(py_file))
        if not scan.candidates:
            continue
        aggressive_funcs = frozenset()
        if registry is not None:
            excluded_names = registry.excluded_funcs_for_file(str(py_file))
            aggressive_funcs = registry.aggressive_funcs_for_file(str(py_file))
            before = len(scan.candidates)
            scan.candidates = [c for c in scan.candidates if c.name not in excluded_names]
            excl_n = before - len(scan.candidates)
            total_excluded += excl_n
            agg_active = aggressive_funcs & {c.name for c in scan.candidates}
            total_aggressive += len(agg_active)
            if excl_n:
                click.echo(f'   {Fore.RED}↷ {py_file.name}: {excl_n} função(ões) excluída(s) pelo registry{Style.RESET_ALL}')
            if agg_active:
                click.echo(f'   {Fore.MAGENTA}⬡ {py_file.name}: retry-agressivo → {', '.join(sorted(agg_active))}{Style.RESET_ALL}')
        if not scan.candidates:
            continue
        fname = py_file.name
        click.echo(f'   {Fore.YELLOW}[HYBRID]{Style.RESET_ALL} {fname} — {len(scan.candidates)} candidato(s):')
        for f in scan.candidates:
            tag = f'{Fore.MAGENTA}[AGG]{Style.RESET_ALL}' if f.name in aggressive_funcs else '     '
            click.echo(f'     {tag} • {f.name:<35} score={f.score:>2}  ({', '.join(f.reasons[:3])})')
        pyx_path = ignite._forge.generate(scan, aggressive_funcs=aggressive_funcs)
        if not pyx_path:
            click.echo(f'   {Fore.RED}✘{Style.RESET_ALL} {fname}: forge falhou')
            continue
        if _OBJREDUCE_AVAILABLE and pyx_path.exists():
            try:
                source = pyx_path.read_text(encoding='utf-8')
                red_result = reduce_source(source, pyx_path, level=1, is_pyx=False)
                if red_result.has_changes:
                    pyx_path.write_text(red_result.transformed, encoding='utf-8')
                    obj_reduce_summary.append(red_result)
                    click.echo(f'   {Fore.CYAN}  ⬡ obj-reduce{Style.RESET_ALL}: {len(red_result.changes)} transformação(ões), ~{red_result.allocs_removed} alloc(s) eliminada(s)')
            except Exception:
                pass
        try:
            pyx_path, opt_report = optimize_pyx_file(pyx_path)
            if opt_report.transformations and (not opt_report.transformations[0].startswith('revertido')):
                opt_summary.append(opt_report)
                n_cdefs = len(opt_report.transformations)
                click.echo(f'   {Fore.MAGENTA}  ⬡ optimizer{Style.RESET_ALL}: {n_cdefs} cdef(s) injetados → {Fore.GREEN}{opt_report.estimated_gain}{Style.RESET_ALL}')
        except Exception:
            pass
        module_name = pyx_path.stem
        ok, err = ignite._compile(module_name)
        if ok:
            click.echo(f'   {Fore.GREEN}✔{Style.RESET_ALL} {fname} → {module_name} ({len(scan.candidates)} funcs, score={scan.total_score})')
            if registry is not None:
                try:
                    from doxoade.tools.vulcan.performance_watcher import PerformanceWatcher
                    watcher = PerformanceWatcher(project_root=root, foundry=ignite.foundry, bin_dir=ignite.bin_dir)
                    wr = watcher.evaluate(py_file, module_name, update_registry=True)
                    wr.render_cli()
                    total_regressions += len(wr.regressions)
                    total_promoted += wr.registry_summary.get('promoted', 0)
                except Exception:
                    pass
        else:
            click.echo(f'   {Fore.RED}✘{Style.RESET_ALL} {fname} falhou na compilação:')
            click.echo(f'{Fore.YELLOW}{str(err)}{Style.RESET_ALL}')
    if registry is not None and (total_excluded or total_aggressive or total_regressions):
        click.echo(f'\n{Fore.MAGENTA}  ⬡ REGRESSION REGISTRY — resumo desta compilação:{Style.RESET_ALL}')
        if total_excluded:
            click.echo(f'    {Fore.RED}Funções excluídas (permanente)  : {total_excluded}{Style.RESET_ALL}')
        if total_aggressive:
            click.echo(f'    {Fore.YELLOW}Funções retry-agressivo         : {total_aggressive}{Style.RESET_ALL}')
        if total_regressions:
            click.echo(f'    {Fore.RED}Novas regressões detectadas     : {total_regressions}{Style.RESET_ALL}')
        if total_promoted:
            click.echo(f'    {Fore.GREEN}Funções promovidas (recuperadas): {total_promoted}{Style.RESET_ALL}')
        click.echo(f'    {Fore.CYAN}Gerencie com: doxoade vulcan regression{Style.RESET_ALL}')
    if opt_summary:
        total_cdefs = sum((len(r.transformations) for r in opt_summary))
        click.echo(f'\n{Fore.MAGENTA}  ⬡ OPTIMIZER: {total_cdefs} cdef(s) em {len(opt_summary)} módulo(s){Style.RESET_ALL}')
        for r in opt_summary:
            click.echo(f'    {r.module_name:<30} → {Fore.GREEN}{r.estimated_gain}{Style.RESET_ALL}')
    if obj_reduce_summary:
        total_allocs = sum((r.allocs_removed for r in obj_reduce_summary))
        total_changes = sum((len(r.changes) for r in obj_reduce_summary))
        click.echo(f'\n{Fore.CYAN}  ⬡ OBJ-REDUCE: {total_changes} transformação(ões) em {len(obj_reduce_summary)} módulo(s), ~{total_allocs} alloc(s) eliminada(s){Style.RESET_ALL}')

def _is_critical_cli_file(file_path):
    """
    Verifica se o arquivo contém decoradores Click ou tags de proteção.
    Arquivos compilados com Click perdem metadados de contexto (make_context).
    """
    try:
        if not os.path.exists(file_path):
            return False
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(8192)
            return '[VULCAN-SKIP]' in content or '@click.' in content or 'import click' in content
    except Exception:
        return False

@click.command('ignite')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--force', is_flag=True, help='Força a re-compilação de todos os alvos.')
@click.option('--jobs', type=int, default=None, help='Número de workers (sobrescreve auto).')
@click.option('--no-pitstop', is_flag=True, help='Usa compilação legada (1 processo por módulo).')
@click.option('--streaming', is_flag=True, help='Forge e compilação em paralelo (melhor para > 15 módulos).')
@click.option('--hybrid', is_flag=True, help='Compilação seletiva por função (HybridForge).')
@click.option('--scan-only', is_flag=True, help='Com --hybrid: mostra candidatos sem compilar.')
@click.option('--simd', is_flag=True, help='Ativa otimizações SIMD (AVX/SSE) na compilação.')
@click.option('--simd-level', default='auto', type=click.Choice(['auto', 'native', 'sse2', 'avx', 'avx2', 'avx512f']), show_default=True, help='Nível SIMD máximo (padrão: auto-detecta).')
@click.pass_context
def ignite(ctx, path, force, jobs, no_pitstop, streaming, hybrid, scan_only, simd, simd_level):
    """Transforma código Python em binários de alta velocidade.

    Modos:
      padrão   → PitStop Engine
      --hybrid → HybridForge (seletivo por função)
      --simd   → injeta flags AVX/SSE2/NEON na compilação

    Exemplos::

    \x08
      doxoade vulcan ignite --simd
      doxoade vulcan ignite --hybrid --simd --simd-level avx2
    """
    signal.signal(signal.SIGINT, _sigint_handler)
    root = _find_project_root(os.getcwd())
    target = path or root
    simd_ctx = _simd_context_or_none(simd, simd_level)
    if simd_ctx and _SIMD_AVAILABLE:
        eff = simd_ctx.effective_caps()
        click.echo(f'\n  {Fore.MAGENTA}⬡ SIMD:{Style.RESET_ALL} {Fore.GREEN}{eff.best.upper()}{Style.RESET_ALL}  {Fore.CYAN}est. {estimate_gain(eff)}{Style.RESET_ALL}')
        click.echo(f'  {Fore.MAGENTA}  flags:{Style.RESET_ALL} {Style.DIM}{' '.join(eff.cflags)}{Style.RESET_ALL}\n')
    elif simd and (not _SIMD_AVAILABLE):
        click.echo(f'  {Fore.YELLOW}⚠ --simd ignorado: módulos SIMD não disponíveis.{Style.RESET_ALL}')
    if hybrid:
        _patch_vulcan_forge()
        click.echo(f'{Fore.YELLOW}{Style.BRIGHT}⬡ [VULCAN-HYBRID] ...{Style.RESET_ALL}')
        registry = None
        try:
            from doxoade.tools.vulcan.regression_registry import RegressionRegistry
            registry = RegressionRegistry(root)
            r = registry.report()
            if r['total']:
                click.echo(f'{Fore.MAGENTA}   > Registry: {Fore.RED}{r['excluded']} excluída(s){Style.RESET_ALL}  {Fore.YELLOW}{r['retry_aggressive']} retry-agressivo{Style.RESET_ALL}')
        except Exception:
            registry = None
        if scan_only:
            click.echo(f'{Fore.CYAN}   > Modo: SCAN ONLY (sem compilação){Style.RESET_ALL}')
            _run_hybrid_with_optimizer(target, root, force, registry=registry)
            return
        click.echo(f'{Fore.CYAN}   > Alvo : {target}{Style.RESET_ALL}')
        click.echo(f'{Fore.CYAN}   > Modo : HÍBRIDO{Style.RESET_ALL}')
        _env_ctx = SIMDEnvironment(simd_ctx) if simd_ctx else _NullContext()
        with ExecutionLogger('vulcan_hybrid', root, ctx.params) as _:
            try:
                with _env_ctx:
                    _run_hybrid_with_optimizer(target=target, root=root, force=force, registry=registry)
            except KeyboardInterrupt:
                _sigint_handler(None, None)
            except Exception as e:
                _print_vulcan_forensic('HYBRID', e)
                sys.exit(1)
        return
    with ExecutionLogger('vulcan_ignite', root, ctx.params) as _:
        click.echo(f'{Fore.YELLOW}{Style.BRIGHT}🔥 [VULCAN-IGNITION] ...{Style.RESET_ALL}')
        from doxoade.tools.vulcan.diagnostic import VulcanDiagnostic
        diag = VulcanDiagnostic(root)
        ok, _ = diag.check_environment()
        if not ok:
            diag.render_report()
            sys.exit(1)
        from doxoade.tools.vulcan.autopilot import VulcanAutopilot
        _patch_vulcan_forge()
        autopilot = VulcanAutopilot(root)
        candidates, mode = ([], 'AUTOMÁTICO')
        if path:
            abs_path = os.path.abspath(path)
            if os.path.isfile(abs_path):
                mode = f'MANUAL (arquivo: {os.path.basename(abs_path)})'
                candidates.append({'file': abs_path})
            elif os.path.isdir(abs_path):
                mode = f'MANUAL (diretório: {os.path.basename(abs_path)})'
                from doxoade.dnm import DNM
                dnm = DNM(abs_path)
                py_files = [str(f) for f in dnm.scan(extensions=['py'])]
                critical_files = _batch_is_critical_cli(py_files)
                candidates = []
                cli_skips = 0
                internal_skips = 0
                for f in py_files:
                    if '.doxoade' in f or '.dnm' in f:
                        internal_skips += 1
                        continue
                    if f in critical_files:
                        cli_skips += 1
                        continue
                    candidates.append({'file': f})
                if internal_skips > 0:
                    click.echo(f'   {Fore.CYAN}↷ {internal_skips} arquivo(s) internos (.doxoade) ignorados.{Style.RESET_ALL}')
                if cli_skips > 0:
                    click.echo(f'   {Fore.YELLOW}↷ {cli_skips} arquivo(s) CLI/Skip ignorados para preservar introspecção.{Style.RESET_ALL}')
        engine_label = f'{Fore.YELLOW}LEGADO{Style.RESET_ALL}' if no_pitstop else f'{Fore.GREEN}PITSTOP{Style.RESET_ALL}' + (f' {Fore.CYAN}+streaming{Style.RESET_ALL}' if streaming else '')
        click.echo(f'{Fore.CYAN}   > Modo  : {mode}{Style.RESET_ALL}')
        click.echo(f'{Fore.CYAN}   > Engine: {engine_label}{Style.RESET_ALL}')
        _env_ctx = SIMDEnvironment(simd_ctx) if simd_ctx else _NullContext()
        try:
            with _env_ctx:
                autopilot.scan_and_optimize(candidates=candidates, force_recompile=force, max_workers=jobs, use_pitstop=not no_pitstop, streaming=streaming)
            click.echo(f'\n{Fore.GREEN}{Style.BRIGHT}✔ [VULCAN] Forja concluída.{Style.RESET_ALL}')
            if simd_ctx:
                click.echo(f'   {Fore.MAGENTA}⬡ SIMD {simd_ctx.effective_caps().best.upper()} aplicado.{Style.RESET_ALL}')
        except KeyboardInterrupt:
            _sigint_handler(None, None)
        except Exception as e:
            _print_vulcan_forensic('IGNITE', e)
            sys.exit(1)

@click.command('regression')
@click.option('--reset', is_flag=True, help='Remove funções excluídas (nova tentativa).')
@click.option('--reset-all', is_flag=True, help='Limpa todo o registry.')
@click.option('--purge-missing', is_flag=True, help='Remove arquivos que não existem mais.')
@click.option('--json', 'output_json', is_flag=True, help='Saída em JSON.')
def vulcan_regression(reset, reset_all, purge_missing, output_json):
    """Gerencia o RegressionRegistry — histórico de regressões de performance."""
    root = _find_project_root(os.getcwd())
    try:
        from doxoade.tools.vulcan.regression_registry import RegressionRegistry
        registry = RegressionRegistry(root)
        if reset_all:
            n = registry.clear_all()
            click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} Registry limpo ({n} entrada(s)).')
            return
        if reset:
            n = registry.clear_excluded()
            click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} {n} função(ões) excluída(s) removida(s).\n{Fore.CYAN}[INFO] Serão recompiladas no próximo ignite.{Style.RESET_ALL}')
            return
        if purge_missing:
            n = registry.purge_missing_files()
            click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} {n} entrada(s) de arquivos inexistentes removidas.')
            return
        if output_json:
            import json as _json
            click.echo(_json.dumps(registry.report(), indent=2, ensure_ascii=False))
        else:
            registry.render_cli()
    except Exception as e:
        _print_vulcan_forensic('REGRESSION', e)
        sys.exit(1)

@click.command('lib')
@click.option('--analyze', is_flag=True, help="Lista dependências 'quentes' candidatas à compilação.")
@click.option('--target', help='Nome da biblioteca instalada no venv a compilar.')
@click.option('--auto', is_flag=True, help='Compila automaticamente os melhores candidatos.')
@click.option('--list-installed', is_flag=True, help='Lista libs instaladas no site-packages.')
@click.option('--optimize', is_flag=True, help='Apenas otimiza os fontes (inspeciona sem compilar). Exige --target.')
@click.option('--no-optimize', is_flag=True, help='Pula o LibOptimizer antes de compilar (debug/benchmarking).')
@click.option('--keep-temp', is_flag=True, help='Mantém cópia temporária para inspeção/debug.')
@click.option('--simd', is_flag=True, help='Ativa otimizações SIMD (AVX/SSE) na compilação.')
@click.option('--simd-level', default='auto', type=click.Choice(['auto', 'native', 'sse2', 'avx', 'avx2', 'avx512f']), show_default=True, help='Nível SIMD máximo (padrão: auto-detecta).')
@click.option('--probe', help='Diagnóstico: mostra como o pacote é (ou não é) encontrado.')
@click.pass_context
def vulcan_lib(ctx, analyze, target, auto, list_installed, optimize, no_optimize, keep_temp, simd, simd_level, probe):
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
        if probe:
            import importlib.util as _iutil
            pkg = probe
            click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN LIB PROBE: '{pkg}'{Style.RESET_ALL}")
            click.echo(f'  {'─' * 55}')
            click.echo(f'  sys.executable : {sys.executable}')
            venv_val = os.environ.get('VIRTUAL_ENV', '<não definido>')
            click.echo(f'  VIRTUAL_ENV    : {venv_val}')
            from doxoade.tools.vulcan.site_packages import _find_active_venv_site_packages
            active_sp = _find_active_venv_site_packages()
            click.echo(f'  Venv ativo SP  : {active_sp or '<não encontrado>'}')
            for sp_str in active_sp:
                from pathlib import Path as _P
                pkg_dir = _P(sp_str) / pkg
                click.echo(f'  Pkg dir        : {pkg_dir}  exists={pkg_dir.exists()}')
                if pkg_dir.exists():
                    py_files = list(pkg_dir.rglob('*.py'))
                    pyd_files = list(pkg_dir.rglob('*.pyd'))
                    so_files = list(pkg_dir.rglob('*.so'))
                    click.echo(f'    .py files    : {len(py_files)}')
                    click.echo(f'    .pyd files   : {len(pyd_files)}')
                    click.echo(f'    .so files    : {len(so_files)}')
                    click.echo(f'    Top entries  :')
                    for e in sorted(pkg_dir.iterdir())[:10]:
                        click.echo(f'      {e.name}')
            try:
                spec = _iutil.find_spec(pkg)
                click.echo(f'  find_spec      : {spec}')
            except Exception as e:
                click.echo(f'  find_spec      : ERRO — {e}')
            result = _resolve_pkg_info(pkg)
            if result:
                click.echo(f'  {Fore.GREEN}_resolve result : {result[0]}  →  {result[1]}{Style.RESET_ALL}')
            else:
                click.echo(f'  {Fore.RED}_resolve result : None{Style.RESET_ALL}')
            gcc_found = None
            for _entry in os.environ.get('PATH', '').split(os.pathsep):
                _entry = _entry.strip().strip('"')
                if _entry and (Path(_entry) / 'gcc.exe').exists():
                    gcc_found = str(Path(_entry) / 'gcc.exe')
                    break
            click.echo(f'  gcc in PATH    : {gcc_found or Fore.RED + 'NÃO ENCONTRADO' + Style.RESET_ALL}')
            gcc_inject = _ensure_gcc_in_path()
            if gcc_inject:
                click.echo(f'  {Fore.YELLOW}gcc encontrado em: {gcc_inject}{Style.RESET_ALL}')
            venv_py = _find_venv_python()
            click.echo(f'  Venv Python    : {venv_py or Fore.RED + 'não encontrado' + Style.RESET_ALL}')
            click.echo()
            return
        if list_installed:
            click.echo(f'{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Libs instaladas no site-packages ---{Style.RESET_ALL}')
            rows: list[tuple[str, int, str]] = []
            seen_names: set[str] = set()
            from doxoade.tools.vulcan.site_packages import _find_active_venv_site_packages
            venv_sp_dirs = _find_active_venv_site_packages()
            scan_dirs = venv_sp_dirs or site_packages_dirs_for_listing()
            for sp in scan_dirs:
                sp_path = Path(sp)
                if not sp_path.is_dir():
                    continue
                if not (sp_path.name == 'site-packages' or sp_path.name == 'dist-packages'):
                    continue
                for item in sorted(sp_path.iterdir()):
                    if not item.is_dir():
                        continue
                    if item.name.endswith(('.dist-info', '.egg-info', '__pycache__')):
                        continue
                    py_files = list(item.rglob('*.py'))
                    if not py_files:
                        ext_files = list(item.rglob('*.pyd')) + list(item.rglob('*.so'))
                        if not ext_files:
                            continue
                    rows.append((item.name, len(py_files), str(item)))
                    seen_names.add(item.name)
            for import_name, py_count, pkg_path_str in _list_installed_importable():
                if import_name not in seen_names:
                    rows.append((import_name, py_count, pkg_path_str))
                    seen_names.add(import_name)
            if not rows:
                click.echo(f'{Fore.YELLOW}Nenhum pacote encontrado.{Style.RESET_ALL}')
                return
            rows.sort(key=lambda r: r[1], reverse=True)
            click.echo(f'  {'BIBLIOTECA':<19} {'ARQUIVOS .PY':>12}')
            click.echo(f'  {'-' * 19} {'-' * 12}')
            for name_r, count, _ in rows[:100]:
                click.echo(f'  {Fore.WHITE}{name_r:<19}{Style.RESET_ALL} {Fore.CYAN}{count:>5}{Style.RESET_ALL}')
            if len(rows) > 100:
                click.echo(f'  {Style.DIM}... e mais {len(rows) - 25} pacote(s){Style.RESET_ALL}')
            return
        if analyze:
            click.echo(f'{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Analisando telemetria de dependências ---{Style.RESET_ALL}')
            from doxoade.tools.vulcan.advisor import VulcanAdvisor
            advisor = VulcanAdvisor(root)
            hot_deps = advisor.get_hot_dependencies()
            if not hot_deps:
                click.echo(f"{Fore.YELLOW}Nenhuma dependência 'quente' encontrada na telemetria recente.{Style.RESET_ALL}")
                return
            click.echo(f'  {'BIBLIOTECA':<28} {'HITS':>8}  COMANDO')
            click.echo(f'  {'-' * 28} {'-' * 8}  {'-' * 35}')
            for dep, hits in list(hot_deps.items())[:20]:
                click.echo(f'  {Fore.WHITE}{dep:<28}{Style.RESET_ALL} {Fore.RED}{hits:>8}{Style.RESET_ALL}  {Style.DIM}doxoade vulcan lib --target {dep}{Style.RESET_ALL}')
            return
        if optimize and (not target):
            click.echo(f'{Fore.YELLOW}[ERRO] --optimize exige --target.{Style.RESET_ALL}\n{Fore.CYAN}Exemplo:{Style.RESET_ALL}\n  doxoade vulcan lib --optimize --target click\n\n{Fore.CYAN}Dica:{Style.RESET_ALL} use --list-installed para ver libs disponíveis.')
            return
        if optimize and target:
            click.echo(f'{Fore.CYAN}   > Modo: OPTIMIZE-ONLY (nenhuma compilação será executada){Style.RESET_ALL}')
            click.echo(f'{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Otimizando (apenas) a biblioteca: {target} ---{Style.RESET_ALL}')
            import importlib.util
            import shutil
            import tempfile
            try:
                spec = importlib.util.find_spec(target)
                if spec is None:
                    click.echo(f"{Fore.RED}[FALHA] Não foi possível localizar '{target}' no venv.{Style.RESET_ALL}")
                    click.echo(f'{Fore.YELLOW}[DICA] Verifique o nome ou use --list-installed.{Style.RESET_ALL}')
                    return
                if spec.submodule_search_locations:
                    pkg_path = Path(next(iter(spec.submodule_search_locations)))
                else:
                    if not spec.origin:
                        click.echo(f"{Fore.RED}[FALHA] Spec não contém origem para '{target}'.{Style.RESET_ALL}")
                        return
                    pkg_path = Path(spec.origin).parent
                if not pkg_path.exists():
                    click.echo(f'{Fore.RED}[FALHA] Caminho da lib não existe: {pkg_path}{Style.RESET_ALL}')
                    return
                tmp_ctx = tempfile.TemporaryDirectory(prefix=f'vulcan_opt_{target}_')
                tmp = tmp_ctx.name
                dest = Path(tmp) / pkg_path.name
                try:
                    shutil.copytree(pkg_path, dest, dirs_exist_ok=False)
                    from doxoade.tools.vulcan.lib_optimizer import LibOptimizer
                    optimizer = LibOptimizer()
                    stats = optimizer.optimize_directory(dest)
                    try:
                        logger.write_artifact(name=f'vulcan_lib_opt_{target}.json', data=stats)
                    except Exception:
                        pass
                    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Resumo da Otimização ---{Style.RESET_ALL}')
                    click.echo(f'  Arquivos processados : {stats.get('files_processed', 0)}')
                    click.echo(f'  Arquivos otimizados  : {stats.get('files_optimized', 0)}')
                    click.echo(f'  Arquivos ignorados   : {stats.get('files_skipped', 0)}')
                    click.echo(f'  Docstrings removidas : {stats.get('docstrings_removed', 0)}')
                    click.echo(f'  Dead branches        : {stats.get('dead_branches', 0)}')
                    click.echo(f'  Imports removidos    : {stats.get('imports_removed', 0)}')
                    click.echo(f'  Locals minificados   : {stats.get('locals_minified', 0)}')
                    bytes_saved = stats.get('bytes_saved', 0)
                    click.echo(f'  Bytes economizados   : {bytes_saved} ({bytes_saved / 1024:.1f} KiB)')
                    click.echo(f'\n{Fore.GREEN}[SUCESSO] Otimização concluída na cópia: {dest}{Style.RESET_ALL}')
                    click.echo(f'{Fore.CYAN}[DICA] Para compilar após otimizar: doxoade vulcan lib --target {target}{Style.RESET_ALL}')
                finally:
                    if keep_temp:
                        click.echo(f'{Fore.YELLOW}[INFO] --keep-temp ativo. Diretório preservado:{Style.RESET_ALL}\n  {Path(tmp)}')
                    else:
                        try:
                            tmp_ctx.cleanup()
                        except Exception:
                            pass
                return
            except Exception as exc:
                click.echo(f'{Fore.RED}[FALHA] Erro durante otimização: {exc}{Style.RESET_ALL}')
                return
        if target:
            run_optimizer = not no_optimize
            simd_ctx = _simd_context_or_none(simd, simd_level)
            pkg_info = _resolve_pkg_info(target)
            if pkg_info is None:
                click.echo(f"{Fore.RED}[FALHA] '{target}' não está instalado no venv ativo.\n{Style.RESET_ALL}{Fore.YELLOW}  Python : {sys.executable}\n  Use --list-installed para ver pacotes disponíveis.{Style.RESET_ALL}")
                return
            resolved_name, pkg_dir = pkg_info
            if resolved_name != target:
                click.echo(f"{Fore.CYAN}  ⬡ Resolvido: '{target}' → importável como '{resolved_name}' ({pkg_dir}){Style.RESET_ALL}")
                target = resolved_name
            mode_parts = []
            if run_optimizer:
                mode_parts.append('OPT')
            if simd_ctx and _SIMD_AVAILABLE:
                mode_parts.append(f'SIMD/{simd_level.upper()}')
            mode_label = ' + '.join(mode_parts) if mode_parts else 'PADRÃO'
            click.echo(f'{Fore.CYAN}{Style.BRIGHT}--- [VULCAN LIB] Forjando: {target}  [{mode_label}] ---{Style.RESET_ALL}')
            click.echo(f'{Fore.CYAN}   > Modo: VENV LOCAL (sem download — cópia isolada dos fontes){Style.RESET_ALL}')
            if not run_optimizer:
                click.echo(f'{Fore.YELLOW}   > --no-optimize: LibOptimizer desabilitado.{Style.RESET_ALL}')
            if simd_ctx and _SIMD_AVAILABLE:
                eff = simd_ctx.effective_caps()
                click.echo(f'  {Fore.MAGENTA}⬡ SIMD:{Style.RESET_ALL} {eff.best.upper()} — {estimate_gain(eff)}')
            elif simd and (not _SIMD_AVAILABLE):
                click.echo(f'  {Fore.YELLOW}⚠ --simd ignorado: módulos SIMD não disponíveis.{Style.RESET_ALL}')
            success, result_message = _lib_compile_with_simd(target, root, simd_ctx, run_optimizer=run_optimizer)
            if success:
                click.echo(f'{Fore.GREEN}{Style.BRIGHT}\n[SUCESSO] {result_message}{Style.RESET_ALL}')
                click.echo(f"{Fore.CYAN}[DICA] Use 'doxoade vulcan status' para ver os binários ativos.{Style.RESET_ALL}")
            else:
                click.echo(f'{Fore.RED}{Style.BRIGHT}\n[FALHA] {result_message}{Style.RESET_ALL}')
                click.echo(f'{Fore.YELLOW}[DICA] Use --list-installed para ver libs disponíveis no venv.{Style.RESET_ALL}')
            return
        elif auto:
            click.echo(f'{Fore.YELLOW}[INFO] --auto: compila as top-3 libs da telemetria automaticamente.{Style.RESET_ALL}')
            from doxoade.tools.vulcan.advisor import VulcanAdvisor
            from doxoade.tools.vulcan.lib_forge import LibForge
            _patch_vulcan_forge()
            advisor = VulcanAdvisor(root)
            hot_deps = advisor.get_hot_dependencies()
            if not hot_deps:
                click.echo(f'{Fore.YELLOW}Sem dados de telemetria para --auto.{Style.RESET_ALL}')
                return
            forge = LibForge(root)
            for lib in list(hot_deps.keys())[:3]:
                click.echo(f'\n{Fore.CYAN}  → Compilando: {lib}{Style.RESET_ALL}')
                success, msg = forge.compile_library(lib)
                if success:
                    click.echo(f'{Fore.GREEN}  ✔ {msg}{Style.RESET_ALL}')
                else:
                    click.echo(f'{Fore.YELLOW}  ↷ {msg}{Style.RESET_ALL}')
            return
        else:
            click.echo(ctx.get_help())

@click.command('benchmark')
@click.argument('path', required=False, type=click.Path(exists=True))
@click.option('--runs', default=10, type=int, show_default=True)
@click.option('--json', 'output_json', is_flag=True)
@click.option('--min-speedup', default=1.1, type=float, show_default=True)
@click.option('--save', is_flag=True)
@click.option('--learn/--no-learn', default=True)
def vulcan_benchmark(path, runs, output_json, min_speedup, save, learn):
    """Mede speedup real Python vs Cython das funções compiladas."""
    root = _find_project_root(os.getcwd())
    target = path or root
    if not output_json:
        click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⚡ VULCAN BENCHMARK — {runs} execuções por função{Style.RESET_ALL}')
        click.echo(f'{Fore.CYAN}  Alvo: {target}{Style.RESET_ALL}\n')
    try:
        from doxoade.tools.vulcan.hybrid_benchmark import run_benchmark
        results = run_benchmark(project_root=root, target=target, runs=runs, output_json=output_json, min_speedup=min_speedup)
        if save and results:
            import json as _json, dataclasses
            bench_path = Path(_find_project_root(os.getcwd())) / '.doxoade' / 'vulcan' / 'bench_results.json'
            bench_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = _json.loads(_json.dumps(results, default=lambda o: dataclasses.asdict(o) if dataclasses.is_dataclass(o) else str(o)))
            bench_path.write_text(_json.dumps(serializable, indent=2), encoding='utf-8')
            click.echo(f'\n{Fore.GREEN}  ✔ Resultados salvos em {bench_path}{Style.RESET_ALL}')
        if learn and results:
            from doxoade.tools.vulcan.regression_registry import RegressionRegistry
            registry = RegressionRegistry(root)
            summary = registry.update_from_benchmark(results, min_speedup=min_speedup)
            click.echo(f'\n{Fore.MAGENTA}{Style.BRIGHT}  ⬡ REGRESSION REGISTRY atualizado{Style.RESET_ALL}')
            click.echo(f'  {Fore.RED}Excluídas      : {summary['excluded']}{Style.RESET_ALL}  {Fore.YELLOW}Retry-Agressivo: {summary['retry_aggressive']}{Style.RESET_ALL}  {Fore.GREEN}Promovidas     : {summary['promoted']}{Style.RESET_ALL}')
            if summary['excluded']:
                click.echo(f'\n  {Fore.RED}⚠ {summary['excluded']} função(ões) permanentemente excluída(s).{Style.RESET_ALL}\n  {Fore.CYAN}  Para resetar: doxoade vulcan regression --reset{Style.RESET_ALL}')
            if summary['retry_aggressive']:
                click.echo(f'\n  {Fore.YELLOW}⬡ {summary['retry_aggressive']} função(ões) marcadas para retry-agressivo.{Style.RESET_ALL}')
    except Exception as e:
        _print_vulcan_forensic('BENCHMARK', e)
        sys.exit(1)

@click.command('pitstop')
@click.option('--clear-cache', is_flag=True, help='Apaga o WarmupCache (força recompilação total).')
def vulcan_pitstop(clear_cache):
    """Informações e controle do PitStop Engine (cache + warm-up)."""
    root = _find_project_root(os.getcwd())
    from doxoade.tools.vulcan.environment import VulcanEnvironment
    from doxoade.tools.vulcan.pitstop import PitstopEngine
    env = VulcanEnvironment(root)
    engine = PitstopEngine(env)
    info = engine.warmup_info()
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  PITSTOP ENGINE INFO:{Style.RESET_ALL}')
    click.echo(f'   Python    : {info['python_exe']}')
    click.echo(f'   Foundry   : {info['foundry']}')
    click.echo(f'   Bin       : {info['bin_dir']}')
    click.echo(f'   Workers   : {info['workers']} processos GCC paralelos')
    click.echo(f'   Estratégia: {info['parallel_strategy']}')
    click.echo(f'   Batch size: {info['batch_size']}')
    click.echo(f'   Cache     : {info['cache']['entries']} entrada(s) em {info['cache']['path']}')
    if info['build_env_keys']:
        click.echo(f'   Env extras: {', '.join(info['build_env_keys'])}')
    if clear_cache:
        cache_path = Path(info['cache']['path'])
        if cache_path.exists():
            cache_path.unlink()
            click.echo(f'\n{Fore.GREEN}[OK]{Fore.RESET} WarmupCache apagado. Próximo ignite recompila tudo.')
        else:
            click.echo(f'\n{Fore.YELLOW}[INFO]{Fore.RESET} Cache já estava vazio.')
