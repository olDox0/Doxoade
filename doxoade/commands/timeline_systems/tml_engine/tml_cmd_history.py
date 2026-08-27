# doxoade/commands/timeline_systems/tml_engine/tml_cmd_history.py
"""
Timeline Command History Engine - Rá/Cronos.
Orquestração e processamento do histórico de comandos.
Integração: Hades (persistência) + Apolo (display).
"""
import zlib
import json
import click
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.aegis.vault import NexusVault
from doxoade.core_database import get_db_connection
from doxoade.tools.alexandria.engine import alexandria_write
import doxoade.tools.aegis.nexus_db as sqlite3


class TimelineHistoryEngine:
    """
    Motor de processamento do histórico temporal.
    Responsável por extrair, formatar e preparar dados para visualização.
    """
    
    def __init__(self):
        self.conn = None
        
    def connect(self):
        """Estabelece conexão com o banco de dados."""
        self.conn = get_db_connection()
        self.conn.row_factory = sqlite3.Row
        
    def disconnect(self):
        """Fecha conexão de forma segura."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def fetch_events(self, limit: int = 10, 
                     command_filter: Optional[str] = None,
                     date_start: Optional[str] = None,
                     date_end: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Busca eventos do histórico com filtros opcionais.
        
        Args:
            limit: Número máximo de eventos
            command_filter: Filtra por nome de comando
            date_start: Data inicial (ISO format)
            date_end: Data final (ISO format)
            
        Returns:
            Lista de dicionários com eventos formatados
        """
        if not self.conn:
            self.connect()
            
        query = "SELECT * FROM command_history WHERE 1=1"
        params = []
        
        if command_filter:
            query += " AND command_name = ?"
            params.append(command_filter)
            
        if date_start:
            query += " AND timestamp >= ?"
            params.append(date_start)
            
        if date_end:
            query += " AND timestamp <= ?"
            params.append(date_end)
            
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        events = self.conn.execute(query, params).fetchall()
        return [dict(ev) for ev in events]
    
    def fetch_heatmap_data(self, scale: str = 'hour', year: int = None,
                           command_filter: Optional[str] = None) -> Dict[str, Any]:
        """Delega ao orquestrador Rá (fonte única de verdade)."""
        from doxoade.commands.timeline_systems.tml_engine.activity_heatmap import ActivityHeatmap
        model = ActivityHeatmap().build(scale=scale, year=year, command=command_filter)
        return model.to_legacy_dict()
    
    def _aggregate_hourly_data(self, year: int, 
                               command_filter: Optional[str] = None) -> Dict[str, Any]:
        """Agrega dados por hora do dia e dia da semana."""
        query = """
        SELECT 
            CAST(strftime('%w', timestamp) AS INTEGER) as day_of_week,
            CAST(strftime('%H', timestamp) AS INTEGER) as hour_of_day,
            COUNT(*) as total_commands,
            SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) as error_count,
            GROUP_CONCAT(DISTINCT command_name) as commands_used
        FROM command_history
        WHERE timestamp LIKE ?
        """
        
        params = [f"{year}%"]
        
        if command_filter:
            query += " AND command_name = ?"
            params.append(command_filter)
            
        query += " GROUP BY day_of_week, hour_of_day"
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        # Constrói matriz 7x24
        matrix = [[0 for _ in range(24)] for _ in range(7)]
        details = {}
        
        for row in rows:
            day = row['day_of_week']
            hour = row['hour_of_day']
            matrix[day][hour] = row['total_commands']
            
            details[f"{day}_{hour}"] = {
                'count': row['total_commands'],
                'errors': row['error_count'],
                'commands': row['commands_used'].split(',') if row['commands_used'] else []
            }
            
        return {
            'scale': 'hour',
            'matrix': matrix,
            'dimensions': (7, 24),
            'details': details,
            'year': year
        }
    
    def _aggregate_daily_data(self, year: int,
                             command_filter: Optional[str] = None) -> Dict[str, Any]:
        """Agrega dados por dia do mês (visão mensal)."""
        query = """
        SELECT 
            CAST(strftime('%m', timestamp) AS INTEGER) as month,
            CAST(strftime('%d', timestamp) AS INTEGER) as day_of_month,
            COUNT(*) as total_commands,
            SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) as error_count
        FROM command_history
        WHERE timestamp LIKE ?
        """
        
        params = [f"{year}%"]
        
        if command_filter:
            query += " AND command_name = ?"
            params.append(command_filter)
            
        query += " GROUP BY month, day_of_month"
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        # Constrói matriz 12x31
        matrix = [[0 for _ in range(31)] for _ in range(12)]
        details = {}
        
        for row in rows:
            month = row['month'] - 1  # 0-indexed
            day = row['day_of_month'] - 1  # 0-indexed
            if 0 <= month < 12 and 0 <= day < 31:
                matrix[month][day] = row['total_commands']
                details[f"{month}_{day}"] = {
                    'count': row['total_commands'],
                    'errors': row['error_count']
                }
                
        return {
            'scale': 'day',
            'matrix': matrix,
            'dimensions': (12, 31),
            'details': details,
            'year': year
        }
    
    def _aggregate_monthly_data(self, 
                                command_filter: Optional[str] = None) -> Dict[str, Any]:
        """Agrega dados por mês (visão anual/multi-anos)."""
        query = """
        SELECT 
            CAST(strftime('%Y', timestamp) AS INTEGER) as year,
            CAST(strftime('%m', timestamp) AS INTEGER) as month,
            COUNT(*) as total_commands,
            SUM(CASE WHEN exit_code != 0 THEN 1 ELSE 0 END) as error_count
        FROM command_history
        """
        
        params = []
        
        if command_filter:
            query += " WHERE command_name = ?"
            params.append(command_filter)
            
        query += " GROUP BY year, month ORDER BY year, month"
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        # Agrupa por anos únicos
        years = sorted(set(row['year'] for row in rows))
        year_map = {year: idx for idx, year in enumerate(years)}
        
        # Constrói matriz Nx12
        matrix = [[0 for _ in range(12)] for _ in range(len(years))]
        details = {}
        
        for row in rows:
            year_idx = year_map[row['year']]
            month = row['month'] - 1  # 0-indexed
            matrix[year_idx][month] = row['total_commands']
            details[f"{year_idx}_{month}"] = {
                'year': row['year'],
                'count': row['total_commands'],
                'errors': row['error_count']
            }
            
        return {
            'scale': 'month',
            'matrix': matrix,
            'dimensions': (len(years), 12),
            'details': details,
            'years': years
        }
    
    @staticmethod
    def format_local_timestamp(ts_str: str) -> str:
        """
        Detecta o fuso horário do sistema e converte o carimbo UTC do banco.
        
        Args:
            ts_str: Timestamp em formato ISO (UTC)
            
        Returns:
            Timestamp formatado no fuso horário local
        """
        if not ts_str:
            return ""
        try:
            # Normaliza o sufixo Z para o padrão ISO offsets (+00:00)
            clean_ts = ts_str.replace('Z', '+00:00')
            
            # Se não houver indicador de fuso, assume UTC
            if '+' not in clean_ts and '-' not in clean_ts[10:]:
                dt_utc = datetime.fromisoformat(clean_ts).replace(tzinfo=timezone.utc)
            else:
                dt_utc = datetime.fromisoformat(clean_ts)
            
            # Converte automaticamente para o fuso local do OS
            dt_local = dt_utc.astimezone()
            return dt_local.strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception:
            # Fallback de segurança
            return ts_str[:19].replace('T', ' ') if ts_str else ""
    
    def render_payload_details(self, event: Dict[str, Any]) -> None:
        """
        Exibe detalhes do payload de um evento.
        
        Args:
            event: Dicionário com dados do evento
        """
        payload_raw = event.get('compressed_payload')
        
        if not payload_raw:
            click.echo(f"   {Style.DIM}Status: Registro de telemetria simples.{Style.RESET_ALL}")
            return
            
        if not NexusVault.is_unlocked():
            click.echo(f"   {Fore.YELLOW}🔒 [PAYLOAD PROTEGIDO] Use 'doxoade vault --open'{Style.RESET_ALL}")
            return
            
        try:
            data = json.loads(zlib.decompress(payload_raw))
            
            # Inputs
            args = data.get('input', {}).get('args', {})
            if args:
                clean_args = {k: v for k, v in args.items() 
                             if v is not None and v is not False}
                if clean_args:
                    click.echo(f"   {Fore.YELLOW}Inputs: {clean_args}")
            
            # Findings
            findings = data.get('output', {}).get('findings', [])
            if findings:
                click.echo(f"   {Fore.CYAN}Achados: {len(findings)} ocorrência(s)")
                for f in findings[:3]:
                    msg = f['message'][:70] if len(f['message']) > 70 else f['message']
                    click.echo(f"     - [{f['severity']}] {msg}")
            else:
                click.echo(f"   {Fore.GREEN}Status: Operação limpa (Zero incidentes).{Style.RESET_ALL}")
                
        except Exception as e:
            click.echo(f"   {Fore.RED}Erro na leitura: {e}")


