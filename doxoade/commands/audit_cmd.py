# doxoade/doxoade/commands/audit_cmd.py
"""
Comando Audit - A Interface de Ma'at v1.0.
Executa auditoria arquitetural e de paridade sob demanda.
"""
import click
import os
from .audit_systems.maat_engine import MaatEngine
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@click.command('audit')
@click.argument('path', type=click.Path(exists=True), default='.')
@click.pass_context
def audit(ctx, path):
    """⚖  Tribunal de Ma'at: Verifica regressões e peso do código."""
    root = _find_project_root(os.path.abspath(path))
    with ExecutionLogger('audit', root, ctx.params) as logger:
        from doxoade.dnm import DNM
        dnm = DNM(root)
        files = dnm.scan(extensions=['py'])
        engine = MaatEngine(root)
        is_stable, findings = engine.run_full_audit(files)
        for f in findings:
            logger.add_finding(severity=f['severity'], message=f['message'], category=f['category'], file=f['file'], line=f.get('line', 1))
        if not is_stable:
            ctx.exit(1)
