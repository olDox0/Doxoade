# -*- coding: utf-8 -*-
import os
import shutil
import hashlib
import click
from pathlib import Path
from doxoade.core_database import get_db_connection
from doxoade.tools.filesystem import _get_project_config

def run_silent_sync(project_root, dry_run=False):
    config = _get_project_config(start_path=project_root)
    bricks = config.get('bricks', {})
    if not bricks: return []

    changes = []
    try:
        conn = get_db_connection()
        for name, local_rel_path in bricks.items():
            local_path = Path(project_root) / local_rel_path
            row = conn.execute("SELECT filename FROM moduloid_acervo WHERE name=?", (name,)).fetchone()
            if not row: continue
            
            from doxoade.commands.moduloid_systems.moduloid_acervo import BRICKS_DIR
            source_brick = BRICKS_DIR / row[0]
            
            def get_hash(p): return hashlib.md5(p.read_bytes()).hexdigest()
            
            needs_update = False
            if not local_path.exists(): needs_update = True
            elif get_hash(local_path) != get_hash(source_brick): needs_update = True

            if needs_update:
                audit_report = "PENDENTE"
                if dry_run:
                    # --- AUDITORIA DE QUALIDADE EM TEMPO REAL ---
                    audit_report = _audit_brick_quality(source_brick)
                
                changes.append({
                    "brick": name,
                    "path": local_rel_path,
                    "status": "DIVERGENTE",
                    "quality": audit_report
                })
                if not dry_run:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_brick, local_path)
        conn.close()
    except Exception as e:
        import sys as _dox_sys, os as _dox_os
        from traceback import print_tb as exc_trace
        exc_obj, exc_tb = _dox_sys.exc_info()
        f_name = _dox_os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_n = exc_tb.tb_lineno
        exc_trace(exc_tb)
        print(f"\033[1;34m[ FORENSIC ]\033[0m \033[1mFile: {f_name} | L: {line_n} | Func: get_hash\033[0m")
        print(f"\033[31m  ■ Type: {type(e).__name__} | Value: {e}\033[0m")
    return changes

def _audit_brick_quality(brick_path):
    """Executa um check rápido de integridade no brick do Acervo."""
    import ast
    try:
        content = brick_path.read_text(encoding='utf-8', errors='ignore')
        ast.parse(content)
        # Check de MPoT básico: funções muito longas?
        tree = ast.parse(content)
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        long_funcs = [f.name for f in funcs if (f.end_lineno - f.lineno) > 60]
        
        if long_funcs:
            return f"AVISO (Funções Longas: {', '.join(long_funcs)})"
        return "ESTÁVEL (Passou na AST)"
    except SyntaxError as e:
        return f"CRÍTICO (Erro de Sintaxe na linha {e.lineno})"
    except Exception:
        return "INDETERMINADO"
