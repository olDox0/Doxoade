# -*- coding: utf-8 -*-
# doxoade/commands/check_notepadpp.py
"""
Expert-Split: Notepad++ Integration Bridge.
Responsável por orquestrar a visualização de erros no editor.
Compliance: PASC-1.2, PASC-8.5, Aegis-Hardening.
"""

import os
import json
import click
from colorama import Fore, Style
from ..tools.npp_integration import signal_notepadpp
from .check import run_check_logic

def run_npp_workflow(path: str, **kwargs):
    """
    Orquestrador da Integração. 
    Garante que apenas UM arquivo seja processado para evitar overhead no N++.
    """
    abs_path = os.path.abspath(path)
    
    # Restrição de Arquivo Único (User Requirement #1)
    if os.path.isdir(abs_path):
        click.echo(Fore.RED + "[!] Erro: A integração Notepad++ suporta apenas análise de arquivo único.")
        return

    if not abs_path.endswith('.py'):
        click.echo(Fore.YELLOW + "[!] Aviso: Integração N++ otimizada apenas para Python.")
        return

    # 1. Executa a lógica de Check nativa (Reuso de Código PASC-10)
    # Passamos no_cache=True para garantir que o feedback no editor seja sempre o atual
    results = run_check_logic(abs_path, no_cache=True, **kwargs)
    
    findings = results.get('findings', [])
    project_root = kwargs.get('project_root', os.path.dirname(abs_path))

    # 2. Sinalização e Persistência
    # O JSON já vai com as sugestões da Gênese injetadas pelo run_check_logic
    signal_notepadpp(abs_path, findings, project_root)
    
    # 3. Feedback no Terminal
    if not findings:
        click.echo(Fore.GREEN + f"[N++ Bridge] Arquivo limpo. Sinalizando limpeza ao editor.")
    else:
        click.echo(Fore.CYAN + f"[N++ Bridge] {len(findings)} erros enviados ao Notepad++.")

def cleanup_npp_bridge(project_root: str):
    """
    Remove ou limpa o feedback visual no Notepad++ (User Requirement #2).
    Segurança: Verifica existência antes de deletar para evitar IOErrors.
    """
    bridge_file = os.path.join(project_root, ".doxoade", "npp_bridge.json")
    if os.path.exists(bridge_file):
        try:
            # Em vez de deletar o arquivo (o que pode quebrar o FileWatcher do N++),
            # enviamos um payload vazio de 'status: CLEAN'.
            empty_payload = {
                "source": "all",
                "status": "CLEAN",
                "findings": []
            }
            with open(bridge_file, 'w', encoding='utf-8') as f:
                json.dump(empty_payload, f)
            click.echo(Fore.GREEN + "[N++ Bridge] Feedback visual limpo com sucesso.")
        except Exception as e:
            click.echo(Fore.RED + f"[N++ Bridge] Falha no cleanup: {e}")