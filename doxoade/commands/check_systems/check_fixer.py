# doxoade/doxoade/commands/check_systems/check_fixer.py
import os
from click import echo
from doxoade.tools.doxcolors import Fore
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

def apply_fixes_to_state(state, fix_specify=None):
    if not state or not hasattr(state, 'findings'):
        return 0
    
    from .fixer import AutoFixer
    from collections import defaultdict
    
    files_map = defaultdict(list)
    # Identifica o que pode ser consertado
    for f in state.findings:
        action = f.get('suggestion_action')
#        if action and (not fix_specify or action == fix_specify):
        if action == 'INDENT_ERR' or (action and (not fix_specify or action == fix_specify)):
            files_map[f['file']].append(f)
            
    if not files_map:
        return 0

    fixed_count = 0
    findings_resolved = []

    with ExecutionLogger('autofix', state.root, {'fix_specify': fix_specify}) as f_log:
        fixer = AutoFixer(f_log)
        for file_path, file_findings in files_map.items():
            file_findings.sort(key=lambda x: x.get('line', 0), reverse=True)
            
            for f in file_findings:
                # Captura o nome da variável da mensagem de erro
                var_name = f.get('message', '').split("'")[1] if "'" in f.get('message', '') else None
                
                # Prepara o contexto incluindo metadados extras (como o nome do módulo para ADD_IMPORT)
                context = {'var_name': var_name}
                if f.get('suggestion_meta'):
                    context.update(f['suggestion_meta'])
                
                # Agora passamos o 'context' completo
                if fixer.apply_fix(f['file'], f['line'], f.get('suggestion_action'), context):
                    echo(f"{Fore.GREEN}   [ FIX-OK ] {Fore.WHITE}{os.path.basename(f['file'])}:{f['line']}")
                    fixed_count += 1
                    findings_resolved.append(f)

    # --- SINCRONIA DE ESTADO ---
    # Remove da lista de pendências o que já foi resolvido
    for f in findings_resolved:
        if f in state.findings:
            state.findings.remove(f)
    
    # Recalcula os totais (Avisos/Erros) para a UI final
    state.sync_summary()
    
    return fixed_count