# -*- coding: utf-8 -*-
"""
Módulo de I/O e Persistência Deepcheck - v46.0 Gold.
Gerencia snapshots, integração Git e exportação de linhagem.
"""
import os
import json
import ast
from colorama import Fore, Style
from click import echo

SNAPSHOT_DIR = os.path.join(".doxoade", "deepcheck_snapshots")

def get_snapshot_path(filename: str) -> str:
    """Gera slug seguro para o sistema de arquivos."""
    slug = filename.replace('\\', '_').replace('/', '_').replace(':', '')
    return os.path.join(SNAPSHOT_DIR, f"{slug}.json")

def load_git_content(file_path: str, commit: str = "HEAD") -> str:
    """Recupera conteúdo do Git de forma segura."""
    from ..tools.git import _run_git_command
    try:
        rel_path = os.path.relpath(file_path, os.getcwd()).replace('\\', '/')
        return _run_git_command(['show', f'{commit}:{rel_path}'], capture_output=True, silent_fail=True)
    except Exception:
        return ""

def save_analysis_snapshot(file_path: str, data: list):
    """Persiste o resultado da análise no diretório de snapshots."""
    try:
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        path = get_snapshot_path(file_path)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_analysis_snapshot(file_path: str) -> dict:
    """Carrega o último estado salvo para comparação."""
    path = get_snapshot_path(file_path)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return {item['function']: item for item in json.load(f)}
        except Exception:
            return {}
    return {}

def render_lineage_summary(visitor):
    """Visualiza a Fronteira de Dados: De onde vem e para onde vai."""
    echo(f"\n   {Fore.BLUE}[ LINHAGEM DE DADOS: FRONTEIRA FINAL ]{Style.RESET_ALL}")
    
    # 1. Inputs (Fontes)
    inputs = [f"{Fore.MAGENTA}{p}{Fore.RESET}" for p in visitor.params.keys()]
    echo(f"      {Fore.WHITE}ENTRADA (Args)   : {', '.join(inputs) if inputs else 'Nenhuma'}")
    
    # 2. Transformações de Fluxo
    # Filtra apenas o que é processamento lógico para o resumo
    transforms = []
    for orig, action, dest in visitor.flow_map:
        if "processa" in action:
            transforms.append(f"{Fore.YELLOW}{dest}{Fore.RESET}")
    
    flow_line = " ➔ ".join(transforms) if transforms else "Lógica Direta"
    echo(f"      {Fore.WHITE}FLUXO (Internal) : {flow_line}")
    
    # 3. Outputs (Destinos)
    outputs = [f"{Fore.GREEN}{r['value']}{Fore.RESET}" for r in visitor.returns]
    echo(f"      {Fore.WHITE}SAÍDA (Return)   : {', '.join(outputs) if outputs else 'Void'}")