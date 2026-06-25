# doxoade/doxoade/commands/db_cmd.py
import os
import ast
import click
import psutil
#import sqlite
import sqlite3
from pathlib import Path

from rich.console import Console
from rich.table import Table

from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from doxoade.tools.alexandria.engine import alexandria
from doxoade.tools.doxcolors import Fore, Style

from doxoade.core_database import DB_FILE

from doxoade.tools.alexandria.engine import alexandria_write
def alexandria_write(query, params):
    """Substitui o acesso direto ao cursor pelo Alexandria."""
    alexandria.enqueue(query, params)

@click.group('db')
def db_group():
    """Hades Engine: Diagnóstico e Manipulação de Dados de Ouro."""
    pass

@db_group.command('optimize')
@click.argument('db_path', type=click.Path(exists=True))
def optimize(db_path):
    """🚀 Hades Boost: Cura inchaço e aplica índices de alta performance."""
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
            alexandria_write("CREATE INDEX IF NOT EXISTS idx_findings_event ON findings(event_id);")
            alexandria_write("CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);")
            
        if 'events' in tables:
            alexandria_write("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp);")
            
        if 'articles' in tables:
            # Essencial para o Doxarchives
            alexandria_write("CREATE INDEX IF NOT EXISTS idx_art_id ON articles(id);")
        
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
        
