# doxoade/doxoade/commands/kvcheck.py
import os
import re
import click
from doxoade.tools.display import _present_results
from doxoade.tools.analysis import _get_code_snippet
from doxoade.commands.doxcolors_systems.colors_command import config
from doxoade.tools.filesystem import _get_project_config
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@click.command('kvcheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, dir_okay=True, file_okay=True), default='.')
@click.option('--ignore', multiple=True, help='Ignora uma pasta ou arquivo específico.')
def kvcheck(ctx, path, ignore):
    """
    Analisa arquivos Kivy (.kv) em busca de problemas comuns e riscos de performance.
    """
    arguments = ctx.params
    with ExecutionLogger('kvcheck', path, arguments) as logger:
        config = _get_project_config(logger, start_path=path if os.path.isdir(path) else os.path.dirname(path))
        if not config.get('search_path_valid'):
            _present_results('text', logger.results)
            return
        files_to_check = []
        if os.path.isfile(path) and path.endswith('.kv'):
            files_to_check.append(path)
        else:
            folders_to_ignore = set(config.get('ignore', []) + list(ignore))
            for root, dirs, files in os.walk(config.get('search_path'), topdown=True):
                dirs[:] = [d for d in dirs if d not in folders_to_ignore]
                for file in files:
                    if file.endswith('.kv'):
                        files_to_check.append(os.path.join(root, file))
        if not files_to_check:
            logger.add_finding('INFO', 'Nenhum arquivo .kv encontrado para análise.')
        else:
            for file_path in files_to_check:
                _analyze_kv_file(file_path, logger)
        _present_results('text', logger.results)

def _analyze_kv_file(file_path, logger):
    """Executa a análise em um único arquivo .kv."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except IOError as e:
        logger.add_finding('ERROR', f'Não foi possível ler o arquivo: {e}', file=file_path)
        return
    id_pattern = re.compile('^\\s+id:\\s*(\\w+)')
    ids_found = {}
    for line_num, line in enumerate(lines, 1):
        match = id_pattern.match(line)
        if match:
            current_id = match.group(1)
            if current_id in ids_found:
                original_line = ids_found[current_id]
                logger.add_finding('WARNING', f"ID duplicado encontrado: '{current_id}'.", file=file_path, line=line_num, details=f'O mesmo ID foi usado anteriormente na linha {original_line}.', snippet=_get_code_snippet(file_path, line_num))
            else:
                ids_found[current_id] = line_num
        if 'source:' in line and ('"/' in line or "'/" in line or '"\\' in line or ("'\\" in line)):
            logger.add_finding('WARNING', "Path de recurso potencialmente 'hardcoded'.", file=file_path, line=line_num, details='Usar paths absolutos ou com barras invertidas pode quebrar a portabilidade.', snippet=_get_code_snippet(file_path, line_num))
