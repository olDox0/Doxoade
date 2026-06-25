import ast
import os
import click
from pathlib import Path
from doxoade.tools.doxcolors import Fore, Style

def trace_db_usage(project_root: str):
    root = Path(project_root).resolve()
    # Padrões que indicam acesso a banco
    db_triggers = {'get_db_connection', 'connect', 'execute', 'commit'}
    db_modules = {'sqlite3', 'nexus_db', 'doxoade.database'}
    
    click.echo(f"{Fore.CYAN}--- [HADES TRACER] Mapeando acesso a dados em: {root} ---{Style.RESET_ALL}")

    for py_file in root.rglob('*.py'):
        if 'venv' in py_file.parts or '.git' in py_file.parts or 'data' in py_file.parts:
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                # Rastrear imports de sqlite/database
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for name in node.names:
                        if any(mod in name.name for mod in db_modules):
                            _report_match(py_file, node.lineno, "Import", f"import {name.name}")

                # Rastrear chamadas (execute, commit, etc)
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name): func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute): func_name = node.func.attr
                    
                    if func_name in db_triggers:
                        # Extrair snippet da linha
                        line_content = _get_line_content(py_file, node.lineno)
                        _report_match(py_file, node.lineno, "Chamada", line_content)
        except Exception:
            continue

def _get_line_content(filepath, lineno):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        return lines[lineno-1].strip()

def _report_match(file, line, kind, content):
    click.echo(f"{Fore.YELLOW}● {Style.DIM}{file.name:<20}{Style.RESET_ALL} {Fore.WHITE}Linha {line:<4} | {kind:<8} | {Fore.MAGENTA}{content}{Style.RESET_ALL}")

if __name__ == "__main__":
    trace_db_usage(".")