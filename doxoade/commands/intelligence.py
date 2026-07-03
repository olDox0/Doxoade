# -*- coding: utf-8 -*-
# doxoade/commands/intelligence.py
import os
import json
import click
import traceback
from pathlib import Path
from rich.console import Console

from doxoade.dnm import DNM
from doxoade.rescue import activate_protocol 
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from doxoade.tools.filesystem import _find_project_root

# PASC 10.1: Configuração para permitir flags APÓS os caminhos
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'], allow_interspersed_args=True)

@click.group('intelligence', invoke_without_command=True, context_settings=CONTEXT_SETTINGS)
@click.option(  '--docs',       '-d', is_flag=True, help="Extrai docstrings.")
@click.option(  '--source',     '-s', is_flag=True, help="Inclui código fonte.")
@click.option(  '--no-comments','-nc',is_flag=True, help="Remove comentários.")
@click.option(  '--concatenate','-c', is_flag=True, help="Minifica o JSON.")
@click.option(  '--ai-export',  '-ai',is_flag=True, help="Gera XML para LLMs.")
@click.option(  '--ia-qwen',    '-iq',is_flag=True, help="Gera XML nativo para Qwen (tool_call format).")
@click.option(  '--output',     '-o', default='chief_dossier.json', help="Saída do dossiê.")
@click.option(  '--focus',      '-f', type=click.Choice(['vulcan', 'check', 'economic']))
@click.option(  '--exclude',    '-x', multiple=True, help="Pastas ou arquivos a ignorar.")
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.pass_context
# ORDEM DOS PARÂMETROS DEVE SEGUIR A ORDEM DOS DECORADORES (Pilha: de cima para baixo)
def intelligence(ctx, docs, source, no_comments, concatenate, ai_export, ia_qwen, output, focus, exclude, paths):
    """Módulo de Inteligência Topológica (v95.6 - Qwen Ready)."""
    if ctx.invoked_subcommand is None:
        scan_paths = paths if paths else ('.',)
        try:
            # Passando os argumentos limpos para o motor
            _run_dossier_scan(
                scan_paths, output, docs, source, 
                no_comments, concatenate, focus, ai_export, ia_qwen, ctx, exclude
            )
        except Exception:
            error_data = traceback.format_exc()
            activate_protocol(error_data)
            ctx.exit(1)

@intelligence.command('recover')
@click.option('--dir', 'backup_path', required=True, help="Pasta de backup do NPP.")
@click.option('--out', 'output_path', default='recovery_zone', help="Destino.")
def recover(backup_path, output_path):
    """Resgata versões estáveis (Protocolo Ma'at)."""
    from .intelligence_systems.recovery_engine import run_recovery_mission
    click.echo("\033[93m🧐 Iniciando Resgate: Material Estável (Janela Ma'at)\033[0m")
    success, msg = run_recovery_mission(backup_path, output_path)
    if success: click.echo(f"\033[92m✅ {msg}\033[0m")
    else: click.echo(f"\033[91m✘ {msg}\033[0m")

