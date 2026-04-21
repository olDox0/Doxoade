# doxoade/doxoade/commands/global_health.py
import os
import re
import sys
import shutil
import subprocess
import site
import sysconfig
from pathlib import Path
from collections import defaultdict
import click
from importlib import metadata
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
PROTECTED_PACKAGES = {'doxoade', 'orn'}
SAFE_GARBAGE_DIRS = {'__pycache__'}
SAFE_GARBAGE_SUFFIXES = {'.pyc', '.pyo', '.tmp', '.bak', '.old'}

def _active_scripts_dir() -> Path:
    return Path(sysconfig.get_paths()['scripts']).resolve()

def _normalize_name(name: str) -> str:
    return re.sub('[-_.]+', '-', name).lower().strip()

def _active_site_packages() -> Path:
    return Path(sysconfig.get_paths()['purelib']).resolve()

def _find_pip_executables():
    if os.name == 'nt':
        cmds = [['where', 'pip'], ['where', 'pip3']]
    else:
        cmds = [['which', '-a', 'pip'], ['which', '-a', 'pip3']]
    found = []
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
            found.extend([line.strip() for line in r.stdout.splitlines() if line.strip()])
        except Exception:
            pass
    unique = []
    seen = set()
    for item in found:
        key = os.path.normcase(item)
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique

def _site_packages_roots():
    roots = []
    try:
        roots.append(Path(sysconfig.get_paths()['purelib']).resolve())
    except Exception:
        pass
    try:
        for p in site.getsitepackages():
            roots.append(Path(p).resolve())
    except Exception:
        pass
    try:
        user_site = site.getusersitepackages()
        if isinstance(user_site, str):
            roots.append(Path(user_site).resolve())
        elif isinstance(user_site, (list, tuple)):
            roots.extend((Path(p).resolve() for p in user_site))
    except Exception:
        pass
    unique = []
    seen = set()
    for root in roots:
        key = os.path.normcase(str(root))
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique

def _is_protected_dist(dist_name: str) -> bool:
    return _normalize_name(dist_name) in {_normalize_name(x) for x in PROTECTED_PACKAGES}

def _collect_distributions():
    """
    Mapeia distribuições por nome normalizado e por pasta de instalação.
    """
    roots = _site_packages_roots()
    by_name = defaultdict(list)
    for root in roots:
        try:
            for dist in metadata.distributions(path=[str(root)]):
                raw_name = dist.metadata.get('Name') or dist.metadata.get('Summary') or dist.name
                if not raw_name:
                    continue
                norm = _normalize_name(raw_name)
                by_name[norm].append({'name': raw_name, 'normalized': norm, 'version': dist.version, 'root': root, 'dist': dist})
        except Exception:
            continue
    return (by_name, roots)

def _delete_path(path: Path, logger, dry_run=False):
    try:
        if dry_run:
            click.echo(Fore.CYAN + f'     - [DRY-RUN] {path}')
            return True
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        click.echo(Fore.GREEN + f'     - [REMOVIDO] {path}')
        logger.add_finding('info', f'Removido: {path}', category='GLOBAL-CLEAR')
        return True
    except Exception as e:
        click.echo(Fore.RED + f'     - [FALHA] {path}: {e}')
        logger.add_finding('error', f'Falha ao remover: {path}', category='GLOBAL-CLEAR', details=str(e))
        return False

def _report_global_health(logger):
    """
    Auditoria: mostra instalações duplicadas, ghost installs e lixo óbvio.
    """
    click.echo(Fore.YELLOW + '\n--- 1. Raízes de instalação detectadas ---')
    roots = _site_packages_roots()
    active_root = _active_site_packages()
    for root in roots:
        tag = '[ATIVA]' if os.path.normcase(str(root)) == os.path.normcase(str(active_root)) else '[EXTRA]'
        click.echo(Fore.WHITE + f'   {tag} {root}')
    click.echo(Fore.YELLOW + '\n--- 2. Distribuições globais ---')
    by_name, _ = _collect_distributions()
    duplicates = []
    protected_found = []
    for name, installs in sorted(by_name.items()):
        if _is_protected_dist(name):
            protected_found.extend(installs)
            continue
        if len(installs) > 1:
            duplicates.append((name, installs))
    if protected_found:
        click.echo(Fore.GREEN + '   > Protegidas encontradas:')
        for inst in protected_found:
            click.echo(Fore.GREEN + f"     - {inst['name']} {inst['version']} @ {inst['root']}")
    if not duplicates:
        click.echo(Fore.GREEN + '   > Nenhuma duplicação óbvia encontrada.')
    else:
        click.echo(Fore.RED + '   > Duplicações encontradas:')
        for name, installs in duplicates:
            click.echo(Fore.RED + f'     - {name}:')
            for inst in installs:
                click.echo(Fore.RED + f"       - {inst['name']} {inst['version']} @ {inst['root']}")
            logger.add_finding('warning', f'Distribuição duplicada: {name}', category='GLOBAL-DUPLICATE', details='; '.join((f"{i['version']} @ {i['root']}" for i in installs)))
    return len(duplicates) == 0

