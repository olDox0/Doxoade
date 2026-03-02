# -*- coding: utf-8 -*-
import os
from click import echo
from doxoade.tools.doxcolors import Fore
from .check_state import CheckState
def apply_fixes_to_state(state):
    if not state or not hasattr(state, "findings"):
        return
    if state is None or not hasattr(state, "findings"):
        return None
    if not fix_specify: fix_specify = None
    """Aplica correções nos achados presentes no estado."""
    from doxoade.commands.check_systems.check_fixer import AutoFixer
    from ...shared_tools import ExecutionLogger
    from collections import defaultdict
    files_map = defaultdict(list)
    for f in state.findings:
        action = f.get('suggestion_action')
        if action and (not fix_specify or action == fix_specify):
            files_map[f['file']].append(f)
    
    if not files_map: return
    with ExecutionLogger('autofix', state.root, {'fix_specify': fix_specify}) as f_log:
        fixer = AutoFixer(f_log)
        for file_path, file_findings in files_map.items():
            file_findings.sort(key=lambda x: x.get('line', 0), reverse=True)
            for f in file_findings:
                var_name = f.get('message', '').split("'")[1] if "'" in f.get('message', '') else None
                if fixer.apply_fix(f['file'], f['line'], f.get('suggestion_action'), {'var_name': var_name}):
                    echo(f"{Fore.GREEN}   [ FIX-OK ] {Fore.WHITE}{os.path.basename(f['file'])}:{f['line']}")