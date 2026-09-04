# -*- coding: utf-8 -*-
# doxoade/doxoade/commands/typhon_systems/__init__.py
""" Fachada Pública do Typhon Doxly Engine.
Expõe motores de Árvore, Probes, Caos e Triangulação para ecossistema Lite XL. """

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

# Sys typhon doxly
from .doxly_tree import DOXLY_TREE, DoxlyDiagnosticTree, DoxlyFailureMode
from .doxly_probes import run_all_doxly_probes, DoxlyProbeReport
from .doxly_chaos import run_doxly_chaos_suite
from .doxly_triangulator import DoxlyTriangulator, TriangulationVerdict

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
    # Sys Typhon Dox
    "DOXLY_TREE",
    "DoxlyDiagnosticTree",
    "DoxlyFailureMode",
    "run_all_doxly_probes",
    "DoxlyProbeReport",
    "run_doxly_chaos_suite",
    "DoxlyTriangulator",
    "TriangulationVerdict",
]
