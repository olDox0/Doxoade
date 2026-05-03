# doxoade/doxoade/commands/db_cmd.py
import click
import os
import sqlite3
from rich.console import Console
from rich.table import Table

from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from doxoade.tools.doxcolors import Fore, Style

@click.group('db')
def db_group():
    """Hades Engine: Diagnóstico e Manipulação de Dados de Ouro."""
    pass

@db_group.command('optimize')
@click.argument('db_path', type=click.Path(exists=True))
def optimize(db_path):
    """🚀 Hades Boost: Cura inchaço e aplica índices de alta performance."""
    import sqlite3
    db_abs = os.path.abspath(db_path)
    click.echo(f"{Fore.CYAN}--- [HADES OPTIMIZE] Turbinando: {os.path.basename(db_abs)} ---{Style.RESET_ALL}")
    
    try:
        conn = sqlite3.connect(db_abs)
        # 1. Identifica tabelas para decidir quais índices criar
        curr = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in curr.fetchall()]
        
        # 2. Aplicação de Índices Estratégicos
        click.echo("[*] Criando índices de busca rápida...")
        
        if 'findings' in tables:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_event ON findings(event_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);")
            
        if 'events' in tables:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);")
            
        if 'articles' in tables:
            # Essencial para o Doxarchives
            conn.execute("CREATE INDEX IF NOT EXISTS idx_art_id ON articles(id);")
        
        # 3. Compactação e Limpeza (Libera espaço em disco)
        click.echo("[*] Executando VACUUM (Desfragmentação física)...")
        conn.execute("VACUUM;")
        
        # 4. Estatísticas de Consulta (Ajuda o SQLite a escolher o melhor caminho)
        click.echo("[*] Executando ANALYZE (Otimização de Query Planner)...")
        conn.execute("ANALYZE;")
        
        conn.commit()
        conn.close()
        click.secho(f"✅ Sucesso! O banco '{os.path.basename(db_abs)}' agora é Gold Standard.", fg='green', bold=True)
    except Exception as e:
        click.echo(f"{Fore.RED}✘ Falha na otimização: {e}{Style.RESET_ALL}")

@db_group.command('view')
@click.argument('db_path', type=click.Path(exists=True))
@click.option('--limit', '-n', default=5, help='Quantidade de linhas por tabela.')
@click.option('--table', '-t', help='Focar em uma tabela específica.')
def view(db_path, limit, table):
    """Exibe o conteúdo e a estrutura do banco de dados .db"""
    console = Console()
    db_abs = os.path.abspath(db_path)
    
    click.echo(f"{Fore.CYAN}--- [HADES VIEW] Analisando: {os.path.basename(db_abs)} ---{Style.RESET_ALL}")
    
    try:
        conn = sqlite3.connect(db_abs)
        curr = conn.cursor()
        
        # 1. Identifica as tabelas
        if table:
            tables = [table]
        else:
            curr.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in curr.fetchall() if t[0] != 'sqlite_sequence']

        if not tables:
            click.echo(f"{Fore.YELLOW}Nenhuma tabela encontrada no banco.{Style.RESET_ALL}")
            return

        for t_name in tables:
            # Pega info das colunas
            curr.execute(f"PRAGMA table_info({t_name})")
            cols = [c[1] for c in curr.fetchall()]
            
            # Pega a amostra
            curr.execute(f"SELECT * FROM {t_name} LIMIT {limit}")
            rows = curr.fetchall()
            
            # Gera a tabela visual com Rich
            rich_table = Table(title=f"Tabela: [bold magenta]{t_name}[/bold magenta]", 
                               title_style="cyan", show_lines=True)
            
            for col in cols:
                rich_table.add_column(col, style="white", overflow="fold")

            for row in rows:
                formatted_row = []
                for val in row:
                    if isinstance(val, bytes):
                        # Tratamento para BLOBs (importante para Doxarchives)
                        formatted_row.append(f"[dim grey][BLOB: {len(val)} bytes][/]")
                    elif val is None:
                        formatted_row.append("[italic red]NULL[/]")
                    else:
                        s_val = str(val)
                        # Trunca strings gigantescas na visualização
                        formatted_row.append(s_val[:100] + "..." if len(s_val) > 100 else s_val)
                rich_table.add_row(*formatted_row)

            console.print(rich_table)
            console.print(f"   [dim]> Amostra de {len(rows)} registro(s)[/]\n")

        conn.close()
    except Exception as e:
        click.echo(f"{Fore.RED}✘ Erro ao ler banco: {e}{Style.RESET_ALL}")

@db_group.command('diag')
@click.argument('db_path', type=click.Path(exists=True))
@click.pass_context
def diag(ctx, db_path):
    """Realiza autópsia completa no banco de dados (Integridade e Schema)."""
    with ExecutionLogger('db-diag', db_path, ctx.params) as logger:
        from .db_systems.hades_engine import HadesEngine
        engine = HadesEngine(db_path)
        engine.run_full_diagnosis(logger)

@db_group.command('sample')
@click.argument('db_path', type=click.Path(exists=True))
@click.option('--size', '-s', default=100, help='Quantidade de linhas por tabela.')
@click.option('--out', '-o', default='gold_sample.db', help='Nome do banco de amostra.')
@click.pass_context
def sample(ctx, db_path, size, out):
    """Cria uma 'Amostra de Ouro' reduzida para testes de analisadores."""
    with ExecutionLogger('db-sample', db_path, ctx.params) as logger:
        from .db_systems.sampling_utils import DataSampler
        click.echo(f"{Fore.CYAN}🧪 Gerando amostra de {size} linhas em '{out}'...{Style.RESET_ALL}")
        sampler = DataSampler(db_path)
        sampler.create_gold_sample(out, size)
        click.echo(Fore.GREEN + "✅ Amostra gerada com sucesso para os laboratórios Doxarchive.")