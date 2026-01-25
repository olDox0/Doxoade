# -*- coding: utf-8 -*-
"""
Debug Utils - PASC-1.2 & MPoT-17.
Environment anchoring and probe orchestration.
"""
import os
# [DOX-UNUSED] import sys
from ..shared_tools import _find_project_root

def get_debug_env(script_path: str) -> dict:
    """Calcula o ambiente com Injeção de Âncora do Core (MPoT-10)."""
    target_abs = os.path.abspath(script_path)
    project_root = _find_project_root(target_abs)
    
    # 1. Localiza a instalação física do Doxoade
    # doxoade/commands/debug_utils.py -> doxoade/ -> (dir_pai_que_contem_o_pacote)
    doxo_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doxo_anchor = os.path.dirname(doxo_pkg_dir)

    env = os.environ.copy()
    # PASC-6.5: Adiciona a âncora do Doxoade e a raiz do projeto ao PYTHONPATH
    env["PYTHONPATH"] = (
        doxo_anchor + os.pathsep + 
        os.path.dirname(project_root) + os.pathsep + 
        env.get("PYTHONPATH", "")
    )
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def build_probe_command(python_exe: str, probe_file: str, script: str, **kwargs) -> list:
    """Constrói o comando da sonda com argumentos dinâmicos."""
    cmd = [python_exe, probe_file, script]
    
    watch = kwargs.get('watch')
    bottleneck = kwargs.get('bottleneck')
    threshold = kwargs.get('threshold')
    extra_args = kwargs.get('args')

    if watch: cmd.extend(["--watch", watch])
    if bottleneck: cmd.extend(["--slow", str(threshold)])
    if extra_args: cmd.extend(extra_args.split())
    
    return cmd