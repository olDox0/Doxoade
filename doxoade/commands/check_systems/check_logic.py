# doxoade/doxoade/commands/check_systems/check_logic.py
"""
Motor de Auditoria Nexus Level 2 - v100.2 Platinum.
Orquestrador de Sondas e Especialistas (Resgatado via Protocolo Osíris).
Compliance: OSL-5, PASC-8.1.
"""
import sys
# [DOX-UNUSED] from .check_engine import _run_clone_detection
from click import progressbar
from doxoade.tools.memory_pool import finding_arena

def run_audit_engine_logic(state, io_manager, **kwargs):
    """Execução central sem dependências de CLI."""
    from ...probes.manager import ProbeManager
    from .check_engine import _filter_by_cache, _scan_single_file, _run_clone_detection
    from doxoade.tools.analysis import _get_code_snippet
    manager = ProbeManager(sys.executable, state.root)
    files = io_manager.resolve_files(kwargs.get('target_files'))
    cache = {} if kwargs.get('no_cache') else io_manager.load_cache()
    to_scan = _filter_by_cache(files, cache, io_manager, state, kwargs.get('no_cache'))
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for fp, cache_key, mtime, size in bar:
                results = _scan_single_file(fp, manager, kwargs)
                for res in results:
                    snip = _get_code_snippet(res['file'], res.get('line', 0))
                    arena_res = finding_arena.rent(res['severity'], res['category'], res['message'], res['file'], res['line'])
                    arena_res['snippet'] = snip
                    state.register_finding(arena_res)
                if mtime > 0 and (not any((f.get('category') == 'SYSTEM' for f in results))):
                    cache[cache_key] = {'mtime': mtime, 'size': size, 'findings': results}
    if kwargs.get('clones'):
        _run_clone_detection(files, manager, state)
    if not kwargs.get('no_cache'):
        io_manager.save_cache(cache)

def _scan_core(fp, manager, kwargs):
    return []

def run_check_logic(path: str, state=None, *_args, **kwargs):
    """
    [RESGATADO] Coordena os especialistas de Auditoria. 
    Designado como Atena-Logic no Panteão.
    """
    from doxoade.tools.vulcan.bridge import vulcan_bridge
    vulcan_bridge.apply_turbo('vulcan_audit', globals())
    
    # [DIAG] Print de console para rastreamento em nível CLI
    print(f"   [ LOGIC DEBUG ] kwargs = {kwargs} | args = {_args}")
    
    from doxoade.tools.telemetry_tools.logger import chief_heartbeat
    chief_heartbeat("HORUS", "LOGIC_RUN_CHECK_LOGIC_ARGS", {
        "path": path,
        "state_is_none": state is None,
        "args": str(_args),
        "kwargs": str(kwargs)
    })
    
    # Roteamento centralizado: Delega a execução para o motor Platinum unificado em check_engine
    from .check_engine import run_check_logic as _real_run_check_logic
    return _real_run_check_logic(path, state, *_args, **kwargs)