# Instância global do engine
timeline_history_engine = TimelineHistoryEngine()


@click.command('cmd-history')
@click.option('-n', '--limit', default=10, help='Número de eventos.')
@click.option('--full', is_flag=True, help='Mostra os detalhes do Payload.')
@click.option('--command', '-c', help='Filtra por comando específico.')
@click.option('--from-date', help='Data inicial (YYYY-MM-DD).')
@click.option('--to-date', help='Data final (YYYY-MM-DD).')
def cmd_history(limit, full, command, from_date, to_date):
    """
    Exibe o histórico cronológico de ações e alterações.
    
    Substituto moderno do comando 'timeline' original.
    """
    engine = timeline_history_engine
    
    try:
        engine.connect()
        
        # Converte datas para formato ISO completo se fornecidas
        date_start = f"{from_date}T00:00:00" if from_date else None
        date_end = f"{to_date}T23:59:59" if to_date else None
        
        events = engine.fetch_events(
            limit=limit,
            command_filter=command,
            date_start=date_start,
            date_end=date_end
        )
        
        if not events:
            click.echo(f"{Fore.YELLOW}Nenhum evento encontrado.{Style.RESET_ALL}")
            return
        
        title = f"Timeline do Doxoade"
        if command:
            title += f" (Comando: {command})"
        title += f" - Últimos {limit}"
        
        click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- {title} ---{Style.RESET_ALL}")
        
        for ev in reversed(events):
            status_color = Fore.GREEN if ev['exit_code'] == 0 else Fore.RED
            local_ts = engine.format_local_timestamp(ev.get('timestamp', ''))
            
            click.echo(f"\n{Style.DIM}{local_ts} {status_color}● {Style.BRIGHT}{ev['command_name']}")
            
            if ev.get('full_command_line'):
                click.echo(f"   {Fore.WHITE}❯ {ev['full_command_line']}{Style.RESET_ALL}")
            
            if full:
                engine.render_payload_details(ev)
                
    finally:
        engine.disconnect()


