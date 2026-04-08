# doxoade/tools/display.py
import click
import re, sys
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
from collections import Counter
from .analysis import _get_code_snippet_from_string

def _get_icon(emoji, fallback):
    try:
        # Tenta codificar para o output atual. Se falhar, usa fallback ASCII.
        emoji.encode(sys.stdout.encoding or 'ascii')
        return emoji
    except UnicodeEncodeError:
        return fallback

# Definição de Ícones Seguros
ICON_LIGHTBULB = _get_icon("💡", "[!]")
ICON_WRENCH = _get_icon("🛠", "->")

def _present_results(output_format, results, max_issues=50, verbose=False):
    findings = results.get('findings', [])
    summary = results.get('summary', {})

    # ---------------------------
    # JSON permanece intacto
    # ---------------------------
    if output_format == 'json':
        import json
        click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        return

    # ---------------------------
    # SEM RESULTADOS
    # ---------------------------
    if not findings:
        click.echo(Fore.GREEN + Style.BRIGHT + "\n[OK] Nenhum problema encontrado! \\o/")
        return

    # ---------------------------
    # RESUMO NO TOPO (novo, leve)
    # ---------------------------
    critical = summary.get('critical', 0)
    errors = summary.get('errors', 0)
    warnings = summary.get('warnings', 0)

    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- ANÁLISE ---")
    click.echo(
        Fore.WHITE +
        f"?? {critical} | ? {errors} | ?? {warnings} | ?? {len(findings)} total"
    )

    # ---------------------------
    # LIMITADOR (anti-spam)
    # ---------------------------
    total = len(findings)
    if total > max_issues:
        findings = findings[:max_issues]
        click.echo(Fore.YELLOW + f"\n[!] Mostrando {max_issues}/{total} resultados (use --max-issues para expandir)")

    # ---------------------------
    # AGRUPAMENTO POR ARQUIVO (sem quebrar estrutura)
    # ---------------------------
    grouped = {}
    for f in findings:
        file = f.get('file') or 'GLOBAL'
        grouped.setdefault(file, []).append(f)

    # ---------------------------
    # PRINT ORGANIZADO
    # ---------------------------
    for file, issues in grouped.items():
        click.echo(Fore.WHITE + Style.BRIGHT + f"\n?? {file}")

        for finding in issues:
            _print_finding_details(finding)
            print()

    # ---------------------------
    # RESUMO FINAL (mantido, mas limpo)
    # ---------------------------
    click.echo(Fore.WHITE + "-" * 40)

    if critical > 0:
        click.echo(f"{Fore.MAGENTA}[CRÍTICO] {critical} problema(s) crítico(s).")
    elif errors > 0:
        click.echo(f"{Fore.RED}[ERRO] {errors} erro(s).")
    else:
        click.echo(f"{Fore.YELLOW}[AVISO] {warnings} aviso(s).")

    print(Style.RESET_ALL)

def _print_finding_details(finding):
    severity = finding.get('severity', 'INFO').upper()
    category = (finding.get('category') or 'UNCATEGORIZED').upper()
    color_map = {'CRITICAL': Fore.MAGENTA, 'ERROR': Fore.RED, 'WARNING': Fore.YELLOW, 'INFO': Fore.CYAN}
    color = color_map.get(severity, Fore.WHITE)
    tag = f"[{severity}][{category}]"
    
    click.echo(color + f"{tag} {finding.get('message', 'Mensagem não encontrada.')}")
    
    if finding.get('file'):
        location = f"   > Em '{finding.get('file')}'"
        if finding.get('line'):
            location += f" (linha {finding.get('line')})"
        click.echo(location)

    if finding.get('details'):
        click.echo(Fore.CYAN + f"   > {finding.get('details')}")
        
    snippet = finding.get('snippet')
    error_line = finding.get('line')
