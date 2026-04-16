# doxoade/doxoade/diagnostic/check_diagnose.py
import os
import sys
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from doxoade.commands.check import run_check_logic, _get_probe_path
from ..probes.manager import ProbeManager
from doxoade.tools.filesystem import _get_venv_python_executable

def verificar_integridade_sondas():
    console = Console()
    console.print(Panel.fit('🔍 [bold cyan]Doxoade Omnisciente: Diagnóstico de Escala Total (Gold)[/bold cyan]'))
    diag_dir = os.path.dirname(__file__)
    exame_1 = os.path.abspath(os.path.join(diag_dir, 'check_exame.py'))
    exame_2 = os.path.abspath(os.path.join(diag_dir, 'check_exame_clone.py'))
    python_exe = _get_venv_python_executable() or sys.executable
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(exame_1)))
    manager = ProbeManager(python_exe, project_root)
    console.print('\n[bold]Fase 1: Bateria de Disparo (Manager Isolation)[/bold]')
    sondas = ['syntax_probe.py', 'static_probe.py', 'hunter_probe.py', 'style_probe.py', 'clone_probe.py', 'orphan_probe.py', 'import_probe.py', 'xref_probe.py']
    table_infra = Table(show_header=True, header_style='bold blue')
    table_infra.add_column('Sonda')
    table_infra.add_column('Execução')
    table_infra.add_column('Payload')
    infra_ok = True
    for s in sondas:
        p_path = _get_probe_path(s)
        is_global = s in ['clone_probe.py', 'orphan_probe.py', 'xref_probe.py', 'import_probe.py']
        payload = {'files': [exame_1, exame_2]} if is_global else None
        target = project_root if s == 'xref_probe.py' else exame_1 if not is_global else None
        res = manager.execute(p_path, target, payload=payload)
        status = '[green]OK[/green]' if res['success'] else f'[red]FALHA[/red]'
        pay_type = 'JSON' if payload else 'FILE'
        table_infra.add_row(s, status, pay_type)
        if not res['success']:
            infra_ok = False
    console.print(table_infra)
    console.print('\n[bold]Fase 2: Sensibilidade Cruzada (Multi-File Check)[/bold]')
    results = run_check_logic(path=diag_dir, fix=False, fast=False, no_cache=True, clones=True, continue_on_error=True, target_files=[exame_1, exame_2])
    findings = results.get('findings', [])
    report_raw = str(findings).lower()
    console.print(f'  - Total de problemas detectados: [bold white]{len(findings)}[/bold white]')
    if len(findings) == 0:
        console.print('  [red]⚠ ALERTA: O pipeline retornou ZERO problemas. Verifique se o loop de arquivos rodou.[/red]')
    check_map = {'SINTAXE/REGRAS': 'unused' in report_raw or 'eval' in report_raw, 'DUPLICATION (Clones)': 'duplicada' in report_raw or 'clone' in report_raw, 'ORPHAN (Código Inútil)': 'não é chamada' in report_raw or 'orphan' in report_raw, 'XREF (Assinatura)': 'argumentos' in report_raw or 'signature' in report_raw}
    if not all(check_map.values()):
        console.print('\n[bold yellow]--- DEBUG DE CEGUEIRA ---[/bold yellow]')
        console.print(f'  Arquivos alvo: {len([exame_1, exame_2])}')
        console.print(f'  Amostra de Findings: {str(findings)[:200]}...')
    table_intel = Table(show_header=True, header_style='bold magenta')
    table_intel.add_column('Capacidade de Detecção')
    table_intel.add_column('Resultado')
    for cap, detectado in check_map.items():
        table_intel.add_row(cap, '[green]CONVERGENTE[/green]' if detectado else '[red]CEGO[/red]')
    console.print(table_intel)
    if infra_ok and all(check_map.values()):
        console.print('\n[bold green]✅ SISTEMA GOLD: O Doxoade atingiu maturidade total de auditoria.[/bold green]')
        return True
    else:
        console.print('\n[bold red]❌ SISTEMA INSTÁVEL: Algumas sondas globais estão falhando.[/bold red]')
        return False
