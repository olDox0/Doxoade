# doxoade/commands/typhon_systems/typhon_cmd.py
# -*- coding: utf-8 -*-
"""
TYPHON CMD — interface Zeus do Typhon no Doxoade.
"""

import click

from doxoade.tools.doxcolors import Fore, Style

from .typhon_consolidated import (
    check,
    chaos,
    probe,
    tree,
    report,
)


@click.group(name="typhon")
def typhon():
    """🌀 Typhon — chaos engineering, probes e diagnóstico vivo."""
    pass


@typhon.command("check")
@click.option("--db", default=None, help="Caminho alternativo do doxoade.db.")
def typhon_check(db):
    """Verifica DB, operational_logs e integridade."""

    summary = check(db_path=db, verbose=True)

    if summary["issues"]:
        raise SystemExit(1)


@typhon.command("chaos")
@click.option("--soteria", is_flag=True, help="Emite envelopes Soteria.")
@click.option("--horus", is_flag=True, help="Emite heartbeats Horus.")
def typhon_chaos(soteria, horus):
    """Roda a suite de chaos do Typhon."""

    summary = chaos(verbose=True, soteria=soteria, horus=horus)

    if summary["silent"] > 0:
        raise SystemExit(1)


@typhon.command("probe")
@click.option("--db", default=None, help="Caminho alternativo do doxoade.db.")
def typhon_probe(db):
    """Roda probes vivos contra o Doxoade."""

    findings = probe(verbose=True, db_path=db)

    if findings:
        raise SystemExit(1)


@typhon.command("tree")
def typhon_tree():
    """Mostra a árvore declarativa de falhas."""

    tree()


@typhon.command("report")
@click.option("--db", default=None, help="Caminho alternativo do doxoade.db.")
@click.option("--soteria", is_flag=True, help="Emite envelopes Soteria.")
@click.option("--horus", is_flag=True, help="Emite heartbeats Horus.")
def typhon_report(db, soteria, horus):
    """Roda check + chaos + probe + tree."""

    res = report(
        db_path=db,
        verbose=True,
        soteria=soteria,
        horus=horus,
    )

    bad = False

    if res["check"]["issues"]:
        bad = True

    if res["chaos"]["silent"] > 0:
        bad = True

    if res["probe"]:
        bad = True

    if bad:
        raise SystemExit(1)


# Compatibilidade, se o loader do Doxoade esperar `cli`.
cli = typhon
