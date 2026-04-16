# doxoade/doxoade/commands/vulcan_cmd_bootstrap.py
"""
Subcomandos de instalação e verificação do bootstrap Vulcan.

  module             → instala módulo de acionamento Vulcan em projetos externos
  probe              → verifica status dos binários (.pyd/.so) ativos
  verify             → testa redirecionamento PYD em subprocess isolado
  telemetry-bridge   → exibe telemetria de projetos externos bootstrapados
"""
import os
import sys
import re
import subprocess
import json
import hashlib
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style
from .vulcan_cmd import _is_doxoade_project
from ._vulcan_embedded_template import VULCAN_EMBEDDED_CONTENT as _VULCAN_EMBEDDED_CONTENT
_BOOTSTRAP_START = '# [DOXOADE:VULCAN]'
_BOOTSTRAP_END = '# [/DOXOADE:VULCAN]'
_BOOTSTRAP_BLOCK = f'{_BOOTSTRAP_START}\n# [VULCAN-SKIP] Proteção contra introspecção Click\nimport os, sys; _b = os.path.join(os.getcwd(), ".doxoade", "vulcan", "bootstrap.py")\nif os.path.exists(_b):\n    import importlib.util as _u; _s = _u.spec_from_file_location("_vb", _b)\n    _m = _u.module_from_spec(_s); _s.loader.exec_module(_m); _m.ignite(__file__, globals())\n{_BOOTSTRAP_END}\n'
VULCAN_STUB_VERSION = 11

def generate_vulcan_stub() -> str:
    return f'# -*- coding: utf-8 -*-\n"""\nStub Vulcan embutido no projeto.\nGerenciado automaticamente pelo doxoade.\n"""\n\nVULCAN_STUB_VERSION = {VULCAN_STUB_VERSION}\n\ndef activate():\n    try:\n        from doxoade.tools.vulcan.runtime import install_meta_finder, find_vulcan_project_root\n        import __main__\n        root = find_vulcan_project_root(__file__)\n        if root:\n            install_meta_finder(root)\n        return True\n    except Exception:\n        return False\n'
_VULCAN_BOOTSTRAP_CONTENT = '# -*- coding: utf-8 -*-\n"""\nVULCAN BOOTSTRAP — Centralizador de Performance e Telemetria.\nInjetado dinamicamente para manter os arquivos do host limpos.\n"""\nimport os, sys, importlib.util as _u\n\ndef ignite(host_file, host_globals):\n    """Ponto de entrada único para inicializar o ecossistema Vulcan."""\n    root = _find_project_root(host_file)\n    if not root: return\n    \n    # 1. Ativa o MetaFinder (Redirecionamento .pyd/.so)\n    _run_tool(root, "runtime.py", "install_meta_finder", root)\n    \n    # 2. Ativa o Chronos Lite v4 (Telemetria)\n    _run_tool(root, "vulcan_embedded.py")\n\ndef _find_project_root(path):\n    curr = os.path.abspath(path)\n    while curr:\n        if os.path.exists(os.path.join(os.path.dirname(curr), ".doxoade")):\n            return os.path.dirname(curr)\n        parent = os.path.dirname(curr)\n        if parent == curr: break\n        curr = parent\n    return None\n\ndef _run_tool(root, filename, func_name=None, *args):\n    try:\n        path = os.path.join(root, ".doxoade", "vulcan", filename)\n        if not os.path.exists(path): return\n        spec = _u.spec_from_file_location(f"_v_{filename}", path)\n        mod = _u.module_from_spec(spec); spec.loader.exec_module(mod)\n        if func_name and hasattr(mod, func_name):\n            getattr(mod, func_name)(*args)\n    except Exception: pass\n'

def read_stub_version(stub_path: Path) -> int | None:
    if not stub_path.exists():
        return None
    try:
        text = stub_path.read_text(encoding='utf-8', errors='ignore')
        m = re.search('VULCAN_STUB_VERSION\\s*=\\s*(\\d+)', text)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

