# doxoade/commands/git_workflow.py
import sys
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _run_git_command

__version__ = "34.1 Alfa"

@click.command('release')
@click.pass_context
@click.argument('version')
@click.argument('message')
@click.option('--remote', default='origin', help='Nome do remote Git.')
def release(ctx, version, message, remote):
    """Cria e publica uma tag Git para formalizar uma nova versão."""
    with ExecutionLogger('release', '.', ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [RELEASE] Criando tag Git para versão {version} ---")
        if not _run_git_command(['tag', version, '-a', '-m', message]):
            logger.add_finding('error', 'Falha ao criar a tag Git local.')
            sys.exit(1)
        
        click.echo(Fore.GREEN + f"[OK] Tag Git '{version}' criada com sucesso.")
        
        if _run_git_command(['push', remote, version]):
            click.echo(Fore.GREEN + f"[OK] Tag '{version}' enviada para o remote '{remote}'.")
        else:
            logger.add_finding('warning', f"Falha ao enviar a tag para o remote '{remote}'.")

@click.command('sync')
@click.pass_context
@click.option('--remote', default='origin', help='Nome do remote Git.')
@click.option('--force', is_flag=True, help="Força o envio das alterações (git push --force).")
def sync(ctx, remote, force):
    """Sincroniza o branch local atual com o branch remoto (git pull && git push)."""
    with ExecutionLogger('sync', '.', ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [SYNC] Sincronizando branch com o remote '{remote}' ---")

        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True)
        if not current_branch:
            logger.add_finding('error', "Não foi possível determinar o branch atual.")
            sys.exit(1)
        
        # Passo 1: Pull
        click.echo(Fore.YELLOW + "\nPasso 1: Puxando as últimas alterações (git pull)...")
        # Mesmo com force push, tentamos atualizar o local primeiro para reduzir conflitos,
        # a menos que o histórico tenha divergido drasticamente.
        if not _run_git_command(['pull', '--no-edit', remote, current_branch]):
            click.echo(Fore.RED + "[AVISO] 'git pull' falhou (possível divergência de histórico).")
            if not force:
                logger.add_finding('error', "Falha ao executar 'git pull'. Use --force se deseja sobrescrever o remote.")
                sys.exit(1)
            else:
                click.echo(Fore.YELLOW + "   > Ignorando falha no pull devido à flag --force.")
        else:
            click.echo(Fore.GREEN + "[OK] Repositório local atualizado.")

        # Passo 2: Push
        click.echo(Fore.YELLOW + "\nPasso 2: Enviando alterações locais (git push)...")
        
        # Verifica status se não estiver forçando
        is_ahead = "ahead" in (_run_git_command(['status', '-sb'], capture_output=True) or "")
        
        if force:
            click.echo(Fore.RED + Style.BRIGHT + f"   > [ATENÇÃO] Modo FORCE ativado. Sobrescrevendo histórico no remote '{remote}'...")
            push_args = ['push', '--force', remote, current_branch]
        else:
            push_args = ['push', remote, current_branch]

        # Lógica de execução
        if not is_ahead and not force:
            click.echo(Fore.GREEN + "[OK] Nenhum commit local novo para enviar.")
        elif not _run_git_command(push_args):
            logger.add_finding('error', "Falha ao executar 'git push'.")
            sys.exit(1)
        else:
            msg_success = "[OK] Envio forçado concluído com sucesso." if force else "[OK] Commits locais enviados com sucesso."
            click.echo(Fore.GREEN + msg_success)