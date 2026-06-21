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
@click.option('-m', '--message', help='Busca no acervo.')
@click.option('-n', '--limit', default=10)
def history(message, limit):
    """🧠 Hub de Inteligência: Diferencia Erros Ativos de Fantasmas do Passado."""
    conn = get_db_connection()
    import sqlite3
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # [PLATINUM] Query que cruza o Lexicon com Incidentes Abertos
    query = """
        SELECT 
            l.*, 
            (SELECT COUNT(*) FROM open_incidents i WHERE i.finding_hash = l.finding_hash) as is_active
        FROM knowledge_lexicon l
    """
    params = []
    if message:
        query += " WHERE l.message LIKE ? OR l.category LIKE ?"
        params.extend([f"%{message}%", f"%{message}%"])
    
    query += " ORDER BY l.last_seen DESC LIMIT ?"
    params.append(limit)
    
    rows = cursor.execute(query, params).fetchall()
    conn.close()
    
    if not rows:
        click.secho("\n[-] Nada encontrado.", fg='yellow')
        return

    click.secho("\n--- 📚 ACERVO DE INTELIGÊNCIA: TRIANGULAÇÃO HISTÓRICA ---", fg='cyan', bold=True)
    
    for r in rows:
        # 1. Definição de Status
        if r['is_active'] > 0:
            status = f"{Back.RED}{Fore.WHITE} [ ATIVO ] {Style.RESET_ALL}"
            color = Fore.RED
        else:
            status = f"{Fore.GREEN} [ RESOLVIDO ] {Style.RESET_ALL}"
            color = Fore.WHITE
            
        # 2. Formatação de Datas
        last_date = r['last_seen'][:10] if r['last_seen'] else "N/A"
        first_date = r['first_seen'][:10] if r['first_seen'] else "N/A"
        
        click.echo(f"\n{status} {color}{r['message']}")
        click.echo(f"   {Style.DIM}Primeira vez: {first_date} | Última vez: {Fore.YELLOW}{last_date}{Style.RESET_ALL}")
        click.echo(f"   {Style.DIM}Recorrência: {r['occurrence_count']} hits | ID: {r['finding_hash'][:12]}")
        
        if r['snippet_fixed']:
            click.echo(f"   {Fore.GREEN}🛠  SOLUÇÃO APLICADA: {Fore.WHITE}{r['snippet_fixed']}")
        elif r['is_active'] > 0:
            click.echo(f"   {Fore.MAGENTA}🔎 LOCALIZAR: Use 'doxoade search {r['finding_hash'][:8]}'")