def _write_safe_runtime(project_root: Path) -> Path:
    project_root = Path(project_root).resolve()
    vulcan_dir = project_root / '.doxoade' / 'vulcan'
    vulcan_dir.mkdir(parents=True, exist_ok=True)
    (vulcan_dir / 'native').mkdir(exist_ok=True)
    (project_root / '.doxoade' / '__init__.py').write_text('# doxoade marker\n')
    (vulcan_dir / '__init__.py').write_text('# doxoade vulcan marker\n')
    (vulcan_dir / 'bootstrap.py').write_text(_VULCAN_BOOTSTRAP_CONTENT, encoding='utf-8')
    vulcan_src = Path(__file__).resolve().parents[1] / 'tools' / 'vulcan'
    tools = ('runtime.py', 'opt_cache.py', 'lib_optimizer.py', 'lazy_loader.py', 'embedded_lazy.py')
    for fname in tools:
        src_file = vulcan_src / fname
        if src_file.exists():
            (vulcan_dir / fname).write_text(src_file.read_text(encoding='utf-8'), encoding='utf-8')
    for native_exe in project_root.rglob('*.exe'):
        if '.doxoade' not in str(native_exe) and 'venv' not in str(native_exe):
            dest = vulcan_dir / 'native' / native_exe.name
            if not dest.exists():
                try:
                    import shutil
                    shutil.copy2(native_exe, dest)
                except Exception:
                    pass
    (vulcan_dir / 'vulcan_embedded.py').write_text(_VULCAN_EMBEDDED_CONTENT.lstrip(), encoding='utf-8')
    return vulcan_dir / 'bootstrap.py'

def _iter_project_main_files(project_root: Path):
    """Busca pontos de entrada e evita que o Vulcan compile arquivos de comando Click."""
    skip = {'.git', 'venv', '.venv', '__pycache__', 'build', 'dist', '.doxoade'}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith('.py'):
                p = Path(root) / f
                try:
                    content = p.read_text(encoding='utf-8', errors='ignore')
                    if '@click.' in content or 'if __name__ == "__main__"' in content:
                        yield p
                except Exception:
                    continue

def _inject_bootstrap(main_file: Path) -> bool:
    original = main_file.read_text(encoding='utf-8', errors='replace')
    safety_tag = ''
    if '@click.' in original and '[VULCAN-SKIP]' not in original:
        safety_tag = '\n# [VULCAN-SKIP] Proteção contra introspecção Click\n'
    content = original
    while True:
        start = content.find(_BOOTSTRAP_START)
        if start < 0:
            break
        end = content.find(_BOOTSTRAP_END, start)
        if end < 0:
            break
        end += len(_BOOTSTRAP_END)
        if end < len(content) and content[end] == '\n':
            end += 1
        content = content[:start] + content[end:]
    updated = _BOOTSTRAP_BLOCK + safety_tag + content
    if updated == original:
        return False
    main_file.write_text(updated, encoding='utf-8')
    return True

