# -*- coding: utf-8 -*-
# doxoade/commands/impact_analysis.py
import os
import click
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _get_project_config, _find_project_root
from .impact_systems.impact_logic import build_project_index, get_external_consumers
from .impact_systems.impact_state import ImpactState
from .impact_systems.impact_utils import path_to_module_name, get_coupling_status, load_impact_cache, save_impact_cache

@click.command('impact-analysis')
@click.argument('file_path_arg', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('--path', 'project_path', type=click.Path(exists=True), default='.', help="Raiz do projeto.")
@click.option('--tracking', '-t', is_flag=True, help="Relatório de acoplamento.")
@click.option('--internal', '-i', is_flag=True, help="Fluxo de chamadas interno.")
@click.option('--external', '-e', is_flag=True, help="Consumidores externos.")
@click.option('--func', '-f', help="Foca em uma função específica.")
@click.option('--graph', '-g', is_flag=True, help="Gerar Mermaid.")
@click.pass_context
def impact_analysis(ctx, file_path_arg, project_path, tracking, internal, external, func, graph):
    """Analisa dependências e rastreia fluxo via Cache Diferencial (v10.1)."""
    root = _find_project_root(project_path)
    
    with ExecutionLogger('impact-analysis', root, ctx.params) as logger:
        config = _get_project_config(logger, start_path=root)
        search_path = config['search_path']
        
        # 1. Recupera Memória de runs anteriores
        old_idx = load_impact_cache(root)
        
        # 2. Atualização Seletiva (Onde o tempo é poupado)
        click.echo(Fore.CYAN + f"--- [NEXUS IMPACT] Analisando '{os.path.basename(root)}' ---")
        idx = build_project_index(search_path, set(config.get('ignore', [])), old_idx)
        
        # 3. Persistência
        save_impact_cache(root, idx)
        
        target_mod = path_to_module_name(file_path_arg, search_path)
        if target_mod not in idx:
            click.echo(Fore.RED + f"Erro: Módulo {target_mod} não indexado."); return
            
        state = ImpactState(target_module=target_mod, project_root=root, 
                            search_path=search_path, index=idx)

        # --- DESPACHO DE VISUALIZAÇÃO ---
        if internal:
            click.echo(Fore.CYAN + f"\n[INTERNAL] Fluxo de '{target_mod}':")
            meta = state.get_internal_metadata()
            for f_name, info in sorted(meta.items(), key=lambda x: x[1]['line']):
                # Filtra chamadas para funções que existem no próprio arquivo
                calls = [c for c in info['calls'] if c in meta and c != f_name]
                prefix = Fore.GREEN + f"  ƒ {f_name}()"
                if calls: click.echo(f"{prefix} chama: " + Fore.WHITE + f"{', '.join(set(calls))}")
                else: click.echo(f"{prefix} " + Style.DIM + "[Folha]")

        if external:
            click.echo(Fore.MAGENTA + f"\n[EXTERNAL] Consumidores de '{target_mod}':")
            consumers = get_external_consumers(state, func_filter=func)
            for c in consumers:
                click.echo(Fore.YELLOW + f"  ▼ {c['path']}")
                click.echo(Fore.WHITE + f"    └── usa: {', '.join(c['calls'])}")
            if not consumers: click.echo("  (Nenhum uso externo detectado)")

        if tracking or (not internal and not external and not graph):
            data = idx[target_mod]
            fan_out = len(data['imports'])
            consumers = get_external_consumers(state)
            fan_in = len(consumers)
            val, (status_color, status_txt) = get_coupling_status(fan_out, fan_in)
            
            click.echo(Fore.CYAN + Style.BRIGHT + f"\n=== IMPACTO: {target_mod} ===")
            click.echo(f"  Instabilidade: {val:.2f} -> {status_color}{status_txt}")
            click.echo(Fore.YELLOW + f"  Depende de   : {fan_out} módulos")
            click.echo(Fore.YELLOW + f"  Usado por    : {fan_in} arquivos")