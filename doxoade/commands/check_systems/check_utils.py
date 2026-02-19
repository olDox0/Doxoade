# -*- coding: utf-8 -*-
# doxoade/commands/check_utils.py
import os
from click import echo
from colorama import Fore, Style
from collections import defaultdict
from typing import List, Dict, Any
from .check_state import CheckState

def render_archived_view(state: CheckState):
    """Renderiza o Dossiê Consolidado (PASC 8.2)."""
    if not state.findings:
        echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [ESTADO DE OURO]{Fore.WHITE} Nenhum problema encontrado!")
        return

    # Agrupamento Único (MPoT-4)
    grouped = defaultdict(list)
    for f in state.findings:
        if f.get('category') != 'SYSTEM':
            grouped[f.get('file', 'unknown')].append(f)

    if not grouped: return
    echo(f"\n{Fore.BLUE}{Style.BRIGHT}--- 📂 DOSSIÊ DE DÍVIDA TÉCNICA ({len(grouped)} arquivos) ---{Style.RESET_ALL}")

    for file_path, file_findings in sorted(grouped.items()):
        # Especialista de Arquivo
        _render_single_file_dossier(file_path, file_findings)

    # Sumário Final de Rodapé
    summary = state.summary
    echo(f"{Fore.BLUE}{Style.BRIGHT}─" * 75 + Style.RESET_ALL)
    echo(f"  {Fore.WHITE}SOMA TOTAL: {Fore.RED}{summary.get('errors', 0)} Erros{Fore.WHITE} | {Fore.YELLOW}{summary.get('warnings', 0)} Avisos")
    echo(f"{Fore.BLUE}{Style.BRIGHT}─" * 75 + Style.RESET_ALL)

    if state.alb_files:
        _render_alb_report(state.alb_files)

def _render_alb_report(alb_files: List[str]):
    # FIX: Subindo 3 níveis para chegar em doxoade/tools
    from ...tools.governor import governor
    echo(f"\n{Fore.CYAN}{Style.BRIGHT}⚖  ALB RESOURCE REPORT:{Style.RESET_ALL}")
    echo(f"   Status      : {Fore.YELLOW}Análise reduzida em {len(alb_files)} tarefas")
    echo(f"   Economia    : {Fore.GREEN}~{governor.get_savings_estimate()} poupados")
    
    names = [os.path.basename(f) for f in alb_files]
    display_str = ", ".join(names[:10]) + (f" ... e mais {len(names)-10}" if len(names) > 10 else "")
    echo(f"   Alvos       : {Fore.WHITE}{display_str}")

def _render_issue_summary(findings: list, **kwargs):
    """Sumário Estatístico Consolidado (v84.3)."""
    from click import echo # FIX: Importação movida para fora do bloco IF
    
    if not findings and not kwargs.get('full_power'):
        echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [ESTADO DE OURO]{Fore.WHITE} Nenhum problema encontrado!")
        return
    
    # Especialista 1: Agregação de dados
    stats = _calculate_incident_stats(findings)
    
    echo(f"\n{Fore.CYAN}{Style.BRIGHT}📊 RESUMO DE INCIDENTES POR TIPO:{Style.RESET_ALL}")
    
    id_map = {"unused-import": "FIX_UNUSED_IMPORT", "bare-except": "RESTRICT_EXCEPTION", 
              "unused-variable": "REPLACE_WITH_UNDERSCORE", "f-string": "REMOVE_F_PREFIX"}

    for cat in sorted(stats.keys()):
        sub_types = sorted(stats[cat].items(), key=lambda x: (x[0] == "geral", x[0]))
        for sub, count in sub_types:
            label = cat if sub == "geral" else f"{cat}, {sub}"
            line = f"   {Fore.WHITE}{label:<35} : {Fore.YELLOW}{count:<4}"
            hint = f" {Fore.CYAN}· sugestão: {Fore.GREEN}{Style.BRIGHT}doxoade check -fs {id_map[sub]}" if sub in id_map else ""
            echo(f"{line}{hint}{Style.RESET_ALL}")
    
    echo(f"{Fore.CYAN}{Style.DIM}─" * 85 + Style.RESET_ALL)
    _render_resource_report(kwargs.get('full_power'))

