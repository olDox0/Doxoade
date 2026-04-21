# doxoade/doxoade/commands/risk.py
"""
Módulo de Gestão de Risco Operacional (v4.4 - Gold Fortress).
Calcula estabilidade baseada no PASC e na integridade sintática absoluta.
"""
import click
import doxoade.tools.aegis.nexus_db as sqlite3  # noqa
import os
from typing import Dict, Any, List
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection
from doxoade.dnm import DNM
__version__ = '4.4 Alfa (Gold Fortress Edition)'

def _get_project_metrics(cursor: sqlite3.Cursor, project_path: str) -> Dict[str, Any]:
    """Coleta métricas base e violações de peso PASC 1.3."""
    dnm = DNM(project_path)
    all_files = dnm.scan(extensions=['.py'])
    total_count = len(all_files) or 1
    metrics = {'total_files': total_count, 'affected_files': 0, 'by_category': {}, 'overweight_files': 0}
    for f in all_files:
        try:
            size_kb = os.path.getsize(f) / 1024
            if size_kb > 20:
                metrics['overweight_files'] += 1
            else:
                with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                    if len(fp.readlines()) > 500:
                        metrics['overweight_files'] += 1
        except OSError:
            continue
    cursor.execute('\n        SELECT category, COUNT(DISTINCT file_path) as file_count\n        FROM open_incidents WHERE project_path = ? GROUP BY category\n    ', (project_path,))
    for row in cursor.fetchall():
        cat = (row['category'] or 'UNCATEGORIZED').upper()
        metrics['by_category'][cat] = row['file_count']
    cursor.execute('SELECT COUNT(DISTINCT file_path) FROM open_incidents WHERE project_path = ?', (project_path,))
    metrics['affected_files'] = cursor.fetchone()[0]
    return metrics

def calculate_density_penalty(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Cálculo de penalidade realinhado com o PASC v2026."""
    total = metrics['total_files']
    weights = {'SYNTAX': 150, 'CRITICAL': 120, 'SECURITY': 100, 'RUNTIME-RISK': 60, 'COMPLEXITY': 50, 'STYLE': 20, 'DEADCODE': 15}
    results = []
    for cat, count in metrics['by_category'].items():
        density = count / total
        cap = 50 if cat in ['SYNTAX', 'CRITICAL'] else 25
        penalty = min(cap, density * weights.get(cat, 15))
        results.append({'name': cat, 'penalty': round(penalty, 1), 'density_pct': round(density * 100, 1), 'count': count})
    if metrics['overweight_files'] > 0:
        overweight_pct = metrics['overweight_files'] / total * 100
        results.append({'name': 'PASC-WEIGHT', 'penalty': round(min(15, overweight_pct * 2), 1), 'density_pct': round(overweight_pct, 1), 'count': metrics['overweight_files']})
    return results

def _get_engineering_directive(score: float, test_pen: int) -> str:
    """Diretrizes baseadas no PASC 3 (Progressividade)."""
    if score < 40:
        return f'{Fore.MAGENTA}🔥 CATASTROFE: Integridade violada. Revierta as últimas mudanças.'
    if test_pen >= 20:
        return f'{Fore.RED}🛑 BLOQUEIO (Lei 8): Diagnóstico de testes falhou.'
    if score < 75:
        return f'{Fore.YELLOW}🧹 MODO FAXINA (Lei 1): Priorize modularização e Expert-Split.'
    return f'{Fore.GREEN}🚀 ESTADO GOLD: Infraestrutura sólida (MPoT Compliance).'

@click.command('risk')
def risk():
    """Auditoria de Risco v4.4: Conformidade PASC e Densidade Técnica."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        project_path = os.getcwd()
        metrics = _get_project_metrics(cursor, project_path)
        penalties = calculate_density_penalty(metrics)
        cursor.execute("SELECT exit_code FROM command_history WHERE command_name = 'test' ORDER BY id DESC LIMIT 1")
        test_row = cursor.fetchone()
        test_penalty = 0 if test_row and test_row['exit_code'] == 0 else 20
        final_score = max(0, 100 - (sum((p['penalty'] for p in penalties)) + test_penalty))
        _display_report(final_score, metrics, penalties, test_penalty)
    except Exception as e:
        click.echo(Fore.RED + f'[ERRO] Falha no cálculo Fortress: {e}')
    finally:
        conn.close()

def _display_report(score: float, metrics: dict, penalties: list, test_pen: int):
    """Renderizador Chief-Gold unificado."""
    level, color, icon = _get_risk_styling(score)
    click.echo(Fore.CYAN + Style.BRIGHT + f'\n--- [RISK] Fortress Audit v{__version__} ---')
    click.echo(f'Score de Saúde: {color}{Style.BRIGHT}{int(score)}/100 ({level} {icon})')
    af_pct = metrics['affected_files'] / metrics['total_files'] * 100
    click.echo(Fore.WHITE + f"Base: {metrics['total_files']} arquivos | Afetados: {metrics['affected_files']} ({af_pct:.1f}%)")
    click.echo('\nVetores de Impacto PASC:')
    for p in sorted(penalties, key=lambda x: x['penalty'], reverse=True):
        p_col = Fore.RED if p['penalty'] >= 15 else Fore.YELLOW if p['penalty'] >= 5 else Fore.WHITE
        click.echo(f"   [{p['name']:<15}] {p_col}-{p['penalty']:>5}{Style.RESET_ALL} | Impacto: {p['density_pct']}% ({p['count']} un)")
    if test_pen > 0:
        click.echo(f"   [{'TEST-REGRESSION':<15}] {Fore.RED}-{test_pen:>5}{Style.RESET_ALL} | Status: FALHA")
    click.echo(f'\n{Style.BRIGHT}Diretriz Técnica:{Style.NORMAL}')
    click.echo(f'   {_get_engineering_directive(score, test_pen)}\n')

def _get_risk_styling(score: float):
    if score >= 90:
        return ('GOLD', Fore.GREEN, '🏆')
    if score >= 80:
        return ('STABLE', Fore.GREEN, '🟢')
    if score >= 60:
        return ('WARNED', Fore.YELLOW, '🟡')
    if score >= 40:
        return ('DANGER', Fore.RED, '🟠')
    return ('BROKEN', Fore.MAGENTA, '🔴')