@click.command('module')
@click.argument('target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=False)
@click.option('--main', 'main_files', multiple=True, type=click.Path(exists=True, dir_okay=False), help='Arquivo específico para injetar bootstrap.')
@click.option('--auto-main', is_flag=True, help='Detecta e injeta em pontos de entrada prováveis (main.py, cli.py, etc).')
@click.option('--force-stub', is_flag=True, help='Recria o stub Vulcan mesmo se já existir.')
@click.option('--no-telemetry', is_flag=True, help='Não injeta Chronos Lite.')
def vulcan_module(target_path, main_files, auto_main, force_stub, no_telemetry):
    """Instala módulo de acionamento Vulcan em projetos externos.
    
    TARGET_PATH: Raiz do projeto alvo (default: atual).
    """
    project_root = Path(target_path).resolve()
    stub_path = project_root / '.doxoade' / 'vulcan_embedded.py'
    if no_telemetry:
        click.echo(f'{Fore.YELLOW}[INFO]{Style.RESET_ALL} Chronos Lite desativado (--no-telemetry).')
        click.echo(f'  {Style.DIM}Para desativar no ambiente: defina VULCAN_TELEMETRY_SYNC=0.{Style.RESET_ALL}')
    current_version = read_stub_version(stub_path)
    should_write = force_stub or current_version is None or current_version != VULCAN_STUB_VERSION
    if should_write:
        stub_path.parent.mkdir(parents=True, exist_ok=True)
        stub_path.write_text(generate_vulcan_stub(), encoding='utf-8')
        if force_stub:
            click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan recriado (--force-stub).')
        elif current_version is None:
            click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan criado (v{VULCAN_STUB_VERSION}).')
        else:
            click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan atualizado v{current_version} → v{VULCAN_STUB_VERSION}.')
    else:
        click.echo(f'{Fore.YELLOW}[INFO]{Style.RESET_ALL} Stub Vulcan já está na versão {VULCAN_STUB_VERSION}.')
    if _is_doxoade_project(project_root):
        click.echo(f'\n{Fore.RED}[ERRO] vulcan module não pode ser aplicado ao próprio projeto doxoade.{Style.RESET_ALL}')
        click.echo(f'{Fore.YELLOW}[INFO] O doxoade já possui MetaFinder nativo em doxoade/tools/vulcan/meta_finder.py{Style.RESET_ALL}')
        click.echo(f'{Fore.CYAN}[DICA] Para compilar módulos do doxoade, use: doxoade vulcan ignite{Style.RESET_ALL}')
        return
    click.echo(f'{Fore.GREEN}[OK]{Style.RESET_ALL} Stub Vulcan embutido criado em {stub_path}')
    runtime_dst = _write_safe_runtime(project_root)
    click.echo(f'{Fore.GREEN}[OK]{Fore.RESET} Runtime instalado em: {runtime_dst}')
    if not no_telemetry:
        click.echo(f'{Fore.MAGENTA}[⚡ Chronos Lite v4]{Style.RESET_ALL} Click + HotLines + Libs + Disco + Vulcan stats → ~/.doxoade/doxoade.db')
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
        click.echo(f'{Fore.GREEN}[OK]{Fore.RESET} Bootstrap injetado/atualizado em:')
        for p in changed:
            click.echo(f'  - {p.relative_to(project_root)}')
        click.echo(f'\n{Fore.CYAN}[INFO] Bootstrap instala MetaFinder e Chronos Lite automaticamente.{Style.RESET_ALL}')
    elif main_files or auto_main:
        click.echo(f'{Fore.YELLOW}[AVISO]{Fore.RESET} Nenhum arquivo de entrada compatível encontrado para injeção.')
        click.echo(f'  {Style.DIM}Dica: Tente especificar manualmente com --main <caminho/arquivo.py>{Style.RESET_ALL}')
    else:
        click.echo(f"{Fore.CYAN}[DICA]{Fore.RESET} Use --auto-main para injetar nos arquivos detectados, ou --main <arquivo> para o arquivo que contém seu '@click.group'.")

@click.command('probe')
@click.option('--path', 'target_path', default='.', type=click.Path(exists=True, file_okay=False, dir_okay=True), show_default=True, help='Projeto alvo a inspecionar.')
@click.option('--verbose', '-v', is_flag=True, help='Mostra detalhes de hash e paths.')
def vulcan_probe(target_path, verbose):
    """Verifica quais módulos estão ativos e seriam redirecionados para PYD."""
    project_root = Path(target_path).resolve()
    bin_dir = project_root / '.doxoade' / 'vulcan' / 'bin'
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  VULCAN PROBE — {project_root.name}{Style.RESET_ALL}')
    if not bin_dir.exists():
        click.echo(f'  {Fore.RED}Nenhuma foundry encontrada em {bin_dir}{Fore.RESET}')
        return
    ext = '.pyd' if os.name == 'nt' else '.so'
    binaries = sorted(bin_dir.glob(f'*{ext}'))
    if not binaries:
        click.echo(f'  {Fore.YELLOW}Nenhum binário ativo.{Fore.RESET}')
        return
    skip = {'.git', 'venv', '.venv', '__pycache__', 'build', 'dist', '.doxoade'}
    py_files: list[Path] = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith('.py'):
                py_files.append(Path(root) / f)
    hash_index: dict[str, Path] = {}
    for py in py_files:
        h = hashlib.sha256(str(py.resolve()).encode()).hexdigest()[:6]
        hash_index[h] = py
    active, stale, orphan = ([], [], [])
    for bin_path in binaries:
        base = bin_path.stem.split('.')[0]
        parts = base.split('_')
        pyd_hash = parts[-1] if len(parts) >= 3 else None
        pyd_stem = '_'.join(parts[1:-1]) if pyd_hash else '_'.join(parts[1:])
        source = hash_index.get(pyd_hash) if pyd_hash else None
        if not source:
            for py in py_files:
                if py.stem == pyd_stem:
                    source = py
                    break
        if not source:
            orphan.append((bin_path, pyd_stem, pyd_hash))
            continue
        try:
            is_stale = source.stat().st_mtime > bin_path.stat().st_mtime
        except OSError:
            is_stale = True
        rel_src = source.relative_to(project_root)
        (stale if is_stale else active).append((bin_path, rel_src, source))
    click.echo(f'\n  {Fore.GREEN}{Style.BRIGHT}✔ ATIVOS ({len(active)}):{Style.RESET_ALL}')
    if active:
        for bin_path, rel_src, source in active:
            size_kb = bin_path.stat().st_size / 1024
            click.echo(f'    {Fore.GREEN}✔{Fore.RESET} {str(rel_src):<45} {Fore.WHITE}{size_kb:>6.1f} KB{Fore.RESET}')
            if verbose:
                click.echo(f'       {Fore.CYAN}PYD:{Fore.RESET} {bin_path.name}')
                click.echo(f'       {Fore.CYAN}SRC:{Fore.RESET} {source}')
    else:
        click.echo(f'    {Fore.YELLOW}(nenhum){Fore.RESET}')
    if stale:
        click.echo(f'\n  {Fore.YELLOW}{Style.BRIGHT}⚠ STALE ({len(stale)}):{Style.RESET_ALL}')
        for bin_path, rel_src, source in stale:
            click.echo(f'    {Fore.YELLOW}⚠{Fore.RESET} {str(rel_src):<45} {Fore.YELLOW}[recompile: doxoade vulcan ignite]{Fore.RESET}')
            if verbose:
                import time as _time
                py_t = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(source.stat().st_mtime))
                pyd_t = _time.strftime('%Y-%m-%d %H:%M:%S', _time.localtime(bin_path.stat().st_mtime))
                click.echo(f'       .py  modificado: {py_t}')
                click.echo(f'       .pyd compilado : {pyd_t}')
    if orphan:
        click.echo(f'\n  {Fore.RED}{Style.BRIGHT}✘ ÓRFÃOS ({len(orphan)}):{Style.RESET_ALL}')
        for bin_path, pyd_stem, pyd_hash in orphan:
            click.echo(f'    {Fore.RED}✘{Fore.RESET} {bin_path.name}' + (f'  {Fore.YELLOW}(hash: {pyd_hash}){Fore.RESET}' if pyd_hash else ''))
    total = len(binaries)
    click.echo(f'\n  {Fore.CYAN}{'─' * 55}{Fore.RESET}')
    click.echo(f'  Total: {total}  │  {Fore.GREEN}Ativos: {len(active)}{Fore.RESET}  │  {Fore.YELLOW}Stale: {len(stale)}{Fore.RESET}  │  {Fore.RED}Órfãos: {len(orphan)}{Fore.RESET}')
    if len(active) == total:
        click.echo(f'\n  {Fore.GREEN}{Style.BRIGHT}✅ 100% dos módulos redirecionados para PYD.{Style.RESET_ALL}')
    elif active:
        pct = len(active) / total * 100
        click.echo(f"\n  {Fore.YELLOW}⚡ {pct:.0f}% ativos. Use 'doxoade vulcan ignite' para recompilar stale.{Fore.RESET}")
    else:
        click.echo(f"\n  {Fore.RED}Nenhum módulo ativo. Execute 'doxoade vulcan ignite'.{Fore.RESET}")
    click.echo()

