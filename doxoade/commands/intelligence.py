# -*- coding: utf-8 -*-
"""
Módulo de Inteligência de Topologia (Chief Insight) - v41.0.
Scanner profundo de arquitetura, dependências e saúde sistêmica.
"""

import os
import json
import ast
import re
import sys
from datetime import datetime, timezone
# [DOX-UNUSED] from pathlib import Path
from typing import List, Dict, Any

import click
from rich.console import Console

from ..shared_tools import ExecutionLogger
from ..tools.git import _run_git_command
from ..dnm import DNM

__version__ = "41.0 Alfa (Chief-Gold)"

class ChiefInsightVisitor(ast.NodeVisitor):
    """Analisador de Topologia e Coesão de Código."""
    
    def __init__(self):
        self.stats = {
            "classes": [], "functions": [], "imports": {"stdlib": [], "external": []},
            "complexities": [], "mpot_4_violations": 0
        }
        
    def visit_ClassDef(self, node: ast.ClassDef):
        methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        self.stats["classes"].append({"name": node.name, "methods_count": len(methods)})
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._analyze_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._analyze_func(node)
        self.generic_visit(node)

    def _analyze_func(self, node):
        line_count = (node.end_lineno - node.lineno) if node.end_lineno else 0
        if line_count > 60: self.stats["mpot_4_violations"] += 1
        
        complexity = self._calculate_complexity(node)
        self.stats["complexities"].append(complexity)
        self.stats["functions"].append({
            "name": node.name, "lines": line_count, "complexity": complexity, "args": len(node.args.args)
        })

    def _calculate_complexity(self, node: ast.AST) -> int:
        return 1 + sum(1 for child in ast.walk(node) if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)))

    def visit_Import(self, node: ast.Import):
        for alias in node.names: self._sort_import(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module: self._sort_import(node.module)

    def _sort_import(self, name: str):
        root_mod = name.split('.')[0]
        if root_mod in sys.builtin_module_names or root_mod in ["os", "sys", "pathlib", "re", "json", "ast", "subprocess", "datetime", "abc", "typing"]:
            self.stats["imports"]["stdlib"].append(name)
        else:
            self.stats["imports"]["external"].append(name)

def _get_git_hotness(file_path: str) -> int:
    """Retorna o número de modificações no arquivo nos últimos 30 dias."""
    try:
        res = _run_git_command(['rev-list', '--count', '--since="30 days ago"', 'HEAD', '--', file_path], capture_output=True, silent_fail=True)
        return int(res) if res and res.isdigit() else 0
    except Exception as e:
        import os as _dox_os
        exc_type, exc_obj, exc_tb = sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _get_git_hotness\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return 0

def _analyze_file_chief(file_path: str, root: str) -> Dict[str, Any]:
    rel_path = os.path.relpath(file_path, root).replace('\\', '/')
    ext = os.path.splitext(file_path)[1].lower()
    content = ""
    
    # Heurística de leitura rápida (MPoT-18)
    for enc in ['utf-8', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                content = f.read()
                break
        except Exception as e:
            import sys as _dox_sys, os as _dox_os
            exc_type, exc_obj, exc_tb = sys.exc_info()
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _analyze_file_chief\033[0m")
            print(f"\033[31m    ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            continue

    data = {
        "path": rel_path, "size": os.path.getsize(file_path), "loc": len(content.splitlines()),
        "hotness_score": _get_git_hotness(file_path)
    }

    if ext == '.py':
        try:
            tree = ast.parse(content)
            visitor = ChiefInsightVisitor()
            visitor.visit(tree)
            data.update({
                "type": "source", "classes": visitor.stats["classes"], "functions": visitor.stats["functions"],
                "external_deps": list(set(visitor.stats["imports"]["external"])),
                "mpot_violations": visitor.stats["mpot_4_violations"],
                "avg_complexity": round(sum(visitor.stats["complexities"])/len(visitor.stats["complexities"]), 2) if visitor.stats["complexities"] else 1,
                "todos": _find_debt_tags(content)
            })
        except Exception as e:
            import os as _dox_os
            exc_type, exc_obj, exc_tb = sys.exc_info()
            f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            line_n = exc_tb.tb_lineno
            print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {file_path} | L: {line_n} | Func: _analyze_file_chief\033[0m")
            print(f"\033[31m    ■ Type: {type(e).__name__} | Value: {e}\033[0m")
            data["type"] = "source_corrupt"
            
    elif ext in ['.md', '.txt', '.json']:
        data["type"] = "documentation"
        if ext == '.md': data["summary"] = re.findall(r'^#+\s+(.*)', content, re.MULTILINE)[:5]
            
    return data

def _find_debt_tags(content: str) -> List[Dict[str, Any]]:
    debt = []
    patterns = r'#\s*(TODO|FIXME|BUG|HACK|ADTI)\b[:\s]*(.*)'
    for i, line in enumerate(content.splitlines(), 1):
        m = re.search(patterns, line, re.IGNORECASE)
        if m: debt.append({"line": i, "tag": m.group(1).upper(), "msg": m.group(2).strip()})
    return debt

@click.command('intelligence')
@click.option('--output', '-o', default='chief_dossier.json')
@click.pass_context
def intelligence(ctx, output):
    """Gera um Dossiê de Inteligência Topológica (Chief Standard)."""
    root = "."
    console = Console()
    
    with ExecutionLogger('intelligence', root, ctx.params) as logger:
        console.print("[bold gold3]🧐 Doxoade Chief Insight v41.0[/bold gold3]")
        
        dnm = DNM(root)
        files = dnm.scan() 
        
        dossier_files = []
        with click.progressbar(files, label='Escaneando Topologia') as bar:
            for f in bar:
                res = _analyze_file_chief(f, root)
                if res: dossier_files.append(res)

        # Insights Agregados
        all_funcs = [func for f in dossier_files if "functions" in f for func in f["functions"]]
        
        report = {
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "project": os.path.basename(os.path.abspath(root)),
                "doxoade_version": __version__
            },
            "executive_summary": {
                "files_count": len(dossier_files),
                "total_loc": sum(f.get('loc', 0) for f in dossier_files),
                "mpot_violations": sum(f.get('mpot_violations', 0) for f in dossier_files if 'mpot_violations' in f),
                "avg_project_complexity": round(sum(f['avg_complexity'] for f in dossier_files if 'avg_complexity' in f) / len([f for f in dossier_files if 'avg_complexity' in f]), 2) if dossier_files else 0,
                "most_complex_function": max(all_funcs, key=lambda x: x['complexity']) if all_funcs else "None",
                "hottest_files": sorted(dossier_files, key=lambda x: x.get('hotness_score', 0), reverse=True)[:5]
            },
            "codebase": dossier_files
        }

        try:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            console.print(f"\n[bold green]✅ Dossiê Chief salvo em: {output}[/bold green]")
            console.print(f"   - [cyan]LOC:[/cyan] {report['executive_summary']['total_loc']} | [cyan]Violations:[/cyan] {report['executive_summary']['mpot_violations']}")
            console.print(f"   - [yellow]Média de Complexidade:[/yellow] {report['executive_summary']['avg_project_complexity']}")
        except Exception as e:
            console.print(f"[bold red]❌ Erro:[/bold red] {e}")
            sys.exit(1)