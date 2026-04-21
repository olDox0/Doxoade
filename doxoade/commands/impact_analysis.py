# doxoade/doxoade/commands/impact_analysis.py
import os
import click
import json
from doxoade.tools.doxcolors import Fore, Style
from doxoade.commands.impact_systems.impact_logic import build_project_index, get_external_consumers
from doxoade.commands.impact_systems.impact_state import ImpactState
from doxoade.commands.impact_systems.impact_utils import path_to_module_name, load_impact_cache, save_impact_cache
from doxoade.commands.doxcolors_systems.colors_command import config
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.filesystem import _get_project_config
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@click.command('impact-analysis')
@click.argument('file_path_arg', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--path', 'project_path', type=click.Path(exists=True), default='.', help='Raiz do projeto.')
@click.option('--tracking', '-t', is_flag=True, help='Relatório de acoplamento.')
@click.option('--internal', '-i', is_flag=True, help='Fluxo de chamadas interno.')
@click.option('--external', '-e', is_flag=True, help='Consumidores externos.')
@click.option('--func', '-f', help='Foca em uma função específica.')
@click.option('--graph', '-g', 'show_graph', is_flag=True, help='Gerar Mermaid.')
@click.option('--alerts', '-a', is_flag=True, help='Detectar problemas estruturais.')
@click.option('--html', '-H', is_flag=True, help='Gerar HTML interativo.')
@click.option('--xml', '-x', is_flag=True, default=False, help='Gerar XML.')
@click.option('--output', '-o', type=click.Path(), help='Salvar saída em arquivo.')
@click.pass_context
def impact_analysis(ctx, file_path_arg, project_path, tracking, internal, external, func, show_graph, alerts, html, xml, output):
    """Analisa dependências e rastreia fluxo via Cache Diferencial (v10.1)."""
    root = _find_project_root(project_path)
    with ExecutionLogger('impact-analysis', root, ctx.params) as logger:
        config = _get_project_config(logger, start_path=root)
        search_path = config['search_path']
        old_idx = load_impact_cache(root)
        click.echo(Fore.CYAN + f"--- [NEXUS IMPACT] Analisando '{os.path.basename(root)}' ---")
        idx = build_project_index(search_path, set(config.get('ignore', [])), old_idx)
        save_impact_cache(root, idx)
        target_mod = path_to_module_name(file_path_arg, search_path)
        if target_mod not in idx:
            click.echo(Fore.RED + f'Erro: Módulo {target_mod} não indexado.')
            return
        state = ImpactState(target_module=target_mod, project_root=root, search_path=search_path, index=idx)
        if internal:
            click.echo(Fore.CYAN + f"\n[INTERNAL] Fluxo de '{target_mod}':")
            meta = state.get_internal_metadata()
            for f_name, info in sorted(meta.items(), key=lambda x: x[1]['line']):
                calls = [c for c in info['calls'] if c in meta and c != f_name]
                prefix = Fore.GREEN + f'  ƒ {f_name}()'
                if calls:
                    click.echo(f'{prefix} chama: ' + Fore.WHITE + f"{', '.join(set(calls))}")
                else:
                    click.echo(f'{prefix} ' + Style.DIM + '[Folha]')
        if external:
            click.echo(Fore.MAGENTA + f"\n[EXTERNAL] Consumidores de '{target_mod}':")
            consumers = get_external_consumers(state, func_filter=func)
            for c in consumers:
                click.echo(Fore.YELLOW + f"  ▼ {c['path']}")
                click.echo(Fore.WHITE + f"    └── usa: {', '.join(c['calls'])}")
            if not consumers:
                click.echo('  (Nenhum uso externo detectado)')
        if tracking or (not internal and (not external) and (not show_graph) and (not html) and (not xml)):
            from doxoade.commands.impact_systems.impact_utils import get_coupling_status
            data = idx[target_mod]
            fan_out = len(data['imports'])
            consumers = get_external_consumers(state)
            fan_in = len(consumers)
            val, (status_color, status_txt) = get_coupling_status(fan_out, fan_in)
            click.echo(Fore.CYAN + Style.BRIGHT + f'\n--- IMPACTO: {target_mod} ---')
            click.echo(f'  Instabilidade: {val:.2f} -> {status_color}{status_txt}')
            click.echo(Fore.YELLOW + f'  Depende de   : {fan_out} módulos')
            click.echo(Fore.YELLOW + f'  Usado por    : {fan_in} arquivos')
        if show_graph or xml or html:
            from doxoade.commands.impact_systems.impact_fluxogram import build_import_fluxogram, graph_stats, analyze_cycles
            from doxoade.commands.impact_systems.fluxogram_imports import to_mermaid, to_json, to_payload, to_xml
            flux_graph = build_import_fluxogram(idx, include_external=True, target_module=target_mod, depth=1)
            stats = graph_stats(flux_graph)
            cycles = analyze_cycles(flux_graph) if alerts else []
            if html:
                from doxoade.commands.impact_systems.impact_html import to_html
                mermaid_data = to_mermaid(flux_graph, highlight_cycles=bool(alerts), target_module=target_mod)
                payload = to_payload(flux_graph)
                payload['stats'] = stats
                payload['alerts'] = cycles
                html_out = to_html(mermaid_data, stats, cycles).replace('{{DATA_JSON}}', json.dumps(payload, ensure_ascii=False))
                out_file = output or 'impact_report.html'
                with open(out_file, 'w', encoding='utf-8') as f:
                    f.write(html_out)
                click.echo(Fore.GREEN + f'✅ Relatório HTML interativo gerado em: {out_file}')
            elif xml:
                xml_out = to_xml(flux_graph, include_cycles=bool(alerts))
                out_file = output or 'impact_report.xml'
                with open(out_file, 'w', encoding='utf-8') as f:
                    f.write(xml_out)
                click.echo(Fore.GREEN + f'✅ Relatório XML gerado em: {out_file}')
            elif show_graph:
                mermaid_data = to_mermaid(flux_graph, highlight_cycles=bool(alerts), target_module=target_mod)
                click.echo('\n[GRAPH] Fluxo de imports Mermaid:')
                click.echo(mermaid_data)