@click.command('verify')
@click.argument('target_path', default='.', type=click.Path(exists=True))
@click.option('--verbose', '-v', is_flag=True)
def vulcan_verify(target_path, verbose):
    """Verifica se o redirecionamento PYD está funcional em projeto externo.

    \x08
    Separa dois tipos de binário:
      bin/     → binários do PROJETO (rastreáveis por hash ao .py de origem)
      lib_bin/ → binários de LIBS EXTERNAS (compilados de site-packages)
    """
    project_root = Path(target_path).resolve()
    bin_dir = project_root / '.doxoade' / 'vulcan' / 'bin'
    lib_bin_dir = project_root / '.doxoade' / 'vulcan' / 'lib_bin'
    runtime_py = project_root / '.doxoade' / 'vulcan' / 'runtime.py'
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ VULCAN VERIFY — {project_root.name}{Style.RESET_ALL}')
    ext = '.pyd' if os.name == 'nt' else '.so'
    proj_bins = list(bin_dir.glob(f'*{ext}')) if bin_dir.exists() else []
    lib_bins = list(lib_bin_dir.glob(f'*{ext}')) if lib_bin_dir.exists() else []
    any_bins = bool(proj_bins or lib_bins)
    embedded_path = project_root / '.doxoade' / 'vulcan' / 'vulcan_embedded.py'
    chronos_lite_ok = False
    if embedded_path.exists():
        try:
            txt = embedded_path.read_text(encoding='utf-8', errors='ignore')
            chronos_lite_ok = '_LibCodeSampler' in txt and '_ExternalCodeSampler' in txt
        except Exception:
            pass
    checks = {'runtime.py presente': runtime_py.exists(), 'bin/ presente': bin_dir.exists(), 'vulcan_embedded.py presente': embedded_path.exists(), 'Chronos Lite v4 integrado': chronos_lite_ok}
    main_files = list(project_root.rglob('__main__.py'))
    bootstrap_found = any((_BOOTSTRAP_START in p.read_text(encoding='utf-8', errors='ignore') for p in main_files if '.doxoade' not in str(p)))
    checks['bootstrap em __main__.py'] = bootstrap_found
    checks[f'binários {ext} (bin/ + lib_bin/)'] = any_bins
    all_ok = True
    for label, ok in checks.items():
        icon = f'{Fore.GREEN}✔' if ok else f'{Fore.RED}✘'
        all_ok = all_ok and ok
        click.echo(f'   {icon}{Style.RESET_ALL} {label}')
    if lib_bins:
        total_kb = sum((p.stat().st_size for p in lib_bins)) / 1024
        click.echo(f'   {Fore.CYAN}ℹ{Style.RESET_ALL}  lib_bin/: {len(lib_bins)} lib binário(s)  ({total_kb:.1f} KB total)')
    if not all_ok:
        click.echo(f"\n{Fore.YELLOW}  ⚠ Pré-checks falharam. Execute 'doxoade vulcan module --path {target_path} --auto-main'.{Style.RESET_ALL}")
        if not chronos_lite_ok:
            click.echo(f"  {Fore.MAGENTA}  → Chronos Lite v2 ausente: execute 'doxoade vulcan module --path {target_path} --force-stub' para atualizar para stub v{VULCAN_STUB_VERSION}.{Style.RESET_ALL}")
        return
    if lib_bins:
        click.echo(f'\n{Fore.MAGENTA}{Style.BRIGHT}  ⬡ LIBS EXTERNAS COMPILADAS (lib_bin/) — {len(lib_bins)} binário(s){Style.RESET_ALL}')
        lib_by_stem: dict[str, list] = {}
        for bp in sorted(lib_bins):
            parts = bp.stem.split('.')[0].split('_')
            stem = '_'.join(parts[1:-1]) if len(parts) >= 3 else bp.stem
            lib_by_stem.setdefault(stem, []).append(bp)
        for stem, paths in sorted(lib_by_stem.items()):
            newest = max(paths, key=lambda p: p.stat().st_mtime)
            size_kb = newest.stat().st_size / 1024
            n_extra = len(paths) - 1
            extra = f'  {Style.DIM}(+{n_extra} antiga(s)){Style.RESET_ALL}' if n_extra else ''
            click.echo(f'   {Fore.MAGENTA}⬡{Style.RESET_ALL} {stem:<30} {Fore.WHITE}{size_kb:>6.1f} KB{Style.RESET_ALL}{extra}')
            if verbose:
                for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
                    age = '← atual' if p is newest else '← antiga'
                    click.echo(f'       {Fore.CYAN}{p.name}{Style.RESET_ALL}  {Style.DIM}{age}{Style.RESET_ALL}')
        n_old = sum((len(v) - 1 for v in lib_by_stem.values()))
        if n_old > 0:
            click.echo(f'\n  {Fore.YELLOW}⚠ {n_old} binário(s) antigo(s). Limpe com: doxoade vulcan purge{Style.RESET_ALL}')
    if not proj_bins:
        msg = f"\n{Fore.CYAN}  ℹ bin/ vazio.{Style.RESET_ALL}\n  Execute 'doxoade vulcan ignite'." if lib_bins else f"\n{Fore.RED}  ✘ Nenhum binário.{Style.RESET_ALL}\n  Execute 'doxoade vulcan ignite'."
        click.echo(msg)
        click.echo()
        return
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ PROJETO (bin/) — testando redirecionamento...{Style.RESET_ALL}')
    skip = {'.git', 'venv', '.venv', '__pycache__', 'build', 'dist', '.doxoade'}
    py_index: dict[str, Path] = {}
    for r, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if f.endswith('.py'):
                p = Path(r) / f
                h = hashlib.sha256(str(p.resolve()).encode()).hexdigest()[:6]
                py_index[h] = p
    results = []
    for bin_path in proj_bins[:10]:
        base = bin_path.stem.split('.')[0]
        parts = base.split('_')
        phash = parts[-1] if len(parts) >= 3 else None
        src = py_index.get(phash)
        if not src:
            results.append({'bin': bin_path.name, 'status': 'ÓRFÃO', 'src': None})
            continue
        try:
            modname = str(src.with_suffix('').relative_to(project_root)).replace(os.sep, '.')
        except ValueError:
            modname = src.stem
        probe_script = f"""\nimport sys, importlib, json\nsys.path.insert(0, r'{project_root}')\nimport importlib.util as _u\n_spec = _u.spec_from_file_location('_rt', r'{runtime_py}')\n_mod  = _u.module_from_spec(_spec)\n_spec.loader.exec_module(_mod)\n_mod.install_meta_finder(r'{project_root}')\nmodname = '{modname}'\ntry:\n    mod  = importlib.import_module(modname)\n    file = getattr(mod, '__file__', '') or ''\n    loader_name = type(getattr(mod, '__loader__', None)).__name__\n    redirected = '.doxoade' in file.replace('\\\\', '/') or loader_name == 'VulcanLoader'\n    print(json.dumps({{"stem": modname, "file": file, "loader": loader_name, "redirected": redirected}}))\nexcept Exception as e:\n    print(json.dumps({{"stem": modname, "file": "", "redirected": False, "error": str(e)}}))\n"""
        try:
            proc = subprocess.run([sys.executable, '-c', probe_script], capture_output=True, text=True, timeout=10, cwd=str(project_root))
            for line in proc.stdout.strip().splitlines():
                try:
                    data = json.loads(line)
                    data['bin'] = bin_path.name
                    data['src'] = str(src.relative_to(project_root))
                    results.append(data)
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            results.append({'bin': bin_path.name, 'status': 'TIMEOUT', 'src': str(src)})
        except Exception as exc:
            results.append({'bin': bin_path.name, 'status': f'ERRO: {exc}', 'src': str(src)})
    redirected = [r for r in results if r.get('redirected')]
    not_redir = [r for r in results if not r.get('redirected') and r.get('src')]
    orphans = [r for r in results if r.get('status') == 'ÓRFÃO']
    click.echo(f'\n{Fore.CYAN}  {'─' * 55}{Style.RESET_ALL}')
    if redirected:
        click.echo(f'  {Fore.GREEN}{Style.BRIGHT}✔ REDIRECIONADOS ({len(redirected)}):{Style.RESET_ALL}')
        for r in redirected:
            click.echo(f'   {Fore.GREEN}✔{Style.RESET_ALL} {r['src']}')
            if verbose:
                click.echo(f'     → {Fore.CYAN}{r.get('file', '')}{Style.RESET_ALL}')
    if not_redir:
        click.echo(f'\n  {Fore.YELLOW}{Style.BRIGHT}⚠ NÃO REDIRECIONADOS ({len(not_redir)}):{Style.RESET_ALL}')
        for r in not_redir:
            click.echo(f'   {Fore.YELLOW}⚠{Style.RESET_ALL} {r['src']}  {Style.DIM}({r.get('error', '')}){Style.RESET_ALL}')
    if orphans:
        click.echo(f'\n  {Fore.RED}{Style.BRIGHT}✘ ÓRFÃOS ({len(orphans)}):{Style.RESET_ALL}')
        for r in orphans:
            click.echo(f'   {Fore.RED}✘{Style.RESET_ALL} {r['bin']}')
        click.echo(f'  {Fore.CYAN}  Limpe com: doxoade vulcan purge{Style.RESET_ALL}')
    total = len(results)
    pct = len(redirected) / total * 100 if total else 0
    click.echo(f'\n  {Fore.CYAN}Total: {total}  │  {Fore.GREEN}Redirecionados: {len(redirected)} ({pct:.0f}%){Fore.RESET}  │  {Fore.YELLOW}Falhos: {len(not_redir)}{Fore.RESET}  │  {Fore.RED}Órfãos: {len(orphans)}{Style.RESET_ALL}')
    if pct == 100 and total > 0:
        click.echo(f'\n  {Fore.GREEN}{Style.BRIGHT}✅ Redirecionamento 100% funcional.{Style.RESET_ALL}')
    elif pct > 0:
        click.echo(f"\n  {Fore.YELLOW}⚡ Redirecionamento parcial. Verifique bootstrap e rode 'vulcan ignite'.{Style.RESET_ALL}")
    elif total > 0:
        click.echo(f"\n  {Fore.RED}✘ Nenhum redirecionamento ativo. Execute 'doxoade vulcan module --path {target_path} --auto-main'.{Style.RESET_ALL}")
    click.echo()

