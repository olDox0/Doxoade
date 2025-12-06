import click

def soma_simples(a, b):
    return a + b

@click.command()
def comando_cli():
    """Este comando tem decorator, a validação de args deve ignorá-lo."""
    click.echo("Rodando CLI")

# A função 'funcao_removida' NÃO existe aqui propositalmente.