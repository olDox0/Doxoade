# doxoade/doxoade/commands/config.py
import os
import toml
import click
from doxoade.tools.doxcolors import Fore
from doxoade.commands.doxcolors_systems.colors_command import config
from doxoade.tools.filesystem import _get_project_config
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@click.group('config')
def config_group():
    """Gerencia a configuração do doxoade para o projeto."""
    pass

@config_group.command('fix')
@click.pass_context
def config_fix(ctx):
    """Audita e repara o arquivo de configuração pyproject.toml."""
    path = '.'
    arguments = ctx.params
    with ExecutionLogger('config-fix', path, arguments) as logger:
        click.echo(Fore.CYAN + '--- [CONFIG --FIX] Auditando o pyproject.toml ---')
        config = _get_project_config(logger, start_path=path)
        root_path = config.get('root_path')
        config_path = os.path.join(root_path, 'pyproject.toml')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf--8') as f:
                    toml_data = toml.load(f)
            else:
                click.echo(Fore.YELLOW + "   > Arquivo 'pyproject.toml' não encontrado. Criando um novo.")
                toml_data = {}
        except toml.TomlDecodeError as e:
            logger.add_finding('CRITICAL', "O arquivo 'pyproject.toml' está corrompido.", details=str(e))
            click.echo(Fore.RED + f"   > [ERRO] O arquivo 'pyproject.toml' parece estar corrompido: {e}")
            return
        tool_table = toml_data.setdefault('tool', {})
        doxoade_config = tool_table.setdefault('doxoade', {})
        doxoade_config.setdefault('ignore', [])
        current_source_dir = doxoade_config.setdefault('source_dir', '.')
        if config.get('search_path_valid'):
            logger.add_finding('INFO', "Configuração do 'source_dir' está válida.")
            click.echo(Fore.GREEN + f"   > [OK] 'source_dir' ('{current_source_dir}') é válido.")
        else:
            logger.add_finding('WARNING', f"O 'source_dir' configurado ('{current_source_dir}') é inválido.")
            click.echo(Fore.YELLOW + f"   > [AVISO] O 'source_dir' atual ('{current_source_dir}') aponta para um diretório inexistente.")
            if click.confirm(Fore.CYAN + "     > Corrigir para '.' (diretório raiz do projeto)?"):
                doxoade_config['source_dir'] = '.'
                try:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        toml.dump(toml_data, f)
                    logger.add_finding('INFO', "O 'source_dir' foi corrigido para '.'.")
                    click.echo(Fore.GREEN + "   > [OK] 'pyproject.toml' corrigido com sucesso.")
                except IOError as e:
                    logger.add_finding('CRITICAL', "Falha ao escrever no 'pyproject.toml'.", details=str(e))
                    click.echo(Fore.RED + f'   > [ERRO] Não foi possível salvar o arquivo: {e}')
