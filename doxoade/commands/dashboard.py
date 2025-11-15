# doxoade/commands/dashboard.py
import click
#import os
import sqlite3
from colorama import Fore, Style

# Importa apenas o que é absolutamente necessário no nível do módulo
from ..database import get_db_connection

# As funções auxiliares permanecem privadas a este módulo
def _display_error_trend_db(cursor):
    """Exibe o número de erros por comando, lendo do banco de dados."""
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Tendência de Erros por Comando ---")
    try:
        cursor.execute("""
            SELECT e.command, COUNT(f.id)
            FROM events e
            JOIN findings f ON e.id = f.event_id
            WHERE f.severity IN ('ERROR', 'CRITICAL')
            GROUP BY e.command
            ORDER BY COUNT(f.id) DESC;
        """)
        rows = cursor.fetchall()
        if not rows:
            click.echo("Nenhum erro registrado.")
            return
        for row in rows:
            click.echo(f"  - {row['command']}: {row['COUNT(f.id)']} erro(s)")
    except sqlite3.Error as e:
        click.echo(Fore.YELLOW + f"  Não foi possível gerar tendência de erros: {e}")

def _display_common_issues_db(cursor):
    """Exibe os tipos de 'finding' mais comuns usando Pandas."""
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Problemas Mais Comuns (Top 5) ---")
    try:
        # --- LAZY LOADING DO PANDAS ---
        # A importação só acontece se o comando dashboard for executado
        import pandas as pd
        
        cursor.execute("SELECT message, severity FROM findings WHERE severity IN ('ERROR', 'CRITICAL')")
        rows = cursor.fetchall()
        if not rows:
            click.echo("Nenhum problema comum registrado.")
            return
            
        df = pd.DataFrame(rows, columns=['message', 'severity'])
        # Simplifica a mensagem para agrupar erros similares
        df['simple_message'] = df['message'].str.split("'").str[0].str.strip()
        
        common_issues = df.groupby('simple_message').size().sort_values(ascending=False).head(5)
        click.echo(common_issues.to_string())
    except ImportError:
        click.echo(Fore.YELLOW + "  Aviso: 'pandas' não está instalado. Não é possível exibir os problemas mais comuns.")
        click.echo(Fore.YELLOW + "  Execute: pip install pandas")
    except sqlite3.Error as e:
        click.echo(Fore.YELLOW + f"  Não foi possível gerar resumo de problemas: {e}")


@click.command('dashboard')
@click.option('--project', default=None, help="Filtra o dashboard para um projeto específico.")
def dashboard(project):
    """Exibe um painel com a saúde e tendências dos projetos analisados."""
    click.echo(Fore.YELLOW + Style.BRIGHT + "--- [DASHBOARD] Inteligência de Engenharia Doxoade ---")
    
    conn = None # Garante que conn exista no bloco finally
    try:
        conn = get_db_connection()
        if not conn:
            click.echo(Fore.RED + "Não foi possível conectar ao banco de dados.")
            return
            
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        _display_error_trend_db(cursor)
        _display_common_issues_db(cursor)

    except Exception as e:
        click.echo(Fore.RED + f"\nUm erro inesperado ocorreu ao gerar o dashboard: {e}")
    finally:
        if conn:
            conn.close()