@click.command('telemetry-bridge')
@click.option('--limit', '-n', default=20, help='Número de registros a exibir.')
@click.option('--project', '-p', default=None, help='Filtra por nome/caminho do projeto (substring de working_dir).')
@click.option('--since', default=None, metavar='YYYY-MM-DD', help='Exibe apenas registros a partir desta data.')
@click.option('--stats', '-s', is_flag=True, help='Tabela agregada por projeto (CPU/RAM/I/O médios).')
@click.option('--libs', '-l', is_flag=True, help='Mapa de libs de terceiros detectadas por projeto.')
@click.option('--verbose', '-v', is_flag=True, help='Expande cada registro: arquivo, disco (partição + ops), top-3 Vulcan, libs.')
def vulcan_telemetry_bridge(limit, project, since, stats, libs, verbose):
    """Exibe telemetria de projetos externos bootstrapados pelo Vulcan.

    \x08
    Lê registros 'vulcan_ext_*' gravados pelo Chronos Lite v2.
    Cada registro contém:
      • Comando Click e arquivo executado
      • CPU / RAM (picos)
      • I/O em bytes (read/write MB) e em operações (syscall count)
      • Uso da partição do disco
      • Libs de terceiros carregadas + versões
      • Vulcan stats (timing de funções otimizadas)

    Requer bootstrap:
      doxoade vulcan module --path <projeto> --auto-main
    """
    from doxoade.database import get_db_connection
    import sqlite3 as _sqlite3
    conn = get_db_connection()
    conn.row_factory = _sqlite3.Row
    cursor = conn.cursor()
    try:
        conditions = ["command_name LIKE 'vulcan_ext_%'"]
        params: list = []
        if project:
            conditions.append('(working_dir LIKE ? OR command_name LIKE ?)')
            params += [f'%{project}%', f'%{project}%']
        if since:
            conditions.append('timestamp >= ?')
            params.append(since)
        where = ' AND '.join(conditions)
        if stats:
            _render_bridge_stats(cursor, where, params)
            return
        if libs:
            _render_bridge_libs(cursor, where, params)
            return
        params.append(limit)
        cursor.execute(f'SELECT * FROM command_history WHERE {where} ORDER BY id DESC LIMIT ?', params)
        rows = cursor.fetchall()
        if not rows:
            click.echo(f'\n{Fore.YELLOW}  Nenhum projeto externo no índice.{Style.RESET_ALL}\n  {Fore.CYAN}Instrumente com: doxoade vulcan module --path <projeto> --auto-main{Style.RESET_ALL}')
            return
        click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ TELEMETRIA DE PROJETOS EXTERNOS  (Chronos Lite v2 — {len(rows)} registro(s)){Style.RESET_ALL}')
        click.echo(f'  {Style.DIM}--stats para agregação  │  --libs para dependências  │  --verbose para detalhes{Style.RESET_ALL}\n')
        last_project = None
        for row in rows:
            cwd = row['working_dir'] or ''
            proj_id = Path(cwd).name if cwd else 'desconhecido'
            if proj_id != last_project:
                click.echo(f'  {Fore.YELLOW}{Style.BRIGHT}◈ {proj_id}{Style.RESET_ALL}  {Style.DIM}{cwd}{Style.RESET_ALL}')
                last_project = proj_id
            ts = (row['timestamp'] or '')[:19].replace('T', ' ')
            cmd = (row['command_name'] or '').replace('vulcan_ext_', '').replace('_', ' ')
            dur = row['duration_ms'] or 0.0
            cpu = row['cpu_percent'] or 0.0
            ram = row['peak_memory_mb'] or 0.0
            io_r = row['io_read_mb'] or 0.0
            io_w = row['io_write_mb'] or 0.0
            cpu_color = Fore.RED if cpu > 80 else Fore.YELLOW if cpu > 40 else Fore.GREEN
            click.echo(f'    {Fore.WHITE}{ts}{Style.RESET_ALL} │ {Fore.CYAN}{cmd:<22}{Style.RESET_ALL} │ {dur:>7.0f}ms │ CPU {cpu_color}{cpu:>5.1f}%{Style.RESET_ALL} │ RAM {Fore.MAGENTA}{ram:>6.1f}MB{Style.RESET_ALL} │ I/O R:{io_r:.2f} W:{io_w:.2f}MB')
            if verbose and row['system_info']:
                try:
                    si = json.loads(row['system_info'])
                    sf = si.get('script_file', '')
                    if sf:
                        click.echo(f'      {Style.DIM}arquivo : {sf}{Style.RESET_ALL}')
                    disk = si.get('disk', {})
                    if disk:
                        dtotal = disk.get('disk_total_gb', 0)
                        dused = disk.get('disk_used_gb', 0)
                        dpct = disk.get('disk_used_pct', 0)
                        io_rc = disk.get('io_read_count', 0)
                        io_wc = disk.get('io_write_count', 0)
                        click.echo(f'      {Fore.BLUE}disco   {Style.RESET_ALL}: {dused:.1f}/{dtotal:.1f}GB ({dpct}%)  ops R:{io_rc:,}  W:{io_wc:,}')
                    vs = si.get('vulcan_stats', {})
                    if vs:
                        top3 = sorted(vs.items(), key=lambda x: x[1].get('total_ms', 0), reverse=True)[:3]
                        for fn, data in top3:
                            hits = data.get('hits', 0)
                            avg = data['total_ms'] / hits if hits > 0 else 0
                            fb = data.get('fallbacks', 0)
                            fb_s = f'{Fore.RED}{fb}fb{Style.RESET_ALL}' if fb else f'{Fore.GREEN}0fb{Style.RESET_ALL}'
                            fn_d = fn[:35] + '..' if len(fn) > 37 else fn
                            click.echo(f'      {Fore.MAGENTA}⬡{Style.RESET_ALL} {fn_d:<38} {hits:>4}×  avg {avg:.3f}ms  {fb_s}')
                    lib_map = si.get('libs', {})
                    if lib_map:
                        sample = list(lib_map.items())[:5]
                        lib_str = '  '.join((f'{k}({v})' if v else k for k, v in sample))
                        extra = f'  +{len(lib_map) - 5} mais' if len(lib_map) > 5 else ''
                        click.echo(f'      {Fore.CYAN}libs    {Style.RESET_ALL}: {lib_str}{Style.DIM}{extra}{Style.RESET_ALL}')
                except Exception:
                    pass
        click.echo()
    finally:
        conn.close()

