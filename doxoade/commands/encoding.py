# doxoade/commands/encoding.py
import os
import sys
import tempfile
from pathlib import Path

import click
from colorama import Fore, Style

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import ExecutionLogger

__version__ = "34.0 Alfa"

@click.command('encoding')
@click.pass_context
@click.argument('targets', nargs=-1, required=True)
def encoding(ctx, targets):
    """Altera a codificação de arquivos para um formato de destino (ex: UTF-8)."""
    if len(targets) < 2:
        click.echo(Fore.RED + "[ERRO] Uso incorreto. Exemplo: doxoade encoding *.md UTF-8")
        return

    input_targets = targets[:-1]
    target_encoding_str = targets[-1]
    
    encoding_aliases = {
        'utf8': 'utf-8', 'unicode': 'utf-8',
        'utf16': 'utf-16', 'utf32': 'utf-32',
        'latin1': 'latin-1', 'iso-8859-1': 'latin-1'
    }
    target_encoding = encoding_aliases.get(target_encoding_str.lower(), target_encoding_str)

    arguments = {'targets': input_targets, 'encoding': target_encoding}
    with ExecutionLogger('encoding', '.', arguments) as logger:
        click.echo(Fore.CYAN + f"--- [ENCODING] Convertendo arquivos para {target_encoding.upper()} ---")

        files_to_process = set()
        for target in input_targets:
            found_files = list(Path('.').rglob(target))
            if not found_files and '*' not in target:
                 if Path(target).is_file(): files_to_process.add(Path(target))
            for p in found_files:
                if p.is_file():
                    files_to_process.add(p)

        if not files_to_process:
            logger.add_finding('warning', f"Nenhum arquivo encontrado para os alvos: {', '.join(input_targets)}")
            click.echo(Fore.YELLOW + "Nenhum arquivo correspondente encontrado.")
            return

        success_count, skipped_count, error_count = 0, 0, 0
        for file_path in sorted(list(files_to_process)):
            status, message = _change_file_encoding(file_path, target_encoding)
            
            if status == 'success':
                success_count += 1
                click.echo(Fore.GREEN + f"[CONVERTIDO] '{file_path}' -> {message}")
            elif status == 'skipped':
                skipped_count += 1
                click.echo(Fore.WHITE + Style.DIM + f"[IGNORADO]    '{file_path}' já está em {target_encoding.upper()}.")
            else: # 'error'
                error_count += 1
                logger.add_finding('error', message, file=str(file_path))
                click.echo(Fore.RED + f"[ERRO]        '{file_path}': {message}")
        
        click.echo(Fore.CYAN + "\n--- Conversão Concluída ---")
        click.echo(f"Processados: {success_count} | Ignorados: {skipped_count} | Erros: {error_count}")
        
        if logger.results['summary']['errors'] > 0:
            sys.exit(1)

def _change_file_encoding(file_path, new_encoding):
    """Lê um arquivo, tenta detectar seu encoding, e o reescreve de forma segura."""
    encodings_to_try = [new_encoding, 'utf-8', sys.getdefaultencoding(), 'cp1252', 'latin-1']
    
    source_encoding = None
    content = None

    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            source_encoding = enc
            break
        except UnicodeDecodeError:
            continue
        except (IOError, OSError) as e:
            return 'error', f"Não foi possível ler o arquivo: {e}"

    if not source_encoding:
        return 'error', "Não foi possível detectar a codificação original do arquivo."

    if source_encoding.lower() == new_encoding.lower():
        return 'skipped', ""

    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding=new_encoding, delete=False, dir=os.path.dirname(file_path)) as temp_file:
            temp_filepath = temp_file.name
            temp_file.write(content)
        
        os.replace(temp_filepath, file_path)
        return 'success', f"{source_encoding.upper()} para {new_encoding.upper()}"
    except (IOError, OSError) as e:
        return 'error', f"Falha ao escrever o novo arquivo: {e}"
    except Exception as e:
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return 'error', f"Ocorreu um erro inesperado: {e}"