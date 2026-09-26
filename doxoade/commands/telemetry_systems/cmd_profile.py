# -*- coding: utf-8 -*-
# doxoade/commands/telemetry_systems/cmd_profile.py
"""
⚡ ZEUS / HORUS — Orquestrador Global do Shadow Profiler.
Executa qualquer comando do Doxoade sob a Chrono-Matrix do ShadowMatrix.
Uso: doxoade profile [-o arquivo.json] [--json] <comando> [opções...]
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
import click
from doxoade.tools.doxcolors import Fore, Style
from .shadow_matrix import ShadowMatrix


@click.command(
    "profile",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    ),
    help="🦅 Executa qualquer comando do Doxoade sob o Shadow Profiler (Chrono-Matrix)."
)
@click.option('--json', 'as_json', is_flag=True, help='Emite o relatório em JSON puro no stdout.')
@click.option('--output', '-o', type=click.Path(dir_okay=False, writable=True), default=None, help='Salva o dossiê JSON completo em um arquivo especificado.')
@click.pass_context
def cmd_profile(ctx: click.Context, as_json: bool, output: str | None):
    """
    Encapsula a invocação do comando filho com telemetria in-process de 200Hz.
    Pode exibir o HUD ou salvar o JSON temporal completo diretamente em arquivo.
    """
    args = ctx.args
    if not args:
        click.echo(ctx.get_help())
        click.echo(f"\n{Fore.YELLOW}💡 Exemplos de uso:{Style.RESET_ALL}")
        click.echo(f"   doxoade profile consult search --deep asyncio")
        click.echo(f"   doxoade profile -o timeline_data.json consult search --deep asyncio\n")
        return

    target_label = " ".join(args)
    from doxoade.cli import cli as root_cli

    with ShadowMatrix(target_name=target_label, enabled=True) as profiler:
        exit_code = 0
        try:
            root_cli.main(args=list(args), standalone_mode=False)
        except SystemExit as se:
            exit_code = se.code if isinstance(se.code, int) else (1 if se.code else 0)
        except click.ClickException as ce:
            ce.show()
            exit_code = ce.exit_code
        except Exception as e:
            click.secho(f"\n[ERRO PROFILE] Falha na execução do comando: {e}", fg="red")
            exit_code = 1

    # Gravação em arquivo (quando solicitado com -o / --output)
    if output:
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(profiler.report_data, indent=2), encoding="utf-8")
        click.secho(f"\n✔ Dossiê de profiling gravado em: {out_path}", fg="green")
        # Também renderiza o HUD resumido na tela se não foi pedido --json
        if not as_json:
            profiler.render_hud()
    elif as_json:
        click.echo(json.dumps(profiler.report_data, indent=2))
    else:
        profiler.render_hud()

    if exit_code != 0:
        ctx.exit(exit_code)
