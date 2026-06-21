# doxoade/doxoade/commands/vault_cmd.py
import click
# [DOX-UNUSED] from doxoade.tools.doxcolors import Style
from doxoade.tools.aegis.vault import NexusVault

@click.group('vault')
def vault_group():
    """🛡️ Nexus Vault: Gestão de proteção de dados sensíveis."""
    pass

@vault_group.command('setup')
@click.password_option('--password', confirmation_prompt=True, help='Define a Master Password')
def vault_setup(password):
    """Configura a senha mestre de forma segura."""
    NexusVault.set_password(password)
    click.secho("\n[OK] Master Password configurada com segurança.", fg='green', bold=True)

@vault_group.command('open')
@click.password_option('--password', prompt='Senha do Cofre', help='Senha para desbloqueio')
@click.option('--hours', default=24, help='Tempo de abertura em horas.')
def vault_open(password, hours):
    """Abre o cofre para visualização de dados detalhados."""
    if NexusVault.unlock(password, hours):
        click.secho(f"\n[✔] Cofre Aberto! Acesso autorizado por {hours}h.", fg='cyan', bold=True)
    else:
        click.secho("\n[✘] Acesso Negado: Senha Incorreta.", fg='red', bold=True)

@vault_group.command('lock')
def vault_lock():
    """Fecha o cofre imediatamente."""
    NexusVault.lock()
    click.echo("\n[!] Cofre trancado. Dados sensíveis protegidos.")

@vault_group.command('status')
def vault_status():
    """Verifica o estado atual de segurança."""
    if NexusVault.is_unlocked():
        click.secho("\n[SITUAÇÃO] Cofre: DESBLOQUEADO (Acesso Livre)", fg='yellow')
    else:
        click.secho("\n[SITUAÇÃO] Cofre: PROTEGIDO (Acesso Restrito)", fg='green', bold=True)