#    error_line = int(finding.get('line') or -1)
    
    if snippet and isinstance(snippet, dict):
        for line_num_str, code_line in snippet.items():
            line_num = int(line_num_str)
            prefix = "   > " if line_num == error_line else "     "
            line_color = Fore.WHITE + Style.BRIGHT if line_num == error_line else Fore.WHITE + Style.DIM
            click.echo(line_color + f"{prefix}{line_num:4}: {code_line}")

    if finding.get('import_suggestion'):
        click.echo(Fore.CYAN + Style.BRIGHT + "\n   > [ABDUÇÃO]")
        click.echo(Fore.GREEN + f"   {ICON_LIGHTBULB} SUGESTÃO:\n   > {finding.get('import_suggestion')}")
        return

    if finding.get('suggestion_content') or finding.get('suggestion_action'):
        source = finding.get('suggestion_source', 'GÊNESE')
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n   {ICON_LIGHTBULB} SOLUÇÃO CONHECIDA:")
        click.echo(Fore.GREEN + f"   > Fonte: {source}")
        
        if finding.get('suggestion_action'):
            click.echo(Fore.YELLOW + f"   {ICON_WRENCH}  AÇÃO: {finding.get('suggestion_action')}")
            
        if finding.get('suggestion_content'):
            # Mostra a linha corrigida
            click.echo(Fore.GREEN + f"   > Sugestão: {finding['suggestion_content'].strip()}")
            
        if snippet and finding.get('suggestion_line') and finding.get('suggestion_content'):
            suggestion_line = finding.get('suggestion_line')
            suggestion_snippet = _get_code_snippet_from_string(finding['suggestion_content'], suggestion_line, context_lines=2)
            
            if suggestion_snippet:
                for line_num, code_line in suggestion_snippet.items():
                    prefix = "   > " if line_num == suggestion_line else "     "
                    click.echo(Fore.GREEN + f"{prefix}{line_num:4}: {code_line}")

def _print_summary(results, ignored_count):
# [DOX-UNUSED]     summary = results.get('summary', {})
    findings = results.get('findings', [])
    display_findings = [f for f in findings if f.get('hash') not in (ignored_count or set())]
    
    click.echo(Style.BRIGHT + "\n" + "-"*60)
    
    if not display_findings:
        click.echo(Fore.GREEN + "[OK] Análise concluída. Nenhum problema encontrado!")
        return
        
    category_counts = Counter(f['category'] for f in display_findings)
    if category_counts:
        click.echo(Fore.CYAN + "📊 Distribuição e Filtros:")
        click.echo(Fore.WHITE + f"{'CATEGORIA':<20} | {'QTD':<5} | {'AÇÃO SUGERIDA'}")
        click.echo(Fore.WHITE + "-"*60)
        
        CRITICAL_CATS = {'SECURITY', 'CRITICAL', 'SYNTAX', 'RISK-MUTABLE'}
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            if category in CRITICAL_CATS:
                cat_color, action = Fore.RED, f"{Fore.RED}CORRIGIR IMEDIATAMENTE"
            else:
                cat_color, action = Fore.YELLOW, f"{Style.DIM}--exclude {category}{Style.RESET_ALL}"
            click.echo(f"{cat_color}{category:<20}{Style.RESET_ALL} | {Fore.WHITE}{count:<5}{Style.RESET_ALL} | {action}")

    click.echo(Fore.WHITE + "-"*60)
    # Resumo final simplificado
    total = len(display_findings)
    click.echo(f"[FIM] {total} Problema(s) listado(s).")

def _present_diff_output(output, error_line_number=None):
    lines_to_print = []
    in_relevant_hunk = (error_line_number is None)
    
    for line in output.splitlines():
        if line.startswith('@@'):
            match = re.search(r'@@ -(\d+)(,(\d+))? \+(\d+)(,(\d+))? @@(.*)', line)
            if not match: continue
            start_line = int(match.group(1))
            lines_to_print.append(Fore.CYAN + f"Mudanças perto da linha {start_line}")
            in_relevant_hunk = True 
        elif in_relevant_hunk:
            if line.startswith('+'): lines_to_print.append(Fore.GREEN + f"     + | {line[1:]}")
            elif line.startswith('-'): lines_to_print.append(Fore.RED + f"     - | {line[1:]}")
            elif line.startswith(' '): lines_to_print.append(Fore.WHITE + f"       | {line[1:]}")
    
    if lines_to_print:
        click.echo('\n'.join(lines_to_print))
        
def _format_timestamp(iso_str):
    try:
        dt_utc = datetime.fromisoformat(iso_str)
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return iso_str
    except ValueError: return iso_str
    
def _print_maat_summary(findings, score):
    """Interface de Ma'at: O Peso do Coração contra a Pena."""
    from doxoade.tools.doxcolors import Fore, Style, Back
    
    print("\n" + Back.WHITE + Fore.BLACK + f" ⚖  SENTENÇA DE MA'AT: {score}/100 " + Style.RESET_ALL)
    
    for f in findings:
        prefix = f"{Fore.RED}[REGRESSÃO]{Fore.RESET}" if f['severity'] == 'CRITICAL' else f"{Fore.YELLOW}[ALERTA]{Fore.RESET}"
        print(f"  {prefix} {f['category']}: {f['message']}")