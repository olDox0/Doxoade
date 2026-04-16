# doxoade/doxoade/commands/db_query.py
import click
from doxoade.tools.doxcolors import Fore
import json
from doxoade.database import get_db_connection
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@click.command('db-query')
@click.pass_context
@click.argument('sql_query', required=True)
def db_query(ctx, sql_query):
    """(DEBUG) Executa uma query SQL diretamente no banco de dados da doxoade."""
    arguments = ctx.params
    with ExecutionLogger('db-query', '.', arguments) as logger:
        click.echo(Fore.YELLOW + f'Executando query: {sql_query}')
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            if not rows:
                click.echo(Fore.GREEN + 'Query executada com sucesso. Nenhum resultado retornado.')
                return
            results = [dict(row) for row in rows]
            click.echo(json.dumps(results, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.add_finding('ERROR', 'Falha na execução da query SQL.', details=str(e))
            click.echo(Fore.RED + f'Erro ao executar a query: {e}')
        finally:
            conn.close()
