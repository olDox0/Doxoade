# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_engine.py
import os
import ast
from datetime import datetime
try:
    from ..intelligence_utils import SemanticAnalyzer, CSemanticAnalyzer, HTMLSemanticAnalyzer, NexusThothMapper, ChiefInsightVisitor, find_debt_tags
    from .intelligence_css import CSSSemanticAnalyzer
    from .intelligence_js import JSSemanticAnalyzer  # <-- NOVO
except ImportError:
    from doxoade.commands.intelligence_utils import SemanticAnalyzer, CSemanticAnalyzer, HTMLSemanticAnalyzer, NexusThothMapper, ChiefInsightVisitor, find_debt_tags
    from doxoade.commands.intelligence_systems.intelligence_css import CSSSemanticAnalyzer
    from doxoade.commands.intelligence_systems.intelligence_js import JSSemanticAnalyzer  # <-- NOVO

CRITICAL_THRESHOLD = datetime(2026, 2, 14, 21, 0, 0)

def analyze_file_chief(file_path: str, project_root: str, docs=False, source=False) -> dict:
    """Motor de Scan Nexus v100.1 (PASC 1.3 Compliance c/ C/C++, HTML, CSS, JS/TS)."""
    rel_path = os.path.relpath(file_path, project_root).replace('\\', '/')
    
    data = {
        "path": rel_path,
        "size": os.path.getsize(file_path),
        "god_assignment": "Unknown"
    }
    
    # ADICIONADO: '.js', '.jsx', '.ts', '.tsx' na lista
    valid_exts = ('.py', '.c', '.cpp', '.h', '.hpp', '.html', '.css', '.js', '.jsx', '.ts', '.tsx')
    if not file_path.endswith(valid_exts):
        return data
        
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        is_python = file_path.endswith('.py')
        is_html = file_path.endswith('.html')
        is_css = file_path.endswith('.css')
        is_js = file_path.endswith(('.js', '.jsx', '.ts', '.tsx')) # Engloba ecossistema JS
        
        if is_python:
            sem = SemanticAnalyzer(content)
            data.update(sem.get_summary())

            visitor = ChiefInsightVisitor()
            if sem.tree:
                visitor.visit(sem.tree)
            all_imports = visitor.stats["imports"]["stdlib"] + visitor.stats["imports"]["external"]
            data["god_assignment"] = NexusThothMapper.identify(rel_path, all_imports)

            data["mpot_4_violations"] = visitor.stats["mpot_4_violations"]
            data["debt_tags"]         = find_debt_tags(content)

            backups = _get_safe_backups(file_path)
            if backups:
                data["archaeology_layers"] = _perform_triple_diff(content, backups)

        elif is_html:
            sem_html = HTMLSemanticAnalyzer(content)
            data.update(sem_html.get_summary())
            data["god_assignment"] = NexusThothMapper.identify(rel_path, [])
            data["mpot_4_violations"] = 0 
            data["debt_tags"]         = find_debt_tags(content)

        elif is_css:
            sem_css = CSSSemanticAnalyzer(content)
            data.update(sem_css.get_summary())
            data["god_assignment"] = NexusThothMapper.identify(rel_path, [])
            data["mpot_4_violations"] = 0 
            data["debt_tags"]         = find_debt_tags(content) 

        elif is_js:
            # NOVO: FLUXO JS/TS
            sem_js = JSSemanticAnalyzer(content)
            data.update(sem_js.get_summary())
            # Envia as dependências mapeadas para tentar inferir Deus Regente (ex: front vs back)
            data["god_assignment"] = NexusThothMapper.identify(rel_path, sem_js.imports)
            data["mpot_4_violations"] = 0 
            data["debt_tags"]         = find_debt_tags(content) # Suporta // TODO e /* TODO */ nativamente

        else:
            sem_c = CSemanticAnalyzer(content)
            data.update(sem_c.get_summary())
            data["god_assignment"]    = NexusThothMapper.identify(rel_path, sem_c.includes)
            data["mpot_4_violations"] = 0
            data["debt_tags"]         = find_debt_tags(content)
            
        if source: 
            data["source_minified"] = content[:5000]
        
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
    diff_report =[]
    try:
        curr_tree = ast.parse(current_code)
        curr_funcs = {n.name: ast.unparse(n) for n in ast.walk(curr_tree) if isinstance(n, ast.FunctionDef)}
        for i, b_path in enumerate(backup_list):
            layer = _analyze_layer(i + 1, b_path, curr_funcs)
            if layer:
                diff_report.append(layer)
    except (SyntaxError, IndentationError):
        pass # Ignora silenciosamente arquivos mal formados
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="intelligence_engine._perform_triple_diff", silent=True)
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
            "lost_logic":[]
        }
        # Detecta o que foi removido (Logic Loss)
        for name, code in b_funcs.items():
            if name not in curr_funcs and not name.startswith('_'):
                report["lost_logic"].append({"function": name, "raw_code": code})
        
        return report if report["lost_logic"] else None
        
    except (SyntaxError, IndentationError):
        # Normal para backups parciais do Notepad++ (código quebrado durante digitação)
        return None
    except Exception as e:
        from doxoade.tools.error_info import handle_error
        handle_error(e, context="intelligence_engine._analyze_layer", silent=True)
        return None