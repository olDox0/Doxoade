# doxoade/commands/history.py
import click
import sqlite3
import os
from colorama import Fore, Style
from ..database import get_db_connection
from ..shared_tools import ExecutionLogger, _format_timestamp, _get_code_snippet

def _render_context(content, target_line, context_lines, header_title, header_color):
    """Renderiza um bloco de código com destaque."""
    click.echo(f"\n{header_color}--- {header_title} ---{Style.RESET_ALL}")
    
    if not content:
        click.echo(f"{Style.DIM}(Conteúdo não disponível){Style.RESET_ALL}")
        return

    lines = content.splitlines()
    if not lines: return

    # Se target_line for 0 ou None, tenta mostrar o início
    t_line = target_line if target_line and target_line > 0 else 1
    
    start = max(0, t_line - context_lines - 1)
    end = min(len(lines), t_line + context_lines)
    
    for i in range(start, end):
        line_num = i + 1
        prefix = " >> " if line_num == t_line else "    "
        # Destaque visual: Linha do erro em Vermelho ou Verde dependendo do contexto
        if line_num == t_line:
            line_style = header_color + Style.BRIGHT
        else:
            line_style = Fore.WHITE + Style.DIM
            
        click.echo(f"{line_style}{prefix}{line_num:4}: {lines[i]}{Style.RESET_ALL}")

@click.command('history')
@click.pass_context
@click.option('--hash', 'finding_hash', help="Filtra por hash específico.")
@click.option('--message', '-m', help="Filtra por texto na mensagem.")
@click.option('--file', '-f', help="Filtra por nome de arquivo.")
@click.option('--category', '-c', help="Filtra por categoria (ex: SYNTAX, SECURITY, DEADCODE).")
@click.option('--limit', '-n', default=20, help="Quantidade de resultados.")
@click.option('--context', default=3, help="Linhas de contexto de código.")
@click.option('--unsolved', is_flag=True, help="Mostra incidentes ABERTOS (O problema atual) em vez de soluções.")
def history(ctx, finding_hash, message, file, category, limit, context, unsolved):
    """
    Inteligência Forense: Consulta histórico de soluções e incidentes ativos.
    """
    with ExecutionLogger('history', '.', ctx.params) as logger:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Seleção da Tabela (Solved vs Unsolved)
        if unsolved:
            table = "open_incidents"
            date_col = "timestamp" # Incidentes usam timestamp
            title_mode = "INCIDENTE ATIVO (PROBLEMA)"
            color_mode = Fore.RED
        else:
            table = "solutions"
            date_col = "timestamp"
            title_mode = "SOLUÇÃO APRENDIDA (RESOLVIDO)"
            color_mode = Fore.GREEN

        # Construção Dinâmica da Query
        query = f"SELECT * FROM {table} WHERE 1=1"
        params = []
        
        if finding_hash:
            query += " AND finding_hash LIKE ?"
            params.append(f"%{finding_hash}%")
        if message:
            query += " AND message LIKE ?"
            params.append(f"%{message}%")
        if file:
            query += " AND file_path LIKE ?"
            params.append(f"%{file}%")
        if category and 'category' in [i[1] for i in cursor.execute(f"PRAGMA table_info({table})")]:
            query += " AND category LIKE ?"
            params.append(f"%{category}%")
        
        query += f" ORDER BY {date_col} DESC LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(query, params)
            results = cursor.fetchall()

            if not results:
                click.echo(Fore.YELLOW + "Nenhum registro encontrado para os filtros aplicados.")
                return

            click.echo(Fore.CYAN + f"--- Encontrados {len(results)} registros em '{table}' ---")
            
            for row in results:
                # Metadados
                f_hash = row['finding_hash']
                msg = row['message']
                f_path = row['file_path']
                line = row['line'] if 'line' in row.keys() else (row['error_line'] if 'error_line' in row.keys() else 0)
                cat = row['category'] if 'category' in row.keys() else 'UNKNOWN'
                ts = _format_timestamp(row[date_col])

                click.echo(Style.BRIGHT + f"\n[{title_mode}]")
                click.echo(f"  Mensagem:  {Fore.WHITE}{msg}{Style.RESET_ALL}")
                click.echo(f"  Categoria: {Fore.CYAN}{cat}{Style.RESET_ALL}")
                click.echo(f"  Arquivo:   {Fore.YELLOW}{f_path}:{line}{Style.RESET_ALL}")
                click.echo(f"  Hash:      {Style.DIM}{f_hash}{Style.RESET_ALL}")
                click.echo(f"  Data:      {ts}")

                # Contexto do Código
                code_content = ""
                header_text = ""
                
                if unsolved:
                    # Para incidentes não resolvidos, lemos o arquivo REAL do disco
                    # para mostrar como ele está "quebrado" AGORA.
                    if os.path.exists(f_path):
                        try:
                            with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
                                code_content = f.read()
                            header_text = "Estado Atual (Com Erro)"
                        except Exception:
                            code_content = "(Erro ao ler arquivo do disco)"
                    else:
                        code_content = "(Arquivo não encontrado no disco)"
                else:
                    # Para soluções, mostramos o conteúdo ESTÁVEL (Pós-Fix) salvo no banco
                    code_content = row['stable_content']
                    header_text = "Estado Estável (Pós-Correção)"

                _render_context(code_content, line, context, header_text, color_mode)
                
                click.echo(Fore.MAGENTA + "-"*60 + Style.RESET_ALL)

        except Exception as e:
            logger.add_finding("ERROR", "Falha na query forense.", details=str(e))
            click.echo(Fore.RED + f"Erro SQL/Lógica: {e}")
        finally:
            conn.close()