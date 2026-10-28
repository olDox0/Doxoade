# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_audit.py
"""
Audit: compara o CDATA de um dossiê XML com o arquivo original no disco.

Uso:
    doxoade intelligence audit dossie.xml arquivo.py
    doxoade intelligence audit dossie.xml          # compara todos do XML

O diff é literal (unified), mostrando exatamente o que a minificação do
relatório alterou em relação ao original.
"""
from __future__ import annotations

import os
import re
import difflib
from pathlib import Path
from typing import Dict, List, Optional

import click
import xml.etree.ElementTree as ET

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.filesystem import _find_project_root

def _parse_dossier(xml_path: str) -> Dict:
    with open(xml_path, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    if "<doxoade_nexus_report>" not in raw:
        raise click.ClickException(f"'{xml_path}' não parece um dossiê.")

    # Correção inline de bugs do _save_llm_report antigo:
    # 1. Apóstrofo em nome de tag: <ma'at> → <ma_at>
    fixed = re.sub(r"<(/?)([a-z_][a-z0-9_]*)'([a-z0-9_\-.]*)\s*>", r"<\1\2_\3>", raw)
    # 2. CDATA mal escapado: ]]><![CDATA[> → ]]]]><![CDATA[>
    fixed = fixed.replace(']]><![CDATA[>', ']]]]><![CDATA[>')

    try:
        root = ET.fromstring(fixed)
    except ET.ParseError as e:
        raise click.ClickException(
            f"XML inválido mesmo após correção inline: {e}. "
            f"O arquivo pode estar truncado ou corrompido."
        )

    files = []
    for file_elem in root.iter("file"):
        path = file_elem.get("path")
        src_elem = file_elem.find("source_code")
        source_raw = src_elem.text if src_elem is not None else None
        files.append({"path": path, "source_raw": source_raw})
    return {"files": files}


# ─────────────────────────────────────────────────────────────────────────────
# Diff literal (unified) — igual ao `diff.py`/`mirror.py` em espírito
# ─────────────────────────────────────────────────────────────────────────────
def _diff_literal(xml_src: str, disk_src: str, path: str, context: int) -> Dict:
    """Unified diff entre CDATA cru do XML e conteúdo do arquivo em disco."""
    # Normaliza: garante \n no final de cada linha
    def _norm_lines(text: str):
        if not text:
            return []
        lines = text.splitlines()
        return [line + "\n" for line in lines]

    xml_lines = _norm_lines(xml_src)
    disk_lines = _norm_lines(disk_src)
    diff_lines = list(difflib.unified_diff(
        xml_lines, disk_lines,
        fromfile=f"XML:{path}",
        tofile=f"DISCO:{path}",
        n=context,
        lineterm="",
    ))
    return {
        "equal": not diff_lines,
        "diff_text": "\n".join(line.rstrip("\n") for line in diff_lines),
        "xml_lines": len(xml_lines),
        "disk_lines": len(disk_lines),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Comando — simples, como mirror.py
# ─────────────────────────────────────────────────────────────────────────────
@click.command('audit')
@click.argument('xml_path', type=click.Path(exists=True, dir_okay=False))
@click.argument('file_path', type=click.Path(exists=True, dir_okay=False), required=False)
@click.option('-U', '--context', default=3, type=int,
              help='Linhas de contexto no unified diff (default: 3).')
@click.option('--only-diff', is_flag=True,
              help='Só mostra arquivos com divergência.')
@click.option('--summary', is_flag=True,
              help='Só mostra o resumo (sem diff).')
@click.option('--filter', 'filter_mode',
              type=click.Choice(['all', 'removed', 'added']), default='all',
              help='Filtra linhas do diff: all (default), removed (só -), added (só +).')
def audit(xml_path, file_path, context, only_diff, summary, filter_mode):
    """Compara o CDATA do dossiê XML com o arquivo original no disco."""
    root = _find_project_root(os.getcwd())
    click.echo(Fore.CYAN + Style.BRIGHT + f'--- [AUDIT] {xml_path} vs disco ---')

    dossier = _parse_dossier(xml_path)

    target_rel = None
    if file_path:
        target_abs = os.path.abspath(file_path)
        try:
            target_rel = os.path.relpath(target_abs, root).replace('\\', '/')
        except ValueError:
            target_rel = None
        click.echo(Fore.WHITE + f'  Filtro: {target_rel}')

    compared = 0
    diverged = 0
    for f in dossier["files"]:
        path = f["path"]
        if target_rel and path != target_rel:
            continue
        if f["source_raw"] is None:
            continue
        abs_path = os.path.join(root, path.replace("/", os.sep))
        if not os.path.exists(abs_path):
            click.echo(Fore.YELLOW + f'  ⚠ Fantasma: {path}')
            continue
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as fh:
            disk_src = fh.read()
        result = _diff_literal(f["source_raw"], disk_src, path, context)
        compared += 1
        if result["equal"]:
            if not only_diff and not summary:
                click.echo(Fore.GREEN + f'  ✔ {path} (idêntico)')
        else:
            diverged += 1
            if summary:
                # Só conta, não mostra diff
                click.echo(Fore.YELLOW + f'  ✗ {path} (divergente)')
                continue
            click.echo(Fore.YELLOW + f'\n■ {path}')
            click.echo(Fore.WHITE + f'  xml={result["xml_lines"]} linhas | disco={result["disk_lines"]} linhas')
            for line in result["diff_text"].splitlines():
                if line.startswith('+'):
                    if filter_mode in ('all', 'added'):
                        click.echo(Fore.GREEN + line)
                elif line.startswith('-'):
                    if filter_mode in ('all', 'removed'):
                        click.echo(Fore.RED + line)
                else:
                    if filter_mode == 'all':
                        click.echo(Style.DIM + line + Style.RESET_ALL)

    click.echo(Fore.CYAN + f'\n--- Resumo: {compared} comparados, {diverged} divergentes ---')
    if diverged > 0:
        raise SystemExit(1)
