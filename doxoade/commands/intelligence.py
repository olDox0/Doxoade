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
@click.option('--focus', '-f', type=click.Choice(['vulcan', 'check', 'economic'], case_sensitive=False), 
              help="Filtra e sumariza o relatório para um foco específico (e.g., 'vulcan' para segurança, 'check' para anomalias, 'economic' para um resumo conciso).")
@click.pass_context
def intelligence(ctx, output, docs, source, concatenate, focus):
    """Módulo de Inteligência Topológica (v94.3)."""
    if ctx.invoked_subcommand is None:
        _run_dossier_scan(output, docs, source, concatenate, focus, ctx)

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

def _run_dossier_scan(output, include_docs, include_source, concat, focus, ctx):
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
        _save_report(dossier_files, output, root, concat, focus, console)

def _save_report(files, output, root, concat, focus, console):
    from datetime import datetime, timezone
    
    report_files = []
    economic_summary = {}
    report_type = "nexus_intelligence_report"
    
    # Filtering logic based on 'focus'
    if focus:
        report_type = f"{focus}_intelligence_report"
        console.print(f"[bold yellow]⚡ Gerando Relatório Focado: {focus.upper()}[/bold yellow]")
        
        # Simple aggregation for economic summary
        total_complexity = 0
        total_debt_tags = 0
        total_mpot_violations = 0
        
        for f in files:
            include_file = True 
            
            if focus == 'vulcan':
                # Vulcan: Focus on security (Anúbis), critical logic (Atena, Zeus), or high complexity
                god_assignment = f.get("god_assignment", "Unknown")
                complexity = f.get("complexity", 0) # From SemanticAnalyzer.get_summary()
                if god_assignment in ["Anúbis", "Zeus", "Atena"] or complexity > 10: # Example thresholds
                    include_file = True
                else:
                    include_file = False
                    
            elif focus == 'check':
                # Check: Focus on potential issues (MPoT violations, high complexity, debt tags)
                mpot_violations = f.get("mpot_4_violations", 0) 
                debt_tags = f.get("debt_tags", []) 
                complexity = f.get("complexity", 0)
                if mpot_violations > 0 or len(debt_tags) > 0 or complexity > 15: # Example thresholds
                    include_file = True
                else:
                    include_file = False

            elif focus == 'economic':
                # Economic: Include all files but only with a summarized view
                include_file = True 

            if include_file:
                report_files.append(f)
                total_complexity += f.get("complexity", 0)
                total_debt_tags += len(f.get("debt_tags", []))
                total_mpot_violations += f.get("mpot_4_violations", 0) 
        
        # Build economic_summary for focused reports
        economic_summary = {
            "total_files_scanned": len(files),
            "total_files_in_report": len(report_files),
            "god_distribution_in_report": _calculate_distribution(report_files),
            "average_complexity_in_report": (total_complexity / len(report_files)) if report_files else 0,
            "total_debt_tags_in_report": total_debt_tags,
            "total_mpot_violations_in_report": total_mpot_violations
        }
        
        # For 'economic' focus, we also want a *more* economic representation of each file in codebase_map
        if focus == 'economic':
            summarized_report_files = []
            for f in report_files:
                summarized_report_files.append({
                    "path": f.get("path"),
                    "god_assignment": f.get("god_assignment"),
                    "status": f.get("status"),
                    "complexity": f.get("complexity", 0),
                    "functions_count": len(f.get("functions", [])), # Functions from SemanticAnalyzer.get_summary()
                    "classes_count": len(f.get("classes", [])), # Classes from SemanticAnalyzer.get_summary()
                    "docstring_intent": f.get("docstring_intent", "N/A"), 
                    "debt_tags_count": len(f.get("debt_tags", [])),
                    "mpot_violations_count": f.get("mpot_4_violations", 0)
                })
            report_files = summarized_report_files # Replace detailed files with summarized ones
        
    else: # No focus, generate full report
        report_files = files
        # Calculate full economic summary for non-focused reports
        total_complexity = sum(f.get("complexity", 0) for f in files)
        total_debt_tags = sum(len(f.get("debt_tags", [])) for f in files)
        total_mpot_violations = sum(f.get("mpot_4_violations", 0) for f in files)

        economic_summary = {
            "total_files_scanned": len(files),
            "total_files_in_report": len(files),
            "god_distribution_in_report": _calculate_distribution(files),
            "average_complexity_in_report": (total_complexity / len(files)) if files else 0,
            "total_debt_tags_in_report": total_debt_tags,
            "total_mpot_violations_in_report": total_mpot_violations
        }

    # Estrutura Nexus para IAs
    report = {
        report_type: { 
            "version": "2026.Chief.v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_project": os.path.basename(root),
            "token_optimization": "ENABLED" if concat else "DISABLED",
            "focus_applied": focus if focus else "NONE"
        },
        "economic_summary": economic_summary, 
        "codebase_map": report_files 
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