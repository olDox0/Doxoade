# doxoade/repair_imports.py
import os
import re
import click
BROKEN_IMPORT_PATTERN = re.compile('^(\\s*)from doxoade.tools\\.doxcolors\\b', re.MULTILINE)
FIXED_IMPORT_STRING = '\\1from doxoade.tools.doxcolors'

@click.command()
@click.option('--path', '-p', default='doxoade', help='Caminho do diretório de código-fonte a ser verificado.', type=click.Path(exists=True))
@click.option('--apply', is_flag=True, help='Aplica as correções. Sem esta flag, apenas simula as alterações.')
def fix_imports(path, apply):
    """
    Repara automaticamente as importações de 'tools.doxcolors' para 'doxoade.tools.doxcolors'.
    """
    if apply:
        click.secho('--- MODO DE APLICAÇÃO ---', fg='yellow', bold=True)
        click.secho('As alterações serão salvas permanentemente nos arquivos.', fg='yellow')
    else:
        click.secho('--- MODO DE SIMULAÇÃO (DRY-RUN) ---', fg='cyan', bold=True)
        click.secho('Nenhum arquivo será modificado. Use --apply para salvar as alterações.', fg='cyan')
    project_path = os.path.abspath(path)
    files_modified = 0
    total_files_scanned = 0
    ignore_dirs = {'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade_cache'}
    for root, dirs, files in os.walk(project_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if not file.endswith('.py'):
                continue
            total_files_scanned += 1
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                modified_content, num_subs = BROKEN_IMPORT_PATTERN.subn(FIXED_IMPORT_STRING, original_content)
                if num_subs > 0:
                    click.echo(f'[!] Modificação necessária em: {os.path.relpath(file_path, start=os.getcwd())}')
                    files_modified += 1
                    if apply:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(modified_content)
                        click.secho('    -> [CORRIGIDO]', fg='green')
            except Exception as e:
                click.secho(f'[X] Erro ao processar {file_path}: {e}', fg='red')
    click.secho('\n--- RESUMO DA OPERAÇÃO ---', bold=True)
    click.echo(f'Total de arquivos Python escaneados: {total_files_scanned}')
    if files_modified > 0:
        status_color = 'yellow' if apply else 'cyan'
        action_text = 'foram corrigidos' if apply else 'precisam de correção'
        click.secho(f'{files_modified} arquivos {action_text}.', fg=status_color)
        if not apply:
            click.secho('Para salvar as alterações, rode o script novamente com a flag --apply', fg='cyan', bold=True)
    else:
        click.secho('Nenhuma importação incorreta foi encontrada.', fg='green')
if __name__ == '__main__':
    fix_imports()