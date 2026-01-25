# -*- coding: utf-8 -*-
# doxoade/commands/check_utils.py
import os
from typing import List, Dict, Any
from colorama import Fore, Style
from click import echo

def _finalize_log(findings, logger, root, excludes):
    """Envia os achados para o logger com caminhos resilientes."""
    exclude_set = set([c.upper() for c in (excludes or [])])
    from ..tools.analysis import _get_code_snippet
    
    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        if cat in exclude_set: continue
        
        abs_f = os.path.abspath(f['file'])
        try:
            # Tenta mostrar o caminho relativo à raiz do projeto alvo
            rel_f = os.path.relpath(abs_f, root)
            # Se subir demais (../..), usa o nome do arquivo para não poluir a UI
            if rel_f.count('..') > 2:
                rel_f = os.path.basename(abs_f)
        except ValueError:
            # Fallback para caminhos em drives diferentes (Windows)
            rel_f = abs_f

        logger.add_finding(
            severity=f['severity'], message=f['message'], category=cat,
            file=rel_f, line=f.get('line', 0),
            snippet=_get_code_snippet(abs_f, f.get('line')),
            suggestion_action=f.get('suggestion_action')
        )

# doxoade/commands/check_utils.py

def _render_archived_view(results):
    """Exibe o Dossiê Gold de forma simétrica com Colorimetria Industrial."""
    findings = results.get('findings', [])
    if not findings:
        echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ [ESTADO DE OURO]{Fore.WHITE} Nenhum problema encontrado!{Style.RESET_ALL}")
        return

    from collections import defaultdict
    grouped = defaultdict(list)
    for f in findings:
        grouped[f['file']].append(f)

    # Título do Dossiê em Azul Cobalto
    echo(f"\n{Fore.BLUE}{Style.BRIGHT}--- 📂 DOSSIÊ DE DÍVIDA TÉCNICA ({len(grouped)} arquivos afetados) ---{Style.RESET_ALL}")
    
    # Mapeamento de Cores por Categoria (Compliance: PASC-10)
    cat_colors = {
        'COMPLEXITY': Fore.RED,
        'RUNTIME-RISK': Fore.RED + Style.BRIGHT,
        'SECURITY': Fore.MAGENTA + Style.BRIGHT,
        'SYNTAX': Fore.LIGHTRED_EX + Style.BRIGHT,
        'DEADCODE': Fore.CYAN,
        'UNUSED-PRIVATE': Fore.CYAN + Style.DIM,
        'STYLE': Fore.YELLOW,
        'QA-REMINDER': Fore.GREEN,
        'SYSTEM': Fore.CYAN + Style.BRIGHT
    }

    for file_path, file_findings in sorted(grouped.items()):
        # [MPoT-7] Limpeza de redundância para evitar poluição visual
        unique_findings = []
        seen_keys = set()
        for f in file_findings:
            key = (f.get('line', 0), f.get('message', ''))
            if key not in seen_keys:
                unique_findings.append(f)
                seen_keys.add(key)
        
        count = len(unique_findings)
        
        # Cabeçalho do Arquivo com Intensidade Dinâmica
        header_color = Fore.BLUE if count < 5 else (Fore.YELLOW if count < 10 else Fore.RED)
        echo(f"\n{header_color}{Style.BRIGHT}[  {count:03}  ]{Fore.WHITE} {file_path}{Style.RESET_ALL}")
        
        for f in unique_findings:
            cat = f.get('category', 'STYLE').upper()
            sev = f.get('severity', 'WARNING').upper()
            line = str(f.get('line', '??')).ljust(4)
            
            # Seleção de Cor baseada na Categoria ou Severidade Crítica
            color = cat_colors.get(cat, Fore.YELLOW)
            if sev == 'CRITICAL': color = Fore.MAGENTA + Style.BRIGHT
            
            # RENDERIZAÇÃO GOLD: 
            # Bullet (Cor) | Linha (Dim) | Categoria (Cor Alinhada) | Mensagem (White)
            echo(f"   {color}■{Fore.WHITE}{Style.DIM} [ L-{line}] {Style.NORMAL}{color}{cat:<15}{Fore.WHITE}: {f['message']}{Style.RESET_ALL}")

    # Resumo Final de Alta Visibilidade
    summary = results.get('summary', {})
    echo(f"{Fore.BLUE}{Style.BRIGHT}─" * 75 + Style.RESET_ALL)
    echo(f"  {Fore.WHITE}SOMA TOTAL: "
         f"{Fore.RED}{summary.get('errors', 0)} Erros{Fore.WHITE} | "
         f"{Fore.YELLOW}{summary.get('warnings', 0)} Avisos{Fore.WHITE} | "
         f"{Fore.MAGENTA}{summary.get('critical', 0)} Críticos")
    echo(f"{Fore.BLUE}{Style.BRIGHT}─" * 75 + Style.RESET_ALL)
    