@click.command('heatmap-data')
@click.option('--scale', type=click.Choice(['hour', 'day', 'month']), 
              default='hour', help='Escala temporal')
@click.option('--year', '-y', type=int, help='Ano alvo')
@click.option('--command', '-c', help='Filtra por comando específico')
@click.option('--json', 'as_json', is_flag=True, help='Saída em formato JSON')
def heatmap_data(scale, year, command, as_json):
    """
    Extrai dados agregados para visualização em heatmap.
    
    Comando interno para uso pelo sistema de visualização.
    """
    engine = timeline_history_engine
    
    try:
        engine.connect()
        
        data = engine.fetch_heatmap_data(
            scale=scale,
            year=year,
            command_filter=command
        )
        
        if as_json:
            click.echo(json.dumps(data, indent=2, default=str))
        else:
            # Preview textual dos dados
            click.echo(f"{Fore.CYAN}{Style.BRIGHT}--- Heatmap Data ({scale.upper()}) ---{Style.RESET_ALL}")
            click.echo(f"Dimensões: {data['dimensions']}")
            click.echo(f"Total de células com dados: {sum(1 for v in data['details'].values() if v['count'] > 0)}")
            
            if scale == 'hour':
                days = ['D', 'S', 'T', 'Q', 'Q', 'S', 'S']
                for day_idx, day_name in enumerate(days):
                    row_sum = sum(data['matrix'][day_idx])
                    if row_sum > 0:
                        click.echo(f"  {day_name}: {row_sum} comandos")
                        
    finally:
        engine.disconnect()