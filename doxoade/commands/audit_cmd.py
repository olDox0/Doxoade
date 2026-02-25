# -*- coding: utf-8 -*-
# doxoade/commands/audit_cmd.py
"""
Comando Audit - A Interface de Ma'at v1.0.
Executa auditoria arquitetural e de paridade sob demanda.
"""
import click
import os
from .audit_systems.maat_engine import MaatEngine
from ..shared_tools import ExecutionLogger, _find_project_root
@click.command('audit')
@click.argument('path', type=click.Path(exists=True), default='.')
@click.pass_context
def audit(ctx, path):
    """⚖  Tribunal de Ma'at: Verifica regressões e peso do código."""
    root = _find_project_root(os.path.abspath(path))
    
    with ExecutionLogger('audit', root, ctx.params) as logger:
        # Identifica arquivos para auditar (focado em .py)
        from ..dnm import DNM
        dnm = DNM(root)
        files = dnm.scan(extensions=['py'])
        
        engine = MaatEngine(root)
        is_stable, findings = engine.run_full_audit(files)
        
        # Registra achados no log global
        for f in findings:
            logger.add_finding(
                severity=f['severity'],
                message=f['message'],
                category=f['category'],
                file=f['file'],
                line=f.get('line', 1)
            )
            
        if not is_stable:
            ctx.exit(1)