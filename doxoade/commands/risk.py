# doxoade/commands/risk.py
"""
Módulo de Gestão de Risco e Estabilidade (R0) - Versão 3.0 (Estado Presente)
Foca no estado atual do código, ignorando histórico de comandos falhos.
"""
import click
import sqlite3
import statistics
from colorama import Fore, Style
from ..database import get_db_connection

def get_check_penalty(cursor):
    """Calcula penalidade baseada em incidentes ABERTOS (Estado Atual)."""
    try:
        # Filtra explicitamente pastas de teste e temporárias
        cursor.execute("""
            SELECT category, file_path FROM open_incidents 
            WHERE file_path NOT LIKE '%test%' 
            AND file_path NOT LIKE '%Temp%' 
            AND file_path NOT LIKE '%pytest%'
        """)
        rows = cursor.fetchall()
    except: return 0, "Erro DB"
    
    penalty = 0
    weights = {'SYNTAX': 15, 'CRITICAL': 10, 'RUNTIME-RISK': 8, 'ERROR': 5, 'WARNING': 2}
    
    count = 0
    for r in rows:
        cat = (r['category'] or '').upper()
        penalty += weights.get(cat, 1)
        count += 1
        
    return min(40, penalty), f"{count} problemas de código ativos"

def get_style_penalty(cursor):
    """Lê o último relatório do 'style' (MPoT)."""
    try:
        # Busca último evento 'style'
        cursor.execute("SELECT id FROM events WHERE command = 'style' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row: return 0, "Sem dados de estilo"
        
        event_id = row['id']
        cursor.execute("SELECT count(*) FROM findings WHERE event_id = ?", (event_id,))
        violations = cursor.fetchone()[0]
        
        # Penalidade leve (estilo é importante, mas não crítico)
        penalty = min(20, violations * 2)
        return penalty, f"{violations} violações de arquitetura (MPoT)"
    except: return 0, "N/A"

def get_complexity_penalty(cursor):
    """
    Analisa complexidade baseada em dados do 'deepcheck' ou 'health'.
    Procura findings de categoria 'COMPLEXITY'.
    """
    try:
        # Busca nos últimos eventos
        cursor.execute("""
            SELECT id FROM events 
            WHERE command IN ('health', 'deepcheck') 
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if not row: return 0, "Sem dados de complexidade"
        
        event_id = row['id']
        # Tenta achar métricas nos detalhes dos findings
        # (Isso é uma aproximação, idealmente teríamos uma tabela de métricas)
        cursor.execute("SELECT count(*) FROM findings WHERE event_id = ? AND message LIKE '%Alta Complexidade%'", (event_id,))
        high_complex_funcs = cursor.fetchone()[0]
        
        penalty = min(20, high_complex_funcs * 5)
        return penalty, f"{high_complex_funcs} funções complexas"
    except: return 0, "N/A"

def get_test_status_penalty(cursor):
    """Verifica se o último teste passou."""
    try:
        cursor.execute("SELECT exit_code FROM command_history WHERE command_name = 'test' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row: return 0, "Sem testes recentes"
        
        if row['exit_code'] != 0:
            return 30, "Última bateria de testes FALHOU"
        return 0, "Testes passando"
    except: return 0, "N/A"

def get_risk_level(score):
    if score >= 90: return "BAIXO", Fore.GREEN
    if score >= 70: return "MÉDIO", Fore.YELLOW
    if score >= 50: return "ALTO", Fore.RED
    return "CRÍTICO", Fore.MAGENTA

@click.command('risk')
def risk():
    """(Gerencial) Score de Risco V3 (Estado Atual do Código)."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Código (Check)
        check_pen, check_msg = get_check_penalty(cursor)
        
        # 2. Arquitetura (Style)
        style_pen, style_msg = get_style_penalty(cursor)
        
        # 3. Complexidade
        complex_pen, complex_msg = get_complexity_penalty(cursor)
        
        # 4. Testes
        test_pen, test_msg = get_test_status_penalty(cursor)
        
        # Cálculo: 100 - Penalidades
        total_penalty = check_pen + style_pen + complex_pen + test_pen
        final_score = max(0, 100 - total_penalty)
        
        level, color = get_risk_level(final_score)

        click.echo(Fore.CYAN + Style.BRIGHT + "--- Relatório de Risco V3 (Estado Presente) ---")
        click.echo(f"\nScore Atual: {color}{Style.BRIGHT}{int(final_score)}/100 ({level}){Style.RESET_ALL}")
        
        click.echo("\nComposição do Risco (Penalidades):")
        
        # Helper de exibição
        def show_factor(name, penalty, msg):
            p_color = Fore.GREEN if penalty == 0 else (Fore.YELLOW if penalty < 10 else Fore.RED)
            print(f"   [{name:<12}] {p_color}-{penalty:<3}{Style.RESET_ALL} | {msg}")

        show_factor("Código", check_pen, check_msg)
        show_factor("Arquitetura", style_pen, style_msg)
        show_factor("Complexidade", complex_pen, complex_msg)
        show_factor("Testes", test_pen, test_msg)

        # Recomendação
        click.echo(f"\n{Style.BRIGHT}Próximo Passo:")
        if test_pen > 0:
            click.echo(Fore.RED + "   CORRIGIR TESTES. Nada importa se os testes não passam.")
        elif check_pen > 20:
            click.echo(Fore.YELLOW + "   LIMPEZA. Resolva os incidentes abertos (doxoade check --fix).")
        elif style_pen > 10:
            click.echo(Fore.BLUE + "   REFATORAÇÃO. Melhore a arquitetura e documentação.")
        else:
            click.echo(Fore.GREEN + "   INOVAÇÃO. O terreno está limpo para novas features.")

    except Exception as e:
        click.echo(Fore.RED + f"Erro: {e}")
    finally:
        conn.close()