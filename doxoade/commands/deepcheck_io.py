# -*- coding: utf-8 -*-
# doxoade/commands/deepcheck_io.py
import os
import json
from colorama import Fore, Style
from click import echo

SNAPSHOT_DIR = os.path.join(".doxoade", "deepcheck_snapshots")

def get_snapshot_path(file_path: str) -> str:
    slug = file_path.replace('\\', '_').replace('/', '_').replace(':', '')
    return os.path.join(SNAPSHOT_DIR, f"{slug}.json")

def load_git_content(file_path: str, commit: str) -> str:
    from ..tools.git import _run_git_command
    try:
        rel = os.path.relpath(file_path, os.getcwd()).replace('\\', '/')
        return _run_git_command(['show', f"{commit}:{rel}"], capture_output=True, silent_fail=True)
    except Exception: return ""

def save_snapshot(file_path: str, data: list):
    try:
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        with open(get_snapshot_path(file_path), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception: pass

def load_snapshot(file_path: str) -> dict:
    path = get_snapshot_path(file_path)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return {item['function']: item for item in json.load(f)}
        except Exception: return {}
    return {}

def render_lineage_summary(visitor):
    echo(f"\n   {Fore.BLUE}[ LINHAGEM DE DADOS: RESUMO EXECUTIVO ]{Style.RESET_ALL}")
    inputs = [f"{Fore.MAGENTA}{p}{Fore.RESET}" for p in visitor.params.keys()]
    echo(f"      {Fore.WHITE}FONTES (Inputs)  : {', '.join(inputs) if inputs else 'Nenhuma'}")
    outputs = [f"{Fore.GREEN}{r['value']}{Fore.RESET}" for r in visitor.returns]
    echo(f"      {Fore.WHITE}DESTINO (Output) : {', '.join(outputs) if outputs else 'Void'}")