def _check_pip_health(logger):
    click.echo(Fore.YELLOW + '\n--- 1. Análise de Saúde do Pip ---')
    all_ok = True
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', '--version'], capture_output=True, text=True, check=True, encoding='utf-8')
    except (subprocess.CalledProcessError, FileNotFoundError):
        msg = 'O pip não está acessível pelo Python atual.'
        click.echo(Fore.RED + f'   > [FALHA] {msg}')
        logger.add_finding('critical', msg, category='PIP-HEALTH')
        return False
    pip_path = result.stdout.split('from ')[1].split(' (python')[0].strip()
    active_scripts = _active_scripts_dir()
    active_site = _active_site_packages()
    click.echo(Fore.GREEN + "   > [OK] pip vinculado via 'python -m pip'.")
    click.echo(Fore.YELLOW + '\n--- 2. Executáveis do Pip no PATH ---')
    executables = _find_pip_executables()
    if not executables:
        click.echo(Fore.YELLOW + '   > Nenhum executável pip adicional encontrado no PATH.')
    else:
        for exe in executables:
            exe_parent = Path(exe).resolve().parent
            if os.path.normcase(str(exe_parent)) == os.path.normcase(str(active_scripts)):
                click.echo(Fore.GREEN + f'   > [ATIVO] {exe}')
            else:
                click.echo(Fore.RED + f'   > [FANTASMA] {exe}')
                logger.add_finding('warning', 'Executável pip fora do ambiente ativo.', category='PIP-HEALTH', details=exe)
    try:
        current_version = metadata.version('pip')
        click.echo(Fore.GREEN + f'\n   > [OK] pip instalado: {current_version}')
    except metadata.PackageNotFoundError:
        click.echo(Fore.RED + '\n   > [FALHA] pip não foi encontrado via metadata.')
        all_ok = False
        logger.add_finding('critical', 'pip não encontrado via metadata.', category='PIP-HEALTH')
    return all_ok

def _clean_pip_duplicates(logger):
    click.echo(Fore.YELLOW + '\n--- 1. Limpeza de duplicações do Pip ---')
    active_scripts = _active_scripts_dir()
    active_site = _active_site_packages()
    removed_any = False
    for exe in _find_pip_executables():
        exe_path = Path(exe).resolve()
        if os.path.normcase(str(exe_path.parent)) == os.path.normcase(str(active_scripts)):
            continue
        try:
            exe_path.unlink(missing_ok=True)
            click.echo(Fore.GREEN + f'   > [REMOVIDO] {exe_path}')
            logger.add_finding('info', 'Executável pip removido.', category='PIP-CLEAN', details=str(exe_path))
            removed_any = True
        except Exception as e:
            click.echo(Fore.RED + f'   > [FALHA] {exe_path}: {e}')
            logger.add_finding('error', 'Falha ao remover executável pip.', category='PIP-CLEAN', details=str(e))
    click.echo(Fore.YELLOW + '\n--- 2. Remoção de instalações duplicadas do pacote pip ---')
    pip_dists = []
    for dist in metadata.distributions():
        try:
            name = dist.metadata.get('Name', '').strip().lower()
            if name != 'pip':
                continue
            files = list(dist.files or [])
            roots = set()
            for file_obj in files:
                try:
                    full_path = file_obj.locate()
                    parent = full_path.parent
                    while parent != parent.parent and parent.name not in {'site-packages', 'dist-packages'}:
                        parent = parent.parent
                    roots.add(str(parent))
                except Exception:
                    continue
            pip_dists.append((dist, roots))
        except Exception:
            continue
    for dist, roots in pip_dists:
        for root_str in roots:
            root = Path(root_str).resolve()
            if os.path.normcase(str(root)) == os.path.normcase(str(active_site)):
                continue
            candidates = []
            try:
                for item in root.iterdir():
                    n = item.name.lower()
                    if n == 'pip' or n.startswith('pip-') or n.startswith('pip.') or n.startswith('pip-') or n.startswith('pip_dist'):
                        candidates.append(item)
                    if n.startswith('pip') and (n.endswith('.dist-info') or n.endswith('.egg-info')):
                        candidates.append(item)
            except Exception:
                continue
            for candidate in candidates:
                try:
                    if candidate.is_dir():
                        shutil.rmtree(candidate)
                    else:
                        candidate.unlink(missing_ok=True)
                    click.echo(Fore.GREEN + f'   > [REMOVIDO] {candidate}')
                    logger.add_finding('info', 'Duplicação do pip removida.', category='PIP-CLEAN', details=str(candidate))
                    removed_any = True
                except Exception as e:
                    click.echo(Fore.RED + f'   > [FALHA] {candidate}: {e}')
                    logger.add_finding('error', 'Falha ao remover duplicação do pip.', category='PIP-CLEAN', details=str(e))
    return removed_any

