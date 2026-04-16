# doxoade/doxoade/commands/check_notepadpp.py
import os
import click
from doxoade.tools.doxcolors import Fore
from doxoade.tools.npp_integration import signal_notepadpp
from .check import run_check_logic

def run_npp_workflow(path: str, **kwargs):
    """
    Expert-Split: Orquestrador Notepad++.
    Compliance: PASC-8.13 (Separação de Contexto).
    """
    target = os.path.abspath(path)
    if os.path.isdir(target):
        click.echo(Fore.RED + '[!] Erro: NPP Integration exige um arquivo específico.')
        return
    project_root = kwargs.pop('project_root', os.path.dirname(target))
    kwargs['no_cache'] = True
    kwargs['full_power'] = True
    results = run_check_logic(target, **kwargs)
    findings = results.get('findings', [])
    signal_notepadpp(target, findings, project_root)
    if not findings:
        click.echo(Fore.GREEN + '[N++ Bridge] Arquivo limpo. Feedback enviado.')
    else:
        click.echo(Fore.CYAN + f'[N++ Bridge] {len(findings)} incidentes mapeados no editor.')