def _run_dossier_scan(scan_paths, output, include_docs, include_source, no_comments, concat, focus, ai_export, ia_qwen, ctx, cli_excludes):
    from .intelligence_systems.intelligence_engine import analyze_file_chief
    from .intelligence_utils import strip_comments, get_ignore_spec
    
    root = _find_project_root(os.getcwd())
    console = Console()
    
    # Inicializa o filtro de exclusão (Lê TOML + CLI)
    ignore_spec = get_ignore_spec(root, extra_patterns=list(cli_excludes))
    
    with ExecutionLogger('intelligence', root, ctx.params):
        console.print("[bold gold3]🔍 Doxoade Chief Insight v95.6 (Qwen Ready)[/bold gold3]")
        valid_exts = (
            '.py', '.c', '.cpp', '.h', '.hpp', '.html', '.css', '.js', '.jsx', '.ts', '.tsx',
            '.pyd', '.so'
        )
        all_files_raw = []
        for p in scan_paths:
            p_abs = os.path.abspath(p)
            if os.path.isfile(p_abs):
                all_files_raw.append(p_abs)
            else:
                nav = DNM(p_abs)
                all_files_raw.extend(nav.scan(extensions=list(valid_exts)))
        
        unique_files = []
        for f in dict.fromkeys(all_files_raw):
            rel_path = os.path.relpath(f, root).replace('\\', '/')
            if not ignore_spec.match_file(rel_path):
                unique_files.append(f)
        
        dossier_files = []
        with click.progressbar(unique_files, label='[VULCAN:INTEL]') as bar:
            for f in bar:
                try:
                    res = analyze_file_chief(f, root, docs=include_docs, source=include_source)
                    if res and isinstance(res, dict) and 'size' in res:
                        if no_comments and res.get('source_minified'):
                            res['source_minified'] = strip_comments(res['source_minified'], f)
                        dossier_files.append(res)
                except Exception:
                    continue
        
        _save_report(dossier_files, output, root, concat, focus, ai_export, ia_qwen, console)

def _save_report(files, output, root, concat, focus, ai_export, ia_qwen, console):
    from datetime import datetime, timezone
    
    report_files = []
    economic_summary = {}
    report_type = "nexus_intelligence_report"
    
    # Filtering logic based on 'focus'
    if focus:
        report_type = f"{focus}_intelligence_report"
        console.print(f"[bold yellow]⚡ Gerando Relatório Focado: {focus.upper()}[/bold yellow]")
        
        total_complexity = 0
        total_debt_tags = 0
        total_mpot_violations = 0
        
        for f in files:
            include_file = True
            
            if focus == 'vulcan':
                god_assignment = f.get("god_assignment", "Unknown")
                complexity = f.get("complexity", 0)
                if god_assignment in ["Anúbis", "Zeus", "Atena"] or complexity > 10:
                    include_file = True
                else:
                    include_file = False
            elif focus == 'check':
                mpot_violations = f.get("mpot_4_violations", 0)
                debt_tags = f.get("debt_tags", [])
                complexity = f.get("complexity", 0)
                if mpot_violations > 0 or len(debt_tags) > 0 or complexity > 15:
                    include_file = True
                else:
                    include_file = False
            elif focus == 'economic':
                include_file = True
            
            if include_file:
                report_files.append(f)
                total_complexity += f.get("complexity", 0)
                total_debt_tags += len(f.get("debt_tags", []))
                total_mpot_violations += f.get("mpot_4_violations", 0)
        
        economic_summary = {
            "total_files_scanned": len(files),
            "total_files_in_report": len(report_files),
            "god_distribution_in_report": _calculate_distribution(report_files),
            "average_complexity_in_report": (total_complexity / len(report_files)) if report_files else 0,
            "total_debt_tags_in_report": total_debt_tags,
            "total_mpot_violations_in_report": total_mpot_violations
        }
        
        if focus == 'economic':
            summarized_report_files = []
            for f in report_files:
                summarized_report_files.append({
                    "path": f.get("path"),
                    "god_assignment": f.get("god_assignment"),
                    "status": f.get("status"),
                    "complexity": f.get("complexity", 0),
                    "functions_count": len(f.get("functions", [])),
                    "classes_count": len(f.get("classes", [])),
                    "docstring_intent": f.get("docstring_intent", "N/A"),
                    "debt_tags_count": len(f.get("debt_tags", [])),
                    "mpot_violations_count": f.get("mpot_4_violations", 0)
                })
            report_files = summarized_report_files
    else:
        report_files = files
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
    
    report = {
        report_type: {
            "version": "2026.Chief.v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_project": os.path.basename(root),
            "token_optimization": "ENABLED" if concat else "DISABLED",
            "focus_applied": focus if focus else "NONE"
        },
        "economic_summary": economic_summary,
        "codebase_map": report_files
    }
    
    # DESVIO PARA FORMATO QWEN (PRIORIDADE MÁXIMA)
    if ia_qwen:
        qwen_output = output.replace('.json', '') + "_qwen.xml" if output.endswith('.json') else output + "_qwen.xml"
        _save_qwen_report(report, qwen_output, console)
    elif ai_export:
        ai_output = output.replace('.json', '') + "_llm.xml" if output.endswith('.json') else output + "_llm.xml"
        _save_llm_report(report, ai_output, console)
    else:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=None if concat else 2, ensure_ascii=False)
        console.print(f"\n[bold green]✅ Dossiê NEXUS Gerado: {output}[/bold green]")