def _render_bridge_stats(cursor, where: str, params: list):
    """Tabela agregada de performance por projeto externo."""
    cursor.execute(f'\n        SELECT working_dir,\n               COUNT(*)            AS execucoes,\n               AVG(duration_ms)    AS avg_dur,\n               MAX(duration_ms)    AS max_dur,\n               AVG(cpu_percent)    AS avg_cpu,\n               AVG(peak_memory_mb) AS avg_ram,\n               SUM(io_read_mb)     AS total_io_r,\n               SUM(io_write_mb)    AS total_io_w\n        FROM command_history\n        WHERE {where}\n        GROUP BY working_dir\n        ORDER BY avg_dur DESC\n        ', params)
    rows = cursor.fetchall()
    if not rows:
        click.echo(f'\n{Fore.YELLOW}  Nenhum dado para agregar.{Style.RESET_ALL}')
        return
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ PERFORMANCE AGREGADA — PROJETOS EXTERNOS{Style.RESET_ALL}')
    hdr = f'  {'PROJETO':<25} │ {'Exec':>5} │ {'Avg(ms)':>8} │ {'Max(ms)':>8} │ {'CPU%':>6} │ {'RAM MB':>7} │ {'IO_R MB':>8} │ {'IO_W MB':>8}'
    click.echo(f'\n{Fore.WHITE}{hdr}{Style.RESET_ALL}')
    click.echo('  ' + '─' * (len(hdr) - 2))
    for row in rows:
        proj = Path(row['working_dir']).name[:25] if row['working_dir'] else 'desconhecido'
        click.echo(f'  {Fore.CYAN}{proj:<25}{Style.RESET_ALL} │ {int(row['execucoes']):>5} │ {row['avg_dur']:>8.0f} │ {row['max_dur']:>8.0f} │ {row['avg_cpu'] or 0:>6.1f} │ {row['avg_ram'] or 0:>7.1f} │ {row['total_io_r'] or 0:>8.2f} │ {row['total_io_w'] or 0:>8.2f}')
    click.echo()

