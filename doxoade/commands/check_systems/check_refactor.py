# doxoade/doxoade/commands/check_systems/check_refactor.py
import re
# [DOX-UNUSED] import os
from doxoade.tools.streamer import ufs
from .check_state import CheckState
from .fixer import AutoFixer

def analyze_refactor_opportunities(state: CheckState):
    """Varre achados em busca de gatilhos para o AutoFixer e gera prévias."""
    fixer = AutoFixer(None)
    for f in state.findings:
        msg = f.get('message', '').lower()
        cat = f.get('category', '').upper()
        file_path = f.get('file')
        action = None

        # Suporte estendido para recuo inválido em SyntaxErrors e IndentationErrors
        if cat == 'SYNTAX_INDENT' or cat == 'INDENT' or (cat == 'SYNTAX' and any(x in msg for x in ["indent", "unindent", "unexpected"])):
            f['suggestion_action'] = 'INDENT_ERR'
            f['message'] = f"⚠️ Alinhamento inválido detectado (Erro de Indentação: {f.get('message', '')})"
            preview = fixer.simulate_fix(f['file'], f['line'], 'INDENT_ERR', {})
            if preview:
                f['suggestion_content'] = preview
            continue
            
        if cat == 'SYNTAX' and 'expected an indented block' in msg:
            action = 'FIX_BLOCK_SYNTAX'
            # Importante: O erro aponta para a linha do 'except', 
            # mas o fix acontece na linha de cima.
            f['suggestion_action'] = action
            preview = fixer.simulate_fix(file_path, f['line'], action, {})
            if preview:
                f['suggestion_content'] = preview
                # Injeta a linha original no snippet para a UI conseguir mostrar o "Antes"
                lines = ufs.get_lines(file_path)
                target_idx = f['line'] - 2 # Linha do comentário
                if 0 <= target_idx < len(lines):
                    if not f.get('snippet'): f['snippet'] = {}
                    f['snippet'][str(target_idx + 1)] = lines[target_idx]
            continue # Pula para o próximo finding

        # --- 1. LÓGICA DE RESTAURAÇÃO (PASC 8.19) ---
        if "undefined name '" in msg:
            match = re.search(r"undefined name '(.+?)'", msg)
            if match:
                missing_var = match.group(1)
                lines = ufs.get_lines(file_path)
                
                for i, line in enumerate(lines):
                    # Se achamos o nome dentro de um comentário nosso, sugerimos a volta
                    if "[DOX-UNUSED]" in line and missing_var in line:
                        action = 'RESTORE_UNUSED'
                        f['line'] = i + 1 
                        f['message'] = f"Símbolo vital '{missing_var}' detectado no lixo. Restauração necessária."
                        break
                
                # Prioridade 2: Injetar se for um módulo utilitário comum
                if not action and missing_var in ['os', 'sys', 'traceback', 'json', 'click', 're', 'shutil']:
                    action = 'ADD_IMPORT'
                    f['suggestion_meta'] = {'module': missing_var}

        # --- 2. REPARO DE ESTILO ---
        if not action:
            if 'from __future__ imports must occur' in msg:
                action = 'MOVE_FUTURE'
            elif 'f-string is missing placeholders' in msg:
                action = 'REMOVE_F_PREFIX'
            elif 'except:' in msg or ('except' in msg and ':' in msg and ('exception' not in msg)):
                action = 'RESTRICT_EXCEPTION'
            elif 'imported but unused' in msg:
                action = 'FIX_UNUSED_IMPORT'
            elif 'assigned to but never used' in msg:
                action = 'REPLACE_WITH_UNDERSCORE'
            
        if action:
            f['suggestion_action'] = action
            ctx = f.get('suggestion_meta', {}).copy()
            if "'" in f.get('message', ''):
                parts = f.get('message', '').split("'")
                if len(parts) > 1: ctx['var_name'] = parts[1]

            preview = fixer.simulate_fix(f['file'], f['line'], action, ctx)
            if preview:
                f['suggestion_content'] = preview