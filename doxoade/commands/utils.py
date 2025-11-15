# doxoade/commands/utils.py
import os
import sys
import re
import json
import textwrap
import sqlite3
import click
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style
from ..shared_tools import _print_finding_details, _get_code_snippet
from ..database import get_db_connection

#from ..shared_tools import ExecutionLogger

__version__ = "34.0 Alfa"

@click.command('log')
@click.option('-n', '--lines', 'limit', default=10, help="Limita o número de findings exibidos.")
@click.option('-s', '--snippets', is_flag=True, help="Exibe os trechos de código para cada problema.")
@click.option('-b', '--busca', 'search_term', default=None, help="Filtra os findings pela mensagem, categoria ou nome do arquivo.")
def log(limit, snippets, search_term):
    """Exibe e busca nas últimas entradas de log do banco de dados do doxoade."""
    
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Constrói a query SQL dinamicamente
        query = """
            SELECT 
                f.*, 
                e.command, e.project_path, e.timestamp, e.doxoade_version
            FROM findings f
            JOIN events e ON f.event_id = e.id
        """
        params = []

        if search_term:
            click.echo(Fore.CYAN + f"Buscando por '{search_term}' nos logs...")
            query += " WHERE f.message LIKE ? OR f.category LIKE ? OR f.file LIKE ?"
            like_term = f"%{search_term}%"
            params.extend([like_term, like_term, like_term])

        query += " ORDER BY e.timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        findings = cursor.fetchall()

        if not findings:
            click.echo(Fore.YELLOW + "Nenhum problema correspondente encontrado no banco de dados.")
            return

        click.echo(Style.BRIGHT + f"\n--- Exibindo {len(findings)} problema(s) encontrado(s) ---")
        
        # Inverte a lista para mostrar do mais antigo ao mais recente
        for finding in reversed(findings):
            finding_dict = dict(finding)
            
            # --- LÓGICA CONSOLIDADA AQUI DENTRO DO LOOP ---
            
            # 1. Adiciona o contexto do evento no campo 'details'
            event_info = (
                f"Comando: {finding_dict.get('command', 'N/A')} | "
                f"Projeto: {os.path.basename(finding_dict.get('project_path', 'N/A'))} | "
                f"Data: {finding_dict.get('timestamp', 'N/A')}"
            )
            finding_dict['details'] = event_info

            # 2. Se -s for usado, gera o snippet sob demanda
            if snippets and finding_dict.get('file') and finding_dict.get('line'):
                project_path = finding_dict.get('project_path', '')
                full_file_path = os.path.join(project_path, finding_dict['file'])
                
                if os.path.exists(full_file_path):
                    snippet = _get_code_snippet(full_file_path, finding_dict['line'])
                    if snippet:
                        finding_dict['snippet'] = snippet
            
            # 3. Chama a função de impressão com o dicionário completo
            _print_finding_details(finding_dict)
            click.echo("-" * 40)

    except sqlite3.Error as e:
        click.echo(Fore.RED + f"Ocorreu um erro ao ler o banco de dados: {e}", err=True)
    finally:
        if conn:
            conn.close()

@click.command('show-trace')
@click.pass_context
@click.argument('filepath', type=click.Path(exists=True, dir_okay=False), required=False)
def show_trace(ctx, filepath):
    """Analisa e exibe um arquivo de trace de sessão (.jsonl) de forma legível."""
    target_file = filepath
    if not target_file:
        click.echo(Fore.CYAN + "Nenhum arquivo especificado. Procurando pelo trace mais recente...")
        target_file = _find_latest_trace_file()
        if not target_file:
            click.echo(Fore.RED + "Nenhum arquivo de trace ('doxoade_trace_*.jsonl') encontrado no diretório atual."); return
        click.echo(Fore.GREEN + f"Encontrado: '{target_file}'")

    click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- [TRACE REPLAY] Exibindo sessão de '{target_file}' ---")
    
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            click.echo(Fore.YELLOW + "O arquivo de trace está vazio."); return

        first_ts = json.loads(lines[0]).get('ts', 0)
        
        for line in lines:
            try:
                entry = json.loads(line)
                ts = entry.get('ts', 0)
                stream = entry.get('stream', 'unknown')
                data = entry.get('data', '').rstrip('\n')
                
                relative_time = ts - first_ts
                
                color = Fore.YELLOW
                if stream == 'stdout': color = Fore.GREEN
                elif stream == 'stderr': color = Fore.RED
                
                click.echo(color + f"[{relative_time:8.3f}s] [{stream.upper():<6}] " + Style.RESET_ALL + data)

            except (json.JSONDecodeError, KeyError):
                click.echo(Fore.RED + f"[ERRO] Linha malformada no arquivo de trace: {line.strip()}")
                continue
                
    except Exception as e:
        click.echo(Fore.RED + f"Falha ao processar o arquivo de trace: {e}")
    pass # Placeholder

