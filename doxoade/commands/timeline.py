# doxoade/doxoade/commands/timeline.py
import zlib
import json
import click

from doxoade.tools.doxcolors   import Fore, Style
from doxoade.tools.aegis.vault import NexusVault
from doxoade.database          import get_db_connection

import doxoade.tools.aegis.nexus_db as sqlite3  # noqa

#@click.command('timeline')
#@click.option('--unlock', prompt=True, hide_input=True, help="Senha do Cofre Nexus")
#def timeline(unlock):
#    if not verify_vault(unlock):
#        click.secho(" [!] Acesso Negado: Senha do Cofre Incorreta.", fg='red')
#        return
#    # Prossegue com a descompactação e exibição...

if NexusVault.is_unlocked():
    # Mostra os dados detalhados, descompacta o payload, etc.
    render_full_payload(d['compressed_payload'])
else:
    # Mostra apenas que os dados estão protegidos
    click.echo(f"   {Style.DIM}[🔒 PAYLOAD PROTEGIDO - Use 'doxoade vault --open']{Style.RESET_ALL}")

@click.command('timeline')
@click.option('-n', '--limit', default=10, help='Número de eventos.')
@click.option('--full', is_flag=True, help='Mostra o diff completo das alterações.')
def timeline(limit, full):
    """Exibe o histórico cronológico de ações e alterações."""
    conn = get_db_connection()
    # PASC-8.7: Uso obrigatório de Row Factory para integridade de colunas
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM command_history ORDER BY id DESC LIMIT ?', (limit,))
    events = cursor.fetchall()
    
    click.echo(Fore.CYAN + Style.BRIGHT + f'--- Timeline do Doxoade (Últimos {limit}) ---')
    
    for d in reversed(events):
        # Agora o acesso é por NOME, independente da ordem no banco
        exit_code = d['exit_code']
        duration = d['duration_ms']
        payload_raw = d.get('compressed_payload')
        
        click.echo(f"\n{Style.DIM}{d['timestamp'][:19]} {status_color}{status_icon} {Style.BRIGHT}{d['command_name']}")
        click.echo(f"{Style.DIM}   Tempo: {Fore.WHITE}{duration:.0f}ms")
        
        # Se houver dados compactados e a flag --full estiver ativa
        if full and payload_raw:
            try:
                # Descompactação On-the-fly
                decompressed = zlib.decompress(payload_raw)
                data = json.loads(decompressed)
                
                # Exibe Achados (Findings)
                findings = data['output'].get('findings', [])
                if findings:
                    click.echo(f"   {Fore.CYAN}Achados: {len(findings)} ocorrência(s)")
                    for f in findings[:5]: # Mostra os 5 primeiros
                        click.echo(f"     - [{f['severity']}] {f['message'][:60]}")
                
                # Exibe Detalhes do Input
                args = data['input'].get('args', {})
                if args:
                    clean_args = {k: v for k, v in args.items() if v}
                    click.echo(f"   {Fore.YELLOW}Inputs: {clean_args}")
                    
            except Exception as e:
                click.echo(f"   {Fore.RED}Erro ao ler payload: {e}")
        
        status_color = Fore.GREEN if exit_code == 0 else Fore.RED
        status_icon = '✔' if exit_code == 0 else '✘'
        
        click.echo(f"\n{Style.DIM}{d['timestamp'][:19]} {status_color}{status_icon} {Style.BRIGHT}{d['command_name']}")
        click.echo(f"{Style.DIM}   Dir: {d['working_dir']}")
        click.echo(f"{Style.DIM}   Tempo: {Fore.WHITE}{duration:.0f}ms")
        
        # LINHA 39 CORRIGIDA:
        cursor.execute('SELECT * FROM file_audit WHERE command_id = ?', (d['id'],))
        changes = cursor.fetchall()
        if changes:
            for change in changes:
                op_color = Fore.YELLOW if change['operation_type'] == 'MODIFY' else Fore.GREEN
                click.echo(f"   {op_color}[{change['operation_type']}] {change['file_path']}")
                if full and change['diff_content']:
                    diff_view = '\n'.join(['      ' + l for l in change['diff_content'].splitlines()])
                    click.echo(Fore.WHITE + Style.DIM + diff_view)
    conn.close()