def _render_bridge_libs(cursor, where: str, params: list):
    """
    Mapa de libs de terceiros detectadas por projeto.

    Agrega todos os registros do projeto e exibe:
      • Frequência de detecção (em quantos registros a lib apareceu)
      • Versões observadas (pode haver mais de uma se o projeto mudou)
    Ordenado por frequência descendente.
    """
    cursor.execute(f'SELECT working_dir, system_info FROM command_history WHERE {where} ORDER BY id DESC', params)
    rows = cursor.fetchall()
    if not rows:
        click.echo(f'\n{Fore.YELLOW}  Nenhum dado disponível.{Style.RESET_ALL}')
        return
    agg: dict[str, dict[str, dict]] = {}
    for row in rows:
        proj = Path(row['working_dir']).name if row['working_dir'] else 'desconhecido'
        if not row['system_info']:
            continue
        try:
            si = json.loads(row['system_info'])
            for name, ver in si.get('libs', {}).items():
                agg.setdefault(proj, {}).setdefault(name, {'count': 0, 'versions': set()})
                agg[proj][name]['count'] += 1
                if ver:
                    agg[proj][name]['versions'].add(ver)
        except Exception:
            continue
    if not agg:
        click.echo(f'\n{Fore.YELLOW}  Nenhuma lib detectada. Verifique se stub v{VULCAN_STUB_VERSION} está instalado.{Style.RESET_ALL}')
        return
    click.echo(f'\n{Fore.CYAN}{Style.BRIGHT}  ⬡ MAPA DE LIBS — PROJETOS EXTERNOS{Style.RESET_ALL}')
    for proj, lib_map in sorted(agg.items()):
        click.echo(f'\n  {Fore.YELLOW}{Style.BRIGHT}◈ {proj}{Style.RESET_ALL}  {Style.DIM}({len(lib_map)} lib(s) distintas){Style.RESET_ALL}')
        for name, data in sorted(lib_map.items(), key=lambda x: x[1]['count'], reverse=True):
            ver_str = ', '.join(sorted(data['versions'])) if data['versions'] else '—'
            click.echo(f'    {Fore.CYAN}{name:<25}{Style.RESET_ALL} v{ver_str:<18} {Style.DIM}{data['count']}× detectada{Style.RESET_ALL}')
    click.echo()