@db_group.command('trace')
def trace():
    """🔍 DNA Tracer: Localiza todos os pontos de acesso ao Database."""
    import re
    from pathlib import Path
    
    click.secho("\n--- [HADES TRACER] Mapeando Consumidores de Dados ---", fg='cyan', bold=True)
    
    # Padrões que indicam uso do banco
    patterns = [
        (re.compile(r"get_db_connection"), "Core connection"),
        (re.compile(r"nexus_db"), "Aegis Layer"),
        (re.compile(r"\.execute\("), "Raw SQL")
    ]
    
    # Varredura recursiva forçada (ignorando apenas venv e .git)
    found_count = 0
    for p in Path('.').rglob('*.py'):
        if 'venv' in str(p) or '.git' in str(p): continue
        try:
            content = p.read_text(encoding='utf-8', errors='ignore')
            matches = [label for pat, label in patterns if pat.search(content)]
            if matches:
                found_count += 1
                click.echo(f"  • {Fore.YELLOW}{str(p):<45}{Style.RESET_ALL} -> {', '.join(set(matches))}")
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            from traceback import print_tb as exc_trace
            exc_obj, exc_tb = _dox_sys.exc_info()
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            exc_trace(exc_tb)
            print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: trace\033[0m")
            print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    click.echo(f"\n[OK] {found_count} arquivos dependentes localizados.")
    
@db_group.command('audit')
def db_audit():
    """Analisa o uso do banco, integridade e segurança de acesso."""
    import psutil
    db_path = str(DB_FILE)
    console = Console()
    
    click.echo(f"{Fore.CYAN}--- [HADES AUDIT] Investigação de integridade ---{Style.RESET_ALL}")

    # 1. Investigar locks
    active_procs = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Lista arquivos abertos pelo processo
            for file in proc.open_files():
                if 'doxoade.db' in file.path: # Verifica especificamente nosso db
                    active_procs.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    if active_procs:
        click.echo(f"{Fore.YELLOW}[!] Processos ativos segurando o banco:{Style.RESET_ALL}")
        for p in set(active_procs): # set() para evitar duplicados
            click.echo(f"  - {p}")
        click.echo(f"{Fore.YELLOW}Dica: Se este processo não estiver fazendo nada útil, encerre-o com 'taskkill /PID <pid> /F'{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.GREEN}[OK] Nenhum processo bloqueando o banco.{Style.RESET_ALL}")

    # 2. Integridade SQLite
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            res = conn.execute("PRAGMA integrity_check").fetchone()
            if res[0] == "ok":
                click.echo(f"{Fore.GREEN}[OK] Integridade do arquivo DB: OK{Style.RESET_ALL}")
            else:
                click.echo(f"{Fore.RED}[FALHA] Corrupção detectada: {res[0]}{Style.RESET_ALL}")
            conn.close()
        except Exception as e:
            click.echo(f"{Fore.RED}[ERRO] Falha ao verificar integridade: {e}{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.RED}[ERRO] Arquivo do banco não encontrado em: {db_path}{Style.RESET_ALL}")
        
@db_group.command('usage')
@click.argument('path', type=click.Path(exists=True), default='.')
def db_usage(path):
    """Mapeia todos os arquivos que importam ou usam o banco de dados."""
    target_path = Path(path).resolve()
    click.echo(f"{Fore.CYAN}--- [DB-AUDIT] Mapeando dependências de banco de dados ---{Style.RESET_ALL}")
    
    # Gatilhos que indicam que o arquivo acessa o DB
    triggers = {'sqlite3', 'get_db_connection', 'nexus_db'}
    found_files = []

    for py_file in target_path.rglob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                # Detecta imports de sqlite3 ou nexus_db
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for name in node.names:
                        if any(t in name.name for t in triggers):
                            found_files.append((py_file, node.lineno, 'Import'))
                
                # Detecta chamadas diretas a get_db_connection
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == 'get_db_connection':
                        found_files.append((py_file, node.lineno, 'Call'))

        except Exception as e:
            continue

    if found_files:
        for f_path, line, kind in found_files:
            rel_p = f_path.relative_to(target_path.parent)
            click.echo(f"  {Fore.YELLOW}● {Fore.WHITE}{str(rel_p):<30} {Fore.DIM}| Linha {line:<4} | Tipo: {kind}{Style.RESET_ALL}")
#            click.echo(f"  {Fore.YELLOW}● {Fore.WHITE}{rel_p:<30} {Fore.DIM}| Linha {line:<4} | Tipo: {kind}{Style.RESET_ALL}")
    else:
        click.echo(f"{Fore.GREEN}✔ Nenhum acesso ao banco detectado.{Style.RESET_ALL}")

@db_group.command('refactor')
@click.argument('target_file', required=False, type=click.Path(exists=True))
@click.option('--autopilot', is_flag=True, help="Refatora todos os arquivos detectados pelo 'db usage'.")
@click.option('--dry-run', is_flag=True, help="Simula as alterações sem gravar no disco.")
def refactor(target_file, autopilot, dry_run):
    """Refatora chamadas SQL para usar o motor assíncrono Alexandria."""
    from doxoade.tools.vulcan.refactor_exec import apply_alexandria_patch
    from pathlib import Path
    import ast
    
    click.echo(f"{Fore.CYAN}--- [ALEXANDRIA] Orquestração de Refatoração ---{Style.RESET_ALL}")
    files_to_process = set()

    if target_file:
        files_to_process.add(Path(target_file).resolve())
    elif autopilot:
        click.echo(f"{Style.DIM}[*] Autopilot ativado: Analisando AST em busca de chamadas .execute()...{Style.RESET_ALL}")
        # Varredura inteligente (semelhante ao db usage)
        for py_file in Path('.').rglob('*.py'):
            if 'venv' in py_file.parts or '.git' in py_file.parts or py_file.name == 'db_refactorer.py':
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8', errors='ignore'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
                        files_to_process.add(py_file)
                        break # Encontrou um execute(), adiciona o arquivo e vai para o próximo
            except Exception:
                continue
    else:
        click.echo(f"{Fore.RED}✘ Especifique um arquivo alvo ou use --autopilot.{Style.RESET_ALL}")
        return

    if not files_to_process:
        click.echo(f"{Fore.GREEN}✔ Nenhum arquivo precisa de refatoração.{Style.RESET_ALL}")
        return

    click.echo(f"{Fore.YELLOW}Arquivos na fila de refatoração: {len(files_to_process)}{Style.RESET_ALL}\n")

    for f_path in files_to_process:
        # Recebe a tupla com 3 valores agora
        success, msg, diff = apply_alexandria_patch(f_path, dry_run=dry_run)
        
        if success:
            color = Fore.YELLOW if dry_run else Fore.GREEN
            click.echo(f"\n{color}● {f_path.name}: {msg}{Style.RESET_ALL}")
            
            # Pinta o diff estilo Git
            if diff:
                click.echo(f"{Style.DIM}--- PREVIEW DA CIRURGIA AST ---{Style.RESET_ALL}")
                for line in diff.splitlines():
                    if line.startswith('+') and not line.startswith('+++'):
                        click.echo(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
                    elif line.startswith('-') and not line.startswith('---'):
                        click.echo(f"{Fore.RED}{line}{Style.RESET_ALL}")
                    elif line.startswith('@@'):
                        click.echo(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
                    else:
                        click.echo(f"{Style.DIM}{line}{Style.RESET_ALL}")
                click.echo(f"{Style.DIM}-------------------------------{Style.RESET_ALL}")
        else:
            click.echo(f"  {Style.DIM}○ {f_path.name}: {msg}{Style.RESET_ALL}")

    if dry_run:
        click.echo(f"\n{Fore.YELLOW}MODO DRY-RUN: Simulação concluída. Use sem --dry-run para gravar.{Style.RESET_ALL}")
