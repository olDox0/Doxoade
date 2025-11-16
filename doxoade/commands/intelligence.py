# doxoade/commands/intelligence.py
import os
#import sys
import json
import ast

from datetime import datetime, timezone
import chardet

import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _get_project_config
#from ..shared_tools import ExecutionLogger, _load_config

__version__ = "37.2 Alfa (Hardening)"

def _generate_tree_representation(path, ignore_patterns):
    """Gera uma representação textual da árvore de diretórios."""
    tree_lines = []
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in sorted(dirs) if d not in ignore_patterns]
        files = [f for f in sorted(files)]
        
        level = root.replace(path, '').count(os.sep)
        indent = ' ' * 4 * (level)
        tree_lines.append(f"{indent}{os.path.basename(root)}/")
        
        sub_indent = ' ' * 4 * (level + 1)
        for f in files:
            tree_lines.append(f"{sub_indent}{f}")
    return "\n".join(tree_lines)

def _get_file_encoding(file_path):
    """Detecta a codificação de um arquivo com alta confiança."""
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(1024)
            if not raw_data: return 'empty'
            result = chardet.detect(raw_data)
            # CORREÇÃO: Usamos .get() para um acesso seguro.
            return result.get('encoding', 'unknown')
    except (IOError, OSError):
        return 'unreadable'

def _extract_python_functions(file_path, logger):
    """Usa AST para extrair nomes de funções de um arquivo Python."""
    functions = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({"name": node.name, "line": node.lineno})
    except (SyntaxError, ValueError) as e:
        # CORREÇÃO: Assinatura corrigida (severity, message)
        logger.add_finding('warning', f"Não foi possível analisar AST de: {file_path}", details=str(e))
    return functions

def _analyze_file_metadata(file_path_str, root_path, logger):
    """Coleta todos os metadados para um único arquivo."""
    try:
        stats = os.stat(file_path_str)
        file_info = {
            "path": os.path.relpath(file_path_str, root_path).replace('\\', '/'),
            "size_bytes": stats.st_size,
            "created_at_utc": datetime.fromtimestamp(stats.st_ctime, tz=timezone.utc).isoformat(),
            "modified_at_utc": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
            "encoding": _get_file_encoding(file_path_str)
        }
        if file_path_str.endswith('.py'):
            # CORREÇÃO: Usamos .get() para uma atribuição segura.
            file_info["functions"] = _extract_python_functions(file_path_str, logger)
        return file_info
    except (FileNotFoundError, OSError) as e:
        logger.add_finding('warning', f"Não foi possível analisar o arquivo: {file_path_str}", details=str(e))
        return None

def _gather_filesystem_data(path, logger, ignore_patterns):
    """Versão refatorada que delega a análise de arquivo."""
    click.echo(Fore.WHITE + "Coletando telemetria do sistema de arquivos...")
    file_list = []
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in sorted(dirs) if d not in ignore_patterns]
        for file in sorted(files):
            file_path_str = os.path.join(root, file)
            metadata = _analyze_file_metadata(file_path_str, path, logger)
            if metadata:
                file_list.append(metadata)
    return file_list

@click.command('intelligence')
@click.pass_context
@click.option('--output', '-o', default='doxoade_report.json', help="Nome do arquivo de saída do relatório.")
def intelligence(ctx, output):
    """Gera um dossiê de diagnóstico completo do projeto em formato JSON."""
    path = '.'
    arguments = ctx.params
    with ExecutionLogger('intelligence', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [INTELLIGENCE] Gerando dossiê de diagnóstico ---")

        config = _get_project_config(logger)
        
        # CORREÇÃO LÓGICA: Limpar barras finais dos padrões de ignore
        raw_ignore = config.get('ignore', [])
        clean_ignore = {item.strip('/\\') for item in raw_ignore}
        
        # Adicionar padrões padrão
        ignore_patterns = clean_ignore.union({'venv', '.git', '__pycache__', '.pytest_cache', 'doxoade.egg-info'})

        report_data = {
            "report_generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "doxoade_version": __version__,
            "project_path": os.path.abspath(path),
            "telemetry": {
                "directory_tree": _generate_tree_representation(path, ignore_patterns),
                "filesystem": _gather_filesystem_data(path, logger, ignore_patterns)
            }
        }
        
        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=4)
            click.echo(Fore.GREEN + f"\n[OK] Dossiê de diagnóstico salvo em: {output}")
            # CORREÇÃO: Assinatura corrigida
            logger.add_finding('info', f"Relatório de inteligência gerado com sucesso em '{output}'.")
        except IOError as e:
            click.echo(Fore.RED + f"\n[ERRO] Falha ao salvar o relatório: {e}")
            # CORREÇÃO: Assinatura corrigida
            logger.add_finding('error', "Falha ao escrever o arquivo de relatório.", details=str(e))
            import sys
            sys.exit(1)