def _render_resource_report(full_power):
    # FIX: Subindo 3 níveis para chegar em doxoade/tools
    from ...tools.memory_pool import finding_arena
    from ...tools.streamer import ufs
    from ...tools.governor import governor
    
    status = f"{Fore.RED}OVERRIDE" if full_power else f"{Fore.GREEN}ATIVO"
    echo(f"\n{Fore.BLUE}{Style.BRIGHT}🛡  ALB PROTECT ({status}):{Style.RESET_ALL}")
    
    if governor.interventions > 0:
        echo(f"   Economia de CPU       : {Fore.GREEN}~{governor.get_savings_estimate()} poupados")
        echo(f"   Tarefas Adaptadas     : {Fore.YELLOW}{governor.interventions} arquivos omitidos")
    
    echo(f"   Reciclagem de Memória : {Fore.GREEN}{finding_arena._ptr} objetos reutilizados")
    echo(f"   Economia de Disco     : {Fore.GREEN}{ufs.reads_saved} aberturas evitadas")
    echo(f"{Fore.CYAN}{Style.DIM}─" * 85 + Style.RESET_ALL)

def _finalize_log(findings, logger, root, excludes):
    """Bridge de Compatibilidade para o ExecutionLogger legado."""
    from ...tools.analysis import _get_code_snippet
    exclude_set = set([c.upper() for c in (excludes or [])])
    
    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat in exclude_set: continue
        
        abs_f = os.path.abspath(f['file'])
        logger.add_finding(
            severity=f['severity'], message=f['message'], category=cat,
            file=abs_f, line=f.get('line', 0),
            snippet=_get_code_snippet(abs_f, f.get('line', 0)),
            suggestion_action=f.get('suggestion_action')
        )
        
def _calculate_incident_stats(findings: List[Dict[str, Any]]) -> dict:
    """Especialista de contagem estatística centralizado (PASC 8.5)."""
    from collections import defaultdict
    stats = defaultdict(lambda: defaultdict(int))
    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat == 'SYSTEM': continue
        
        msg = f.get('message', '').lower()
        sub = "geral"
        if "f-string" in msg: sub = "f-string"
        elif "imported but unused" in msg: sub = "unused-import"
        elif "assigned to but never used" in msg: sub = "unused-variable"
        elif "except:" in msg or ("except" in msg and ":" in msg and "exception" not in msg): sub = "bare-except"
        stats[cat][sub] += 1
    return stats
    
def _render_single_file_dossier(file_path, findings):
    """Renderiza os achados de um arquivo individual (MPoT-4)."""
    # Filtro de unicidade para evitar poluição visual
    unique_findings = []
    seen = set()
    for f in findings:
        key = (f.get('line', 0), f.get('message', ''))
        if key not in seen:
            unique_findings.append(f); seen.add(key)

    count = len(unique_findings)
    header_color = Fore.BLUE if count < 5 else (Fore.YELLOW if count < 10 else Fore.RED)
    echo(f"\n{header_color}{Style.BRIGHT}[  {count:03}  ]{Fore.WHITE} {file_path}{Style.RESET_ALL}")
    
    cat_colors = {
        'COMPLEXITY': Fore.RED, 'RUNTIME-RISK': Fore.RED + Style.BRIGHT, 
        'SECURITY': Fore.MAGENTA + Style.BRIGHT, 'SYNTAX': Fore.LIGHTRED_EX + Style.BRIGHT, 
        'DEADCODE': Fore.CYAN, 'STYLE': Fore.YELLOW, 'QA-REMINDER': Fore.GREEN
    }

    for f in unique_findings:
        cat = f.get('category', 'STYLE').upper()
        line_err = f.get('line', 0)
        color = cat_colors.get(cat, Fore.YELLOW)
        echo(f"   {color}■{Fore.WHITE}{Style.DIM} [ L-{str(line_err).ljust(4)}] {Style.NORMAL}{color}{cat:<15}{Fore.WHITE}: {f['message']}{Style.RESET_ALL}")
        
        # Snippet JIT (Restauração de Visão)
        snippet = f.get('snippet')
        if snippet:
            for snip_line, snip_text in sorted(snippet.items()):
                is_target = (int(snip_line) == line_err)
                prefix = "      > " if is_target else "        "
                s_color = Fore.WHITE + Style.BRIGHT if is_target else Fore.WHITE + Style.DIM
                echo(f"{s_color}{prefix}{snip_line:4}: {snip_text}{Style.RESET_ALL}")
            
        if f.get('suggestion_action'):
            echo(f"      {Fore.CYAN}💡 AÇÃO SUGERIDA: {Fore.GREEN}{Style.BRIGHT}{f['suggestion_action']}{Style.RESET_ALL}")