def _calculate_distribution(files):
    dist = {}
    for f in files:
        g = f.get("god_assignment", "Unknown")
        dist[g] = dist.get(g, 0) + 1
    return dist
    
def _save_llm_report(report_data, output_path, console):
    """Traduz o JSON arquitetural para um formato de alta absorção por LLMs (PASC 11.0)."""
    lines = []
    
    meta = None
    for key in report_data.keys():
        if key.endswith("intelligence_report"):
            meta = report_data[key]
            break
    
    if meta:
        lines.append("# DOXOADE NEXUS INTELLIGENCE REPORT")
        lines.append(f"**Target Project:** {meta.get('target_project')}")
        lines.append(f"**Generated At:** {meta.get('generated_at')}")
        lines.append(f"**Focus Applied:** {meta.get('focus_applied')}\n")
    
    lines.append("```xml")
    
    eco = report_data.get("economic_summary", {})
    lines.append("<project_summary>")
    lines.append(f"  <total_files_scanned>{eco.get('total_files_scanned', 0)}</total_files_scanned>")
    lines.append(f"  <total_files_in_report>{eco.get('total_files_in_report', 0)}</total_files_in_report>")
    lines.append(f"  <average_complexity>{eco.get('average_complexity_in_report', 0):.2f}</average_complexity>")
    lines.append(f"  <total_debt_tags>{eco.get('total_debt_tags_in_report', 0)}</total_debt_tags>")
    lines.append("  <god_distribution>")
    for god, count in eco.get("god_distribution_in_report", {}).items():
        lines.append(f"    <{god.lower().replace('ú','u')}>{count}</{god.lower().replace('ú','u')}>")
    lines.append("  </god_distribution>")
    lines.append("</project_summary>\n")
    
    lines.append("<codebase_map>")
    for f in report_data.get("codebase_map", []):
        path = f.get('path', 'unknown')
        god = f.get('god_assignment', 'Unknown')
        comp = f.get('complexity', 0)
        status = f.get('status', 'unknown')
        lines.append(f'\n  <file path="{path}" role="{god}" complexity="{comp}" status="{status}">')
        
        classes = f.get('classes', [])
        if classes:
            lines.append(f"    <classes>{', '.join(classes)}</classes>")
        
        funcs = f.get('functions', [])
        if funcs:
            funcs_str = []
            for fn in funcs:
                if isinstance(fn, str): funcs_str.append(fn)
                elif isinstance(fn, dict): funcs_str.append(str(fn.get('name', 'unknown')))
                else: funcs_str.append(str(getattr(fn, 'name', fn)))
            lines.append(f"    <functions>{', '.join(funcs_str)}</functions>")
        
        debt = f.get('debt_tags_count', len(f.get('debt_tags', [])))
        mpot = f.get('mpot_violations_count', f.get('mpot_4_violations', 0))
        if debt > 0 or mpot > 0:
            lines.append(f"    <technical_debt tags=\"{debt}\" mpot_violations=\"{mpot}\" />")
        
        src = f.get('source_minified')
        if src:
            safe_src = src.replace(']]>', ']]]]><![CDATA[>')
            lines.append("    <source_code><![CDATA[")
            lines.append(safe_src)
            lines.append("    ]]></source_code>")
        
        lines.append("  </file>")
    lines.append("</codebase_map>")
    lines.append("```\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    console.print(f"\n[bold magenta]🤖 Dossiê LLM-Ready Gerado: {output_path}[/bold magenta]")

def _save_qwen_report(report_data, output_path, console):
    """
    Gera relatório no formato nativo de Tool Calling do Qwen.
    VERSÃO FINAL: Remove TODOS os espaços e valida estrutura XML.
    """
    import json as _json
    import html
    
    lines = []
    
    # 1. Extrair metadados
    meta = next((v for k, v in report_data.items() if k.endswith("intelligence_report")), None)
    if not meta:
        console.print("[bold red]✘ Metadados do relatório não encontrados.[/bold red]")
        return
    
    eco = report_data.get("economic_summary", {})
    codebase = report_data.get("codebase_map", [])
    
    # 2. BLOCO DE RACIOCÍNIO PRÉVIO (sem espaços extras)
    lines.append("<think>")
    lines.append(f"Analisando codebase do projeto: {meta.get('target_project', 'Desconhecido')}.")
    lines.append(f"Total de arquivos escaneados: {eco.get('total_files_scanned', 0)}.")
    lines.append(f"Filtros aplicados: {meta.get('focus_applied', 'NONE')}.")
    lines.append("")
    lines.append("Distribuição de responsabilidades (God Assignment):")
    for god, count in eco.get("god_distribution_in_report", {}).items():
        lines.append(f"  - {god}: {count} arquivos")
    lines.append("")
    lines.append(f"Complexidade média: {eco.get('average_complexity_in_report', 0):.2f}")
    lines.append(f"Total de debt tags: {eco.get('total_debt_tags_in_report', 0)}")
    lines.append(f"Total de MPoT violations: {eco.get('total_mpot_violations_in_report', 0)}")
    lines.append("")
    lines.append("Estruturando o codebase_map como JSON serializado dentro de CDATA para processamento seguro.")
    lines.append("</think>")
    lines.append("")
    
    # 3. BLOCO PRINCIPAL DE TOOL CALLING (SEM ESPAÇOS NAS TAGS)
    lines.append("<tool_call>")
    lines.append("<function=doxoade_nexus_report>")
    
    # Parâmetros simples (escapados, SEM espaços, com strip())
    target = html.escape(str(meta.get('target_project', '')).strip())
    gen_at = html.escape(str(meta.get('generated_at', '')).strip())
    version = html.escape(str(meta.get('version', '')).strip())
    focus = html.escape(str(meta.get('focus_applied', '')).strip())
    
    lines.append(f"<parameter=target_project>{target}</parameter=target_project>")
    lines.append(f"<parameter=generated_at>{gen_at}</parameter=generated_at>")
    lines.append(f"<parameter=report_version>{version}</parameter=report_version>")
    lines.append(f"<parameter=focus_applied>{focus}</parameter=focus_applied>")
    
    # Parâmetros complexos (JSON COMPACTO sem espaços, dentro de CDATA válido)
    # IMPORTANTE: separators=(',', ':') remove TODOS os espaços do JSON
    eco_json = _json.dumps(eco, ensure_ascii=False, separators=(',', ':'))
    codebase_json = _json.dumps(codebase, ensure_ascii=False, separators=(',', ':'))
    
    lines.append(f"<parameter=economic_summary><![CDATA[{eco_json}]]></parameter=economic_summary>")
    lines.append(f"<parameter=codebase_map><![CDATA[{codebase_json}]]></parameter=codebase_map>")
    
    lines.append("</function>")
    lines.append("</tool_call>")
    
    # 4. Escrita segura (UTF-8)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        console.print(f"\n[bold magenta]🧠 Dossiê Qwen-Ready Gerado: {output_path}[/bold magenta]")
        console.print(f"[dim]   Formato: tool_call nativo + <think> + CDATA seguro[/dim]")
    except Exception as e:
        console.print(f"[bold red]✘ Falha ao gerar XML Qwen: {e}[/bold red]")