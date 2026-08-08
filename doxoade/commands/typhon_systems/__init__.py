# doxoade/doxoade/commands/typhon_systems/__init__.py
# -*- coding: utf-8 -*-

from doxoade.commands.typhon_systems.typhon_tree import TREE
from doxoade.commands.typhon_systems.typhon_chaos import INJECTORS, run_chaos_suite, print_tree
from doxoade.commands.typhon_systems.typhon_probes import run_all_probes
from doxoade.commands.typhon_systems.typhon_consolidated import (
    check,
    chaos,
    probe,
    tree,
    report,
)
from doxoade.commands.typhon_systems.typhon_cmd import typhon

# Compatibilidade, se o lazy loader esperar `cli`
cli = typhon

__all__ = [
    "TREE",
    "INJECTORS",
    "run_chaos_suite",
    "print_tree",
    "run_all_probes",
    "check",
    "chaos",
    "probe",
    "tree",
    "report",
    "typhon",
    "cli",
]
