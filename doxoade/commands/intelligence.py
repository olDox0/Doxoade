# doxoade/commands/intelligence.py
import os
import json
import ast
import re
from datetime import datetime, timezone
import chardet
import click
from colorama import Fore

from ..shared_tools import ExecutionLogger, _get_project_config
from ..tools.git import _run_git_command
from ..dnm import DNM

__version__ = "38.0 Alfa (Deep Insight)"

class InsightVisitor(ast.NodeVisitor):
    """Extrai inteligência profunda da AST."""
    def __init__(self):
        self.classes = []
        self.functions = []
        self.imports = []
        self.todos = []
        
    def visit_ClassDef(self, node):
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        self.classes.append({
            "name": node.name,
            "lineno": node.lineno,
            "docstring": ast.get_docstring(node) or "",
            "methods": methods,
            "bases": [ast.unparse(b) for b in node.bases]
        })
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Ignora métodos dentro de classes (já pegos no visit_ClassDef de forma rasa)
        # ou pega tudo? Vamos pegar tudo para ter stats completos.
        args = [a.arg for a in node.args.args]
        decorators = [ast.unparse(d) for d in node.decorator_list]
        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "docstring": ast.get_docstring(node) or "",
            "args": args,
            "decorators": decorators,
            "complexity": self._estimate_complexity(node)
        })
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")
        self.generic_visit(node)

    def _estimate_complexity(self, node):
        """Estimativa rápida de complexidade ciclomática."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)):
                complexity += 1
        return complexity

def _extract_todos(content):
    """Extrai comentários de dívida técnica."""
    todos = []
    for i, line in enumerate(content.splitlines(), 1):
        if "#" in line:
            comment = line.split("#", 1)[1].strip()
            # Regex para pegar TODO, FIXME, HACK, etc
            match = re.match(r'\b(TODO|FIXME|HACK|XXX|BUG)\b[:\s]*(.*)', comment, re.IGNORECASE)
            if match:
                tag, text = match.groups()
                todos.append({
                    "tag": tag.upper(),
                    "line": i,
                    "text": text.strip()
                })
    return todos

def _analyze_python_deep(file_path, content):
    """Realiza a análise profunda do código Python."""
    try:
        tree = ast.parse(content, filename=file_path)
        visitor = InsightVisitor()
        visitor.visit(tree)
        
        return {
            "classes": visitor.classes,
            "functions": visitor.functions,
            "imports": sorted(list(set(visitor.imports))),
            "todos": _extract_todos(content),
            "loc": len(content.splitlines())
        }
    except Exception as e:
        return {"error": f"AST Parse Error: {str(e)}"}

def _get_git_info(file_path):
    """Obtém informações do último commit deste arquivo."""
    try:
        # Formato: Hash|Autor|Data|Mensagem
        fmt = "%h|%an|%ai|%s"
        # Precisamos do caminho relativo à raiz do git
        cmd = ['log', '-n', '1', f'--format={fmt}', '--', file_path]
        output = _run_git_command(cmd, capture_output=True, silent_fail=True)
        if output:
            parts = output.strip().split('|')
            if len(parts) >= 4:
                return {
                    "last_commit_hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                }
    except Exception: pass
    return None

def _analyze_file_metadata(file_path_str, root_path, logger):
    """Coleta metadados ricos para um único arquivo."""
    try:
        stats = os.stat(file_path_str)
        rel_path = os.path.relpath(file_path_str, root_path).replace('\\', '/')
        
        # Leitura segura
        content = ""
        encoding = "utf-8"
        try:
            with open(file_path_str, 'rb') as f:
                raw = f.read()
                result = chardet.detect(raw)
                encoding = result.get('encoding', 'utf-8')
                content = raw.decode(encoding or 'utf-8', errors='replace')
        except Exception:
            return None # Pula arquivos binários ou ilegíveis

        file_info = {
            "path": rel_path,
            "size_bytes": stats.st_size,
            "modified_at_utc": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc).isoformat(),
            "language": "python" if file_path_str.endswith(".py") else "text",
            "git_status": _get_git_info(file_path_str)
        }

        if file_path_str.endswith('.py'):
            # Injeta a inteligência profunda
            deep_data = _analyze_python_deep(file_path_str, content)
            file_info.update(deep_data)
        else:
            # Para outros arquivos, apenas conta linhas
            file_info["loc"] = len(content.splitlines())

        return file_info
    except Exception as e:
        logger.add_finding('warning', f"Erro ao analisar: {file_path_str}", details=str(e))
        return None

@click.command('intelligence')
@click.pass_context
@click.option('--output', '-o', default='doxoade_report.json', help="Nome do arquivo de saída.")
def intelligence(ctx, output):
    """Gera um dossiê de Inteligência Profunda (Deep Insight) do projeto."""
    path = '.'
    arguments = ctx.params
    
    with ExecutionLogger('intelligence', path, arguments) as logger:
        click.echo(Fore.CYAN + "--- [INTELLIGENCE] Gerando Dossiê de Conhecimento ---")
        
        # Usa o DNM para navegação robusta (respeita .gitignore)
        dnm = DNM(path)
        files = dnm.scan() # Pega tudo, não só .py, mas respeita ignores
        
        click.echo(Fore.WHITE + f"   > Analisando {len(files)} arquivos (Estrutura, Semântica, Git)...")
        
        analyzed_files = []
        with click.progressbar(files, label='Processando') as bar:
            for file_path in bar:
                data = _analyze_file_metadata(file_path, path, logger)
                if data:
                    analyzed_files.append(data)

        # Sumário Executivo
        total_loc = sum(f.get('loc', 0) for f in analyzed_files)
        total_todos = sum(len(f.get('todos', [])) for f in analyzed_files if 'todos' in f)
        
        report_data = {
            "header": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "doxoade_version": __version__,
                "project_root": os.path.abspath(path),
                "metrics": {
                    "total_files": len(analyzed_files),
                    "total_loc": total_loc,
                    "technical_debt_items": total_todos
                }
            },
            "codebase": analyzed_files
        }
        
        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2)
            click.echo(Fore.GREEN + f"\n[OK] Dossiê salvo em: {output}")
            click.echo(f"   - LOC Total: {total_loc}")
            click.echo(f"   - Dívida Técnica: {total_todos} itens")
        except IOError as e:
            click.echo(Fore.RED + f"\n[ERRO] Falha ao salvar relatório: {e}")
            sys.exit(1)