def _render_issue_summary(findings: List[Dict[str, Any]]):
    """Sumário Estatístico Chief-Gold (Alinhamento Industrial)."""
    if not findings: return
    from collections import defaultdict
    
    stats = defaultdict(lambda: defaultdict(int))
    id_map = {
        "unused-import": "FIX_UNUSED_IMPORT",
        "bare-except": "RESTRICT_EXCEPTION",
        "unused-variable": "REPLACE_WITH_UNDERSCORE",
        "f-string": "REMOVE_F_PREFIX"
    }

    for f in findings:
        cat = f.get('category', 'UNCATEGORIZED').upper()
        msg = f.get('message', '').lower()
        sub = "geral"
        if "f-string" in msg: sub = "f-string"
        elif "imported but unused" in msg: sub = "unused-import"
        elif "assigned to but never used" in msg: sub = "unused-variable"
        elif "except:" in msg or ("except" in msg and ":" in msg and "exception" not in msg): sub = "bare-except"
#        elif "except:" in msg or ("except" in msg and "exception" not in msg): sub = "bare-except"
        stats[cat][sub] += 1

    echo(f"\n{Fore.CYAN}{Style.BRIGHT}📊 RESUMO DE INCIDENTES POR TIPO:{Style.RESET_ALL}")
    
    for cat in sorted(stats.keys()):
        # Coloca o 'geral' por último
        sub_types = sorted(stats[cat].items(), key=lambda x: (x[0] == "geral", x[0]))
        for sub, count in sub_types:
            label = cat if sub == "geral" else f"{cat}, {sub}"
            line = f"   {Fore.WHITE}{label:<35} : {Fore.YELLOW}{count:<4}"
            
            hint = ""
            if sub in id_map:
                hint = f" {Fore.CYAN}· sugestão: {Fore.GREEN}{Style.BRIGHT}doxoade check -fs {id_map[sub]}"
            
            echo(f"{line}{hint}{Style.RESET_ALL}")
    echo(f"{Fore.CYAN}{Style.DIM}─" * 85 + Style.RESET_ALL)
    
    from ..tools.memory_pool import finding_arena
    from ..tools.streamer import ufs
    
    echo(f"\n{Fore.BLUE}{Style.BRIGHT}🛡  ALB PROTECT:{Style.RESET_ALL}")
    echo(f"   Reciclagem de Memória : {Fore.GREEN}{finding_arena._ptr} objetos reutilizados")
    echo(f"   Economia de Disco     : {Fore.GREEN}{ufs.reads_saved} aberturas evitadas")
    echo(f"{Fore.CYAN}{Style.DIM}─" * 85 + Style.RESET_ALL)
    
def _load_file_lines(file_path: str) -> list:
    """Usa o Streamer Unificado para evitar re-leitura de disco (MPoT-3)."""
    from ..tools.streamer import ufs # PASC-6.6
    return ufs.get_lines(file_path)