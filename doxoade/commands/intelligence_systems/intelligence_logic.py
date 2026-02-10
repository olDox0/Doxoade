# -*- coding: utf-8 -*-
"""
Motor de Inteligência Topológica - v41.5.
Responsável por análise profunda e resiliência de caminho (PASC 8.4).
"""
import os
# [DOX-UNUSED] import sys
import ast
from typing import Dict, Any
from ...tools.git import _run_git_command
from ..intelligence_utils import ChiefInsightVisitor, find_debt_tags, analyze_document

def analyze_file_chief(file_path: str, project_root: str) -> Dict[str, Any]:
    """Analisa um arquivo individual com resiliência industrial."""
    # Garante caminhos canônicos para o relatório
    rel_path = os.path.relpath(file_path, project_root).replace('\\', '/')
    ext = os.path.splitext(file_path)[1].lower()
    
    data = {
        "path": rel_path, 
        "size": os.path.getsize(file_path),
        "hotness_score": _get_git_hotness_safe(file_path, project_root)
    }

    # Se for documentação rica
    if ext in ['.json', '.md'] or 'docs/' in rel_path.lower():
        data["type"] = "documentation"
        data["doc_content"] = analyze_document(file_path, ext)
        return data

    # Se for código fonte Python
    if ext == '.py':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content)
            visitor = ChiefInsightVisitor()
            visitor.visit(tree)
            
            data.update({
                "type": "source",
                "loc": len(content.splitlines()),
                "mpot_violations": visitor.stats["mpot_4_violations"],
                "avg_complexity": round(sum(visitor.stats["complexities"])/len(visitor.stats["complexities"]), 2) if visitor.stats["complexities"] else 1,
                "functions": visitor.stats["functions"],
                "todos": find_debt_tags(content)
            })
        except Exception:
            data["type"] = "source_corrupt"
            
    return data

def _get_git_hotness_safe(file_path: str, root: str) -> int:
    """Verifica se é um repo Git antes de medir o hotness (Fail-Safe)."""
    if not os.path.exists(os.path.join(root, ".git")):
        return 0
    try:
        # PASC-6.4: Comando otimizado para contar commits nos últimos 30 dias
        res = _run_git_command(['rev-list', '--count', '--since="30 days ago"', 'HEAD', '--', file_path], 
                              capture_output=True, silent_fail=True)
        return int(res) if res and res.isdigit() else 0
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _get_git_hotness_safe\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return 0