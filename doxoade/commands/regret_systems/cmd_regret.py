# -*- coding: utf-8 -*-
# doxoade/commands/regret_systems/cmd_regret.py
"""
⚡ Comando CLI Click para o Doxoade Regret — Auditoria de Regressões, Orfandade e Proveniência.
Suporta arquivos existentes, deletados, histórico de linhagem e snippets forenses (-s/--snippet).
Compliance: ProDeNov 1.2.1 | PASC-6.1
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


@click.command("regret", help="📉 Detecta regressões semânticas, perdas de UX, comandos extirpados, órfãos e linhagem ancestral.")
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
    "--orphans/--no-orphans", "-O/-nO",
    default=True,
    help="🧩 Executa auditoria de funcionalidades órfãs (Padrão: True)."
)
@click.option(
    "--provenance", "-P",
    is_flag=True,
    default=False,
    help="🏛️ Executa auditoria de proveniência e linhagem ancestral (detecta vazamentos em splits de God Classes e templates)."
)
@click.option(
    "--snippet", "-s", "--snippets", "show_snippets",
    is_flag=True,
    default=False,
    help="📜 Exibe snippets de código detalhados das regressões, órfãos e trechos extirpados para análise baseada em evidências."
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
def regret_group(
    target: str | None,
    base: str | None,
    backup_id: str | None,
    commits: int,
    orphans: bool,
    provenance: bool,
    show_snippets: bool,
    dump: bool,
    quiet: bool
):
    """Audita a perda de capacidades entre revisões de código, backups, detecta orfandade e emite evidências de código."""
    try:
        use_backup = backup_id is not None
        actual_backup_id = None if backup_id == "__LATEST__" else backup_id

        report = RegretEngine.run_suite(
            target_path=target,
            base_revision=base,
            use_backup=use_backup,
            backup_id=actual_backup_id,
            commits_back=commits,
            check_orphans=orphans,
            check_provenance=provenance,
            show_snippets=show_snippets,
            dump_to_pot=dump,
            verbose=not quiet
        )
        if report["total_regressions"] > 0:
            sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}✖ Falha ao executar doxoade regret: {e}{Fore.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    regret_group()
