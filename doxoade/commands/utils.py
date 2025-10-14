# doxoade/commands/utils.py
import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path

import click
from colorama import Fore, Style

#from ..shared_tools import ExecutionLogger

__version__ = "34.0 Alfa"

@click.command('log')
@click.pass_context
@click.option('-n', '--lines', default=1, help="Exibe as últimas N linhas do log.", type=int)
@click.option('-s', '--snippets', is_flag=True, help="Exibe os trechos de código para cada problema.")
def log(ctx, lines, snippets):
    """Exibe as últimas entradas do arquivo de log do doxoade."""
    log_file = Path.home() / '.doxoade' / 'doxoade.log'
    
    if not log_file.exists():
        click.echo(Fore.YELLOW + "Nenhum arquivo de log encontrado. Execute um comando de análise primeiro."); return

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        if not all_lines:
            click.echo(Fore.YELLOW + "O arquivo de log está vazio."); return
            
        last_n_lines = all_lines[-lines:]
        
        total_to_show = len(last_n_lines)
        for i, line in enumerate(last_n_lines):
            try:
                entry = json.loads(line)
                # Passa a flag 'snippets' para a função de exibição
                _display_log_entry(entry, index=i + 1, total=total_to_show, show_snippets=snippets)
            except json.JSONDecodeError:
                click.echo(Fore.RED + f"--- Erro ao ler a entrada #{i + 1} ---")
                click.echo(Fore.RED + "A linha no arquivo de log não é um JSON válido.")
                click.echo(Fore.YELLOW + f"Conteúdo da linha: {line.strip()}")
    except Exception as e:
        click.echo(Fore.RED + f"Ocorreu um erro ao ler o arquivo de log: {e}", err=True)

    pass # Placeholder

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
def _display_log_entry(entry, index, total, show_snippets=False):
    try:
        ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
        ts_local = ts.astimezone().strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, KeyError):
        ts_local = entry.get('timestamp', 'N/A')

    header = f"--- Entrada de Log #{index}/{total} ({ts_local}) ---"
    click.echo(Fore.CYAN + Style.BRIGHT + header)

    # --- NOVO BLOCO: CONTEXTO FORENSE DA EXECUÇÃO ---
    click.echo(Fore.WHITE + f"Comando: {entry.get('command', 'N/A')} (Doxoade v{entry.get('doxoade_version', 'N/A')})")
    click.echo(Fore.WHITE + f"Projeto: {entry.get('project_path', 'N/A')}")
    
    context_line = (
        f"Contexto: "
        f"Git({entry.get('git_hash', 'N/A')[:7]}) | "
        f"Plataforma({entry.get('platform', 'N/A')}) | "
        f"Python({entry.get('python_version', 'N/A')}) | "
        f"Tempo({entry.get('execution_time_ms', 0):.2f}ms)"
    )
    click.echo(Fore.WHITE + Style.DIM + context_line)
    # ---------------------------------------------------
    
    summary = entry.get('summary', {})
    errors = summary.get('errors', 0)
    warnings = summary.get('warnings', 0)
    
    summary_color = Fore.RED if errors > 0 else Fore.YELLOW if warnings > 0 else Fore.GREEN
    click.echo(summary_color + f"Resultado: {errors} Erro(s), {warnings} Aviso(s)")

    findings = entry.get('findings')
    if findings:
        click.echo(Fore.WHITE + "Detalhes dos Problemas Encontrados:")
        for finding in findings:
            f_type = finding.get('type', 'info').upper()
            f_color = Fore.RED if 'ERROR' in f_type else Fore.YELLOW
            f_msg = finding.get('message', 'N/A')
            f_file = finding.get('file', 'N/A')
            f_line = finding.get('line', '')
            f_ref = f" [Ref: {finding.get('ref')}]" if finding.get('ref') else ""
            
            click.echo(f_color + f"  - [{f_type}] {f_msg}{f_ref} (em {f_file}, linha {f_line})")

            # --- LÓGICA DE DETALHES COMPLETA ---
            if finding.get('details'):
                click.echo(Fore.CYAN + f"    > {finding.get('details')}")

            # --- LÓGICA DE EXIBIÇÃO DE SNIPPETS ---
            snippet = finding.get('snippet')
            if show_snippets and snippet:
                # Usamos .get() com um valor padrão para evitar erros se a linha não for um número
                f_line_int = int(finding.get('line', -1)) 
                for line_num_str, code_line in snippet.items():
                    line_num = int(line_num_str)
                    if line_num == f_line_int:
                        # Destaque para a linha do erro
                        click.echo(Fore.WHITE + Style.BRIGHT + f"      > {line_num:3}: {code_line}")
                    else:
                        # Contexto com menos destaque
                        click.echo(Fore.WHITE + Style.DIM + f"        {line_num:3}: {code_line}")
            # ----------------------------------------
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