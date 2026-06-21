# doxoade/doxoade/tools/display.py
import click
import re, sys
# [DOX-UNUSED] import os
from collections import Counter
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection
# [DOX-UNUSED] from .analysis import _get_code_snippet_from_string
from .display_systems import display_elements as ui

def _get_lexicon_remedy(f_hash, message=None):
    """Consulta o Acervo Hades com busca dupla (Hash + Semântica)."""
    try:
        conn = get_db_connection()
        # 1. Tenta por Hash exato
        res = conn.execute("SELECT snippet_fixed FROM knowledge_lexicon WHERE finding_hash = ?", (f_hash,)).fetchone()
        
        # 2. Fallback: Tenta por similaridade de mensagem
        if not res and message:
            res = conn.execute("SELECT snippet_fixed FROM knowledge_lexicon WHERE message = ? LIMIT 1", (message,)).fetchone()
            
        conn.close()
        return res[0] if res else None
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] _get_lexicon_remedy: {e}")
        return None

def _get_icon(emoji, fallback):
    try:
        emoji.encode(sys.stdout.encoding or 'ascii')
        return emoji
    except UnicodeEncodeError:
        return fallback
ICON_LIGHTBULB = _get_icon('💡', '[!]')
ICON_WRENCH = _get_icon('🛠', '->')

def _present_results(output_format, results, max_issues=50, verbose=False):
    findings = results.get('findings', [])
    summary = results.get('summary', {})
    
    if output_format == 'json':
        import json
        click.echo(json.dumps(results, indent=2))
        return

    if not findings:
        click.secho("\n✨ [ESTADO DE OURO] Excelência mantida.", fg='green', bold=True)
        return

    # Header Industrial
    ui.sep(color=Fore.WHITE, dim=False)
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}🔍 RESULTADOS DA AUDITORIA{Style.RESET_ALL}")
    click.echo(f"   Criticos: {summary.get('critical')} | Erros: {summary.get('errors')} | Avisos: {summary.get('warnings')}")
    ui.sep(color=Fore.WHITE, dim=False)

    grouped = {}
    for f in findings:
        path = f.get('file') or 'GLOBAL'
        grouped.setdefault(path, []).append(f)

    for file_path, issues in grouped.items():
        ui.file_panel(file_path)
        for finding in issues:
            _print_finding_details(finding)
    
    ui.sep()

def _print_finding_details(finding):
    """Card de Auditoria Platinum Gold - Sincronizado com Prévias."""
    severity = finding.get('severity', 'INFO').upper()
    category = (finding.get('category') or 'UNCATEGORIZED').upper()
    f_hash = finding.get('finding_hash') or finding.get('hash')
    file_path = finding.get('file')
    line_num = finding.get('line', 0)
    action = finding.get('suggestion_action')
    
    click.echo(ui.badge(severity, category, finding.get('message')))
    click.echo(f"     {Style.DIM}↳ {Fore.CYAN}{file_path}:{line_num}{Style.RESET_ALL}")
    
    # Exibe o bloco de código
    ui.code_block(file_path, line_num, finding.get('snippet'))
    
    # Tenta obter remédio do histórico (Hades) ou sugestão do motor (Atena)
    remedy_text = _get_lexicon_remedy(f_hash)
    
    if action:
        # Se for correção de bloco, a linha original que queremos mostrar no diff
        # é a linha de cima (onde está o comentário)
        orig_line_idx = line_num - 1 if action == 'FIX_BLOCK_SYNTAX' else line_num
        
        original_line = ""
        if finding.get('snippet'):
            original_line = finding['snippet'].get(str(orig_line_idx)) or finding['snippet'].get(orig_line_idx, "")

        ui.remedy(
            f"doxoade check --fix -fs {action}", 
            is_historical=False,
            fixed_content=finding.get('suggestion_content'),
            original_content=original_line,
            line_num=orig_line_idx
        )
    if finding.get('archaeology'):
        arc = finding['archaeology']
        attr = finding.get('attrition')
        click.echo(f"     {Fore.BLUE}🏛️  ORIGEM: {Fore.WHITE}{arc['date_str']} ({arc['hash'][:7]})")
        
        if attr and attr.get('evidence'):
            click.echo(f"     {Fore.MAGENTA}🥀 ATRIÇÃO: {Fore.WHITE}Uso removido em {attr['date']} ({attr['hash'][:7]})")
            for line in attr['evidence']:
                click.echo(f"      {Fore.RED}{Style.DIM} - {line[:70]}{Style.RESET_ALL}")

def _print_summary(results, ignored_count):
    findings = results.get('findings', [])
    display_findings = [f for f in findings if f.get('hash') not in (ignored_count or set())]
    click.echo(Style.BRIGHT + '\n' + '-' * 60)
    if not display_findings:
        click.echo(Fore.GREEN + '[OK] Análise concluída. Nenhum problema encontrado!')
        return
    category_counts = Counter((f['category'] for f in display_findings))
    if category_counts:
        click.echo(Fore.CYAN + '📊 Distribuição e Filtros:')
        click.echo(Fore.WHITE + f"{'CATEGORIA':<20} | {'QTD':<5} | {'AÇÃO SUGERIDA'}")
        click.echo(Fore.WHITE + '-' * 60)
        CRITICAL_CATS = {'SECURITY', 'CRITICAL', 'SYNTAX', 'RISK-MUTABLE'}
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            if category in CRITICAL_CATS:
                cat_color, action = (Fore.RED, f'{Fore.RED}CORRIGIR IMEDIATAMENTE')
            else:
                cat_color, action = (Fore.YELLOW, f'{Style.DIM}--exclude {category}{Style.RESET_ALL}')
            click.echo(f'{cat_color}{category:<20}{Style.RESET_ALL} | {Fore.WHITE}{count:<5}{Style.RESET_ALL} | {action}')
    click.echo(Fore.WHITE + '-' * 60)
    total = len(display_findings)
    click.echo(f'[FIM] {total} Problema(s) listado(s).')

def _present_diff_output(output, error_line_number=None):
    lines_to_print = []
    in_relevant_hunk = error_line_number is None
    for line in output.splitlines():
        if line.startswith('@@'):
            match = re.search('@@ -(\\d+)(,(\\d+))? \\+(\\d+)(,(\\d+))? @@(.*)', line)
            if not match:
                continue
            start_line = int(match.group(1))
            lines_to_print.append(Fore.CYAN + f'Mudanças perto da linha {start_line}')
            in_relevant_hunk = True
        elif in_relevant_hunk:
            if line.startswith('+'):
                lines_to_print.append(Fore.GREEN + f'     + | {line[1:]}')
            elif line.startswith('-'):
                lines_to_print.append(Fore.RED + f'     - | {line[1:]}')
            elif line.startswith(' '):
                lines_to_print.append(Fore.WHITE + f'       | {line[1:]}')
    if lines_to_print:
        click.echo('\n'.join(lines_to_print))

def _format_timestamp(iso_str):
    try:
        dt_utc = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        import logging as _dox_log
        _dox_log.error(f"[INFRA] _format_timestamp: {e}")
        return iso_str

def _print_summary(results, ignored_count):
    """Barra de sumário final com estatísticas de categorias."""
    findings = results.get('findings', [])
    if not findings: return
    
    category_counts = Counter((f['category'] for f in findings))
    click.echo(Fore.CYAN + '📊 Distribuição e Filtros:')
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        click.echo(f"   {Fore.WHITE}{category:<20} | {Fore.YELLOW}{count:<5}")
    click.echo(Fore.WHITE + '-' * 60)
