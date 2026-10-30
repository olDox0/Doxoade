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

def _classify_diff(diff_lines: List[str]) -> Dict:
    """
    v1.1 — Classifica as diferenças de um diff unified.

    Retorna:
    - type: 'whitespace' | 'comments' | 'code' | 'mixed' | 'unknown'
    - real_divergence: bool (True se há código real divergente)
    - whitespace_count, comments_count, code_count: contadores
    """
    whitespace = 0
    comments = 0
    code = 0

    for line in diff_lines:
        if not line.startswith(('+', '-')):
            continue
        if line.startswith(('+++', '---')):
            continue

        content = line[1:].strip()
        if not content:
            whitespace += 1
            continue

        # Comentários: //, /*, */, #, -- (Lua), <!-- (HTML)
        if content.startswith(('//', '/*', '*/', '#')):
            comments += 1
            continue
        if content.startswith('--'):
            comments += 1
            continue
        if content.startswith('<!--'):
            comments += 1
            continue

        # Código real
        code += 1

    if code > 0 and (whitespace > 0 or comments > 0):
        return {
            "type": "mixed",
            "real_divergence": True,
            "whitespace_count": whitespace,
            "comments_count": comments,
            "code_count": code,
        }
    if code > 0:
        return {
            "type": "code",
            "real_divergence": True,
            "whitespace_count": whitespace,
            "comments_count": comments,
            "code_count": code,
        }
    if comments > 0 and whitespace > 0:
        return {
            "type": "mixed",
            "real_divergence": False,
            "whitespace_count": whitespace,
            "comments_count": comments,
            "code_count": 0,
        }
    if comments > 0:
        return {
            "type": "comments",
            "real_divergence": False,
            "whitespace_count": whitespace,
            "comments_count": comments,
            "code_count": 0,
        }
    if whitespace > 0:
        return {
            "type": "whitespace",
            "real_divergence": False,
            "whitespace_count": whitespace,
            "comments_count": 0,
            "code_count": 0,
        }
    return {
        "type": "unknown",
        "real_divergence": False,
        "whitespace_count": 0,
        "comments_count": 0,
        "code_count": 0,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Diff literal (unified) — igual ao `diff.py`/`mirror.py` em espírito
# ─────────────────────────────────────────────────────────────────────────────
def _diff_literal(xml_src: str, disk_src: str, path: str, context: int) -> Dict:
    """Unified diff entre CDATA cru do XML e conteúdo do arquivo em disco."""
    def _norm_lines(text: str):
        if not text:
            return []
        return [line + "\n" for line in text.splitlines()]

    xml_lines = _norm_lines(xml_src)
    disk_lines = _norm_lines(disk_src)
    diff_lines = list(difflib.unified_diff(
        xml_lines, disk_lines,
        fromfile=f"XML:{path}",
        tofile=f"DISCO:{path}",
        n=context,
        lineterm="",
    ))

    ext = os.path.splitext(path)[1].lower()
    classification = _classify_diff(diff_lines)

    # Nota dinâmica por extensão + classificação
    note = None
    if ext in ('.c', '.cpp', '.h', '.hpp', '.cc', '.cxx'):
        if classification["type"] == "whitespace":
            note = "C/C++: diferenças apenas de espaços/linhas em branco (minificação)."
        elif classification["type"] == "comments":
            note = "C/C++: diferenças apenas de comentários (minificação)."
        elif classification["type"] == "mixed" and not classification["real_divergence"]:
            note = "C/C++: diferenças de espaços e comentários (minificação)."
        elif classification["type"] == "mixed":
            note = (
                f"C/C++: ATENÇÃO — há diferenças de CÓDIGO "
                f"({classification['code_count']} linha(s)). "
                f"Pode ser divergência real, não só minificação."
            )
        elif classification["type"] == "code":
            note = (
                f"C/C++: ATENÇÃO — há {classification['code_count']} linha(s) "
                f"de CÓDIGO divergente. Investigar."
            )
    elif ext == '.py':
        if classification["real_divergence"]:
            note = None  # Python divergente é esperado (exit 1)
    elif ext in ('.md', '.toml', '.json', '.txt', '.yml', '.yaml'):
        if not classification["real_divergence"]:
            note = "Doc/config: diferenças de espaços/comentários (minificação)."
    elif ext in ('.js', '.jsx', '.ts', '.tsx', '.lua'):
        if not classification["real_divergence"]:
            note = f"{ext[1:].upper()}: diferenças de espaços/comentários (minificação)."

    return {
        "equal": not diff_lines,
        "diff_text": "\n".join(line.rstrip("\n") for line in diff_lines),
        "xml_lines": len(xml_lines),
        "disk_lines": len(disk_lines),
        "truncated": False,
        "shown": len(diff_lines),
        "note": note,
        "ext": ext,
        "classification": classification,
    }

def _render_report(report: Dict, console: Console, list_all: bool) -> None:
    src = report.get("source")
    if src is None:
        return

    console.print(f"\n[bold cyan]📄 DIFF LITERAL (Camada C1) — "
                  f"{len(src)} arquivo(s) comparado(s)[/bold cyan]")

    divergences = [d for d in src if not d["equal"]]
    if not divergences:
        console.print("   [green]✔ Nenhuma divergência literal.[/green]")
        return

    # v1.1 — Veredito por extensão + classificação
    py_div = [d for d in divergences if d.get("ext") == ".py"]
    c_real = [d for d in divergences if d.get("ext") in ('.c', '.cpp', '.h', '.hpp', '.cc', '.cxx')
              and d.get("classification", {}).get("real_divergence")]
    c_minif = [d for d in divergences if d.get("ext") in ('.c', '.cpp', '.h', '.hpp', '.cc', '.cxx')
               and not d.get("classification", {}).get("real_divergence")]
    doc_div = [d for d in divergences if d.get("ext") in ('.md', '.toml', '.json', '.txt', '.yml', '.yaml')]
    other_div = [d for d in divergences if d not in py_div and d not in c_real and d not in c_minif and d not in doc_div]

    console.print(f"\n[bold]📊 Veredito por extensão:[/bold]")
    if py_div:
        console.print(f"   [red]🔴 {len(py_div)} arquivo(s) Python divergente(s)[/red]")
    if c_real:
        console.print(f"   [red]🔴 {len(c_real)} arquivo(s) C/C++ com CÓDIGO divergente[/red]")
    if c_minif:
        console.print(f"   [yellow]🟡 {len(c_minif)} arquivo(s) C/C++ divergente(s) (minificação)[/yellow]")
    if doc_div:
        console.print(f"   [dim]ℹ️ {len(doc_div)} arquivo(s) doc/config divergente(s) (minificação)[/dim]")
    if other_div:
        console.print(f"   [cyan]ℹ️ {len(other_div)} arquivo(s) outro(s) divergente(s)[/cyan]")

    # Diff por arquivo (nota antes do diff)
    for d in divergences:
        console.print(f"\n[bold]■ {d['path']}[/bold]")
        if d.get("note"):
            console.print(f"   [yellow]⚠️  {d['note']}[/yellow]")
        console.print(f"   xml={d['xml_lines']} linhas | disco={d['disk_lines']} linhas")
        if d.get("truncated"):
            console.print(f"   [dim](diff truncado em {d['shown']} linhas)[/dim]")
        console.print(d["diff_text"])


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
@click.option('--strict', is_flag=True,
              help='Exit 1 para QUALQUER divergência (não só Python/Código real).')
def audit(xml_path, file_path, context, only_diff, summary, filter_mode, strict):
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

def _emit_exit_code(report: Dict, strict: bool = False) -> int:
    """
    v1.1 — Exit 1 se:
    - Python divergir (sempre).
    - C/C++ com código real divergir (classificação real_divergence=True).
    - --strict e qualquer divergir.
    """
    src = report.get("source") or []
    for d in src:
        if d["equal"]:
            continue
        ext = d.get("ext", "")
        classification = d.get("classification", {})
        if ext == ".py":
            return 1
        if ext in ('.c', '.cpp', '.h', '.hpp', '.cc', '.cxx') and classification.get("real_divergence"):
            return 1
        if strict:
            return 1
    return 0
