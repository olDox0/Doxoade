# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_engine.py
import os
import ast
from datetime import datetime
from ..intelligence_utils import SemanticAnalyzer, NexusThothMapper, ChiefInsightVisitor
CRITICAL_THRESHOLD = datetime(2026, 2, 14, 21, 0, 0)
def analyze_file_chief(file_path: str, project_root: str, docs=False, source=False) -> dict:
    """Motor de Scan Nexus v100.1 (PASC 1.3 Compliance)."""
    rel_path = os.path.relpath(file_path, project_root).replace('\\', '/')
    
    data = {
        "path": rel_path,
        "size": os.path.getsize(file_path),
        "god_assignment": "Unknown"
    }
    if not file_path.endswith('.py'):
        return data
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # 1. Análise Semântica
        sem = SemanticAnalyzer(content)
        data.update(sem.get_summary())
        
        # 2. Identificação de Divindade
        visitor = ChiefInsightVisitor()
        visitor.visit(sem.tree)
        all_imports = visitor.stats["imports"]["stdlib"] + visitor.stats["imports"]["external"]
        data["god_assignment"] = NexusThothMapper.identify(rel_path, all_imports)
        # 3. Arqueologia de 3 Camadas (Protocolo Osíris)
        backups = _get_safe_backups(file_path)
        if backups:
            data["archaeology_layers"] = _perform_triple_diff(content, backups)
        if source: data["source_minified"] = content[:5000] # Token Optimization
        
    except Exception as e:
        data["error"] = str(e)
    
    return data
def _get_safe_backups(file_path, count=3):
    """Localiza os backups mais recentes dentro da zona de segurança (Janela Ma'at)."""
    candidates = []
    # Busca .bak e nppBackup
    potentials = [file_path + ".bak"]
    npp_dir = os.path.join(os.path.dirname(file_path), 'nppBackup')
    if os.path.exists(npp_dir):
        base = os.path.basename(file_path)
        potentials.extend([os.path.join(npp_dir, f) for f in os.listdir(npp_dir) if f.startswith(base)])
    for p in potentials:
        if os.path.exists(p):
            mtime = datetime.fromtimestamp(os.path.getmtime(p))
            # Só aceita se for ANTES do incidente
            if mtime < CRITICAL_THRESHOLD:
                candidates.append((mtime, p))
    
    # Retorna os 'count' mais recentes da zona segura
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidates[:count]]
#    return [] # Implementação detalhada enviada no bloco anterior
def _perform_triple_diff(current_code, backup_list):
    """Compara o código atual com até 3 backups (Protocolo Osíris)."""
    diff_report = []
    try:
        curr_tree = ast.parse(current_code)
        curr_funcs = {n.name: ast.unparse(n) for n in ast.walk(curr_tree) if isinstance(n, ast.FunctionDef)}
        for i, b_path in enumerate(backup_list):
            layer = _analyze_layer(i + 1, b_path, curr_funcs)
            if layer:
                diff_report.append(layer)
    except Exception: pass
    return diff_report
def _analyze_layer(level, b_path, curr_funcs):
    """Analisa uma única camada de backup contra o código atual."""
    try:
        with open(b_path, 'r', encoding='utf-8', errors='ignore') as f:
            b_code = f.read()
        
        b_tree = ast.parse(b_code)
        b_funcs = {n.name: ast.unparse(n) for n in ast.walk(b_tree) if isinstance(n, ast.FunctionDef)}
        
        mtime = os.path.getmtime(b_path)
        report = {
            "layer": level,
            "date": datetime.fromtimestamp(mtime).isoformat(),
            "lost_logic": []
        }
        # Detecta o que foi removido (Logic Loss)
        for name, code in b_funcs.items():
            if name not in curr_funcs and not name.startswith('_'):
                report["lost_logic"].append({"function": name, "raw_code": code})
        
        return report if report["lost_logic"] else None
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        exc_obj, exc_tb = _dox_sys.exc_info() #exc_type
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: _analyze_layer\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
        return None