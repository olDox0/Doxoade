# -*- coding: utf-8 -*-
# .doxoade\dumppot.txt
"""
doxoade git-search — Pesquisa e navegação remota de repositórios GitHub.

Filosofia: apenas licenças permissivas (compatíveis com MIT), foco em
acelerar desenvolvimento sem criar obrigações legais de copyleft.
"""
from __future__ import annotations

import os
import sys
import json
import base64
import shutil
import subprocess
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import click

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

__version__ = '1.2 Alfa (Reference Hunter + Remote Navigator)'

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────

PERMISSIVE_LICENSES: Tuple[str, ...] = (
    'mit', 'apache-2.0', 'bsd-2-clause', 'bsd-3-clause',
    'isc', 'unlicense', '0bsd',
)

COPYLEFT_LICENSES: Tuple[str, ...] = (
    'gpl-2.0', 'gpl-3.0', 'agpl-3.0',
    'lgpl-2.1', 'lgpl-3.0', 'mpl-2.0',
)

REFERENCES_DIR_NAME = 'references'
REF_METADATA_FILE = '.doxoade_ref.json'

CACHE_DIR_NAME = '.doxoade/cache/git_search'

_EXCLUDE_CONTRACT_PATTERNS = (
    'tests/', 'test_', 'conftest.py',
    'docs/examples/', 'docs/guide/',
    '_test.py',
)

# ─────────────────────────────────────────────────────────────
# Helpers de ambiente
# ─────────────────────────────────────────────────────────────

def _gh_installed() -> bool:
    return shutil.which('gh') is not None


