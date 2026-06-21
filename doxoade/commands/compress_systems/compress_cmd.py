# doxoade/doxoade/commands/compress_systems/compress_cmd.py
import click
# [DOX-UNUSED] import os
from .compress_utils import uncompress_zst_to_targz

@click.group('compress', no_args_is_help=True)
def compress_group():
    """Utilitário de compressão Doxoade."""
    pass

@compress_group.command('file')
@click.argument('file_path')
@click.option('--uncompress', is_flag=True)
def compress_file_cmd(file_path, uncompress):
    """Comprime ou descomprime um arquivo específico."""
    if uncompress and file_path.endswith('.zst'):
        output = file_path.replace('.tar.zst', '-final.tar.gz')
        click.echo(f"[*] Convertendo {file_path} para {output}...")
        if uncompress_zst_to_targz(file_path, output):
            click.secho(f"[OK] Arquivo pronto para WSL: {output}", fg='green')