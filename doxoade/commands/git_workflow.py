# doxoade/commands/git_workflow.py
import sys
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _run_git_command

__version__ = "34.2 Alfa (Safe Sync)"

def _format_git_status(status_line):
    """Formata a linha de status do git diff --name-status para exibição amigável."""
    if not status_line.strip(): return ""
    
    parts = status_line.split('\t')
    if len(parts) < 2: return status_line
    
    code = parts[0][0] # M, A, D, etc.
    file = parts[1]
    
    if code == 'A': return f"{Fore.GREEN}[NOVO] {file}{Style.RESET_ALL}"
    if code == 'M': return f"{Fore.YELLOW}[MODIFICADO] {file}{Style.RESET_ALL}"
    if code == 'D': return f"{Fore.RED}[DELETADO] {file} (PERIGO!){Style.RESET_ALL}"
    if code == 'R': return f"{Fore.CYAN}[RENOMEADO] {file}{Style.RESET_ALL}"
    
    return f"[{code}] {file}"

def _analyze_impact(remote, branch):
    """
    Realiza uma análise forense do que vai acontecer se o sync prosseguir.
    Retorna True se o usuário confirmar, False se abortar.
    """
    click.echo(Fore.WHITE + "\n🔍 [SAFE MODE] Analisando impacto da sincronização...")
    
    # 1. Atualiza referências sem tocar nos arquivos (Fetch)
    _run_git_command(['fetch', remote])
    
    remote_ref = f"{remote}/{branch}"
    
    # 2. Analisa INCOMING (O que vem do servidor -> Local)
    # Mostra o que o Pull vai fazer
    incoming_changes = _run_git_command(
        ['diff', '--name-status', f'HEAD..{remote_ref}'], 
        capture_output=True
    )
    
    # 3. Analisa OUTGOING (Local -> Servidor)
    # Mostra o que o Push vai fazer
    outgoing_changes = _run_git_command(
        ['diff', '--name-status', f'{remote_ref}..HEAD'], 
        capture_output=True
    )
    
    has_danger = False
    
    # --- RELATÓRIO INCOMING ---
    click.echo(Fore.CYAN + "\n📥 [INCOMING] O que o SERVIDOR fará no seu PC (Pull):")
    if incoming_changes and incoming_changes.strip():
        for line in incoming_changes.splitlines():
            formatted = _format_git_status(line)
            click.echo(f"   {formatted}")
            if '[DELETADO]' in formatted: has_danger = True
    else:
        click.echo(Fore.WHITE + Style.DIM + "   (Nenhuma alteração vinda do servidor)")

    # --- RELATÓRIO OUTGOING ---
    click.echo(Fore.MAGENTA + "\n📤 [OUTGOING] O que VOCÊ fará no Servidor (Push):")
    if outgoing_changes and outgoing_changes.strip():
        for line in outgoing_changes.splitlines():
            formatted = _format_git_status(line)
            click.echo(f"   {formatted}")
            if '[DELETADO]' in formatted: has_danger = True
    else:
        click.echo(Fore.WHITE + Style.DIM + "   (Nenhuma alteração local para enviar)")

    # Alerta de Regressão/Deleção
    if has_danger:
        click.echo(Fore.RED + Style.BRIGHT + "\n🚨 ALERTA: Existem arquivos marcados para DELEÇÃO!")
        click.echo(Fore.RED + "   Verifique se isso é intencional antes de prosseguir.")
        
    click.echo(Fore.WHITE + "-" * 60)
    
    if click.confirm(Fore.YELLOW + "Deseja aplicar estas alterações (Pull + Push)?"):
        return True
    return False

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
@click.option('--safe', is_flag=True, help="Modo seguro: Analisa e pede confirmação antes de alterar arquivos.")
def sync(ctx, remote, force, safe):
    """Sincroniza o branch local atual com o branch remoto (git pull && git push)."""
    with ExecutionLogger('sync', '.', ctx.params) as logger:
        click.echo(Fore.CYAN + f"--- [SYNC] Sincronizando branch com o remote '{remote}' ---")

        current_branch = _run_git_command(['branch', '--show-current'], capture_output=True)
        if not current_branch:
            # Fallback para ambientes CI/CD ou detecção manual
            current_branch = _run_git_command(['rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True)
            
        if not current_branch or "HEAD" in current_branch:
            logger.add_finding('error', "Não foi possível determinar o branch atual (Detached HEAD?).")
            sys.exit(1)
        
        current_branch = current_branch.strip()

        # --- MODO SAFE: Análise Prévia ---
        if safe:
            if not _analyze_impact(remote, current_branch):
                click.echo(Fore.YELLOW + "\n[SYNC] Operação cancelada pelo usuário.")
                sys.exit(0)

        # Passo 1: Pull
        click.echo(Fore.YELLOW + "\nPasso 1: Puxando as últimas alterações (git pull)...")
        # Mesmo com force push, tentamos atualizar o local primeiro para reduzir conflitos,
        # a menos que o histórico tenha divergido drasticamente.
        if not _run_git_command(['pull', '--no-edit', remote, current_branch]):
            click.echo(Fore.RED + "[AVISO] 'git pull' falhou (possível divergência de histórico).")
            if not force:
                logger.add_finding('error', "Falha ao executar 'git pull'. Use --force se deseja sobrescrever o remote (CUIDADO).")
                sys.exit(1)
            else:
                click.echo(Fore.YELLOW + "   > Ignorando falha no pull devido à flag --force.")
        else:
            click.echo(Fore.GREEN + "[OK] Repositório local atualizado.")

        # Passo 2: Push
        click.echo(Fore.YELLOW + "\nPasso 2: Enviando alterações locais (git push)...")
        
        # Verifica status se não estiver forçando
        status_output = _run_git_command(['status', '-sb'], capture_output=True) or ""
        is_ahead = "ahead" in status_output
        
        if force:
            click.echo(Fore.RED + Style.BRIGHT + f"   > [ATENÇÃO] Modo FORCE ativado. Sobrescrevendo histórico no remote '{remote}'...")
            push_args = ['push', '--force', remote, current_branch]
        else:
            push_args = ['push', remote, current_branch]

        # Lógica de execução
        if not is_ahead and not force and "behind" not in status_output:
            click.echo(Fore.GREEN + "[OK] Nenhum commit local novo para enviar.")
        elif not _run_git_command(push_args):
            logger.add_finding('error', "Falha ao executar 'git push'.")
            sys.exit(1)
        else:
            msg_success = "[OK] Envio forçado concluído com sucesso." if force else "[OK] Commits locais enviados com sucesso."
            click.echo(Fore.GREEN + msg_success)