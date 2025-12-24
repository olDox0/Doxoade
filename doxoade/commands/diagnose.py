# doxoade/commands/diagnose.py
import click
import json
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger
from ..diagnostic.inspector import SystemInspector

@click.command('diagnose')
@click.option('--json', 'as_json', is_flag=True, help="Saída em formato JSON.")
def diagnose(as_json):
    """
    Relatório completo de saúde do sistema, ambiente e integridade.
    """
    inspector = SystemInspector()
    
    with ExecutionLogger('diagnose', '.', {}) as logger:
        if not as_json:
            click.echo(Fore.CYAN + "--- [DIAGNOSE] Iniciando varredura do sistema ---")
        
        data = inspector.run_full_diagnosis()
        
        if as_json:
            click.echo(json.dumps(data, indent=2))
            return

        # 1. Ambiente
        env = data['environment']
        click.echo(Fore.WHITE + Style.BRIGHT + "\n🖥️  AMBIENTE DE EXECUÇÃO")
        click.echo(f"   OS:       {Fore.YELLOW}{env['os']} {env['release']} ({env['arch']}){Style.RESET_ALL}")
        click.echo(f"   Python:   {Fore.YELLOW}{env['python_version']}{Style.RESET_ALL}")
        
        if env['venv_active']:
            venv_status = f"{Fore.GREEN}ATIVO{Style.RESET_ALL}"
            # Mostra o caminho relativo para ficar mais limpo
            path_display = env['venv_path'][-40:] if len(env['venv_path']) > 40 else env['venv_path']
            click.echo(f"   VENV:     {venv_status} (...{path_display})")
        else:
            click.echo(f"   VENV:     {Fore.RED}INATIVO (Cuidado: Usando Python Global){Style.RESET_ALL}")
            
        # 2. Git
        git = data['git']
        click.echo(Fore.WHITE + Style.BRIGHT + "\n📦 ESTADO DO REPOSITÓRIO")
        if git['is_git_repo']:
            branch_color = Fore.GREEN if git['branch'] in ['main', 'master', 'dev'] else Fore.YELLOW
            click.echo(f"   Branch:   {branch_color}{git['branch']}{Style.RESET_ALL}")
            
            # Mudança de terminologia: SUJO -> MODIFICADO
            if git['dirty_tree']:
                status_text = f"{Fore.YELLOW}MODIFICADO (Alterações não salvas){Style.RESET_ALL}"
                click.echo(f"   Status:   {status_text}")
                
                # Lista os arquivos pendentes
                pending = git.get('pending_files', [])
                click.echo(f"   Pendentes: {len(pending)} arquivo(s)")
                for f in pending[:5]: # Mostra os primeiros 5
                    click.echo(f"      {Fore.RED}• {f}{Style.RESET_ALL}")
                if len(pending) > 5:
                    click.echo(f"      {Style.DIM}... e mais {len(pending)-5}{Style.RESET_ALL}")
            else:
                click.echo(f"   Status:   {Fore.GREEN}LIMPO (Tudo salvo){Style.RESET_ALL}")
            
            click.echo(f"   Último:   {Style.DIM}{git.get('last_commit', 'N/A')}{Style.RESET_ALL}")
        else:
            click.echo(f"   {Fore.RED}Não é um repositório Git.{Style.RESET_ALL}")

        # 3. Integridade
        core = data['integrity']
        click.echo(Fore.WHITE + Style.BRIGHT + "\n🛡️  INTEGRIDADE DO NÚCLEO")
        all_ok = True
        for mod, status in core.items():
            if status == "OK":
                clean_name = mod.replace("doxoade.", "")
                click.echo(f"   {clean_name:<20} {Fore.GREEN}✔ OK{Style.RESET_ALL}")
            else:
                click.echo(f"   {mod:<20} {Fore.RED}✘ {status}{Style.RESET_ALL}")
                all_ok = False
        
        if all_ok:
            click.echo(Fore.GREEN + "\n[OK] Diagnóstico concluído. Sistema saudável.")
        else:
            click.echo(Fore.RED + "\n[FALHA] Existem componentes quebrados.")