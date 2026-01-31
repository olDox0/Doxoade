# -*- coding: utf-8 -*-
# doxoade/commands/check_notepadpp.py
import os
import click
from colorama import Fore
from ..tools.npp_integration import signal_notepadpp
from .check import run_check_logic

def run_npp_workflow(path: str, **kwargs):
    """
    Expert-Split para fluxo de editor.
    Compliance: PASC-8.14 (Anti-Fragilidade)
    """
    target = os.path.abspath(path)
    
    if os.path.isdir(target):
        click.echo(Fore.RED + "[!] Erro: NPP Integration exige um arquivo específico.")
        return

    # Injeção Segura de Flags (Evita o TypeError de múltiplos valores)
    # NPP Bridge exige dados frescos e completos
    kwargs['no_cache'] = True
    kwargs['full_power'] = True

    # Executa a auditoria usando apenas o kwargs atualizado
    results = run_check_logic(target, **kwargs)
    
    findings = results.get('findings', [])
    project_root = kwargs.get('project_root', os.path.dirname(target))

    signal_notepadpp(target, findings, project_root)
    
    if not findings:
        click.echo(Fore.GREEN + "[N++ Bridge] Arquivo limpo. Feedback enviado.")
    else:
        # PASC-6.2: Verbosidade Seletiva
        click.echo(Fore.CYAN + f"[N++ Bridge] {len(findings)} incidentes mapeados no editor.")