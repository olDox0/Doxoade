# doxoade/doxoade/commands/horus_cmd.py
import click
import json
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection

@click.group('horus')
def horus_group():
    """👁️  Hórus: Sistema de Observabilidade de Incepção (Black Box)."""
    pass

@horus_group.command('view')
@click.option('--limit', '-n', default=50)
@click.option('--func', '-f')
@click.option('--full', is_flag=True)
def horus_view(limit, func, full):
    conn = get_db_connection()
    rows = conn.execute("SELECT timestamp, action, data FROM operational_logs WHERE subsystem='HORUS' ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()

    click.secho(f"\n--- 👁️  OLHO DE HÓRUS: ANÁLISE DE FLUXO TÁTICO ---", fg='cyan', bold=True)
    
    stack_level = 0
    for r in reversed(rows):
        data = json.loads(r['data'])
        f_raw = data.get('func', '???')
        f_name = f_raw.split('.')[-1]
        
        if r['action'] == 'FUNCTION_IN':
            indent = "  " * stack_level
            # Destaque em Ciano para entrada normal
            click.echo(f"{Style.DIM}{indent}➔ {Fore.CYAN}{f_name}{Fore.WHITE} (IN)")
            if full: 
                click.echo(f"{Style.DIM}{indent}   Args: {Fore.WHITE}{data.get('input')}")
            stack_level += 1
            
        elif r['action'] == 'FUNCTION_OUT':
            stack_level = max(0, stack_level - 1)
            indent = "  " * stack_level
            output_val = str(data.get('output', 'void'))
            
            # --- LÓGICA DE SUSPEIÇÃO (UX DINÂMICA) ---
            color = Fore.GREEN
            alert = ""
            
            # Se a função deveria retornar algo mas veio vazio/None/void
            is_empty = output_val in ['None', 'void', '[]', '{}', '""', "''"]
            critical_keywords = ['build', 'capture', 'env', 'command', 'exec', 'stream']
            
            if is_empty:
                if any(k in f_name.lower() for k in critical_keywords):
                    color = Fore.YELLOW # Alerta: Retorno vazio suspeito
                    alert = f" {Fore.YELLOW}[!] EMPTY RETURN"
                else:
                    color = Fore.WHITE # Retorno vazio normal (procedimento)
            
            click.echo(f"{Style.DIM}{indent}⇠ {color}{f_name}{Fore.WHITE} (OUT){alert}")
            if full: 
                click.echo(f"{Style.DIM}{indent}   Res: {color}{output_val}")

        elif r['action'] == 'FUNCTION_ERROR':
            stack_level = max(0, stack_level - 1)
            indent = "  " * stack_level
            # Erro em Vermelho/Magenta para atenção imediata
            click.echo(f"{Fore.RED}{Style.BRIGHT}{indent}✘ {f_name} (FATAL ERROR)")
            click.echo(f"{Fore.MAGENTA}{indent}   Motivo: {data.get('error')}")
            click.echo(f"{Style.DIM}{indent}   " + "!" * 40)

@horus_group.command('purge')
def horus_purge():
    """Limpa o registro tático de IO."""
    conn = get_db_connection()
    conn.execute("DELETE FROM operational_logs WHERE subsystem='HORUS'")
    conn.commit()
    conn.close()
    click.secho("[OK] Memória operacional de Hórus purificada.", fg='green')
    
@horus_group.command('run', context_settings=dict(ignore_unknown_options=True))
@click.argument('cmd_string')
def horus_run(cmd_string):
    """Executa um comando sob a vigilância total de Hórus."""
    import shlex
    import subprocess
    import os
    import sys
    
    click.secho(f"👁️  [HORUS SHADOW] Iniciando vigilância em: {cmd_string}", fg='cyan', bold=True)
    
    # Prepara o ambiente para o processo filho ativar o Horus automaticamente
    env = os.environ.copy()
    env['DOXOADE_HORUS_ACTIVE'] = '1'
    
    # Dispara o comando como um subprocesso
    args = shlex.split(cmd_string)
    # Se o comando começar com 'doxoade', garantimos que use o interpretador atual
    if args[0] == 'doxoade':
        args = [sys.executable, "-m", "doxoade"] + args[1:]

    try:
        subprocess.run(args, env=env)
    except Exception as e:
        click.secho(f"✘ Falha ao orquestrar sombra: {e}", fg='red')

    click.secho("\n[!] Vigilância encerrada. Use 'doxoade horus view' para ver o rastro.", fg='yellow')