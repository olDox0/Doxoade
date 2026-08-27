# -*- coding: utf-8 -*-
# doxoade/commands/timeline_systems/tml_data/project_resolver.py
""" Timeline Nexus - Detector de Projetos Hospedeiros.
Extrai o nome canônico do projeto com filtro inteligente de fixtures de teste. """

import os
from pathlib import Path
from typing import Optional

_SUBFOLDER_IGNORE = {
    'venv', 'scripts', 'bin', 'lib', 'src', 'tests', 'test',
    'regression_tests', 'fixtures', 'pytest_temp_dir',
    'bricks', 'data', 'logs', 'output', 'build', 'dist',
    '.doxoade', '.git', '__pycache__', '.pytest_cache',
    'site-packages', 'tmp'
}

_KNOWN_FIXTURE_PREFIXES = (
    'test_', 'project_syntax_', 'project_healthy', 'projeto_de_teste', 'test_project'
)


def resolve_project_name(raw_path: Optional[str]) -> str:
    """
    Identifica o nome real do projeto hospedeiro (ex: sysutils, doxoade).
    Descarta pastas temporárias de teste e as colapsa no projeto real.
    """
    if not raw_path or raw_path in ('.', '', 'N/A'):
        return 'doxoade'

    # Normaliza separadores
    p_str = raw_path.replace('\\', '/').rstrip('/')

    # 1. Se o caminho faz parte da suite de testes de um projeto-mãe:
    # Ex: C:/.../doxoade/tests/fixtures/test_syntax -> doxoade
    for test_marker in ('/tests/', '/regression_tests/', '/pytest_temp_dir/'):
        if test_marker in p_str.lower():
            idx = p_str.lower().find(test_marker)
            base = p_str[:idx].rstrip('/')
            if base:
                return os.path.basename(base)

    # 2. Se contém /venv/, a pasta mãe do venv é o projeto
    if '/venv' in p_str.lower():
        idx = p_str.lower().find('/venv')
        base = p_str[:idx].rstrip('/')
        if base:
            return os.path.basename(base)

    # 3. Se o caminho ainda existe fisicamente no disco, tenta achar a raiz via marcadores
    p = Path(p_str)
    if p.exists():
        curr = p if p.is_dir() else p.parent
        for parent in [curr, *curr.parents]:
            if any((parent / marker).exists() for marker in ('.git', 'pyproject.toml', 'setup.py', '.doxoade')):
                return parent.name
        return curr.name

    # 4. Fallback de subpastas de trás para frente
    parts = [seg for seg in p_str.split('/') if seg and ':' not in seg]
    while parts and (parts[-1].lower() in _SUBFOLDER_IGNORE or parts[-1].lower().startswith(_KNOWN_FIXTURE_PREFIXES)):
        parts.pop()

    name = parts[-1] if parts else 'doxoade'
    
    # Tratamento final para nomes de fixtures isoladas
    if name.lower().startswith(_KNOWN_FIXTURE_PREFIXES):
        return 'doxoade'

    return name


def get_current_project_name() -> str:
    """Identifica o nome do projeto onde o terminal está posicionado atualmente."""
    return resolve_project_name(os.getcwd())
