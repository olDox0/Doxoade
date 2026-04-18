import click
import os
from .compress_utils import uncompress_zst_to_targz

@click.command()
@click.argument('file_path')
@click.option('--uncompress', is_flag=True, help='Descomprime e normaliza RootFS.')
def compress_cmd(file_path, uncompress):
    """Utilitário de compressão Doxoade (PASC-8.4)."""
    if uncompress and file_path.endswith('.zst'):
        output = file_path.replace('.tar.zst', '-final.tar.gz')
        click.echo(f"[*] Convertendo {file_path} para {output}...")
        if uncompress_zst_to_targz(file_path, output):
            click.secho(f"[OK] Arquivo pronto para WSL: {output}", fg='green')