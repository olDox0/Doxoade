# doxoade/doxoade/commands/dashboard.py
"""
Módulo de Inteligência de Engenharia (Dashboard).
Consolida métricas de erros e tendências utilizando dados do banco Sapiens.
Versão compatível com auditoria de segurança Bandit e MPoT.
"""
import click
import doxoade.tools.aegis.nexus_db as sqlite3  # noqa
from collections import Counter
from rich.console import Console
from rich.table import Table
from doxoade.database import get_db_connection

def _display_error_trend_db(cursor: sqlite3.Cursor):
    """
    Exibe o número de erros por comando de forma visual com Rich.
    
    Substituído assert por validação explícita para conformidade com segurança.
    """
    if cursor is None:
        raise ValueError('Cursor do banco de dados é obrigatório para o Dashboard.')
    console = Console()
    table = Table(title='📊 Tendência de Erros por Comando', title_style='bold cyan')
    table.add_column('Comando', style='white')
    table.add_column('Erros/Críticos', justify='right', style='red')
    try:
        cursor.execute("\n            SELECT e.command, COUNT(f.id) as total\n            FROM events e\n            JOIN findings f ON e.id = f.event_id\n            WHERE f.severity IN ('ERROR', 'CRITICAL')\n            GROUP BY e.command\n            ORDER BY total DESC;\n        ")
        rows = cursor.fetchall()
        if not rows:
            console.print('[yellow]Nenhum erro crítico registrado no histórico.[/yellow]')
            return
        for row in rows:
            table.add_row(str(row['command']), str(row['total']))
        console.print(table)
    except sqlite3.Error as e:
        console.print(f'[yellow]Aviso: Falha ao gerar tendência de erros: {e}[/yellow]')

def _display_common_issues_db(cursor: sqlite3.Cursor):
    """
    Agrupa e exibe os 5 padrões de erro mais frequentes.
    Utiliza Counter nativo para manter leveza no Termux.
    """
    if cursor is None:
        raise ValueError('Cursor do banco de dados é obrigatório para análise de padrões.')
    console = Console()
    console.print('\n[bold cyan]--- Problemas Mais Comuns (Top 5) ---[/bold cyan]')
    try:
        cursor.execute("\n            SELECT message \n            FROM findings \n            WHERE severity IN ('ERROR', 'CRITICAL')\n        ")
        rows = cursor.fetchall()
        if not rows:
            console.print('[dim]Nenhum problema comum catalogado.[/dim]')
            return
        messages = [row['message'].split("'")[0].strip() for row in rows]
        counts = Counter(messages).most_common(5)
        table = Table(show_header=True, header_style='bold magenta')
        table.add_column('Frequência', justify='center', style='dim')
        table.add_column('Padrão de Erro')
        for msg, freq in counts:
            table.add_row(f'{freq}x', msg)
        console.print(table)
    except sqlite3.Error as e:
        console.print(f'[red]Erro na análise de recorrência: {e}[/red]')

@click.command('dashboard')
@click.option('--project', default=None, help='Filtra o dashboard para um projeto específico.')
def dashboard(project):
    """
    Exibe o painel analítico central do Doxoade.
    Analisa saúde, dívida técnica e tendências.
    """
    console = Console()
    console.print('[bold yellow]--- [DASHBOARD] Inteligência Doxoade v69 ---[/bold yellow]\n')
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            console.print('[bold red]Falha crítica: Base de dados inacessível.[/bold red]')
            return
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        _display_error_trend_db(cursor)
        _display_common_issues_db(cursor)
    except Exception as e:
        console.print(f'[bold red]\nErro inesperado no Dashboard: {e}[/bold red]')
    finally:
        if conn:
            conn.close()