# -*- coding: utf-8 -*-
# doxoade/commands/check_notepadpp.py
import os
import click
from colorama import Fore
from ..tools.npp_integration import signal_notepadpp
from .check import run_check_logic

def run_npp_workflow(path: str, **kwargs):
    """
    Expert-Split: Orquestrador Notepad++.
    Compliance: PASC-8.13 (Separação de Contexto).
    """
    target = os.path.abspath(path)
    
    if os.path.isdir(target):
        click.echo(Fore.RED + "[!] Erro: NPP Integration exige um arquivo específico.")
        return

    # PASC-8.5: Limpeza Cirúrgica do Contrato
    # Extraímos 'project_root' do kwargs para que ele não colida com as chamadas internas
    # mas o mantemos disponível para o signal_notepadpp no final.
    project_root = kwargs.pop('project_root', os.path.dirname(target))

    # Injeção de Segurança para o Bridge
    kwargs['no_cache'] = True
    kwargs['full_power'] = True

    # Agora o kwargs está 'limpo' de duplicatas
    results = run_check_logic(target, **kwargs)
    
    findings = results.get('findings', [])

    # Usa o root que extraímos cirurgicamente
    signal_notepadpp(target, findings, project_root)
    
    if not findings:
        click.echo(Fore.GREEN + "[N++ Bridge] Arquivo limpo. Feedback enviado.")
    else:
        click.echo(Fore.CYAN + f"[N++ Bridge] {len(findings)} incidentes mapeados no editor.")