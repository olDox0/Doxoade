# doxoade/doxoade/commands/horus_cmd.py
import click
# [DOX-UNUSED] import json
from doxoade.tools.doxcolors import Fore, Style
from doxoade.database import get_db_connection

@click.group('horus')
def horus_group():
    """👁️  Hórus: Sistema de Observabilidade de Incepção (Black Box)."""
    pass

def run_horus_view_logic(limit=100, full=False, focus=None):
    """Lógica de visualização NSR pura, invocável por outros sistemas."""
    from doxoade.database import get_db_connection
    import json
    
    conn = get_db_connection()
    query = """
        SELECT timestamp, action, data, subsystem 
        FROM operational_logs 
        WHERE subsystem IN ('HORUS', 'SHADOW', 'AEGIS') 
        ORDER BY id DESC LIMIT ?
    """
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()

    click.secho("\n--- 👁️  INQUÉRITO HÓRUS: TIMELINE DO INCIDENTE ---", fg='cyan', bold=True)
    
    stack_level = 0
    for r in reversed(rows):
        try:
            data = json.loads(r['data'])
            # Filtro de Foco inteligente
            if focus and focus not in data.get('file', '') and focus not in data.get('f', ''):
                continue
            
            f_name = data.get('f', data.get('func', '???')).split('.')[-1]
            sub = r['subsystem']
            color = Fore.CYAN if sub == 'SHADOW' else Fore.MAGENTA
            action = r['action']
            
            if action in ['ENTER', 'FUNCTION_IN']:
                indent = "  " * stack_level
                click.echo(f"{Style.DIM}{indent}{color}[{sub}] ➔ {f_name}{Style.RESET_ALL}")
                if full and 'args' in data:
                    click.echo(f"{Style.DIM}{indent}      Args: {Fore.YELLOW}{data['args']}{Style.RESET_ALL}")
                stack_level += 1
            elif action in ['EXIT', 'FUNCTION_OUT']:
                stack_level = max(0, stack_level - 1)
                indent = "  " * stack_level
                status = data.get('status', 'SUCCESS')
                s_color = Fore.GREEN if status == 'SUCCESS' else Fore.RED
                click.echo(f"{Style.DIM}{indent}{color}[{sub}] ⇠ {f_name} {s_color}({status}){Style.RESET_ALL}")
                if full and 'snapshot' in data:
                    click.echo(f"{Style.DIM}{indent}      Snapshot: {data['snapshot']}")
            elif 'error' in action.lower() or 'fail' in action.lower():
                # Destaca falhas funcionais e erros de subprocessos em vermelho no terminal
                indent = "  " * max(0, stack_level - 1)
                err_msg = data.get('error', data.get('stderr', 'Erro operacional ocultado.'))
                click.echo(f"{indent}{Fore.RED}{Style.BRIGHT}❌ [{sub} ERROR] {action} em {f_name}: {err_msg}{Style.RESET_ALL}")
                if full:
                    # Imprime as coordenadas e o dicionário de telemetria completo
                    click.echo(f"{indent}      Diagnostic Payload: {Fore.YELLOW}{data}{Style.RESET_ALL}")
            else:
                # Log operacional comum ou de outras categorias
                indent = "  " * stack_level
                click.echo(f"{Style.DIM}{indent}{color}[{sub} INFO] {action}: {f_name}{Style.RESET_ALL}")
                if full:
                    click.echo(f"{Style.DIM}{indent}      Payload: {Fore.YELLOW}{data}{Style.RESET_ALL}")
        except Exception: continue

@horus_group.command('view')
@click.option('--limit', '-n', default=100)
@click.option('--full', is_flag=True)
@click.option('--focus', help='Foca o rastro apenas em um arquivo')
def horus_view(limit, full, focus):
    run_horus_view_logic(limit, full, focus)

@horus_group.command('purge')
def horus_purge():
    """Limpa o registro tático (HORUS, SHADOW e AEGIS)."""
    conn = get_db_connection()
    conn.execute("DELETE FROM operational_logs WHERE subsystem IN ('HORUS', 'SHADOW', 'AEGIS', 'DIAG')")
    conn.commit()
    conn.close()
    click.secho("[OK] Memória operacional do Nexus purificada.", fg='green')
    
@horus_group.command('run', context_settings=dict(ignore_unknown_options=True))
@click.argument('cmd_args', nargs=-1, type=click.UNPROCESSED)
def horus_run(cmd_args):
    """Executa um comando sob a vigilância total de Hórus."""
    import shlex
    import subprocess
    import os
    import sys
    import shutil
    
    if not cmd_args:
        return
    try:
        # [PLATINUM] Inteligência de Parsing:
        if len(cmd_args) == 1 and " " in cmd_args[0]:
            full_cmd = shlex.split(cmd_args[0].replace('\\', '/'))
        else:
            full_cmd = list(cmd_args)
            
        # Injeção de interpretador para evitar 'doxoade is not recognized' no Windows
        if full_cmd[0] == 'doxoade':
            full_cmd = [sys.executable, "-m", "doxoade"] + full_cmd[1:]
        elif not shutil.which(full_cmd[0]) and full_cmd[0] != sys.executable:
            # Encaminha comandos não mapeados na raiz para o executável padrão
            full_cmd = [sys.executable, "-m", "doxoade"] + full_cmd
            
        click.secho(f"👁️  [HORUS SHADOW] Monitorando: {' '.join(full_cmd)}", fg='cyan', bold=True)
        
        env = os.environ.copy()
        env['DOXOADE_HORUS_ACTIVE'] = '1'
        
        subprocess.run(full_cmd, env=env, shell=False)
    except Exception as e:
        click.secho(f"✘ Falha ao orquestrar sombra: {e}", fg='red')
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)

    click.secho("\n[!] Vigilância encerrada. Use 'doxoade horus view' para ver o rastro.", fg='yellow')
    
@horus_group.command('db')
def horus_db():
    """Analisa a saúde e latência do subsistema de dados Hades."""
    from doxoade.database import get_db_stats
    try:
        stats = get_db_stats()
        
        click.secho("\n--- 👁️  HÓRUS: MONITORAMENTO HADES ---", fg='cyan', bold=True)
        click.echo(f"  Peso Físico: {Fore.YELLOW}{stats['size_mb']} MB")
        click.echo(f"  Integridade: {Fore.GREEN}{stats['integrity']}")
        
        if stats['bloat_pct'] > 10:
            click.secho(f"  [!] Inchaço: {stats['bloat_pct']}% - Sugerido: doxoade db optimize", fg='red')
        
        click.echo(f"\n  Acervo Lexicon: {Fore.CYAN}{stats['counts']['knowledge_lexicon']} padrões")
        click.echo(f"  Histórico Bruto: {Fore.WHITE}{stats['counts']['findings']} registros")
    except Exception as e:
        import sys as exc_sys
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = exc_sys.exc_info()
        exc_trace(exc_tb)