def _clear_global_garbage(logger):
    """
    Limpeza segura:
    1) __pycache__
    2) .pyc/.pyo/.tmp/.bak/.old
    3) dist-info / egg-info órfão
    4) duplicatas fora da pasta ativa, mas nunca doxoade/ORN
    """
    active_root = _active_site_packages()
    by_name, roots = _collect_distributions()
    removed_any = False
    click.echo(Fore.YELLOW + '\n--- 1. Limpando lixo óbvio ---')
    for root in roots:
        if not root.exists():
            continue
        for entry in root.iterdir():
            if entry.name in SAFE_GARBAGE_DIRS:
                removed_any |= _delete_path(entry, logger)
            elif entry.is_file() and entry.suffix.lower() in SAFE_GARBAGE_SUFFIXES:
                removed_any |= _delete_path(entry, logger)
            elif entry.is_dir() and entry.name.endswith(('.dist-info', '.egg-info')):
                base = entry.name
                norm = _normalize_name(base.split('-')[0])
                if norm in {_normalize_name(p) for p in PROTECTED_PACKAGES}:
                    continue
                has_dist = any((os.path.normcase(str(inst['root'])) == os.path.normcase(str(root)) for inst in by_name.get(norm, [])))
                if not has_dist:
                    removed_any |= _delete_path(entry, logger)
    click.echo(Fore.YELLOW + '\n--- 2. Removendo duplicatas fora da instalação ativa ---')
    for name, installs in by_name.items():
        if _is_protected_dist(name):
            continue
        if len(installs) <= 1:
            continue
        for inst in installs:
            root = inst['root']
            if os.path.normcase(str(root)) == os.path.normcase(str(active_root)):
                continue
            dist = inst['dist']
            try:
                files = list(dist.files or [])
            except Exception:
                files = []
            candidates = []
            for p in root.iterdir():
                if p.name.startswith(dist.metadata['Name'].replace('-', '_')) and p.name.endswith('.dist-info'):
                    candidates.append(p)
                if p.name.startswith(dist.metadata['Name'].replace('-', '_')) and p.is_dir():
                    candidates.append(p)
            for candidate in candidates:
                if candidate.exists():
                    removed_any |= _delete_path(candidate, logger)
    return removed_any

@click.command('doctor')
@click.pass_context
@click.option('--global', 'check_global', is_flag=True, help='Audita instalações globais do Python ativo.')
@click.option('--global-clear', is_flag=True, help='Remove lixo seguro e duplicatas fora da instalação ativa.')
@click.option('--pip', 'check_pip', is_flag=True, help='Audita o pip do Python ativo.')
@click.option('--pip-clean', is_flag=True, help='Remove duplicações e executáveis fantasmas do pip.')
def global_health(ctx, check_global, global_clear, check_pip, pip_clean):
    """
    Diagnóstico e limpeza da instalação global da Doxoade.
    """
    arguments = ctx.params
    with ExecutionLogger('doctor', '.', arguments) as logger:
        click.echo(Fore.CYAN + Style.BRIGHT + '--- [DOCTOR] Diagnóstico do ambiente global ---')
        if not any([check_global, global_clear, check_pip, pip_clean]):
            click.echo(Fore.YELLOW + 'Use --global para auditoria ou --global-clear para limpeza.')
            sys.exit(1)
        ok = True
        if global_clear:
            if click.confirm(Fore.YELLOW + '\n[PERIGO] Deseja limpar o lixo seguro encontrado?'):
                cleared = _clear_global_garbage(logger)
                ok = ok and cleared
            else:
                click.echo(Fore.YELLOW + '   > Limpeza cancelada.')
        if check_pip:
            click.echo(Fore.CYAN + Style.BRIGHT + '--- [DOCTOR --PIP] Verificação do Pip ---')
            ok = _check_pip_health(logger)
            if not ok:
                sys.exit(1)
            return
        if pip_clean:
            click.echo(Fore.CYAN + Style.BRIGHT + '--- [DOCTOR --PIP-CLEAN] Limpeza do Pip ---')
            if click.confirm(Fore.YELLOW + '\n[PERIGO] Deseja remover duplicações e fantasmas do pip?'):
                _clean_pip_duplicates(logger)
            return
        click.echo(Fore.CYAN + Style.BRIGHT + '\n--- Diagnóstico Concluído ---')
        if ok:
            click.echo(Fore.GREEN + Style.BRIGHT + '[OK] Nenhum problema crítico detectado.')
        else:
            click.echo(Fore.RED + Style.BRIGHT + '[PROBLEMA] Há itens que merecem revisão.')
            sys.exit(1)
