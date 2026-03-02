# -*- coding: utf-8 -*-
# doxoade/commands/check_systems/check_logic.py
"""
Motor de Auditoria Nexus Level 2 - v100.2 Platinum.
Orquestrador de Sondas e Especialistas (Resgatado via Protocolo Osíris).
Compliance: OSL-5, PASC-8.1.
"""
import sys
# [DOX-UNUSED] import os
from .check_engine import _run_clone_detection
from click import progressbar
from ...tools.memory_pool import finding_arena 
#def run_audit_engine_logic(state: CheckState, io_manager, **kwargs):
def run_audit_engine_logic(state, io_manager, **kwargs):
    """Execução central sem dependências de CLI."""
    from ...probes.manager import ProbeManager
    from .check_engine import _filter_by_cache, _scan_single_file, _run_clone_detection
    from ...tools.analysis import _get_code_snippet
    
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
                    arena_res = finding_arena.rent(
                        res['severity'], res['category'], res['message'], 
                        res['file'], res['line']
                    )
                    arena_res['snippet'] = snip
                    state.register_finding(arena_res)
                
                if mtime > 0 and not any(f.get('category') == 'SYSTEM' for f in results):
                    cache[cache_key] = {'mtime': mtime, 'size': size, 'findings': results}
    if kwargs.get('clones'):
        _run_clone_detection(files, manager, state)
    if not kwargs.get('no_cache'):
        io_manager.save_cache(cache)
def _scan_core(fp, manager, kwargs):
    # Lógica de triagem movida do engine.py para cá...
    return [] # Placeholder para a lógica real
    
#def run_check_logic(path: str, state, *_args, **_kwargs):
def run_check_logic(path: str, state=None, *_args, **kwargs):
    """
    [RESGATADO] Coordena os especialistas de Auditoria. 
    Designado como Atena-Logic no Panteão.
    """
    from ...tools.vulcan.bridge import vulcan_bridge
    vulcan_bridge.apply_turbo('vulcan_audit', globals())
    
    # 1. Setup de Ambiente
    from .check_io import CheckIO
    from .check_state import CheckState
    from ...probes.manager import ProbeManager
    from .check_engine import _scan_single_file, _filter_by_cache
    
    io = CheckIO(path)
    state = CheckState(root=io.project_root, target_path=io.target_abs)
    
    # 2. Inicialização do Gerente de Sondas (Aegis Protocol)
    manager = ProbeManager(sys.executable, state.root)
    
    # 3. Coleta e Filtragem (Delta-Scan)
    files = io.resolve_files(kwargs.get('target_files'))
    cache = {} if kwargs.get('no_cache') else io.load_cache()
    to_scan = _filter_by_cache(files, cache, io, state, kwargs.get('no_cache'))
    
    
    if not to_scan and not kwargs.get('clones'):
        return {'summary': state.summary, 'findings': []}
    # 4. Ciclo de Execução JIT
    from click import progressbar
    from ...tools.memory_pool import finding_arena
    from ...tools.analysis import _get_code_snippet
    if to_scan:
        with progressbar(to_scan, label='Auditando') as bar:
            for fp, cache_key, mtime, size in bar:
                # Execução das Sondas (Syntax, Style, Hunter)
                results = _scan_single_file(fp, manager, kwargs)
                
                # Sincronização de Memória Arena (Zero-Allocation)
                for res in results:
                    arena_res = finding_arena.rent(
                        res['severity'], res['category'], 
                        res['message'], res['file'], res['line']
                    )
                    arena_res['snippet'] = _get_code_snippet(res['file'], res.get('line', 0))
                    state.register_finding(arena_res)
                
                # Atualização de Cache (PASC-2)
                if mtime > 0 and not any(f.get('category') == 'SYSTEM' for f in results):
                    cache[cache_key] = {'mtime': mtime, 'size': size, 'findings': results}
    # 5. Detecção Dry (Hefesto/Vulcan)
    if kwargs.get('clones'):
        _run_clone_detection(files, manager, state)
    # 6. Finalização e Persistência
    if not kwargs.get('no_cache'):
        io.save_cache(cache)
        
    return {'summary': state.summary, 'findings': state.findings}