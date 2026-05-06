# doxoade/doxoade/commands/history.py
import click
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection
from datetime import datetime, timezone  # <--- ADICIONE ESTA LINHA
import doxoade.tools.aegis.nexus_db as sqlite3 # noqa

def _format_local_timestamp(ts_str: str) -> str:
    """Detecta o fuso horário do sistema e converte o carimbo UTC do banco."""
    if not ts_str:
        return ""
    try:
        clean_ts = ts_str.replace('Z', '+00:00')
        if '+' not in clean_ts and '-' not in clean_ts[10:]:
            dt_utc = datetime.fromisoformat(clean_ts).replace(tzinfo=timezone.utc)
        else:
            dt_utc = datetime.fromisoformat(clean_ts)
        dt_local = dt_utc.astimezone()
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ts_str[:19].replace('T', ' ')

@click.command('history')
@click.option('-m', '--message', help='Busca no erro.')
@click.option('-n', '--limit', default=10)
def history(message, limit):
    """🧠 Hub de Inteligência: Busca erros e soluções no registro Nexus."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT f.*, e.command, e.timestamp 
        FROM findings f 
        JOIN events e ON f.event_id = e.id 
        WHERE 1=1
    '''
    params = []
    if message:
        query += " AND (f.message LIKE ? OR f.category LIKE ?)"
        params.extend([f"%{message}%", f"%{message}%"])
    
    query += " ORDER BY e.timestamp DESC LIMIT ?"
    params.append(limit)
    
    rows = cursor.execute(query, params).fetchall()
    
    if not rows:
        click.secho("\n[-] Nenhuma evidência encontrada no histórico findings.", fg='yellow')
        return

    click.secho(f"\n--- 🧠 MEMÓRIA SEMÂNTICA ({len(rows)} registros) ---", fg='cyan', bold=True)
    
    for r in rows:
        sev = r['severity'].upper()
        color = Fore.RED if sev in ['ERROR', 'CRITICAL'] else Fore.YELLOW
        
        # CONVERSÃO PARA FUSO HORÁRIO LOCAL
        local_ts = _format_local_timestamp(r.get('timestamp', ''))
        
        click.echo(f"\n{Style.DIM}{local_ts} {color}■ [{r['category']}] {r['message']}")
        click.echo(f"   {Fore.WHITE}Comando: {Fore.CYAN}doxoade {r['command']}")
        click.echo(f"   {Fore.WHITE}Local:   {Fore.YELLOW}{r['file']}:{r['line']}")