# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/__init__.py
""" 📦 Pacote de Análise de Regressões Semânticas e Forense de Git — Doxoade Regret. """

from __future__ import annotations

try:
    from doxoade.commands.regret_systems.regret_git_reader import RegretGitReader
    from doxoade.commands.regret_systems.regret_backup_reader import RegretBackupReader
    from doxoade.commands.regret_systems.regret_lua_inspector import RegretLuaInspector
    from doxoade.commands.regret_systems.regret_python_inspector import RegretPythonInspector
    from doxoade.commands.regret_systems.regret_reporter import RegretReporter
    from doxoade.commands.regret_systems.regret_engine import RegretEngine
    from doxoade.commands.regret_systems.cmd_regret import regret_group
except ImportError:
    from .regret_git_reader import RegretGitReader
    from .regret_backup_reader import RegretBackupReader
    from .regret_lua_inspector import RegretLuaInspector
    from .regret_python_inspector import RegretPythonInspector
    from .regret_reporter import RegretReporter
    from .regret_engine import RegretEngine
    from .cmd_regret import regret_group

__all__ = [
    "RegretGitReader",
    "RegretBackupReader",
    "RegretLuaInspector",
    "RegretPythonInspector",
    "RegretReporter",
    "RegretEngine",
    "regret_group",
]
