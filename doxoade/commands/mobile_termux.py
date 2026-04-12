# doxoade/commands/mobile_termux.py

from __future__ import annotations

import os
import subprocess

from pathlib import Path
from doxoade.tools.system_utils import is_termux

def termux_share_file(file_path: Path):
    """Compartilha arquivo usando o Termux API"""
    if not is_termux():
        console.print("[yellow]Comando disponível apenas no Termux[/yellow]")
        return
    
    try:
        subprocess.run(['termux-share', str(file_path)])
        console.print(f"[green]✓ Compartilhando: {file_path.name}[/green]")
    except FileNotFoundError:
        console.print("[red]Instale termux-api: pkg install termux-api[/red]")


def termux_clipboard_copy(text: str):
    """Copia texto para área de transferência (Termux)"""
    if not is_termux():
        console.print("[yellow]Comando disponível apenas no Termux[/yellow]")
        return
    
    try:
        subprocess.run(['termux-clipboard-set'], input=text.encode())
        console.print("[green]✓ Copiado para área de transferência[/green]")
    except FileNotFoundError:
        console.print("[red]Instale termux-api: pkg install termux-api[/red]")


def termux_toast(message: str):
    """Mostra notificação toast (Termux)"""
    if is_termux():
        try:
            subprocess.run(['termux-toast', message])
        except Exception:
            pass


def setup_micro_split_workflow():
    """Configura atalho Alt-d no micro para workflow de split."""
    import json
    
    config_dir = Path.home() / ".config" / "micro"
    config_dir.mkdir(parents=True, exist_ok=True)
    bindings_file = config_dir / "bindings.json"
    
    current_bindings = {}
    if bindings_file.exists():
        try:
            current_bindings = json.loads(bindings_file.read_text())
        except Exception:
            pass
            
    # Adiciona o atalho Dual View
    current_bindings["Alt-d"] = "command:hsplit,command:new"
    
    # Salva
    bindings_file.write_text(json.dumps(current_bindings, indent=4))
    console.print("[green]✓ Workflow 'Alt-d' configurado no Micro![/green]")
    console.print("   > Abra um arquivo e pressione Alt+d para abrir o painel de rascunho.")