def _check_gh_available() -> Tuple[bool, str]:
    gh_path = shutil.which('gh')
    if not gh_path:
        return False, (
            "GitHub CLI ('gh') não encontrado no PATH.\n"
            "  ↳ Instalação automática: doxoade git-search --install\n"
            "  ↳ Setup completo:        doxoade git-search --setup\n"
            "  ↳ Diagnóstico:           doxoade git-search --check"
        )
    try:
        res = subprocess.run(['gh', 'auth', 'status'],
                             capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return False, (
                "GitHub CLI encontrado, mas não autenticado.\n"
                "  ↳ Execute: doxoade git-search --login"
            )
    except subprocess.TimeoutExpired:
        return False, "Timeout ao verificar autenticação do 'gh'."
    except Exception as e:
        return False, f"Falha ao verificar 'gh auth status': {e}"
    return True, ""


# ─────────────────────────────────────────────────────────────
# Construção da query
# ─────────────────────────────────────────────────────────────

def _build_license_filter(liberal: bool) -> str:
    if not liberal:
        return ''
    return ','.join(PERMISSIVE_LICENSES)


def _build_search_query(
    query: str,
    language: Optional[str],
    min_stars: int,
    updated_after: Optional[str],
    exclude_copyleft: bool,
) -> str:
    parts: List[str] = [query.strip()] if query.strip() else []
    if language:
        parts.append(f'language:{language.lower()}')
    if min_stars > 0:
        parts.append(f'stars:>={min_stars}')
    if updated_after:
        parts.append(f'pushed:>={updated_after}')
    # Exclusão de copyleft agora é feita via pós-filtro em Python
    return ' '.join(parts)


def _filter_copyleft(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove repositórios com licenças de copyleft (filtro pós-busca)."""
    filtered = []
    for repo in results:
        lic_obj = repo.get('license') or {}
        spdx = (lic_obj.get('spdxId') or lic_obj.get('name') or '').lower()
        if any(c in spdx for c in ('gpl', 'agpl', 'lgpl', 'mpl')):
            continue
        filtered.append(repo)
    return filtered


# ─────────────────────────────────────────────────────────────
# Execução da busca
# ─────────────────────────────────────────────────────────────

_GH_JSON_FIELDS = (
    'fullName,description,stargazersCount,forksCount,'
    'language,license,updatedAt,url,isArchived,isFork'
)


def _run_gh_search(
    query: str,
    license_filter: str,
    limit: int,
    sort: str,
) -> Tuple[bool, List[Dict[str, Any]], str]:
    cmd: List[str] = [
        'gh', 'search', 'repos', query,
        '--limit', str(limit),
        '--sort', sort,
        '--json', _GH_JSON_FIELDS,
    ]
    if license_filter:
        cmd.extend(['--license', license_filter])
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=30, encoding='utf-8', errors='replace',
        )
    except subprocess.TimeoutExpired:
        return False, [], 'Timeout (>30s) ao consultar GitHub.'
    except Exception as e:
        return False, [], f'Falha ao executar gh: {e}'
    if res.returncode != 0:
        return False, [], (res.stderr or res.stdout or 'Erro desconhecido do gh.').strip()
    try:
        data = json.loads(res.stdout or '[]')
    except json.JSONDecodeError as e:
        return False, [], f'Resposta do gh não é JSON válido: {e}'
    return True, data, ''


# ─────────────────────────────────────────────────────────────
# Renderização da tabela
# ─────────────────────────────────────────────────────────────

def _shorten(text: str, limit: int) -> str:
    text = (text or '').replace('\n', ' ').strip()
    return text if len(text) <= limit else text[: limit - 1] + '…'


def _render_results_table(results: List[Dict[str, Any]]) -> None:
    if not results:
        click.echo(Fore.YELLOW + '\n⚠  Nenhum repositório encontrado com os filtros atuais.' + Style.RESET_ALL)
        click.echo(Style.DIM + '   Dica: tente --any-license ou --min-stars 0.' + Style.RESET_ALL)
        return
    click.echo()
    header = (
        f"{Style.BRIGHT}{'#':<3} │ {'REPOSITÓRIO':<38} │ {'⭐':>7} │ "
        f"{'LINGUAGEM':<12} │ {'LICENÇA':<14} │ {'ATUALIZADO':<10}{Style.RESET_ALL}"
    )
    click.echo(header)
    click.echo(Fore.WHITE + '─' * 3 + '─┼─' + '─' * 38 + '─┼─' + '─' * 7 + '─┼─'
               + '─' * 12 + '─┼─' + '─' * 14 + '─┼─' + '─' * 10 + Style.RESET_ALL)
    for i, repo in enumerate(results, 1):
        name = _shorten(repo.get('fullName', '?'), 38)
        stars = repo.get('stargazersCount', 0)
        lang = _shorten(repo.get('language') or '—', 12)
        lic_obj = repo.get('license') or {}
        lic = _shorten(lic_obj.get('spdxId') or lic_obj.get('name') or '—', 14)
        updated = (repo.get('updatedAt') or '')[:10] or '—'
        lic_lower = lic.lower()
        if any(p in lic_lower for p in ('mit', 'apache', 'bsd', 'isc', 'unlicense')):
            lic_color = Fore.GREEN
        elif any(c in lic_lower for c in ('gpl', 'agpl', 'lgpl', 'mpl')):
            lic_color = Fore.RED
        else:
            lic_color = Fore.YELLOW
        archived = Fore.RED + ' [ARQUIVADO]' + Style.RESET_ALL if repo.get('isArchived') else ''
        click.echo(
            f"{Fore.CYAN}{i:<3}{Style.RESET_ALL} │ "
            f"{Fore.WHITE}{name:<38}{Style.RESET_ALL} │ "
            f"{Fore.YELLOW}{stars:>7,}{Style.RESET_ALL} │ "
            f"{Fore.CYAN}{lang:<12}{Style.RESET_ALL} │ "
            f"{lic_color}{lic:<14}{Style.RESET_ALL} │ "
            f"{Style.DIM}{updated:<10}{Style.RESET_ALL}{archived}"
        )
        desc = repo.get('description')
        if desc:
            click.echo(f"    {Style.DIM}└─ {_shorten(desc, 100)}{Style.RESET_ALL}")
    click.echo()
    click.echo(Style.DIM + '💡 --clone N → clonar o resultado N em ./references/' + Style.RESET_ALL)
    click.echo(Style.DIM + '💡 --open      → abrir o repositório no navegador' + Style.RESET_ALL)
    click.echo(Style.DIM + '💡 --repo OWNER/REPO --contracts → ver assinaturas sem clonar' + Style.RESET_ALL)


# ─────────────────────────────────────────────────────────────
# Clone + metadados
# ─────────────────────────────────────────────────────────────

def _ensure_references_dir(project_root: Path) -> Path:
    ref_dir = project_root / REFERENCES_DIR_NAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    gitignore = project_root / '.gitignore'
    marker = '# Doxoade git-search references'
    entry = f'{REFERENCES_DIR_NAME}/'
    if gitignore.exists():
        content = gitignore.read_text(encoding='utf-8', errors='ignore')
        if entry not in content.splitlines():
            with open(gitignore, 'a', encoding='utf-8') as f:
                f.write(f'\n{marker}\n{entry}\n')
    else:
        gitignore.write_text(f'{marker}\n{entry}\n', encoding='utf-8')
    return ref_dir


def _clone_result(repo_full_name: str, ref_dir: Path) -> Tuple[bool, str, Optional[Path]]:
    safe_name = repo_full_name.replace('/', '__')
    dest = ref_dir / safe_name
    if dest.exists():
        return False, f'Já existe: {dest}', dest
    url = f'https://github.com/{repo_full_name}.git'
    click.echo(Fore.CYAN + f'\n📦 Clonando {repo_full_name} → {dest}...' + Style.RESET_ALL)
    try:
        res = subprocess.run(
            ['git', 'clone', '--depth=1', url, str(dest)],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, 'Timeout (>300s) ao clonar.', None
    if res.returncode != 0:
        return False, (res.stderr or 'erro desconhecido').strip(), None
    return True, 'clone concluído', dest


def _write_ref_metadata(dest: Path, repo: Dict[str, Any]) -> None:
    try:
        commit = _run_git_command(
            ['rev-parse', 'HEAD'], capture_output=True,
            silent_fail=True, cwd=str(dest),
        ) or 'unknown'
    except Exception:
        commit = 'unknown'
    lic_obj = repo.get('license') or {}
    meta = {
        'repo': repo.get('fullName'),
        'url': repo.get('url'),
        'license': lic_obj.get('spdxId') or lic_obj.get('name'),
        'stars': repo.get('stargazersCount', 0),
        'language': repo.get('language'),
        'cloned_at': datetime.now(timezone.utc).isoformat(),
        'commit': commit.strip(),
        'purpose': 'reference_only',
        'study_notes': '',
    }
    (dest / REF_METADATA_FILE).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


# ─────────────────────────────────────────────────────────────
# Setup: instalação e login do gh
# ─────────────────────────────────────────────────────────────

def _detect_package_manager() -> Optional[Tuple[str, List[str]]]:
    import platform
    system = platform.system().lower()
    candidates: List[Tuple[str, str, str]] = []

    if system == 'windows':
        candidates = [
            ('winget', 'winget',
             'winget install --id GitHub.cli -e --source winget '
             '--accept-package-agreements --accept-source-agreements'),
            ('choco', 'choco', 'choco install gh -y'),
            ('scoop', 'scoop', 'scoop install gh'),
        ]
    elif system == 'darwin':
        candidates = [('brew', 'brew', 'brew install gh')]
    else:
        candidates = [
            ('apt',    'apt-get', 'sudo apt-get install -y gh'),
            ('dnf',    'dnf',     'sudo dnf install -y gh'),
            ('yum',    'yum',     'sudo yum install -y gh'),
            ('pacman', 'pacman',  'sudo pacman -S --noconfirm gh'),
            ('apk',    'apk',     'sudo apk add github-cli'),
        ]
    for name, probe, cmd in candidates:
        if shutil.which(probe):
            return name, cmd.split()
    return None


def _install_gh(auto_yes: bool = False) -> Tuple[bool, str]:
    if _gh_installed():
        return True, "GitHub CLI já instalado."
    pm = _detect_package_manager()
    if not pm:
        return False, (
            "Nenhum gerenciador de pacotes suportado encontrado.\n"
            "  ↳ Instale manualmente: https://cli.github.com/"
        )
    name, cmd = pm
    click.echo(f"\n{Fore.CYAN}📦 Gerenciador detectado: {Fore.YELLOW}{name}{Style.RESET_ALL}")
    click.echo(f"  {Style.DIM}Comando: {' '.join(cmd)}{Style.RESET_ALL}")
    if not auto_yes:
        if not click.confirm(Fore.YELLOW + f'\nExecutar "{name} install" agora?' + Style.RESET_ALL):
            return False, "Instalação cancelada pelo usuário."
    click.echo(Fore.CYAN + f'\n🚀 Executando instalação via {name}...' + Style.RESET_ALL)
    try:
        res = subprocess.run(cmd, text=True, timeout=600)
        if res.returncode != 0:
            return False, f'{name} retornou código {res.returncode}.'
    except subprocess.TimeoutExpired:
        return False, 'Timeout (>600s) na instalação.'
    except Exception as e:
        return False, f'Falha ao executar {name}: {e}'
    if _gh_installed():
        return True, f'GitHub CLI instalado via {name}.'
    return False, (
        f'{name} retornou sucesso, mas "gh" não está no PATH.\n'
        '  ↳ Abra um novo terminal ou reinicie o prompt.'
    )


def _login_gh(auto_yes: bool = False) -> Tuple[bool, str]:
    if not _gh_installed():
        return False, 'gh não instalado.'
    try:
        res = subprocess.run(['gh', 'auth', 'status'],
                             capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return True, 'Já autenticado no GitHub.'
    except Exception:
        pass
    if not auto_yes:
        if not click.confirm(Fore.YELLOW + '\nIniciar login via navegador (web) agora?' + Style.RESET_ALL):
            return False, 'Login cancelado.'
    click.echo(Fore.CYAN + '\n🔐 Iniciando login web do GitHub CLI...' + Style.RESET_ALL)
    click.echo(Fore.WHITE + '   ATENÇÃO: O gh exibirá um código de uso único e pedirá para pressionar ENTER.' + Style.RESET_ALL)
    click.echo(Fore.WHITE + '   Se o navegador não abrir, acesse manualmente: https://github.com/login/device' + Style.RESET_ALL)
    click.echo(Fore.WHITE + '   Cole o código exibido no terminal e autorize.\n' + Style.RESET_ALL)
    env = os.environ.copy()
    env['BROWSER'] = 'none'
    env['GH_BROWSER'] = 'none'
    try:
        res = subprocess.run(
            ['gh', 'auth', 'login', '--web', '--git-protocol', 'https'],
            env=env,
        )
        if res.returncode == 0:
            return True, 'Login web concluído com sucesso.'
        return False, f'gh auth login --web retornou código {res.returncode}.'
    except Exception as e:
        return False, f'Falha no login web: {e}'


def _do_check() -> int:
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 [GIT-SEARCH] Diagnóstico do ambiente{Style.RESET_ALL}\n")
    gh_path = shutil.which('gh')
    if gh_path:
        click.echo(f"  {Fore.GREEN}✔ gh instalado:{Style.RESET_ALL} {gh_path}")
        try:
            res = subprocess.run(['gh', '--version'],
                                 capture_output=True, text=True, timeout=5)
            version = (res.stdout or '').splitlines()[0] if res.stdout else '?'
            click.echo(f"  {Fore.WHITE}Versão:{Style.RESET_ALL} {version}")
        except Exception:
            pass
    else:
        click.echo(f"  {Fore.RED}✘ gh NÃO instalado{Style.RESET_ALL}")
        pm = _detect_package_manager()
        if pm:
            click.echo(f"  {Fore.CYAN}💡 Gerenciador disponível:{Style.RESET_ALL} {pm[0]}")
            click.echo(f"  {Fore.CYAN}💡 Para instalar:{Style.RESET_ALL} doxoade git-search --install")
        else:
            click.echo(f"  {Fore.YELLOW}⚠ Nenhum gerenciador suportado detectado.{Style.RESET_ALL}")
            click.echo(f"  ↳ Baixe manualmente: https://cli.github.com/")
        return 1
    try:
        res = subprocess.run(['gh', 'auth', 'status'],
                             capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            click.echo(f"  {Fore.GREEN}✔ Autenticado no GitHub{Style.RESET_ALL}")
            for line in (res.stdout or '').splitlines():
                click.echo(f"  {Style.DIM}{line.strip()}{Style.RESET_ALL}")
            return 0
        click.echo(f"  {Fore.YELLOW}⚠ Não autenticado{Style.RESET_ALL}")
        click.echo(f"  {Fore.CYAN}💡 Para autenticar:{Style.RESET_ALL} doxoade git-search --login")
        return 1
    except Exception as e:
        click.echo(f"  {Fore.RED}✘ Falha ao verificar auth: {e}{Style.RESET_ALL}")
        return 1


# ─────────────────────────────────────────────────────────────
# Navegação remota: árvore, outline, arquivo
# ─────────────────────────────────────────────────────────────

def _get_default_branch(repo: str) -> str:
    """Obtém o branch padrão via gh repo view (main/master/outro)."""
    try:
        res = subprocess.run(
            ['gh', 'repo', 'view', repo,
             '--json', 'defaultBranchRef',
             '--jq', '.defaultBranchRef.name'],
            capture_output=True, text=True, timeout=15,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return 'main'


def _cache_path(project_root: Path, repo: str, suffix: str) -> Path:
    safe = repo.replace('/', '__')
    cache_dir = project_root / CACHE_DIR_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f'{safe}_{suffix}.json'


def _fetch_remote_tree(
    repo: str, branch: str, project_root: Path, use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Lista a árvore completa via git/trees API (com cache local)."""
    cache_file = _cache_path(project_root, repo, f'tree_{branch}')
    if use_cache and cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    try:
        res = subprocess.run(
            ['gh', 'api',
             f'repos/{repo}/git/trees/{branch}?recursive=1',
             '--jq', '.tree[] | {path: .path, type: .type, size: .size}'],
            capture_output=True, text=True, timeout=60,
        )
        if res.returncode != 0:
            click.echo(Fore.RED + f'✘ Falha ao listar árvore: {(res.stderr or "").strip()}' + Style.RESET_ALL)
            return []
        items: List[Dict[str, Any]] = []
        for line in res.stdout.strip().splitlines():
            if line.strip():
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except subprocess.TimeoutExpired:
        click.echo(Fore.RED + '✘ Timeout ao listar árvore (>60s).' + Style.RESET_ALL)
        return []
    except Exception as e:
        click.echo(Fore.RED + f'✘ Falha ao listar árvore: {e}' + Style.RESET_ALL)
        return []

    try:
        cache_file.write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    return items


def _fetch_remote_file(
    repo: str, path: str, branch: str,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """Lê conteúdo de arquivo remoto, com cache local por (repo, path, branch)."""
    import hashlib

    # Cache lookup
    cache_file: Optional[Path] = None
    if project_root is not None:
        key = hashlib.sha256(f'{repo}:{path}:{branch}'.encode()).hexdigest()[:16]
        cache_dir = project_root / CACHE_DIR_NAME / 'content'
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f'{key}.py'
        if cache_file.exists():
            try:
                return cache_file.read_text(encoding='utf-8', errors='replace')
            except Exception:
                pass

    # Fetch remoto
    try:
        res = subprocess.run(
            ['gh', 'api',
             f'repos/{repo}/contents/{path}?ref={branch}',
             '--jq', '.content'],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode != 0:
            click.echo(Fore.RED + f'✘ Falha ao ler arquivo: {(res.stderr or "").strip()}' + Style.RESET_ALL)
            return None
        raw = (res.stdout or '').strip().replace('\n', '')
        content = base64.b64decode(raw).decode('utf-8', errors='replace')
    except Exception as e:
        click.echo(Fore.RED + f'✘ Falha ao decodificar arquivo: {e}' + Style.RESET_ALL)
        return None

    # Cache write
    if cache_file is not None:
        try:
            cache_file.write_text(content, encoding='utf-8')
        except Exception:
            pass
    return content


def _extract_python_outline(source: str, path: str) -> List[Dict[str, Any]]:
    """Extrai funções/classes + docstrings de um arquivo .py via AST."""
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    results: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = 'class' if isinstance(node, ast.ClassDef) else 'function'
            doc = ast.get_docstring(node) or ''
            summary = doc.strip().splitlines()[0] if doc.strip() else ''
            results.append({
                'path': path,
                'name': node.name,
                'kind': kind,
                'line': node.lineno,
                'doc': summary[:120],
            })
    return results


def _render_tree(items: List[Dict[str, Any]], branch: str, path_filter: Optional[str] = None) -> None:
    """Renderiza a árvore remota."""
    if not items:
        click.echo(Fore.YELLOW + '⚠ Nenhum item encontrado na árvore.' + Style.RESET_ALL)
        return

    filtered = items
    if path_filter:
        prefix = path_filter.rstrip('/') + '/'
        filtered = [i for i in items if i['path'].startswith(prefix) or i['path'] == path_filter]

    # Estatísticas
    n_files = sum(1 for i in filtered if i.get('type') == 'blob')
    n_dirs = sum(1 for i in filtered if i.get('type') == 'tree')
    click.echo(f"{Style.DIM}Branch: {branch} │ {n_files} arquivos │ {n_dirs} diretórios{Style.RESET_ALL}\n")

    # Agrupa por diretório
    by_dir: Dict[str, List[Dict[str, Any]]] = {}
    for item in filtered:
        path = item['path']
        if path_filter:
            rel = path[len(path_filter.rstrip('/')):].lstrip('/')
        else:
            rel = path
        if not rel:
            continue
        parts = rel.split('/')
        if len(parts) == 1:
            d = '.' if item.get('type') == 'blob' else parts[0]
        else:
            d = '/'.join(parts[:-1]) if item.get('type') == 'blob' else '/'.join(parts[:-1]) or parts[0]
        by_dir.setdefault(d, []).append(item)

    for d in sorted(by_dir.keys()):
        click.echo(Fore.CYAN + f'📁 {d}/' + Style.RESET_ALL)
        for item in sorted(by_dir[d], key=lambda x: x['path']):
            if path_filter:
                rel = item['path'][len(path_filter.rstrip('/')):].lstrip('/')
            else:
                rel = item['path']
            name = rel.split('/')[-1]
            if item.get('type') == 'tree':
                continue
            size = item.get('size') or 0
            size_str = f'{size / 1024:.1f} KB' if size > 0 else '—'
            click.echo(f"   📄 {Fore.WHITE}{name:<40}{Style.RESET_ALL} {Style.DIM}{size_str:>10}{Style.RESET_ALL}")


def _render_outline(
    repo: str, items: List[Dict[str, Any]], branch: str,
    path_filter: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> None:
    """Lista funções/classes + docstrings dos .py."""
    py_files = [
        i['path'] for i in items
        if i.get('type') == 'blob' and i['path'].endswith('.py')
    ]
    if path_filter:
        prefix = path_filter.rstrip('/') + '/'
        py_files = [p for p in py_files if p.startswith(prefix) or p == path_filter]

    if not py_files:
        click.echo(Fore.YELLOW + '⚠ Nenhum arquivo .py encontrado.' + Style.RESET_ALL)
        return

    click.echo(Fore.CYAN + Style.BRIGHT + f'📋 Outline de {len(py_files)} arquivo(s) .py' + Style.RESET_ALL)
    click.echo(Style.DIM + f'   Branch: {branch}{Style.RESET_ALL}\n')

    total_symbols = 0
    for py_file in py_files:
        source = _fetch_remote_file(repo, py_file, branch, project_root=project_root)
        if source is None:
            click.echo(Fore.RED + f'  ✘ {py_file} (falha ao ler)' + Style.RESET_ALL)
            continue
        symbols = _extract_python_outline(source, py_file)
        if not symbols:
            continue
        total_symbols += len(symbols)
        click.echo(Fore.CYAN + f'📄 {py_file}' + Style.RESET_ALL)
        for sym in symbols:
            kind_color = Fore.MAGENTA if sym['kind'] == 'class' else Fore.GREEN
            kind_tag = 'class' if sym['kind'] == 'class' else 'func '
            doc_str = f"  {Style.DIM}\"{sym['doc']}\"{Style.RESET_ALL}" if sym['doc'] else ''
            click.echo(
                f"   {Style.DIM}L{sym['line']:<4}{Style.RESET_ALL} "
                f"{kind_color}{kind_tag}{Style.RESET_ALL} "
                f"{Fore.WHITE}{sym['name']:<35}{Style.RESET_ALL}"
                f"{doc_str}"
            )
        click.echo()

    click.echo(Style.DIM + f'Total: {total_symbols} símbolo(s) em {len(py_files)} arquivo(s)' + Style.RESET_ALL)


# ─────────────────────────────────────────────────────────────
# Comando principal
# ─────────────────────────────────────────────────────────────

@click.command('git-search')
@click.argument('query', required=False)
@click.option('--language', '-l', help='Filtra por linguagem (python, c, cpp, rust, go).')
@click.option('--limit', '-n', default=15, type=int, show_default=True,
              help='Número máximo de resultados.')
@click.option('--sort', type=click.Choice(['stars', 'forks', 'updated', 'best-match']),
              default='stars', show_default=True, help='Critério de ordenação.')
@click.option('--min-stars', default=0, type=int, help='Mínimo de estrelas.')
@click.option('--updated-after', help='Data mínima de atualização (YYYY-MM-DD).')
@click.option('--liberal/--any-license', default=True, show_default=True,
              help='Restringe a licenças permissivas (MIT/Apache/BSD/ISC).')
@click.option('--exclude-copyleft/--no-exclude', default=True, show_default=True,
              help='Exclui GPL/AGPL/LGPL da busca (pós-filtro em Python).')
@click.option('--exclude-tests', is_flag=True,
              help='Exclui tests/, docs/examples/, conftest.py do --outline/--contracts.')
@click.option('--json', 'output_json', is_flag=True, help='Saída em JSON.')
@click.option('--clone', '-c', 'clone_index', type=int, default=None,
              help='Clona o resultado N (1-based) para ./references/.')
@click.option('--open', 'open_browser', is_flag=True,
              help='Abre o repositório no navegador.')
@click.option('--readme', 'show_readme', is_flag=True,
              help='Exibe um resumo do README do primeiro resultado.')
@click.option('--install', 'do_install', is_flag=True,
              help='Instala o GitHub CLI (gh) via gerenciador nativo.')
@click.option('--login', 'do_login', is_flag=True,
              help='Inicia "gh auth login" (web) após verificar instalação.')
@click.option('--setup', 'do_setup', is_flag=True,
              help='Atalho: --install + --login (setup completo).')
@click.option('--check', 'do_check', is_flag=True,
              help='Apenas verifica se gh está instalado e autenticado.')
@click.option('--yes', '-y', 'auto_yes', is_flag=True,
              help='Não pede confirmação em operações de instalação.')
@click.option('--repo', 'target_repo', default=None,
              help='Repositório alvo (OWNER/REPO) para navegação remota.')
@click.option('--tree', 'do_tree', is_flag=True,
              help='Lista a árvore completa do repositório remoto.')
@click.option('--outline', 'do_outline', is_flag=True,
              help='Lista funções/classes + docstrings dos .py remotos.')
@click.option('--file', 'file_path', default=None,
              help='Lê um arquivo específico do repositório remoto.')
@click.option('--path', 'path_filter', default=None,
              help='Filtra --tree/--outline por subdiretório.')
@click.option('--branch', default=None,
              help='Branch específico (padrão: detecta automaticamente).')
@click.option('--no-cache', is_flag=True,
              help='Ignora cache local da árvore.')
@click.option('--contracts', 'do_contracts', is_flag=True,
              help='Lista contratos públicos (assinaturas) dos .py remotos.')
@click.pass_context
def git_search(
    ctx,
    query: Optional[str],
    language: Optional[str],
    limit: int,
    sort: str,
    min_stars: int,
    updated_after: Optional[str],
    liberal: bool,
    exclude_copyleft: bool,
    output_json: bool,
    clone_index: Optional[int],
    open_browser: bool,
    show_readme: bool,
    do_install: bool,
    do_login: bool,
    do_setup: bool,
    do_check: bool,
    auto_yes: bool,
    target_repo: Optional[str],
    do_tree: bool,
    do_outline: bool,
    file_path: Optional[str],
    path_filter: Optional[str],
    branch: Optional[str],
    no_cache: bool,
    do_contracts: bool,
    exclude_tests: bool,
):
    project_root = Path(os.getcwd())

    # ── Modos de setup (não exigem query) ──────────────────
    if do_check: sys.exit(_do_check())

    # ── Clone direto (sem busca) ─────────────────────────
    if clone_index is not None and target_repo and not query:
        with ExecutionLogger('git-search-clone', str(project_root), ctx.params) as logger:
            ok, err = _check_gh_available()
            if not ok:
                click.echo(Fore.RED + '\n✘ [GIT-SEARCH] ' + err + Style.RESET_ALL)
                sys.exit(1)

            # Usa REST API (gh api) em vez de GraphQL (gh repo view)
            try:
                meta_res = subprocess.run(
                    ['gh', 'api', f'repos/{target_repo}'],
                    capture_output=True, text=True, timeout=20,
                )
                if meta_res.returncode != 0:
                    err_msg = (meta_res.stderr or meta_res.stdout or '').strip()
                    click.echo(Fore.RED + f'✘ Repositório não encontrado: {target_repo}' + Style.RESET_ALL)
                    if err_msg:
                        click.echo(Style.DIM + f'  {err_msg[:200]}' + Style.RESET_ALL)
                    sys.exit(1)
                raw = json.loads(meta_res.stdout)
            except Exception as e:
                click.echo(Fore.RED + f'✘ Falha ao consultar repo: {e}' + Style.RESET_ALL)
                sys.exit(1)

            # REST retorna snake_case: full_name, stargazers_count, etc.
            full_name = raw.get('full_name') or target_repo
            repo_meta = {
                'fullName': full_name,
                'url': raw.get('html_url') or f'https://github.com/{full_name}',
                'stargazersCount': raw.get('stargazers_count', 0),
                'language': raw.get('language'),
                'license': raw.get('license') or {},
                'isArchived': raw.get('archived', False),
                'isFork': raw.get('fork', False),
            }

            ref_dir = _ensure_references_dir(project_root)
            ok, msg, dest = _clone_result(full_name, ref_dir)
            if not ok:
                click.echo(Fore.RED + f'✘ Clone falhou: {msg}' + Style.RESET_ALL)
                sys.exit(1)
            _write_ref_metadata(dest, repo_meta)
            click.echo(Fore.GREEN + f'✔ Clone concluído: {dest}' + Style.RESET_ALL)
            click.echo(Style.DIM + f'  Metadados: {dest / REF_METADATA_FILE}' + Style.RESET_ALL)
            return

    # ── Clone direto (sem busca) ─────────────────────────
    if clone_index is not None and target_repo and not query:
        with ExecutionLogger('git-search-clone', str(project_root), ctx.params) as logger:
            ok, err = _check_gh_available()
            if not ok:
                click.echo(Fore.RED + '\n✘ [GIT-SEARCH] ' + err + Style.RESET_ALL)
                sys.exit(1)

            # Obtém metadados do repo via gh api (sem busca)
            try:
                meta_res = subprocess.run(
                    ['gh', 'repo', 'view', target_repo,
                     '--json', 'nameWithOwner,description,stargazersCount,'
                               'forksCount,licenseInfo,primaryLanguage,url,'
                               'isArchived,isFork,updatedAt'],
                    capture_output=True, text=True, timeout=20,
                )
                if meta_res.returncode != 0:
                    click.echo(Fore.RED + f'✘ Repositório não encontrado: {target_repo}' + Style.RESET_ALL)
                    sys.exit(1)
                raw_meta = json.loads(meta_res.stdout)
            except Exception as e:
                click.echo(Fore.RED + f'✘ Falha ao consultar repo: {e}' + Style.RESET_ALL)
                sys.exit(1)

            # Normaliza para o formato esperado por _write_ref_metadata
            repo_meta = {
                'fullName': raw_meta.get('nameWithOwner'),
                'url': raw_meta.get('url'),
                'stargazersCount': raw_meta.get('stargazersCount', 0),
                'language': (raw_meta.get('primaryLanguage') or {}).get('name'),
                'license': raw_meta.get('licenseInfo') or {},
                'isArchived': raw_meta.get('isArchived', False),
                'isFork': raw_meta.get('isFork', False),
            }

            ref_dir = _ensure_references_dir(project_root)
            ok, msg, dest = _clone_result(target_repo, ref_dir)
            if not ok:
                click.echo(Fore.RED + f'✘ Clone falhou: {msg}' + Style.RESET_ALL)
                sys.exit(1)
            _write_ref_metadata(dest, repo_meta)
            click.echo(Fore.GREEN + f'✔ Clone concluído: {dest}' + Style.RESET_ALL)
            click.echo(Style.DIM + f'  Metadados: {dest / REF_METADATA_FILE}' + Style.RESET_ALL)
            return

    if do_install or do_login or do_setup:
        with ExecutionLogger('git-search-setup', str(project_root), ctx.params) as logger:
            ok = True
            if do_setup or do_install:
                ok_inst, msg = _install_gh(auto_yes=auto_yes)
                click.echo((Fore.GREEN + '✔ ' if ok_inst else Fore.RED + '✘ ') + msg + Style.RESET_ALL)
                ok = ok and ok_inst
                if not ok_inst:
                    logger.add_finding('error', msg)
            if ok and (do_setup or do_login):
                ok_log, msg = _login_gh(auto_yes=auto_yes)
                click.echo((Fore.GREEN + '✔ ' if ok_log else Fore.RED + '✘ ') + msg + Style.RESET_ALL)
                ok = ok and ok_log
                if not ok_log:
                    logger.add_finding('error', msg)
        sys.exit(0 if ok else 1)

    # ── Modos de navegação remota (exigem --repo) ─────────
    nav_mode = do_tree or do_outline or file_path is not None or do_contracts
    if nav_mode:
        if not target_repo:
            click.echo(Fore.RED + '[ERRO] --tree/--outline/--file exigem --repo OWNER/REPO.' + Style.RESET_ALL)
            sys.exit(1)

        with ExecutionLogger('git-search-nav', str(project_root), ctx.params) as logger:
            ok, err = _check_gh_available()
            if not ok:
                click.echo(Fore.RED + '\n✘ [GIT-SEARCH] ' + err + Style.RESET_ALL)
                logger.add_finding('error', err)
                sys.exit(1)

            # Detecta branch
            detected_branch = branch or _get_default_branch(target_repo)
            click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [GIT-SEARCH] {Fore.WHITE}v{__version__}{Style.RESET_ALL}")
            click.echo(f"  {Fore.WHITE}Repo   :{Style.RESET_ALL} {Fore.YELLOW}{target_repo}{Style.RESET_ALL}")
            click.echo(f"  {Fore.WHITE}Branch :{Style.RESET_ALL} {Fore.CYAN}{detected_branch}{Style.RESET_ALL}")
            if path_filter:
                click.echo(f"  {Fore.WHITE}Filtro :{Style.RESET_ALL} {path_filter}")
            click.echo()

            # --file tem prioridade (não precisa de árvore)
            if file_path is not None:
                content = _fetch_remote_file(
                    target_repo, file_path, detected_branch,
                    project_root=project_root,
                )
                if content is None:
                    logger.add_finding('error', f'Arquivo não encontrado: {file_path}')
                    sys.exit(1)
                click.echo(Fore.CYAN + f'📄 {file_path}' + Style.RESET_ALL)
                click.echo(Fore.WHITE + '─' * 60 + Style.RESET_ALL)
                for i, line in enumerate(content.splitlines(), 1):
                    click.echo(f"{Style.DIM}{i:>4}{Style.RESET_ALL} │ {line}")
                click.echo(Fore.WHITE + '─' * 60 + Style.RESET_ALL)
                click.echo(Style.DIM + f'{len(content.splitlines())} linhas | {len(content)} bytes' + Style.RESET_ALL)
                return

            # --tree / --outline precisam da árvore
            items = _fetch_remote_tree(target_repo, detected_branch, project_root,
                                       use_cache=not no_cache)
            if not items:
                logger.add_finding('error', 'Falha ao obter árvore remota.')
                sys.exit(1)

            if do_tree:
                _render_tree(items, detected_branch, path_filter)
            if do_outline:
                _render_outline(
                    target_repo, items, detected_branch,
                    path_filter, project_root=project_root,
                )
            if do_contracts:
                _render_remote_contracts(
                    target_repo, items, detected_branch,
                    path_filter=path_filter,
                    exclude_tests=exclude_tests,
                    project_root=project_root,
                )

            logger.add_finding('info',
                               f'Navegação remota: {target_repo}@{detected_branch}',
                               category='GIT-SEARCH')
        return

    # ── Fluxo normal (busca) ───────────────────────────────
    with ExecutionLogger('git-search', str(project_root), ctx.params) as logger:
        if (open_browser or clone_index is not None or show_readme) and not query and not target_repo:
            click.echo(Fore.RED + '[ERRO] Use --repo OWNER/REPO junto de --clone.' + Style.RESET_ALL)
            sys.exit(1)
        if not query and not target_repo:
            click.echo(ctx.get_help())
            return

        ok, err = _check_gh_available()
        if not ok:
            click.echo(Fore.RED + '\n✘ [GIT-SEARCH] ' + err + Style.RESET_ALL)
            logger.add_finding('error', err)
            sys.exit(1)

        license_filter = _build_license_filter(liberal)
        final_query = _build_search_query(
            query=query, language=language, min_stars=min_stars,
            updated_after=updated_after, exclude_copyleft=exclude_copyleft,
        )

        click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}☤ [GIT-SEARCH] {Fore.WHITE}v{__version__}{Style.RESET_ALL}")
        click.echo(f"  {Fore.WHITE}Query    :{Style.RESET_ALL} {final_query}")
        click.echo(f"  {Fore.WHITE}Licenças :{Style.RESET_ALL} "
                   f"{Fore.GREEN}{license_filter or '(qualquer)'}{Style.RESET_ALL}")
        if exclude_copyleft:
            click.echo(f"  {Fore.WHITE}Excluindo:{Style.RESET_ALL} "
                       f"{Fore.RED}{', '.join(COPYLEFT_LICENSES)}{Style.RESET_ALL}")
        click.echo()

        success, results, err = _run_gh_search(final_query, license_filter, limit, sort)
        if not success:
            click.echo(Fore.RED + f'✘ Falha na busca: {err}' + Style.RESET_ALL)
            logger.add_finding('error', f'gh search falhou: {err}')
            sys.exit(1)

        if exclude_copyleft:
            before = len(results)
            results = _filter_copyleft(results)
            if len(results) < before:
                click.echo(Style.DIM + f'   (filtro pós-busca: {before - len(results)} repo(s) copyleft descartado(s))' + Style.RESET_ALL)

        if output_json:
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
            return

        _render_results_table(results)
        if not results:
            return

        if clone_index is not None:
            if not (1 <= clone_index <= len(results)):
                click.echo(Fore.RED + f'[ERRO] --clone deve estar entre 1 e {len(results)}.' + Style.RESET_ALL)
                sys.exit(1)
            target = results[clone_index - 1]
            ref_dir = _ensure_references_dir(project_root)
            ok, msg, dest = _clone_result(target['fullName'], ref_dir)
            if not ok:
                click.echo(Fore.RED + f'✘ Clone falhou: {msg}' + Style.RESET_ALL)
                logger.add_finding('error', msg)
                sys.exit(1)
            _write_ref_metadata(dest, target)
            click.echo(Fore.GREEN + f'✔ Clone concluído: {dest}' + Style.RESET_ALL)
            click.echo(Style.DIM + f'  Metadados: {dest / REF_METADATA_FILE}' + Style.RESET_ALL)

        if open_browser:
            url = results[0].get('url')
            if url:
                click.echo(Fore.CYAN + f'\n🌐 Abrindo {url}' + Style.RESET_ALL)
                webbrowser.open(url)

        if show_readme:
            first = results[0]['fullName']
            click.echo(Fore.CYAN + f'\n📖 README de {first}:' + Style.RESET_ALL)
            try:
                res = subprocess.run(
                    ['gh', 'repo', 'view', first,
                     '--json', 'description,homepageUrl,licenseInfo,primaryLanguage'],
                    capture_output=True, text=True, timeout=20,
                )
                if res.returncode == 0:
                    data = json.loads(res.stdout)
                    click.echo(f"  {Fore.WHITE}Descrição:{Style.RESET_ALL} {data.get('description') or '—'}")
                    hp = data.get('homepageUrl')
                    if hp:
                        click.echo(f"  {Fore.WHITE}Homepage :{Style.RESET_ALL} {hp}")
                    lic = (data.get('licenseInfo') or {}).get('spdxId') or '—'
                    click.echo(f"  {Fore.WHITE}Licença  :{Style.RESET_ALL} {lic}")
                    lang = (data.get('primaryLanguage') or {}).get('name') or '—'
                    click.echo(f"  {Fore.WHITE}Linguagem:{Style.RESET_ALL} {lang}")
                else:
                    click.echo(Style.DIM + '  (não foi possível obter o README)' + Style.RESET_ALL)
            except Exception as e:
                click.echo(Fore.YELLOW + f'  ⚠ Falha ao consultar README: {e}' + Style.RESET_ALL)

        logger.add_finding(
            'info',
            f'Busca "{query}" retornou {len(results)} resultado(s).',
            category='GIT-SEARCH',
        )

def _render_remote_contracts(
    repo: str,
    items: List[Dict[str, Any]],
    branch: str,
    path_filter: Optional[str] = None,
    exclude_tests: bool = False,
    project_root: Optional[Path] = None,
) -> None:
    """Extrai e exibe contratos públicos dos .py remotos (sem clonar)."""
    from doxoade.commands.impact_systems.impact_contracts import extract_contracts
    import ast

    py_files = [
        i['path'] for i in items
        if i.get('type') == 'blob' and i['path'].endswith('.py')
    ]
    if path_filter:
        prefix = path_filter.rstrip('/') + '/'
        py_files = [p for p in py_files if p.startswith(prefix) or p == path_filter]
    if exclude_tests:
        py_files = [p for p in py_files
                    if not any(pat in p for pat in _EXCLUDE_CONTRACT_PATTERNS)]

    if not py_files:
        click.echo(Fore.YELLOW + '⚠ Nenhum arquivo .py encontrado.' + Style.RESET_ALL)
        return

    click.echo(Fore.CYAN + Style.BRIGHT
               + f'📋 Contratos públicos de {len(py_files)} arquivo(s) .py'
               + Style.RESET_ALL)
    click.echo(Style.DIM + f'   Branch: {branch}{Style.RESET_ALL}\n')

    total_contracts = 0
    total_files_with_contracts = 0
    skipped_files = 0
    for py_file in py_files:
        source = _fetch_remote_file(repo, py_file, branch, project_root=project_root)
        if source is None:
            skipped_files += 1
            continue
        try:
            tree = ast.parse(source, filename=py_file)
        except SyntaxError:
            skipped_files += 1
            continue
        contracts = extract_contracts(tree, py_file)
        if not contracts:
            continue
        total_contracts += len(contracts)
        total_files_with_contracts += 1
        click.echo(Fore.CYAN + f'📄 {py_file}' + Style.RESET_ALL)
        for name, c in sorted(contracts.items()):
            param_parts = []
            for p in c['params']:
                ptype = p['type'] or 'Any'
                pdef = f" = {p['default']}" if p['default'] else ''
                param_parts.append(f"{Fore.WHITE}{p['name']}{Style.RESET_ALL}: "
                                   f"{Fore.CYAN}{ptype}{Style.RESET_ALL}{pdef}")
            params_str = ', '.join(param_parts)
            ret = c['returns'] or 'Any'
            async_pfx = f"{Fore.MAGENTA}async {Style.RESET_ALL}" if c['is_async'] else ''
            raises_str = ''
            if c['raises']:
                raises_str = f" {Fore.RED}raises ({', '.join(c['raises'])}){Style.RESET_ALL}"
            click.echo(
                f"   {Fore.GREEN}ƒ {async_pfx}{name}{Style.RESET_ALL}"
                f"({params_str}) -> {Fore.YELLOW}{ret}{Style.RESET_ALL}{raises_str}"
            )
        click.echo()

    summary = (f'Total: {total_contracts} contrato(s) em '
               f'{total_files_with_contracts} arquivo(s) .py')
    if skipped_files:
        summary += f' ({skipped_files} arquivo(s) ignorado(s) por erro)'
    click.echo(Style.DIM + summary + Style.RESET_ALL)