@click.command('mk')
@click.pass_context
@click.argument('items', nargs=-1, required=True)
@click.option('--path', '-p', 'base_path', default='.', type=click.Path(exists=True, file_okay=False, resolve_path=True))
def mk(ctx, base_path, items):
#    """Cria arquivos e pastas rapidamente."""
    """
    Cria arquivos e pastas rapidamente. Pastas devem terminar com '/'.
    
    Suporta expansão de chaves para múltiplos arquivos:
    
    Exemplos:
      doxoade mk src/ tests/ main.py
      doxoade mk "src/app/{models.py, views.py, controllers.py}"
    """
    click.echo(Fore.CYAN + f"--- [MK] Criando estrutura em '{base_path}' ---")
    
    processed_items = []
    # --- NOVA LÓGICA DE EXPANSÃO ---
    # Primeiro, processamos os itens para expandir a sintaxe de chaves
    for item in items:
        match = re.match(r'^(.*)\{(.*)\}(.*)$', item)
        if match:
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            # Quebra o conteúdo das chaves pela vírgula
            filenames = [name.strip() for name in content.split(',')]
            for filename in filenames:
                processed_items.append(f"{prefix}{filename}{suffix}")
        else:
            processed_items.append(item)

    created_count = 0
    for item in processed_items:
        normalized_item = os.path.normpath(item)
        full_path = os.path.join(base_path, normalized_item)
        
        try:
            if item.endswith(('/', '\\')):
                os.makedirs(full_path, exist_ok=True)
                click.echo(Fore.GREEN + f"[CRIADO] Diretório: {full_path}")
                created_count += 1
            else:
                parent_dir = os.path.dirname(full_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                
                if not os.path.exists(full_path):
                    Path(full_path).touch()
                    click.echo(Fore.GREEN + f"[CRIADO] Arquivo:   {full_path}")
                    created_count += 1
                else:
                    click.echo(Fore.YELLOW + f"[EXISTE] Arquivo:   {full_path}")
        except OSError as e:
            click.echo(Fore.RED + f"[ERRO] Falha ao criar '{full_path}': {e}")
            continue
            
    click.echo(Fore.CYAN + Style.BRIGHT + "\n--- Concluído ---")
    click.echo(f"{created_count} novo(s) item(ns) criado(s).")
    pass # Placeholder

@click.command('create-pipeline')
@click.pass_context
@click.argument('filename')
@click.argument('commands', nargs=-1, required=True)
def create_pipeline(ctx, filename, commands):
    """Cria um arquivo de pipeline (.dox) com uma sequência de comandos."""
    """
    Cria um arquivo de pipeline (.dox) com uma sequência de comandos.

    Cada comando deve ser passado como um argumento separado e entre aspas.
    Exemplo:
      doxoade create-pipeline deploy.dox "doxoade health" "doxoade save 'Deploy final' --force"
    """
    click.echo(Fore.CYAN + f"--- [CREATE-PIPELINE] Criando arquivo de pipeline: {filename} ---")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Pipeline gerado pelo doxoade em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for command in commands:
                f.write(f"{command}\n")
        
        click.echo(Fore.GREEN + f"[OK] Pipeline '{filename}' criado com sucesso com {len(commands)} passo(s).")
        click.echo(Fore.YELLOW + f"Agora você pode executá-lo com: doxoade auto --file {filename}")
    except IOError as e:
        click.echo(Fore.RED + f"[ERRO] Não foi possível escrever no arquivo '{filename}': {e}")
        sys.exit(1)
    pass # Placeholder

# Funções auxiliares (copie-as para este arquivo também)
def _display_log_entry(cursor, event, index, total, show_snippets=False):
    """Formata e exibe um único evento do banco de dados."""
    ts_local = event['timestamp'] # O timestamp já deve estar em um formato legível
    header = f"--- Entrada de Log #{index}/{total} ({ts_local}) ---"
    click.echo(Fore.CYAN + Style.BRIGHT + header)

    click.echo(Fore.WHITE + f"Comando: {event['command']} (Doxoade v{event['doxoade_version']})")
    click.echo(Fore.WHITE + f"Projeto: {event['project_path']}")
    click.echo(Fore.WHITE + Style.DIM + f"Tempo: {event['execution_time_ms']:.2f}ms")

    # Busca os 'findings' associados a este evento
    cursor.execute("SELECT * FROM findings WHERE event_id = ?", (event['id'],))
    findings = cursor.fetchall()

    if not findings:
        click.echo(Fore.GREEN + "Resultado: Nenhum problema encontrado nesta execução.")
    else:
        summary_text = f"Resultado: {len(findings)} problema(s) encontrado(s)."
        click.echo(Fore.YELLOW + summary_text)
        click.echo(Fore.WHITE + "Detalhes dos Problemas:")
        for finding in findings:
            finding_dict = dict(finding)
            
            # --- NOVA LÓGICA DE SNIPPET SOB DEMANDA ---
            if show_snippets and finding_dict.get('file') and finding_dict.get('line'):
                # O caminho do arquivo no DB é relativo, precisamos do caminho absoluto do projeto
                project_path = event['project_path']
                full_file_path = os.path.join(project_path, finding_dict['file'])
                
                # Se o arquivo ainda existir, recalcula o snippet
                if os.path.exists(full_file_path):
                    snippet = _get_code_snippet(full_file_path, finding_dict['line'])
                    if snippet:
                        finding_dict['snippet'] = snippet # Adiciona ao dicionário antes de imprimir
            # --- FIM DA NOVA LÓGICA ---

            _print_finding_details(finding_dict)
    
    click.echo("")
    pass

def _find_latest_trace_file():
    try:
        trace_dir = Path.home() / '.doxoade' / 'traces'
        if not trace_dir.exists():
            return None
            
        trace_files = list(trace_dir.glob('trace_*.jsonl'))
        if not trace_files:
            return None
            
        latest_file = max(trace_files, key=lambda p: p.stat().st_mtime)
        return str(latest_file)
    except Exception:
        return None
    pass

@click.command('setup-regression')
def setup_regression():
    """Cria a estrutura de diretórios e arquivos para os testes de regressão."""
    click.echo(Fore.CYAN + "--- [SETUP-REGRESSION] Configurando o ambiente do Projeto Cânone ---")
    
    base_dir = "regression_tests"
    fixtures_dir = os.path.join(base_dir, "fixtures")
    canon_dir = os.path.join(base_dir, "canon")
    
    patient_zero_project = os.path.join(fixtures_dir, "project_syntax_error")
    # Usamos textwrap para um código mais limpo
    patient_zero_code = "def func():\\n    pass # Erro de indentacao"

    canon_toml_content = textwrap.dedent("""
        # Define os casos de teste para o sistema de regressão.
        [[test_case]]
        id = "check_finds_syntax_error"
        command = "doxoade check ."
        project = "project_syntax_error"
    """)
    
    try:
        os.makedirs(patient_zero_project, exist_ok=True)
        os.makedirs(canon_dir, exist_ok=True)
        
        with open(os.path.join(patient_zero_project, "main.py"), "w", encoding="utf-8") as f:
            f.write(patient_zero_code)
        
        with open(os.path.join(base_dir, "canon.toml"), "w", encoding="utf-8") as f:
            f.write(canon_toml_content)
            
        click.echo(Fore.GREEN + "   > [OK] Estrutura de regressão simplificada criada com sucesso.")
        
    except OSError as e:
        click.echo(Fore.RED + f"\\n[ERRO] Falha ao criar a estrutura de diretórios: {e}")
        sys.exit(1)