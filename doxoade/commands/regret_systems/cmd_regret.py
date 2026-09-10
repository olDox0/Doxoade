# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/cmd_regret.py
"""
⚡ Comando CLI Click para o Doxoade Regret — Auditoria de Regressões.
Suporta arquivos existentes, deletados (Git/Backup) e refatorações Split/Merge.
"""

from __future__ import annotations
import sys
from pathlib import Path
import click
from doxoade.tools.doxcolors import Fore, Style

try:
    from doxoade.commands.regret_systems.regret_engine import RegretEngine
except ImportError:
    from .regret_engine import RegretEngine


@click.command("regret", help="📉 Detecta regressões semânticas, perdas de UX e comandos extirpados.")
@click.argument("target", required=False, type=click.Path(exists=False))
@click.option(
    "--base", "-b",
    default=None,
    help="Revisão Git base para comparação (ex: origin/main, HEAD~1, f47460f)."
)
@click.option(
    "--backup", "-B", "backup_id",
    is_flag=False,
    flag_value="__LATEST__",
    default=None,
    help="Compara contra o Doxoade Backup em vez do Git (suporta arquivos deletados)."
)
@click.option(
    "--commits", "-n",
    default=1,
    help="Número de commits no passado caso --base não seja informado (Padrão: 1)."
)
@click.option(
    "--dump", "-d",
    is_flag=True,
    help="Salva todos os trechos e métodos extirpados no .doxoade/dumppot.txt."
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Modo silencioso (apenas sumário)."
)
def regret_group(target: str | None, base: str | None, backup_id: str | None, commits: int, dump: bool, quiet: bool):
    """Audita a perda de capacidades entre revisões de código e backups."""
    try:
        use_backup = backup_id is not None
        actual_backup_id = None if backup_id == "__LATEST__" else backup_id

        report = RegretEngine.run_suite(
            target_path=target,
            base_revision=base,
            use_backup=use_backup,
            backup_id=actual_backup_id,
            commits_back=commits,
            dump_to_pot=dump,
            verbose=not quiet
        )
        if report["total_regressions"] > 0:
            sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}✖ Falha ao executar doxoade regret: {e}{Fore.RESET}")
        sys.exit(1)
