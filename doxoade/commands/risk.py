# -*- coding: utf-8 -*-
"""
Módulo de Gestão de Risco Operacional (v4.3 - Gold Standard).
Calcula estabilidade baseada na densidade estatística de arquivos afetados.
Conformidade MPoT: Funções curtas, contratos ativos e lógica desacoplada.
"""

import click
import sqlite3
import os
from typing import Dict, Any, List, Tuple
from colorama import Fore, Style
from ..database import get_db_connection
from ..dnm import DNM

__version__ = "4.3 Alfa (Gold Standard - Final)"

def _get_project_metrics(cursor: sqlite3.Cursor, project_path: str) -> Dict[str, Any]:
    """Coleta métricas base. MPoT-5: Contrato Ativo."""
    if cursor is None or not project_path:
        raise ValueError("Dados de contexto (Cursor/Path) são obrigatórios.")

    dnm = DNM(project_path)
    all_files = dnm.scan(extensions=['.py'])
    total_count = len(all_files) or 1

    metrics = {'total_files': total_count, 'affected_files': 0, 'by_category': {}}

    # Agrupa incidentes por categoria para calcular densidade
    cursor.execute("""
        SELECT category, COUNT(DISTINCT file_path) as file_count
        FROM open_incidents WHERE project_path = ? GROUP BY category
    """, (project_path,))
    
    for row in cursor.fetchall():
        cat = (row['category'] or 'UNCATEGORIZED').upper()
        metrics['by_category'][cat] = row['file_count']

    cursor.execute("SELECT COUNT(DISTINCT file_path) FROM open_incidents WHERE project_path = ?", (project_path,))
    metrics['affected_files'] = cursor.fetchone()[0]
    return metrics

def calculate_density_penalty(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Calcula a penalidade ponderada por densidade de arquivos."""
    if not metrics or 'total_files' not in metrics:
        raise ValueError("Métricas inválidas para cálculo.")

    total = metrics['total_files']
    weights = {
        'SYNTAX': 100, 'CRITICAL': 80, 'SECURITY': 70, 
        'RUNTIME-RISK': 50, 'COMPLEXITY': 40, 'STYLE': 20, 'DEADCODE': 10
    }

    results = []
    for cat, count in metrics['by_category'].items():
        density = count / total
        penalty = min(25, (density * weights.get(cat, 15)))
        results.append({
            'name': cat, 'penalty': round(penalty, 1),
            'density_pct': round(density * 100, 1), 'count': count
        })
    return results

def _get_risk_styling(score: float) -> Tuple[str, str, str]:
    """Determina o nível e a cor do Score (Helper de UI)."""
    if score >= 90: return "BAIXO", Fore.GREEN, "🟢"
    if score >= 75: return "MÉDIO", Fore.YELLOW, "🟡"
    if score >= 50: return "ALTO", Fore.RED, "🟠"
    return "CRÍTICO", Fore.MAGENTA, "🔴"

def _get_engineering_directive(score: float, test_pen: int) -> str:
    """Define a recomendação técnica baseada nos dados."""
    if test_pen >= 30:
        return f"{Fore.RED}🛑 BLOQUEIO: Corrija os testes antes de prosseguir."
    if score < 50:
        return f"{Fore.RED}🛠️ EMERGÊNCIA: Realize um 'Technical Debt Sweep'."
    if score < 80:
        return f"{Fore.YELLOW}🧹 MODO FAXINA: Priorize limpeza e refatoração."
    return f"{Fore.GREEN}🚀 ESTRADA LIVRE: Base sólida para inovação."

def _display_risk_report(score: float, metrics: Dict[str, Any], penalties: List[Dict[str, Any]], test_pen: int):
    """Renderiza o relatório final. MPoT-4: CC < 10."""
    if metrics is None or penalties is None:
        raise ValueError("Dados insuficientes para renderização.")

    level, color, icon = _get_risk_styling(score)
    click.echo(Fore.CYAN + Style.BRIGHT + f"--- [RISK] Auditoria de Densidade v{__version__} ---")
    click.echo(f"\nScore de Saúde: {color}{Style.BRIGHT}{int(score)}/100 ({level} {icon})")
    
    af_pct = (metrics['affected_files'] / metrics['total_files']) * 100
    click.echo(Fore.WHITE + f"Base: {metrics['total_files']} arqs | Afetados: {metrics['affected_files']} ({af_pct:.1f}%)")

    click.echo("\nDistribuição de Impacto:")
    for p in sorted(penalties, key=lambda x: x['penalty'], reverse=True):
        p_col = Fore.RED if p['penalty'] > 10 else (Fore.YELLOW if p['penalty'] > 5 else Fore.WHITE)
        click.echo(f"   [{p['name']:<15}] {p_col}-{p['penalty']:>4}{Style.RESET_ALL} | "
                   f"Afeta {p['density_pct']}% dos arquivos ({p['count']} un)")

    if test_pen > 0:
        click.echo(f"   [{'SEGURANÇA':<15}] {Fore.RED}-{test_pen:>4}{Style.RESET_ALL} | Testes: FALHA/AUSENTE")

    click.echo(f"\n{Style.BRIGHT}Diretriz de Engenharia:")
    click.echo(f"   {_get_engineering_directive(score, test_pen)}")

@click.command('risk')
def risk():
    """(Gerencial) Análise de Risco v4.3: Densidade de Dívida Técnica."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        project_path = os.getcwd()
        metrics = _get_project_metrics(cursor, project_path)
        penalties = calculate_density_penalty(metrics)
        
        cursor.execute("SELECT exit_code FROM command_history WHERE command_name = 'test' ORDER BY id DESC LIMIT 1")
        test_row = cursor.fetchone()
        test_penalty = 0 if (test_row and test_row['exit_code'] == 0) else 20
        
        final_score = max(0, 100 - (sum(p['penalty'] for p in penalties) + test_penalty))
        _display_risk_report(final_score, metrics, penalties, test_penalty)

    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Falha no cálculo: {e}")
    finally:
        conn.close()