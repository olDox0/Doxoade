import click
@click.command('test-shadow')
def test_shadow():
    """Comando para testar a vacinação automática do NSR."""
    click.echo("[*] Iniciando lógica sem proteção manual...")
    disparar_gatilho(10)

def disparar_gatilho(n):
    # O Shadow Runtime injetará o monitor aqui
    return n / 0