# doxoade/doxoade/commands/check_systems/check_refactor.py
"""Motor de Sugestão de Refatoração (PASC 1.0)."""
from .check_state import CheckState

def analyze_refactor_opportunities(state: CheckState):
    """Varre achados em busca de gatilhos para o AutoFixer."""
    for f in state.findings:
        msg = f.get('message', '').lower()
        if 'f-string is missing placeholders' in msg:
            f['suggestion_action'] = 'REMOVE_F_PREFIX'
        elif 'except:' in msg or ('except' in msg and ':' in msg and ('exception' not in msg)):
            f['suggestion_action'] = 'RESTRICT_EXCEPTION'
        elif 'imported but unused' in msg:
            f['suggestion_action'] = 'FIX_UNUSED_IMPORT'
        elif 'assigned to but never used' in msg:
            f['suggestion_action'] = 'REPLACE_WITH_UNDERSCORE'