# doxoade/commands/git_systems/git_feature.py
"""
Doxoade Feature Tracker - O Bloco de Notas Persistente.
Permite acumular anotações de features que serão injetadas no próximo save.
"""
import os
import json
import click
from pathlib import Path
from datetime import datetime
from doxoade.tools.doxcolors import Fore, Style

FEATURES_FILE = ".doxoade/pending_features.json"

def _get_features_path():
    return Path.cwd() / FEATURES_FILE

def load_features():
    path = _get_features_path()
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("features", [])
        except Exception:
            return []
    return []

def save_features(features):
    path = _get_features_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({"features": features}, f, indent=2, ensure_ascii=False)

def add_feature(text):
    features = load_features()
    features.append({
        "timestamp": datetime.now().isoformat(),
        "text": text
    })
    save_features(features)

def clear_features():
    save_features([])

def get_features_summary():
    """Retorna o texto formatado para ser injetado no corpo do commit message."""
    features = load_features()
    if not features:
        return ""
    
    lines = ["\n\n📝 Changelog Acumulado (Doxoade Tracker):"]
    for f in features:
        lines.append(f"- {f['text']}")
    return "\n".join(lines)

@click.command('feature')
@click.argument('text', required=False)
@click.option('--list', '-l', 'list_features', is_flag=True, help='Lista as features acumuladas.')
@click.option('--clear', '-c', is_flag=True, help='Limpa o registro de features acumuladas.')
def feature_cmd(text, list_features, clear):
    """📝 Registrador de Features Acumuladas para o próximo Save."""
    if clear:
        clear_features()
        click.echo(Fore.GREEN + "✔ Registro de features limpo com sucesso.")
        return
        
    if list_features or not text:
        features = load_features()
        if not features:
            click.echo(Fore.YELLOW + "Nenhuma feature acumulada no momento.")
            return
        click.echo(Fore.CYAN + f"📝 Features Acumuladas ({len(features)}):")
        for i, f in enumerate(features, 1):
            click.echo(f"  {Fore.WHITE}{i}. {f['text']} {Style.DIM}({f['timestamp'][:10]}){Style.RESET_ALL}")
        return

    add_feature(text)
    click.echo(Fore.GREEN + f"✔ Feature registrada: '{text}'")
    click.echo(Fore.CYAN + "💡 Ela será incluída automaticamente no próximo 'doxoade save'.")
