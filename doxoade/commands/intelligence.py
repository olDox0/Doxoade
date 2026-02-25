# -*- coding: utf-8 -*-
# doxoade/commands/intelligence.py
import os
import json
import click
from rich.console import Console
from ..shared_tools import ExecutionLogger, _find_project_root
from ..dnm import DNM
from .intelligence_utils import get_ignore_spec
@click.group('intelligence', invoke_without_command=True)
@click.option('--output', '-o', default='chief_dossier.json', help="Saída do dossiê.")
@click.option('--docs', '-d', is_flag=True, help="Extrai docstrings.")
@click.option('--source', '-s', is_flag=True, help="Inclui código fonte completo.")
@click.option('--concatenate', '-c', is_flag=True, help="Minifica o JSON.")
@click.pass_context
def intelligence(ctx, output, docs, source, concatenate):
    """Módulo de Inteligência Topológica (v94.3)."""
    if ctx.invoked_subcommand is None:
        _run_dossier_scan(output, docs, source, concatenate, ctx)
@intelligence.command('recover')
@click.option('--dir', 'backup_path', required=True, help="Pasta de backup do NPP.")
@click.option('--out', 'output_path', default='recovery_zone', help="Destino.")
def recover(backup_path, output_path):
    """Resgata versões estáveis (Protocolo Ma'at - Pré 14/02)."""
    from .intelligence_systems.recovery_engine import run_recovery_mission
    click.echo("\033[93m🧐 Iniciando Resgate: Material Estável (Janela Ma'at)\033[0m")
    success, msg = run_recovery_mission(backup_path, output_path)
    if success: click.echo(f"\033[92m✅ {msg}\033[0m")
    else: click.echo(f"\033[91m✘ {msg}\033[0m")
def _run_dossier_scan(output, include_docs, include_source, concat, ctx):
    from .intelligence_systems.intelligence_engine import analyze_file_chief
#    from .intelligence_systems.intelligence_logic import analyze_file_chief
    
    root = _find_project_root(os.getcwd())
    console = Console()
    
    with ExecutionLogger('intelligence', root, ctx.params):
        console.print("[bold gold3]🧐 Doxoade Chief Insight v94.3[/bold gold3]")
        
        dnm = DNM(root)
        spec = get_ignore_spec(root)
        
        # Coleta inicial
        all_files = dnm.scan()
        filtered_files = []
        for f in all_files:
            # Normalização crucial: Pathspec exige '/' mesmo no Windows
            rel_path = os.path.relpath(f, root).replace('\\', '/')
            
            # PASC 8.13: Se o spec diz para ignorar, pulamos
            if spec and spec.match_file(rel_path):
                continue
            
            filtered_files.append(f)
        dossier_files = []
        with click.progressbar(filtered_files, label='Analizando Código') as bar:
            for f in bar:
                try:
                    res = analyze_file_chief(f, root, docs=include_docs, source=include_source)
                    if res and isinstance(res, dict):
                        dossier_files.append(res)
                except Exception as e:
                    import sys as dox_exc_sys
                    exc_type, exc_obj, exc_tb = dox_exc_sys.exc_info()
                    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                    line_number = exc_tb.tb_lineno
                    print(f"\033[0m \033[1m ■ Exception: {e}\nFilename: {fname}   ■ Line: {line_number} \033[31m ■ Exception type: {exc_type} ■ Exception value: {exc_obj} \033[0m")
        _save_report(dossier_files, output, root, concat, console)
def _save_report(files, output, root, concat, console):
    from datetime import datetime, timezone
    
    # Estrutura Nexus para IAs
    report = {
        "nexus_intelligence_report": {
            "version": "2026.Chief.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_project": os.path.basename(root),
            "token_optimization": "ENABLED" if concat else "DISABLED"
        },
        "topology_summary": {
            "total_files": len(files),
            "god_distribution": _calculate_distribution(files)
        },
        "codebase_map": files
    }
    
    # PASC 6.3: UTF-8 Sem BOM
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=None if concat else 2, ensure_ascii=False)
    
    console.print(f"\n[bold green]✅ Dossiê NEXUS Gerado: {output}[/bold green]")
def _calculate_distribution(files):
    dist = {}
    for f in files:
        g = f.get("god_assignment", "Unknown")
        dist[g] = dist.get(g, 0) + 1
    return dist