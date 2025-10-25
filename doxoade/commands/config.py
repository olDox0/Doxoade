# DEV.V10-20251022. >>>
# doxoade/commands/config.py
# atualizado em 2025/10/22 - Versão do projeto 43(Ver), Versão da função 1.0(Fnc).
# Descrição: Novo comando 'config --fix' para auditar e reparar interativamente
# o arquivo de configuração pyproject.toml do projeto.

import os
import toml
import click
from colorama import Fore, Style

from ..shared_tools import ExecutionLogger, _find_project_root

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
        click.echo(Fore.CYAN + "--- [CONFIG --FIX] Auditando o pyproject.toml ---")
        
        root_path = _find_project_root()
        config_path = os.path.join(root_path, 'pyproject.toml')

        # --- Utilitário 1: Carregar ou Criar Configuração ---
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    toml_data = toml.load(f)
            else:
                click.echo(Fore.YELLOW + "   > Arquivo 'pyproject.toml' não encontrado. Criando um novo.")
                toml_data = {}
        except toml.TomlDecodeError as e:
            logger.add_finding('CRITICAL', "O arquivo 'pyproject.toml' está corrompido.", details=str(e))
            click.echo(Fore.RED + f"   > [ERRO] O arquivo 'pyproject.toml' parece estar corrompido: {e}")
            return
            
        doxoade_config = toml_data.setdefault('tool', {}).setdefault('doxoade', {})
        doxoade_config.setdefault('ignore', [])
        current_source_dir = doxoade_config.setdefault('source_dir', '.')

        # --- Utilitário 2: Validar e Sugerir Correção ---
        search_path = os.path.join(root_path, current_source_dir)

        if os.path.isdir(search_path):
            logger.add_finding('INFO', "Configuração do 'source_dir' está válida.")
            click.echo(Fore.GREEN + f"   > [OK] 'source_dir' ('{current_source_dir}') é válido.")
        else:
            logger.add_finding('WARNING', f"O 'source_dir' configurado ('{current_source_dir}') é inválido.")
            click.echo(Fore.YELLOW + f"   > [AVISO] O 'source_dir' atual ('{current_source_dir}') aponta para um diretório inexistente.")
            
            # Tenta encontrar uma alternativa inteligente
            if current_source_dir != '.' and os.path.isdir(os.path.join(root_path, '.')):
                if click.confirm(Fore.CYAN + "     > Corrigir para '.' (diretório raiz do projeto)?"):
                    doxoade_config['source_dir'] = '.'
                    try:
                        with open(config_path, 'w', encoding='utf-8') as f:
                            toml.dump(toml_data, f)
                        logger.add_finding('INFO', "O 'source_dir' foi corrigido para '.'.")
                        click.echo(Fore.GREEN + "   > [OK] 'pyproject.toml' corrigido com sucesso.")
                    except IOError as e:
                        logger.add_finding('CRITICAL', "Falha ao escrever no 'pyproject.toml'.", details=str(e))
                        click.echo(Fore.RED + f"   > [ERRO] Não foi possível salvar o arquivo: {e}")