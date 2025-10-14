# doxoade/commands/guicheck.py
import ast
import os
import sys

import click
from colorama import Fore

# Importa as ferramentas necessárias do módulo compartilhado
from ..shared_tools import (
    ExecutionLogger,
    _load_config,
    _present_results,
    _get_code_snippet
)

__version__ = "34.0 Alfa"

# =============================================================================
# --- COMANDO GUICHECK (AGORA EM SEU PRÓPRIO MÓDULO) ---
# =============================================================================

@click.command('guicheck')
@click.pass_context
@click.argument('path', type=click.Path(exists=True, file_okay=True), required=False, default='.')
@click.option('--ignore', multiple=True, help="Ignora uma pasta. Combina com as do .doxoaderc.")
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help="Define o formato da saída.")
def guicheck(ctx, path, ignore, format):
    """Analisa arquivos .py em busca de problemas de GUI (Tkinter e Kivy)."""
    arguments = ctx.params

    with ExecutionLogger('guicheck', path, arguments) as logger:
        if format == 'text':
            click.echo(Fore.YELLOW + f"[GUI] Executando análise de GUI em '{os.path.abspath(path)}'...")
        config = _load_config()
        final_ignore_list = list(set(config.get('ignore', []) + list(ignore)))

        gui_findings = _check_gui_files(path, final_ignore_list)
        for f in gui_findings:
            logger.add_finding(f['type'], f['message'], details=f.get('details'), file=f.get('file'), line=f.get('line'), ref=f.get('ref'), snippet=f.get('snippet'))

        _present_results(format, logger.results)

        if logger.results['summary']['errors'] > 0:
            sys.exit(1)

def _check_gui_files(path, ignore_list=None):
    """Orquestra a busca e a análise de arquivos de GUI."""
    files_to_check = _find_py_files_to_check(path, ignore_list)

    all_findings = []
    for file_path in files_to_check:
        try:
            all_findings.extend(_analyze_single_gui_file(file_path))
        except SyntaxError as e:
            all_findings.append({
                'type': 'error', 'message': f"Erro de sintaxe impede a análise: {e.msg}",
                'file': file_path, 'line': e.lineno
            })
        except IOError:
            continue
    return all_findings

def _find_py_files_to_check(path, ignore_list):
    """Encontra todos os arquivos .py a serem analisados, respeitando a lista de ignorados."""
    folders_to_ignore = set([item.lower().strip('/') for item in ignore_list or []] + ['venv', 'build', 'dist', '.git'])
    files_to_check = []

    if os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in folders_to_ignore]
            for file in files:
                if file.endswith('.py'):
                    files_to_check.append(os.path.join(root, file))
    elif path.endswith('.py'):
        files_to_check.append(path)
    return files_to_check

def _analyze_single_gui_file(file_path):
    """Analisa um único arquivo, detectando o framework e chamando o especialista correto."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    framework = None
    if "import tkinter" in content or "from tkinter" in content:
        framework = "tkinter"
    elif "import kivy" in content or "from kivy" in content:
        framework = "kivy"

    if framework:
        tree = ast.parse(content, filename=file_path)
        if framework == "tkinter":
            return _analyze_tkinter_layout(tree, file_path)
        elif framework == "kivy":
            return _analyze_kivy_risks(tree, file_path)

    return []

def _analyze_kivy_risks(tree, file_path):
    """(Especialista Kivy) Analisa uma AST em busca de riscos comuns de Kivy."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        is_button_call = False
        func_node = node.func
        if isinstance(func_node, ast.Name) and func_node.id == 'Button':
            is_button_call = True
        elif isinstance(func_node, ast.Attribute) and func_node.attr == 'Button':
            is_button_call = True

        if is_button_call:
            defined_events = {kw.arg for kw in node.keywords if kw.arg.startswith('on_')}
            if not ('on_press' in defined_events or 'on_release' in defined_events):
                findings.append({
                    'type': 'warning',
                    'message': "Widget de Botão Kivy não parece ter um evento de ação ('on_press' ou 'on_release').",
                    'details': "Um botão sem ação pode indicar uma funcionalidade incompleta.",
                    'file': file_path,
                    'line': node.lineno,
                    'snippet': _get_code_snippet(file_path, node.lineno)
                })
    return findings

def _analyze_tkinter_layout(tree, file_path):
    """(Gerente Tkinter) Orquestra as três fases da análise de layout."""
    widget_parent_map = _build_widget_parent_map(tree)
    parent_layouts, grid_configs = _collect_layout_data(tree, widget_parent_map)
    findings = _perform_layout_analysis(parent_layouts, grid_configs, file_path)
    return findings

def _build_widget_parent_map(tree):
    """(Passagem 1) Mapeia a hierarquia dos widgets."""
    widget_parent_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and node.value.args:
            parent_node = node.value.args[0]
            parent_name = ast.unparse(parent_node)
            if hasattr(node.targets[0], 'id') or hasattr(node.targets[0], 'attr'):
                widget_name = ast.unparse(node.targets[0])
                widget_parent_map[widget_name] = parent_name
    return widget_parent_map

def _collect_layout_data(tree, widget_parent_map):
    """(Passagem 2) Coleta dados de layout e configuração de grid."""
    parent_layouts = {}
    grid_configs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            widget_name = ast.unparse(node.func.value)
            parent_name = widget_parent_map.get(widget_name)
            if not parent_name:
                continue

            if node.func.attr in ['pack', 'grid']:
                parent_layouts.setdefault(parent_name, {}).setdefault(node.func.attr, []).append(node.lineno)

            if node.func.attr in ['rowconfigure', 'columnconfigure']:
                has_weight = any(kw.arg == 'weight' and isinstance(kw.value, ast.Constant) and kw.value.value > 0 for kw in node.keywords)
                if has_weight and node.args and isinstance(node.args[0], ast.Constant):
                    config_type = 'rows_weighted' if node.func.attr == 'rowconfigure' else 'cols_weighted'
                    grid_configs.setdefault(parent_name, {'rows_weighted': set(), 'cols_weighted': set()})[config_type].add(node.args[0].value)
    return parent_layouts, grid_configs

def _perform_layout_analysis(parent_layouts, grid_configs, file_path):
    """(Análise Final) Encontra os problemas com base nos dados coletados."""
    findings = []
    for parent, layouts in parent_layouts.items():
        if len(layouts) > 1:
            all_lines = [line for manager_lines in layouts.values() for line in manager_lines]
            line_report = min(all_lines) if all_lines else None
            findings.append({
                'type': 'error',
                'message': f"Uso misto de gerenciadores ({', '.join(layouts.keys())}) no pai '{parent}'.",
                'file': file_path,
                'line': line_report,
                'snippet': _get_code_snippet(file_path, line_report)
            })

        if 'grid' in layouts and (parent not in grid_configs or not (grid_configs[parent]['rows_weighted'] or grid_configs[parent]['cols_weighted'])):
            line_report = min(layouts['grid']) if layouts['grid'] else None
            findings.append({
                'type': 'warning',
                'message': f"Pai '{parent}' usa .grid() mas não configura 'weight'.",
                'details': "Layout não será responsivo.",
                'file': file_path,
                'line': line_report,
                'snippet': _get_code_snippet(file_path, line_report)
            })
    return findings