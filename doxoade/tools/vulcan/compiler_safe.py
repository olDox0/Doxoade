# doxoade/doxoade/tools/vulcan/compiler_safe.py
import subprocess
import sys
import shutil
from pathlib import Path
import os

def _find_setup_dir(start: Path, stop_at: Path | None=None) -> Path | None:
    """
    Sobe a árvore procurando por setup.py (ou pyproject.toml) a partir de `start`
    até `stop_at` (inclusive). Retorna o Path da pasta que contém o setup, ou None.
    """
    cur = start.resolve()
    stop = stop_at.resolve() if stop_at else None
    while True:
        if (cur / 'setup.py').exists() or (cur / 'pyproject.toml').exists():
            return cur
        if stop and cur == stop:
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None

def compile_module(module_dir: Path, out_dir: Path, project_root: Path | None=None):
    """
    Compila módulos nativos de forma segura.
    - module_dir: pasta do módulo (pode ser o package folder)
    - out_dir: staging output (não escreve diretamente no bin/)
    - project_root: pasta raiz do projeto (opcional)
    """
    module_dir = Path(module_dir)
    out_dir = Path(out_dir)
    project_root = Path(project_root) if project_root else None
    if not module_dir.exists():
        raise FileNotFoundError(f'module_dir does not exist: {module_dir}')
    setup_dir = _find_setup_dir(module_dir, stop_at=project_root)
    if not setup_dir:
        raise RuntimeError(f'No setup.py or pyproject.toml found for module at {module_dir}. Provide a module_src_dir that contains a build entry (setup.py or pyproject.toml).')
    build_dir = setup_dir / 'build'
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    try:
        if (setup_dir / 'setup.py').exists():
            cmd = [sys.executable, 'setup.py', 'build_ext', '--inplace']
        else:
            cmd = [sys.executable, '-m', 'build', '--wheel', '--outdir', str(out_dir)]
    except subprocess.CalledProcessError as e:
        out = getattr(e, 'stdout', '') or ''
        err = getattr(e, 'stderr', '') or ''
        raise RuntimeError(f'Build failed in {setup_dir}. stdout:\n{out}\nstderr:\n{err}') from e
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = '.pyd' if os.name == 'nt' else '.so'
    moved = []
    candidates = list(module_dir.glob(f'**/*{ext}')) + list(setup_dir.glob(f'**/*{ext}'))
    for cand in candidates:
        try:
            dst = out_dir / cand.name
            shutil.move(str(cand), str(dst))
            moved.append(dst)
        except Exception:
            continue
    if not moved:
        raise RuntimeError(f'Build reported success but no {ext} artifacts were found (searched in {module_dir} and {setup_dir}).')
    return moved