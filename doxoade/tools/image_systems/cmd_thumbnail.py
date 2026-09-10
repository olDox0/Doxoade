# -*- coding: utf-8 -*-
# doxoade/tools/image_systems/cmd_thumbnail.py
"""
🖼️ CLI Zeus de Thumbnails — geração, status e limpeza do cache binário.
Registro no Zeus (__main__.py):  cli.add_command(thumb_group)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from doxoade.tools.doxcolors import Fore, Style
from .thumbnail_engine import ThumbnailEngine, PRESETS


@click.group("thumb", help="🖼️ Thumbnails: geração, cache binário e preview de imagens.")
def thumb_group():
    """Grupo de comandos do motor de thumbnails."""
    pass


@thumb_group.command("generate", help="Gera thumbnails (cache binário DOXRLE1 + sidecar).")
@click.argument("path", type=click.Path(exists=True))
@click.option("--preset", "-p", type=click.Choice(sorted(PRESETS.keys())), default="card",
              help="Grade alvo: card (60x34), tree (20x20), preview (240x135).")
@click.option("--recursive", "-r", is_flag=True, help="Varre subpastas (diretórios).")
def cmd_generate(path, preset, recursive):
    """Gera thumbnails para um arquivo ou diretório inteiro."""
    engine = ThumbnailEngine(Path.cwd())
    target = Path(path)
    files = [target] if target.is_file() else engine.scan(target, recursive=recursive)
    if not files:
        click.echo(f"{Fore.YELLOW}⚠ Nenhuma imagem encontrada em: {target}{Fore.RESET}")
        return
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}🖼️  THUMBNAIL ENGINE — {len(files)} imagem(ns) | preset {preset}{Style.RESET_ALL}")
    counters = {"ok": 0, "pending": 0, "error": 0}

    def progress(i, total, src, res):
        counters["ok" if res.ok else res.status] = counters.get(res.status if not res.ok else "ok", 0) + 1
        tag = f"{Fore.GREEN}✔ {res.status:<9}{Fore.RESET}" if res.ok else f"{Fore.RED}✖ error    {Fore.RESET}"
        if res.status == "pending":
            tag = f"{Fore.YELLOW}⏳ pending  {Fore.RESET}"
        click.echo(f"  [{i}/{total}] {tag} {src.name[:44]:<44} {res.rects:>4} rects {res.elapsed_ms:6.1f}ms")

    t0 = time.time()
    results = engine.batch(files, preset=preset, progress=progress)
    ok = sum(1 for r in results if r.ok)
    err = sum(1 for r in results if r.status == "error")
    pend = sum(1 for r in results if r.status == "pending")
    click.echo(f"\n  {Fore.GREEN}✔ {ok} ok{Fore.RESET} | {Fore.YELLOW}⏳ {pend} pending{Fore.RESET} | "
               f"{Fore.RED}✖ {err} error{Fore.RESET} | {time.time() - t0:.2f}s")
    if err and ok == 0:
        sys.exit(1)


@thumb_group.command("status", help="Mostra resumo do cache de thumbnails.")
def cmd_status():
    engine = ThumbnailEngine(Path.cwd())
    st = engine.status()
    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}️  STATUS DO CACHE{Style.RESET_ALL}")
    click.echo(f"  Diretório : {st['cache_dir']}")
    click.echo(f"  Entradas  : {st['total']}")
    click.echo(f"  Bytes     : {st['total_bytes']:,}")
    click.echo(f"  Rects     : {st['total_rects']:,}")
    click.echo(f"  Pillow    : {'✔ disponível' if st['have_pil'] else Fore.YELLOW + '⚠ ausente (Plano B ativo)' + Fore.RESET}")


@thumb_group.command("clean", help="Limpa órfãos/stale (DRY-RUN por padrão; use --apply).")
@click.option("--apply", "-a", is_flag=True, help="Efetiva a limpeza (sai do dry-run).")
def cmd_clean(apply):
    engine = ThumbnailEngine(Path.cwd())
    report = engine.clean(dry_run=not apply)
    mode = f"{Fore.GREEN}[APPLY]{Fore.RESET}" if apply else f"{Fore.YELLOW}[DRY-RUN]{Fore.RESET}"
    click.echo(f"\n{mode} Órfãos: {len(report['orphans'])} | Stale: {len(report['stale'])}")
    for p in report["orphans"][:10]:
        click.echo(f"  {Fore.LIGHTBLACK_EX}• {p}{Fore.RESET}")
    if not apply and (report["orphans"] or report["stale"]):
        click.echo(f"{Fore.YELLOW}💡 Use --apply para efetivar.{Fore.RESET}")
