# doxoade/commands/guicheck.py
import os
import ast
import click
#from colorama import Fore

# Importações de shared_tools corrigidas para usar as funções modernas
from ..shared_tools import (
    ExecutionLogger,
    _present_results,
    _get_project_config,  # <-- USA A FUNÇÃO CORRETA
    _get_code_snippet
)

@click.command('guicheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, dir_okay=True), default='.')
@click.option('--ignore', multiple=True, help="Ignora pastas específicas.")
def guicheck(ctx, path, ignore):
    """Analisa arquivos de GUI (Kivy e Tkinter) em busca de riscos comuns."""
    arguments = ctx.params
    with ExecutionLogger('guicheck', path, arguments) as logger:

        # Lógica moderna para obter a configuração e o caminho de busca
        config = _get_project_config(logger, start_path=path if os.path.isdir(path) else os.path.dirname(path))
        if not config.get('search_path_valid'):
            _present_results('text', logger.results)
            return

        files_to_check = _find_py_files_to_check(config, list(ignore))

        if not files_to_check:
            logger.add_finding('INFO', "Nenhum arquivo Python encontrado para análise de GUI.")
        else:
            _check_gui_files(files_to_check, logger)

        _present_results('text', logger.results)

def _check_gui_files(files, logger):
    """Itera e analisa uma lista de arquivos Python."""
    for file_path in files:
        _analyze_single_gui_file(file_path, logger)

def _find_py_files_to_check(config, cmd_line_ignore):
    """Encontra todos os arquivos .py no caminho de busca, respeitando as exclusões."""
    files_to_check = []
    search_path = config.get('search_path')
    folders_to_ignore = set(config.get('ignore', []) + list(cmd_line_ignore))
    
    for root, dirs, files in os.walk(search_path, topdown=True):
        dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
        for file in files:
            if file.endswith('.py'):
                files_to_check.append(os.path.join(root, file))
    return files_to_check

def _analyze_single_gui_file(file_path, logger):
    """Analisa um único arquivo Python em busca de padrões Kivy e Tkinter."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content, filename=file_path)
            
            # Executa ambas as análises
            _analyze_kivy_risks(tree, file_path, logger)
            _analyze_tkinter_layout(tree, file_path, logger)

    except (SyntaxError, IOError) as e:
        logger.add_finding('ERROR', f"Não foi possível ler ou analisar o arquivo: {e}", file=file_path)

def _analyze_kivy_risks(tree, file_path, logger):
    """Analisa o AST em busca de riscos comuns do Kivy."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # Exemplo: Encontrar uso de eval() em Kivy, que é um risco de segurança
            if node.func.attr == 'eval':
                logger.add_finding(
                    'WARNING',
                    "Uso de 'eval' detectado.",
                    file=file_path,
                    line=node.lineno,
                    details="O uso de eval() pode ser um risco de segurança se a entrada não for controlada.",
                    snippet=_get_code_snippet(file_path, node.lineno)
                )

def _analyze_tkinter_layout(tree, file_path, logger):
    """Analisa o uso misto de .pack() e .grid() no mesmo container Tkinter."""
    # Mapeia variáveis a seus containers (frames, root, etc.)
    widget_parents = _build_widget_parent_map(tree)
    
    # Coleta os gerenciadores de layout usados por cada container
    layout_by_parent = _collect_layout_data(tree, widget_parents)

    # Analisa se há mistura de gerenciadores
    _perform_layout_analysis(layout_by_parent, file_path, logger)

def _build_widget_parent_map(tree):
    """Cria um mapa de {nome_widget: nome_pai}."""
    parents = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute) and hasattr(node.value.func, 'value'):
                widget_name = node.targets[0].id
                parent_name = node.value.args[0].id if node.value.args and isinstance(node.value.args[0], ast.Name) else 'unknown'
                parents[widget_name] = parent_name
    return parents

def _collect_layout_data(tree, widget_parents):
    """Coleta qual gerenciador de layout (.pack ou .grid) é usado por cada container."""
    layout_by_parent = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ['pack', 'grid']:
                widget_name = node.func.value.id if hasattr(node.func.value, 'id') else 'unknown'
                parent = widget_parents.get(widget_name, 'unknown')
                
                if parent not in layout_by_parent:
                    layout_by_parent[parent] = {'methods': set(), 'lines': []}
                
                layout_by_parent[parent]['methods'].add(node.func.attr)
                layout_by_parent[parent]['lines'].append(node.lineno)
    return layout_by_parent

def _perform_layout_analysis(layout_by_parent, file_path, logger):
    """Verifica se algum container usa mais de um gerenciador de layout."""
    for parent, data in layout_by_parent.items():
        if len(data['methods']) > 1:
            line = min(data['lines'])
            logger.add_finding(
                'ERROR',
                f"Uso misto de .pack() e .grid() no mesmo container '{parent}'.",
                file=file_path,
                line=line,
                details="Tkinter não permite usar .pack() e .grid() no mesmo widget pai.",
                snippet=_get_code_snippet(file_path, line)
            )