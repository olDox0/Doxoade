# doxoade/commands/risk.py
"""
Módulo de Gestão de Risco e Estabilidade (R0).
Analisa o histórico operacional (Chronos) e a dívida técnica (Sapiens)
para fornecer um Score de Risco estratégico para o projeto.
"""
import click
import sqlite3
from colorama import Fore, Style
from ..database import get_db_connection

def calculate_stability_score(cursor):
    """
    Analisa o histórico recente do Chronos para determinar a estabilidade.
    
    Retorna:
        (score, mensagem, lista_de_falhas)
    """
    # Pega os últimos 20 comandos
    cursor.execute("""
        SELECT command_name, exit_code, timestamp FROM command_history 
        ORDER BY id DESC LIMIT 20
    """)
    rows = cursor.fetchall()
    
    if not rows:
        return 100.0, "Sem dados suficientes", []

    total = len(rows)
    failures = []
    
    for r in rows:
        if r['exit_code'] != 0:
            # Pega apenas a hora do timestamp para ser breve
            time_short = r['timestamp'].split('T')[1][:8] if 'T' in r['timestamp'] else r['timestamp']
            failures.append(f"{r['command_name']} ({time_short})")

    fail_count = len(failures)
    
    # Assert defensivo (Lógica não pode gerar score negativo)
    stability = max(0, ((total - fail_count) / total) * 100)
    assert 0 <= stability <= 100, "Erro de cálculo de estabilidade"
    
    msg = f"{fail_count} falhas nos últimos {total} comandos"
    return stability, msg, failures

def calculate_debt_score(cursor):
    """
    Analisa os incidentes abertos, ignorando pastas de teste.
    """
    # Filtra incidentes que NÃO estão em pastas de teste
    cursor.execute("""
        SELECT file_path FROM open_incidents 
        WHERE file_path NOT LIKE '%test%' 
        AND file_path NOT LIKE '%tests%'
    """)
    rows = cursor.fetchall()
    count = len(rows)
    
    # Penalidade: 2 pontos por incidente real
    score = max(0, 100 - (count * 2))
    return score, f"{count} incidentes reais (excluindo testes)"

def get_risk_level(total_score):
    """Retorna o rótulo e a cor baseados no score numérico."""
    if total_score >= 90: return "BAIXO", Fore.GREEN
    if total_score >= 70: return "MÉDIO", Fore.YELLOW
    if total_score >= 50: return "ALTO", Fore.RED
    return "CRÍTICO", Fore.MAGENTA

@click.command('risk')
@click.pass_context
def risk(ctx):
    """(Gerencial) Calcula o Score de Risco e Estabilidade do projeto."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Estabilidade Operacional (Chronos)
        stability_val, stability_msg, failures = calculate_stability_score(cursor)
        
        # 2. Dívida Técnica (Sapiens)
        debt_val, debt_msg = calculate_debt_score(cursor)
        
        # 3. Cálculo Final (Média Ponderada)
        # Estabilidade vale 60%, Dívida vale 40%
        final_score = (stability_val * 0.6) + (debt_val * 0.4)
        
        level, color = get_risk_level(final_score)

        click.echo(Fore.CYAN + Style.BRIGHT + "--- Relatório de Gestão de Risco (Doxoade R0) ---")
        
        click.echo(f"\nNível de Risco Global: {color}{Style.BRIGHT}{level}{Style.RESET_ALL} (Score: {int(final_score)}/100)")
        
        click.echo("\nFatores de Análise:")
        
        # Estabilidade
        stab_color = Fore.GREEN if stability_val > 80 else Fore.RED
        click.echo(f"   [Operação] Estabilidade Recente: {stab_color}{stability_val:.1f}%{Style.RESET_ALL}")
        click.echo(f"              {Style.DIM}{stability_msg}{Style.RESET_ALL}")
        
        # Detalhe das falhas (O que você pediu)
        if failures:
            click.echo(Fore.RED + "              Falhas: " + ", ".join(failures[:5]) + ("..." if len(failures) > 5 else ""))
        
        # Dívida
        debt_color = Fore.GREEN if debt_val > 80 else Fore.YELLOW
        click.echo(f"   [Qualidade] Índice de Saúde:      {debt_color}{debt_val:.1f}%{Style.RESET_ALL}")
        click.echo(f"              {Style.DIM}{debt_msg}{Style.RESET_ALL}")

        # Recomendação
        click.echo(f"\n{Style.BRIGHT}Recomendação do Sistema:")
        if final_score >= 90:
            click.echo(Fore.GREEN + "   Ambiente estável. Seguro para desenvolver novas features.")
        elif final_score >= 70:
            click.echo(Fore.YELLOW + "   Atenção moderada. Considere resolver incidentes abertos.")
        else:
            click.echo(Fore.RED + "   ALTO RISCO. O ambiente está instável.")
            click.echo(Fore.RED + "   Foco sugerido: Estabilização antes de Inovação.")

    except Exception as e:
        click.echo(Fore.RED + f"Falha ao calcular risco: {e}")
    finally:
        conn.close()