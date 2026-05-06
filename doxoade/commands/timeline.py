# doxoade/doxoade/commands/timeline.py
import zlib
import json
import click
from datetime import datetime, timezone  # <--- ADICIONE ESTA LINHA

from doxoade.tools.doxcolors   import Fore, Style
from doxoade.tools.aegis.vault import NexusVault
from doxoade.database          import get_db_connection
import doxoade.tools.aegis.nexus_db as sqlite3  # noqa

def _format_local_timestamp(ts_str: str) -> str:
    """Detecta o fuso horário do sistema e converte o carimbo UTC do banco."""
    if not ts_str:
        return ""
    try:
        # Normaliza o sufixo Z para o padrão ISO offsets (+00:00)
        clean_ts = ts_str.replace('Z', '+00:00')
        # Se não houver indicador de fuso, assume que está gravado em UTC
        if '+' not in clean_ts and '-' not in clean_ts[10:]:
            dt_utc = datetime.fromisoformat(clean_ts).replace(tzinfo=timezone.utc)
        else:
            dt_utc = datetime.fromisoformat(clean_ts)
        
        # O SEGREDO: astimezone() sem argumentos converte automaticamente para o fuso local do OS!
        dt_local = dt_utc.astimezone()
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        # Fallback de segurança em caso de string corrompida
        return ts_str[:19].replace('T', ' ')

@click.command('timeline')
@click.option('-n', '--limit', default=10, help='Número de eventos.')
@click.option('--full', is_flag=True, help='Mostra os detalhes do Payload.')
def timeline(limit, full):
    """Exibe o histórico cronológico de ações e alterações."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row 
    events = conn.execute('SELECT * FROM command_history ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    
    click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- Timeline do Doxoade (Últimos {limit}) ---{Style.RESET_ALL}")
    
    for d in reversed(events):
        ev = dict(d)
        status_color = Fore.GREEN if ev['exit_code'] == 0 else Fore.RED
        
        # CONVERSÃO PARA FUSO HORÁRIO LOCAL
        local_ts = _format_local_timestamp(ev.get('timestamp', ''))
        
        click.echo(f"\n{Style.DIM}{local_ts} {status_color}● {Style.BRIGHT}{ev['command_name']}")
        if ev.get('full_command_line'):
            click.echo(f"   {Fore.WHITE}❯ {ev['full_command_line']}{Style.RESET_ALL}")
            
        if full:
            _render_payload_details(ev)
    conn.close()

def _render_payload_details(ev):
    payload_raw = ev.get('compressed_payload')
    if not payload_raw:
        click.echo(f"   {Style.DIM}Status: Registro de telemetria simples.{Style.RESET_ALL}")
        return

    if not NexusVault.is_unlocked():
        click.echo(f"   {Fore.YELLOW}🔒 [PAYLOAD PROTEGIDO] Use 'doxoade vault --open'{Style.RESET_ALL}")
        return

    try:
        data = json.loads(zlib.decompress(payload_raw))
        args = data.get('input', {}).get('args', {})
        if args:
            clean_args = {k:v for k,v in args.items() if v is not None and v is not False}
            if clean_args:
                click.echo(f"   {Fore.YELLOW}Inputs: {clean_args}")
        
        findings = data.get('output', {}).get('findings', [])
        if findings:
            click.echo(f"   {Fore.CYAN}Achados: {len(findings)} ocorrência(s)")
            for f in findings[:3]:
                click.echo(f"     - [{f['severity']}] {f['message'][:70]}")
        else:
            click.echo(f"   {Fore.GREEN}Status: Operação limpa (Zero incidentes).{Style.RESET_ALL}")
    except Exception as e:
        click.echo(f"   {Fore.RED}Erro na leitura: {e}")