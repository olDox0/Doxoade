# doxoade/commands/migrate_db.py
import json
import click
from pathlib import Path
from colorama import Fore, Style
from ..database import get_db_connection

LOG_FILE = Path.home() / '.doxoade' / 'doxoade.log'

def _map_severity(log_type_str):
    """Mapeia o antigo 'type' do log para a nova 'severity' do DB."""
    type_upper = str(log_type_str).upper()
    if type_upper in ['CRITICAL', 'ERROR', 'WARNING', 'INFO']:
        return type_upper
    return 'UNCATEGORIZED'

@click.command('migrate-db')
@click.option('--force', is_flag=True, help="Executa a migração mesmo que o DB já tenha dados.")
def migrate_db(force):
    """Migra dados do antigo 'doxoade.log' para o banco de dados SQLite."""
    click.echo(Fore.CYAN + Style.BRIGHT + "--- [MIGRATE-DB] Iniciando migração do log para o banco de dados ---")

    if not LOG_FILE.exists():
        click.echo(Fore.YELLOW + "Arquivo 'doxoade.log' não encontrado. Nenhuma migração necessária.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verifica se a tabela de eventos já contém dados
        cursor.execute("SELECT COUNT(id) FROM events")
        event_count = cursor.fetchone()[0]

        if event_count > 0 and not force:
            click.echo(Fore.YELLOW + "O banco de dados já contém dados. Use a flag --force para migrar novamente.")
            click.echo(Fore.YELLOW + "AVISO: Usar --force pode resultar em dados duplicados se já migrados anteriormente.")
            return

        click.echo(f"Lendo o arquivo de log: {LOG_FILE}")
        
        migrated_events = 0
        migrated_findings = 0
        skipped_lines = 0

        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    skipped_lines += 1
                    continue

                # Insere o evento principal
                cursor.execute("""
                    INSERT INTO events (timestamp, doxoade_version, command, project_path, execution_time_ms, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    data.get('timestamp'),
                    data.get('doxoade_version', 'N/A'),
                    data.get('command', 'unknown'),
                    data.get('project_path', 'N/A'),
                    data.get('execution_time_ms', 0),
                    data.get('status', 'completed')
                ))
                event_id = cursor.lastrowid
                migrated_events += 1

                # Insere os findings associados, se existirem
                for finding in data.get('findings', []):
                    cursor.execute("""
                        INSERT INTO findings (event_id, severity, category, message, details, file, line, finding_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id,
                        _map_severity(finding.get('type')), # Mapeia 'type' para 'severity'
                        finding.get('category', 'UNCATEGORIZED').upper(),
                        finding.get('message', 'Mensagem ausente'),
                        finding.get('details'),
                        finding.get('file'),
                        finding.get('line'),
                        finding.get('hash')
                    ))
                    migrated_findings += 1
        
        conn.commit()
        
        click.echo(Fore.GREEN + "\n--- Migração Concluída ---")
        click.echo(f"Eventos migrados: {migrated_events}")
        click.echo(f"Problemas (findings) migrados: {migrated_findings}")
        if skipped_lines > 0:
            click.echo(Fore.YELLOW + f"Linhas corrompidas ignoradas: {skipped_lines}")

    except Exception as e:
        conn.rollback()
        click.echo(Fore.RED + f"\n[ERRO] A migração falhou: {e}")
        click.echo(Fore.RED + "O banco de dados foi revertido para o estado anterior.")
    finally:
        conn.close()