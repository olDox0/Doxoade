# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence.py
import os
import re
import json
import click
import traceback
import xml.etree.ElementTree as ET

from pathlib import Path
from rich.console import Console

from doxoade.dnm import DNM
from doxoade.rescue import activate_protocol 
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from doxoade.tools.filesystem import _find_project_root

# PASC 10.1: Configuração para permitir flags APÓS os caminhos
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'], allow_interspersed_args=True)
VALID_EXTS = (
    '.py', '.c', '.cpp', '.h', '.hpp', '.html', '.css', '.js', '.jsx', '.ts', '.tsx',
    '.pyd', '.so', '.toml', '.md', '.s', '.json', '.txt'
)

@click.group('intelligence', invoke_without_command=True, context_settings=CONTEXT_SETTINGS)
@click.option('--docs',       '-d', is_flag=True,  help="Extrai docstrings.")
@click.option('--source',     '-s', is_flag=True,  help="Inclui código fonte.")
@click.option('--no-comments','-nc',is_flag=True,  help="Remove comentários.")
@click.option('--no-spaces',  '-ns',is_flag=True,  help="Remove linhas em branco (Token Saver).") # 🆕 NOVO
@click.option('--concatenate','-c', is_flag=True,  help="Minifica o JSON.")
@click.option('--ai-export',  '-ai',is_flag=True,  help="Gera XML para LLMs.")
@click.option('--ia-qwen',    '-iq',is_flag=True,  help="Gera XML nativo para Qwen (tool_call format).")
@click.option('--output',     '-o', default='chief_dossier.json', help="Saída do dossiê.")
@click.option('--focus',      '-f', type=click.Choice(['vulcan', 'check', 'economic']))
@click.option('--exclude',    '-x', multiple=True, help="Pastas ou arquivos a ignorar.")
@click.option('--ext-exclude','-xe', multiple=True, help="Extensões específicas a ignorar.") # 🆕 NOVO
@click.option('--analyze',    '-a', is_flag=True,  help="Auditoria de Cobertura.")
@click.option('--verbose',    '-v', is_flag=True,  help="Modo verboso.")
@click.option('--graph',      '-g', is_flag=False, flag_value=1, default=0, type=int, help="Inclui arquivos relacionados (grafo de dependências). Nível de profundidade (padrão 1).")
@click.option('--manifest',   '-m', is_flag=True, help="🦉 [THOTH] Gera o manifesto JSON de comandos para IAs (Tool Use).")
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
@click.pass_context
def intelligence(ctx, docs, source, no_comments, no_spaces, concatenate, ai_export, ia_qwen, output, focus, exclude, ext_exclude, analyze, verbose, manifest, paths, graph):
    """Módulo de Inteligência Topológica (v95.6 - Qwen Ready)."""
    if analyze:
        _run_analyze_coverage(paths, exclude, verbose, ext_exclude)
        return

    if manifest:
        generate_manifest() # XML é o padrão absoluto
        return

    if ctx.invoked_subcommand is None:
        scan_paths = paths if paths else ('.',)
        try:
            _run_dossier_scan(
                scan_paths, output, docs, source,
                no_comments, no_spaces, concatenate, focus, ai_export, ia_qwen, ctx, exclude, ext_exclude, graph
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

def _run_dossier_scan(scan_paths, output, include_docs, include_source, no_comments, no_spaces, concat, focus, ai_export, ia_qwen, ctx, cli_excludes, ext_excludes, graph_depth):
    from doxoade.commands.intelligence_systems.intelligence_engine import analyze_file_chief
    # 🆕 CORREÇÃO: Importar minify_code em vez de strip_comments
    from doxoade.commands.intelligence_systems.intelligence_utils import minify_code, get_ignore_spec 
    
    root = _find_project_root(os.getcwd())
    console = Console()
    
    # Fusão de Blacklists (TOML + CLI Paths + CLI Extensions)
    extra_patterns = list(cli_excludes)
    if ext_excludes:
        for ext in ext_excludes:
            if not ext.startswith('.'): ext = '.' + ext
            extra_patterns.append(f"*{ext}")
            
    ignore_spec = get_ignore_spec(root, extra_patterns=extra_patterns)
    
    with ExecutionLogger('intelligence', root, ctx.params):
        console.print("[bold gold3]🔍 Doxoade Chief Insight v95.6 (Qwen Ready)[/bold gold3]")
        valid_exts = (
            '.py', '.c', '.cpp', '.h', '.hpp', '.html', '.css', '.js', '.jsx', '.ts', '.tsx',
            '.pyd', '.so', '.toml', '.md', '.s', '.json', '.txt'
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
                
        # 🆕 --- GRAFO DE DEPENDÊNCIAS ---
        neighbors_map = {}
        if graph_depth > 0:
            from doxoade.commands.intelligence_systems.graph_builder import get_graph_neighbors
            console.print(
                f"[bold cyan]🕸️  Construindo Grafo de Dependências "
                f"(Profundidade: {graph_depth})...[/bold cyan]"
            )
            try:
                neighbors_map, new_files = get_graph_neighbors(
                    unique_files, root, ignore_spec, graph_depth
                )
                if new_files:
                    console.print(
                        f"[bold green]   ↳ {len(new_files)} arquivo(s) "
                        f"relacionado(s) descoberto(s)[/bold green]"
                    )
                # Injeta os arquivos descobertos no scan principal
                unique_files.extend(new_files)
                # Remove duplicatas mantendo ordem
                unique_files = list(dict.fromkeys(unique_files))
            except Exception as e:
                console.print(f"[bold red]   ⚠ Grafo falhou: {e}[/bold red]")
                neighbors_map = {}
        # -------------------------------------------

        dossier_files = []
        with click.progressbar(unique_files, label='[VULCAN:INTEL]') as bar:
            for f in bar:
                try:
                    res = analyze_file_chief(f, root, docs=include_docs, source=include_source)
                    if res and isinstance(res, dict) and 'size' in res:
                        # 🆕 PIPELINE DE MINIFICAÇÃO (-nc e -ns)
                        src = res.get('source_minified')
                        if src and (no_comments or no_spaces):
                            res['source_minified'] = minify_code(src, f, no_comments, no_spaces)
                        
                        # 🆕 ANEXA O GRAFO AO RELATÓRIO (Convertendo caminhos absolutos para relativos)
                        if graph_depth > 0 and f in neighbors_map:
                            res['graph_neighbors'] = [
                                os.path.relpath(x, root).replace('\\', '/') 
                                for x in neighbors_map[f]
                            ]
                        dossier_files.append(res)
                except Exception:
                    continue

        # Passa graph_depth e include_source para o salvador do relatório
        _save_report(dossier_files, output, root, concat, focus, ai_export, ia_qwen, console, graph_depth, include_source)

def _save_report(files, output, root, concat, focus, ai_export, ia_qwen, console, graph_depth=0, include_source=False):
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
    
    if graph_depth > 0:
        total_graph_edges = sum(len(f.get('graph_neighbors', [])) for f in files)
        economic_summary["total_graph_edges"] = total_graph_edges
        economic_summary["graph_depth"] = graph_depth

    # 🆕 Injeção do Glossário de Deuses
    from doxoade.commands.intelligence_systems.intelligence_utils import get_god_glossary
    
    report = {
        report_type: {
            "version": "2026.Chief.v2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_project": os.path.basename(root),
            "token_optimization": "ENABLED" if concat else "DISABLED",
            "focus_applied": focus if focus else "NONE"
        },
        "god_glossary": get_god_glossary(),  # 🆕 Glossário embutido
        "economic_summary": economic_summary,
        "codebase_map": report_files
    }
    
    # DESVIO PARA FORMATO QWEN (PRIORIDADE MÁXIMA)
    if ia_qwen:
        qwen_output = output.replace('.json', '') + "_qwen.xml" if output.endswith('.json') else output + "_qwen.xml"
        _save_qwen_report(report, qwen_output, console)
    elif ai_export:
        ai_output = output.replace('.json', '') + "_llm.xml" if output.endswith('.json') else output + "_llm.xml"
        _save_llm_report(report, ai_output, console, include_source)
#        _save_report(dossier_files, output, root, concat, focus, ai_export, ia_qwen, console, graph_depth, include_source)
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
    
def _save_llm_report(report_data, output_path, console, include_source=False):
    """Traduz o JSON arquitetural para um formato XML bem indentado e legível (PASC 11.0)."""
    lines = []
    meta = None
    for key in report_data.keys():
        if key.endswith("intelligence_report"):
            meta = report_data[key]
            break
    
    if meta:
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<doxoade_nexus_report>')
        lines.append(f'  <target_project>{meta.get("target_project")}</target_project>')
        lines.append(f'  <generated_at>{meta.get("generated_at")}</generated_at>')
        lines.append(f'  <focus_applied>{meta.get("focus_applied")}</focus_applied>')
        
        eco = report_data.get("economic_summary", {})
        lines.append('  <project_summary>')
        lines.append(f'    <total_files_scanned>{eco.get("total_files_scanned", 0)}</total_files_scanned>')
        lines.append(f'    <total_files_in_report>{eco.get("total_files_in_report", 0)}</total_files_in_report>')
        lines.append(f'    <average_complexity>{eco.get("average_complexity_in_report", 0):.2f}</average_complexity>')
        lines.append(f'    <total_debt_tags>{eco.get("total_debt_tags_in_report", 0)}</total_debt_tags>')
        
        # 🆕 Métricas do grafo
        if "total_graph_edges" in eco:
            lines.append(f'    <total_graph_edges>{eco.get("total_graph_edges", 0)}</total_graph_edges>')
            lines.append(f'    <graph_depth>{eco.get("graph_depth", 0)}</graph_depth>')
        
        lines.append('    <god_distribution>')
        for god, count in eco.get("god_distribution_in_report", {}).items():
            safe_god = god.lower().replace('ú','u').replace('ã','a').replace('é','e').replace('í','i').replace('ó','o')
            lines.append(f'      <{safe_god}>{count}</{safe_god}>')
        lines.append('    </god_distribution>')
        lines.append('  </project_summary>')
        
        # 🆕 Glossário de Deuses
        glossary = report_data.get("god_glossary", {})
        if glossary:
            lines.append('  <god_glossary>')
            for god, desc in glossary.items():
                safe_god = god.lower().replace('ú','u').replace('ã','a').replace('é','e').replace('í','i').replace('ó','o').replace(' ','_')
                import html
                desc_escaped = html.escape(desc)
                lines.append(f'    <{safe_god}>{desc_escaped}</{safe_god}>')
            lines.append('  </god_glossary>')
        
        lines.append('  <codebase_map>')
        for f in report_data.get("codebase_map", []):
            path = f.get('path', 'unknown')
            god = f.get('god_assignment', 'Unknown')
            comp = f.get('complexity', 0)
            status = f.get('status', 'unknown')
            lines.append(f'    <file path="{path}" role="{god}" complexity="{comp}" status="{status}">')
            
            classes = f.get('classes', [])
            if classes:
                lines.append(f'      <classes>{", ".join(str(c) for c in classes)}</classes>')
            
            funcs = f.get('functions', [])
            if funcs:
                # 🛡️ Se -s (source) está ativo, não inclui docstrings (já estão no código)
                if include_source:
                    funcs_str = []
                    for fn in funcs:
                        if isinstance(fn, str): 
                            funcs_str.append(fn)
                        elif isinstance(fn, dict): 
                            funcs_str.append(str(fn.get('name', 'unknown')))
                        else: 
                            funcs_str.append(str(getattr(fn, 'name', fn)))
                    lines.append(f'      <functions>{", ".join(funcs_str)}</functions>')
                else:
                    # Inclui docstrings quando -s NÃO está ativo
                    has_docs = any(isinstance(fn, dict) and fn.get('docstring') for fn in funcs)
                    if has_docs:
                        lines.append('      <functions>')
                        for fn in funcs:
                            if isinstance(fn, dict):
                                name = fn.get('name', 'unknown')
                                doc = fn.get('docstring', '')
                                import html
                                doc_escaped = html.escape(doc) if doc else ''
                                lines.append(f'        <function name="{name}">{doc_escaped}</function>')
                            else:
                                lines.append(f'        <function name="{fn}"></function>')
                        lines.append('      </functions>')
                    else:
                        funcs_str = []
                        for fn in funcs:
                            if isinstance(fn, str): funcs_str.append(fn)
                            elif isinstance(fn, dict): funcs_str.append(str(fn.get('name', 'unknown')))
                            else: funcs_str.append(str(getattr(fn, 'name', fn)))
                        lines.append(f'      <functions>{", ".join(funcs_str)}</functions>')
            
            debt = f.get('debt_tags_count', len(f.get('debt_tags', [])))
            mpot = f.get('mpot_violations_count', f.get('mpot_4_violations', 0))
            if debt > 0 or mpot > 0:
                lines.append(f'      <technical_debt tags="{debt}" mpot_violations="{mpot}" />')
            
            # 🆕 Grafo de vizinhos
            graph_n = f.get('graph_neighbors', [])
            if graph_n:
                lines.append('      <graph_neighbors>')
                for neighbor in graph_n:
                    lines.append(f'        <neighbor>{neighbor}</neighbor>')
                lines.append('      </graph_neighbors>')
            
            src = f.get('source_minified')
            if src:
                safe_src = src.replace(']]>', ']]]]><![CDATA[>')
                lines.append('      <source_code><![CDATA[')
                for code_line in safe_src.splitlines():
                    lines.append(code_line)
                lines.append('      ]]></source_code>')
            
            lines.append('    </file>')
        
        lines.append('  </codebase_map>')
        lines.append('</doxoade_nexus_report>')
        
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
        
def _run_analyze_coverage(scan_paths, cli_excludes, verbose, ext_excludes):
    """Auditoria de Cobertura: Blacklist, Extensões e Integridade de Parsing (Nexus Scan)."""
    from doxoade.commands.intelligence_systems.intelligence_engine import analyze_file_chief
    from doxoade.commands.intelligence_systems.intelligence_utils import get_ignore_spec
    from rich.table import Table
    
    scan_paths = scan_paths if scan_paths else ('.',)
    root = _find_project_root(os.getcwd())
    
    # 🆕 Fusão de Blacklists (TOML + CLI Paths + CLI Extensions)
    extra_patterns = list(cli_excludes)
    if ext_excludes:
        for ext in ext_excludes:
            if not ext.startswith('.'): ext = '.' + ext
            extra_patterns.append(f"*{ext}")
            
    ignore_spec = get_ignore_spec(root, extra_patterns=extra_patterns)
    
    # Extensões suportadas pelo Motor Nexus

    stats = {
        "raw": 0, "ignored": 0, "unsupported": 0, "target": 0,
        "success": 0, "failed": 0, "corrupt": 0
    }
    failures = []
    ignored_files = []
    unsupported_exts = {}  # 🆕 NOVO: Mapear extensões não suportadas
    
    console = Console()
    console.print("\n[bold cyan]🔍 Iniciando Auditoria de Cobertura Nexus (PASC Compliance)...[/bold cyan]\n")
    
    # 1. Coleta Bruta
    all_files_raw = []
    for p in scan_paths:
        p_abs = os.path.abspath(p)
        if os.path.isfile(p_abs):
            all_files_raw.append(p_abs)
        else:
            nav = DNM(p_abs)
            all_files_raw.extend(nav.scan()) 
            
    # 2. Processamento e Auditoria em 3 Camadas
    with click.progressbar(all_files_raw, label='[AUDIT] Analisando codebase') as bar:
        for f_abs in bar:
            stats["raw"] += 1
            rel_path = os.path.relpath(f_abs, root).replace('\\', '/')
            
            # CAMADA 1: Blacklist
            if ignore_spec.match_file(rel_path):
                stats["ignored"] += 1
                if verbose: ignored_files.append(rel_path)
                continue
                
            # CAMADA 2: Extensões Suportadas
            if not f_abs.endswith(VALID_EXTS):
                stats["unsupported"] += 1
                # 🆕 Captura a extensão para o relatório
                ext = os.path.splitext(f_abs)[1].lower()
                if ext:
                    unsupported_exts[ext] = unsupported_exts.get(ext, 0) + 1
                continue
                
            stats["target"] += 1
            
            # CAMADA 3: Integridade de Parsing
            try:
                res = analyze_file_chief(f_abs, root)
                if res.get("error"):
                    stats["failed"] += 1
                    failures.append({"file": rel_path, "reason": res["error"]})
                elif res.get("status") == "corrupt":
                    stats["corrupt"] += 1
                    failures.append({"file": rel_path, "reason": "Syntax/Parse Error (AST failed)"})
                else:
                    stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                failures.append({"file": rel_path, "reason": str(e)})

    # 3. Renderização do Relatório
    console.print("\n[bold green]✅ Auditoria Concluída.[/bold green]")
    
    table = Table(title="📊 Resumo de Cobertura e Integridade")
    table.add_column("Métrica", style="cyan")
    table.add_column("Total", justify="right", style="magenta")
    
    table.add_row("Arquivos Brutos (DNM)", str(stats["raw"]))
    table.add_row("Ignorados (Blacklist)", str(stats["ignored"]))
    table.add_row("Extensão Não Suportada", str(stats["unsupported"]))
    table.add_row("Alvos Válidos", str(stats["target"]))
    table.add_row("[green]Parseados com Sucesso[/green]", str(stats["success"]))
    table.add_row("[red]Falha de Leitura/IO[/red]", str(stats["failed"]))
    table.add_row("[yellow]Código Corrompido (AST)[/yellow]", str(stats["corrupt"]))
    
    console.print(table)
    
    # 🆕 NOVO: Tabela de Extensões Não Suportadas
    if unsupported_exts:
        console.print("\n[bold yellow]📦 Extensões Encontradas mas Não Suportadas pelo Motor Nexus:[/bold yellow]")
        ext_table = Table(show_header=True, header_style="bold yellow")
        ext_table.add_column("Extensão", style="cyan")
        ext_table.add_column("Quantidade", justify="right", style="magenta")
        
        # Ordena por quantidade (maior para menor)
        sorted_exts = sorted(unsupported_exts.items(), key=lambda x: x[1], reverse=True)
        for ext, count in sorted_exts:
            ext_table.add_row(ext if ext else "[dim](sem extensão)[/dim]", str(count))
            
        console.print(ext_table)
        console.print("[dim]💡 Dica: Para adicionar suporte nativo, crie um analisador (ex: intelligence_java.py) e adicione a extensão em `VALID_EXTS` no `intelligence_engine.py` e aqui na auditoria.[/dim]")

    # Validação Final
    total_processed = stats["success"] + stats["failed"] + stats["corrupt"]
    if total_processed == stats["target"]:
        console.print("\n[bold green]🎯 VEREDICTO: 100% dos arquivos alvo foram processados pelo motor.[/bold green]")
    else:
        console.print("\n[bold red]⚠️ VEREDICTO: Houve perda de arquivos no pipeline de parsing![/bold red]")

    # Detalhes (Verbose)
    if verbose:
        if ignored_files:
            console.print(f"\n[bold yellow]📂 Arquivos Ignorados pela Blacklist ({len(ignored_files)}):[/bold yellow]")
            for f in ignored_files[:10]: 
                console.print(f"  [dim]- {f}[/dim]")
            if len(ignored_files) > 10:
                console.print(f"  [dim]... e mais {len(ignored_files) - 10} arquivos.[/dim]")
                
        if failures:
            console.print(f"\n[bold red]🐞 Arquivos com Falha de Parsing ({len(failures)}):[/bold red]")
            fail_table = Table(show_header=True, header_style="bold red")
            fail_table.add_column("Arquivo")
            fail_table.add_column("Motivo")
            for f in failures:
                fail_table.add_row(f["file"], f["reason"])
            console.print(fail_table)

def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub('', text) if text else ""

def _clean_type(param_type) -> str:
    t = str(param_type)
    if "Path" in t: return "PATH"
    if "Choice" in t: return "CHOICE"
    if "Int" in t: return "INT"
    if "Float" in t: return "FLOAT"
    if "Bool" in t: return "BOOL"
    return ""  # STRING é o default, omitimos

def _extract_examples(help_text: str) -> list:
    if not help_text: return []
    clean = _strip_ansi(help_text)
    m = re.search(r'Exemplos?:\s*(.*?)(?:\n\n|\Z)', clean, re.DOTALL | re.IGNORECASE)
    if m:
        return [l.strip().lstrip('- ') for l in m.group(1).split('\n') if l.strip().startswith(('doxoade', '-'))]
    return []

def _cmd_to_xml(cmd, name: str) -> ET.Element:
    """Converte um comando Click diretamente em XML compacto (sem dict intermediário)."""
    elem = ET.Element("cmd", name=name)
    
    desc = _strip_ansi(cmd.help or "").strip()
    if desc:
        elem.set("desc", desc)
    
    # Exemplos (compactos como texto separado por ' | ')
    examples = _extract_examples(cmd.help)
    if examples:
        ex_elem = ET.SubElement(elem, "examples")
        ex_elem.text = " | ".join(examples)
    
    # Args posicionais
    for param in cmd.params:
        if isinstance(param, click.Argument):
            attrs = {"name": param.name}
            t = _clean_type(param.type)
            if t: attrs["type"] = t
            if getattr(param, "required", False): attrs["req"] = "1"
            ET.SubElement(elem, "arg", **attrs)
    
    # Options (flags)
    for param in cmd.params:
        if isinstance(param, click.Option):
            attrs = {"name": param.name}
            attrs["flags"] = ",".join(param.opts + param.secondary_opts)
            
            t = _clean_type(param.type)
            if t: attrs["type"] = t
            
            help_text = _strip_ansi(getattr(param, "help", None) or "").strip()
            if help_text: attrs["help"] = help_text
            
            if param.is_flag: attrs["flag"] = "1"
            if param.multiple: attrs["multi"] = "1"
            if getattr(param, "required", False): attrs["req"] = "1"
            
            # Default: só inclui se for significativo
            if not param.is_flag and param.default is not None:
                d = str(param.default)
                if d not in ("Sentinel.UNSET", "None", "", "False"):
                    attrs["default"] = d
            
            ET.SubElement(elem, "opt", **attrs)
    
    # Subcomandos (recursão)
    if isinstance(cmd, click.MultiCommand):
        ctx = click.Context(cmd)
        for sub_name in cmd.list_commands(ctx):
            sub_cmd = cmd.get_command(ctx, sub_name)
            if sub_cmd:
                elem.append(_cmd_to_xml(sub_cmd, sub_name))
    
    return elem

def generate_manifest():
    """Gera o manifesto XML compacto e salva automaticamente."""
    from doxoade.cli import cli
    
    ctx = click.Context(cli)
    
    root = ET.Element("doxoade")
    root.set("version", "85.1")
    root.set("mode", "dry-run")
    root.set("exec", "--run")
    
    # Descrição compacta no topo
    desc_elem = ET.SubElement(root, "desc")
    desc_elem.text = _strip_ansi(cli.help or "").strip()
    
    # Comandos
    for cmd_name in cli.list_commands(ctx):
        cmd = cli.get_command(ctx, cmd_name)
        if cmd:
            root.append(_cmd_to_xml(cmd, cmd_name))
    
    # Formata e salva
    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_bytes
    
    out_path = Path("doxoade_manifest.xml")
    out_path.write_text(xml_str, encoding="utf-8")
    
    cmd_count = len(list(root.iter("cmd")))
    line_count = xml_str.count('\n') + 1
    click.secho(f"✅ [THOTH] Manifesto gerado: {out_path.resolve()}", fg="green", bold=True)
    click.secho(f"   📦 {cmd_count} comandos | {line_count} linhas | {len(xml_str)//1024}KB", fg="cyan")
