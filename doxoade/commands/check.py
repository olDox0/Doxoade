# -*- coding: utf-8 -*-
# doxoade/commands/check.py

import click
from .check_systems.check_state import CheckState
from .check_systems.check_engine import run_check_logic

__all__ = ['check', 'run_check_logic']
@click.command('check')
@click.argument('path',                           type=click.Path(exists=True), default='.')
@click.option(  '--archives',          '-a',      is_flag=True, help="Modo Dossiê.")
@click.option(  '--clones',            '-c',      is_flag=True, help="Detecção de código duplicado (DRY).")
@click.option(  '--continue-on-error', '-coe',    is_flag=True, help="Não para em erros de sintaxe.")
@click.option(  '--exclude',           '-x',      multiple=True,help="Ignora categorias específicas.")
@click.option(  '--fast',              '-t',      is_flag=True, help="Ignora análise de complexidade pesada.")
@click.option(  '--fix',               '-f',      is_flag=True, help="Aplica correções automáticas.")
@click.option(  '--fix-specify',       '-fs',     type=str,     help="Executa apenas um tipo de reparo.")
@click.option(  '--full-power',        '-fp',     is_flag=True, help="Desativa ALB e força varredura total.")
@click.option(  '--no-cache',          '-no',     is_flag=True, help="Ignora o cache de arquivos.")
@click.option(  '--npp',                          is_flag=True, help="Integração com Notepad++.")
@click.option(  '--npp-clear',         '-nppc',   is_flag=True, help="Limpa marcações no editor.")
@click.option(  '--only',              '-o',      type=str,     help="Filtra apenas uma categoria.")
@click.option(  '--security',          '-s',      is_flag=True, help="Ativa auditoria Aegis (Bandit/Safety).")
@click.option(  '--structural-risk',   '-sr',     default=False, show_default=True, help="Classifica risco estrutural Python (dinamismo/import hooks).")
@click.option(  '--ai/--no-ai',                    default=False, show_default=True, help="Aciona ponte IA (ORN) quando houver achados bloqueantes.")
@click.option(  '--format',            'out_fmt', type=click.Choice(['text', 'json']), default='text')
@click.pass_context
def check(ctx, path: str, **kwargs):
    """🔍 Auditoria de Qualidade Modular v85.2 (Full Power)."""
    from .check_systems.check_io import CheckIO
    io = CheckIO(path)

    if kwargs.get('npp_clear'):
        from .check_notepadpp import cleanup_npp_bridge
        cleanup_npp_bridge(io.project_root)
        return

    from ..shared_tools import ExecutionLogger
    with ExecutionLogger('check', io.project_root, ctx.params) as logger:
        state = CheckState(root=io.project_root, target_path=io.target_abs, is_full_power=kwargs.get('full_power'))
        
        # 1.  ------ Motor de Auditoria (Passa 'fast', 'clones', 'no_cache', 'full_power')
        from .check_systems.check_engine import run_audit_engine
        run_audit_engine(state, io, **kwargs)

        # 2.  ------ Segurança Aegis (Passa 'security')
        if kwargs.get('security'):
            from .check_systems.check_security import analyze_security
            analyze_security(state)

        # 2.1 ------ Risco estrutural (diagnóstico preventivo)
        if kwargs.get('structural_risk', True):
            from .check_systems.check_structural import analyze_structural_risk
            analyze_structural_risk(state, io, **kwargs)

        # 3.  ------ Crivos e Refatoração (Passa 'exclude' e 'only')
        from .check_systems.check_filters import apply_filters
        apply_filters(state, **kwargs)
        from .check_systems.check_refactor import analyze_refactor_opportunities
        analyze_refactor_opportunities(state)

        # 4.  ------ Lógica de AUTO-FIX (Restaurada)
        if kwargs.get('fix') or kwargs.get('fix_specify'):
            _apply_modular_fixes(state, kwargs.get('fix_specify'))

        # 5.  ------ NPP Integration
        if kwargs.get('npp'):
            from .check_notepadpp import run_npp_workflow
            run_npp_workflow(path, **kwargs)
            return

        # 6.  ------ Sincronização e Saída
        from ..shared_tools import _update_open_incidents
        _update_open_incidents(state.findings, state.target_path)

        for f in state.findings:
            logger.add_finding(f['severity'], f['message'], f.get('category'), f.get('file'), f.get('line'))

        _render_output(state, kwargs)

        if kwargs.get('ai') and _has_blocking_findings(state):
            from ..API.orn_bridge import dispatch_check_errors_to_orn
            attempts = dispatch_check_errors_to_orn(
                path=state.target_path,
                summary=state.summary,
                findings=state.findings,
            )
            if kwargs.get('out_fmt') == 'text':
                for item in attempts:
                    status = 'OK' if item.ok else 'FALHA'
                    click.echo(f"[ORN-BRIDGE:{item.mode}] {status} - {item.detail}")

    from ..tools.streamer import ufs 
    ufs.clear() # Limpeza de Memória
    import sys
    if _has_blocking_findings(state): sys.exit(1)


def _render_output(state: CheckState, kwargs: dict):
    """Despachante de Interface Único (PASC 8.5)."""
    from .check_systems.check_utils import render_archived_view, _render_issue_summary
    from ..shared_tools import _present_results

    if kwargs.get('out_fmt') == 'json':
        import json
        click.echo(json.dumps({'summary': state.summary, 'findings': state.findings}, indent=2))
        return

    if kwargs.get('archives'):
        render_archived_view(state)
    else:
        # Modo Texto Padrão (Fachada para o display.py legado)
        legacy_data = {'summary': state.summary, 'findings': state.findings}
        _present_results('text', legacy_data)

    # O sumário por tipo sempre aparece no fim (Nexus Gold)
    _render_issue_summary(state.findings, **kwargs)


def _apply_modular_fixes(state, fix_specify):
    """Integra o AutoFixer ao novo CheckState."""
    from .check_systems.check_fixer import apply_fixes_to_state
    apply_fixes_to_state(state, fix_specify)


def _has_blocking_findings(state: CheckState) -> bool:
    """Define se o check deve falhar/acionar ORN.

    Compatibilidade: alguns findings de sintaxe podem não refletir no sumário legado.
    """
    if state.summary.get('critical', 0) > 0 or state.summary.get('errors', 0) > 0:
        return True

    for finding in state.findings:
        sev = str(finding.get('severity', '')).upper()
        if sev in {'ERROR', 'CRITICAL'}:
            return True
        if str(finding.get('category', '')).upper() == 'SYNTAX':
            return True
    return False


def _get_probe_path(probe_name):
    import os
    curr = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(curr, "..", "probes", probe_name))
