# -*- coding: utf-8 -*-
"""
Support_Utils para Intelligence (PASC 1.2 / MPoT 17).
Foco: Extração de Metadados de Documentação e Análise de Fluxo de IO.
"""

import os
import ast
import re
import sys
import json
from typing import List, Dict, Any

# Padrões de IO para busca via AST
IO_KEYWORDS = {'open', 'read', 'write', 'load', 'dump', 'print', 'input', 'get', 'post', 'request'}
IO_MODULES = {'os', 'sys', 'pathlib', 'shutil', 'subprocess', 'socket', 'requests', 'json', 'toml'}

def get_ignore_spec(root: str):
    import toml
    import pathspec
    config_path = os.path.join(root, "pyproject.toml")
    if not os.path.exists(config_path): return None
    try:
        config = toml.load(config_path)
        patterns = config.get("tool", {}).get("doxoade", {}).get("ignore", [])
        return pathspec.PathSpec.from_lines('gitwildmatch', patterns) if patterns else None
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)

        _print_forensic("get_ignore_spec", e)
    return None

class ChiefInsightVisitor(ast.NodeVisitor):
    def __init__(self):
        self.stats = {
            "classes": [], "functions": [], 
            "imports": {"stdlib": [], "external": []},
            "complexities": [], "mpot_4_violations": 0
        }
        
    def _detect_io_calls(self, node: ast.AST) -> List[str]:
        """Rastreia chamadas de IO dentro da função (PASC 8.2)."""
        io_found = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Detecta chamadas diretas (ex: print())
                if isinstance(child.func, ast.Name) and child.func.id in IO_KEYWORDS:
                    io_found.add(child.func.id)
                # Detecta chamadas de módulo (ex: os.path.join())
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name) and child.func.value.id in IO_MODULES:
                        io_found.add(f"{child.func.value.id}.{child.func.attr}")
        return list(io_found)

    def _analyze_func(self, node):
        line_count = (node.end_lineno - node.lineno) if node.end_lineno else 0
        if line_count > 60: self.stats["mpot_4_violations"] += 1
        
        complexity = 1 + sum(1 for child in ast.walk(node) if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With)))
        self.stats["complexities"].append(complexity)
        
        self.stats["functions"].append({
            "name": node.name, 
            "lines": line_count, 
            "complexity": complexity, 
            "args": len(node.args.args),
            "io_flow": self._detect_io_calls(node) # Novo: Rastreio de Fluxo
        })

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._analyze_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._analyze_func(node)
        self.generic_visit(node)

def analyze_document(file_path: str, ext: str) -> Dict[str, Any]:
    """Extrai dados ricos de documentação (PASC 3.2 / 8.3)."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if ext == '.json':
                data = json.loads(content)
                # Retorna chaves principais para não sobrecarregar se for gigante
                return {"doc_type": "structured_data", "keys": list(data.keys())[:20], "raw": data if len(content) < 5000 else "truncated"}
            elif ext == '.md':
                headers = re.findall(r'^#+\s+(.*)', content, re.MULTILINE)
                return {"doc_type": "markdown", "headers": headers[:10], "brief": content[:500]}
    except Exception as e:
        from traceback import print_tb as exc_trace
        _, exc_obj, exc_tb = sys.exc_info()
        print(f"\033[31m ■ Exception type: {e} . . .  ■ Exception value: {'\n  >>>   '.join(str(exc_obj).split('\''))}\n")
        exc_trace(exc_tb)
        return {"error": str(e)}
    return {}

def find_debt_tags(content: str) -> List[Dict[str, Any]]:
    debt = []
    patterns = r'#\s*(TODO|FIXME|BUG|HACK|ADTI)\b[:\s]*(.*)'
    for i, line in enumerate(content.splitlines(), 1):
        m = re.search(patterns, line, re.IGNORECASE)
        if m: debt.append({"line": i, "tag": m.group(1).upper(), "msg": m.group(2).strip()})
    return debt

def _print_forensic(func_name: str, e: Exception):
    import os as _dox_os
    _, _, exc_tb = sys.exc_info()
    f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1] if exc_tb else "unknown"
    line_n = exc_tb.tb_lineno if exc_tb else 0
    print(f"\033[1;34m\n[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: {func_name}\033[0m")
    print(f"\033[31m    ■ Type: {type(e).__name__} | Value: {e}\033[0m")