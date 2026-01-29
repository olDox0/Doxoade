# -*- coding: utf-8 -*-
"""
Debug Utils - PASC-1.2 & MPoT-17.
Environment anchoring and probe orchestration.
"""
import os
import sys
from ..shared_tools import _find_project_root

def get_debug_env(script_path: str) -> dict:
    """Injeta a âncora do Doxoade e a raiz do projeto no ambiente filho."""
    target_abs = os.path.abspath(script_path)
    project_root = _find_project_root(target_abs)
    
    # Localiza onde o Doxoade está instalado fisicamente
    # Sobe 2 níveis a partir de commands/debug_utils.py para chegar na raiz do pacote
    doxo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    env = os.environ.copy()
    # Adiciona a pasta PAI do doxoade para que 'import doxoade' funcione
    # Adiciona a pasta do projeto atual para que imports locais funcionem
    env["PYTHONPATH"] = os.pathsep.join([
        doxo_dir,
        os.path.dirname(project_root) if project_root else os.path.dirname(target_abs),
        env.get("PYTHONPATH", "")
    ])
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def build_probe_command(python_exe: str, probe_file: str, script: str, **kwargs) -> list:
    """Constrói o comando garantindo caminhos absolutos para evitar o 'Aborted!'."""
    # Garante que o caminho da sonda e do script sejam absolutos
    cmd = [python_exe, os.path.abspath(probe_file), os.path.abspath(script)]
    
    if kwargs.get('watch'): cmd.extend(["--watch", kwargs['watch']])
    if kwargs.get('bottleneck'): cmd.extend(["--slow", str(kwargs.get('threshold', 100))])
    if kwargs.get('args'): cmd.extend(kwargs['args'].split())
    
    return cmd