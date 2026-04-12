from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime  # ← ADICIONE ESTA LINHA
from rich.console import Console
from rich.prompt import Confirm
from doxoade.tools.system_utils import is_termux
from doxoade.commands.mobile_termux import termux_share_file, termux_clipboard_copy, termux_toast, setup_micro_split_workflow

def show_file_info(file_path: Path):
    """Mostra informações detalhadas do arquivo"""
    stat = file_path.stat()
    
    table = Table(title=f"📊 Informações: {file_path.name}")
    table.add_column("Propriedade", style="cyan")
    table.add_column("Valor", style="white")
    
    table.add_row("Tamanho", f"{stat.st_size:,} bytes")
    table.add_row("Linhas", str(len(file_path.read_text(errors='ignore').splitlines())))
    table.add_row("Modificado", str(datetime.fromtimestamp(stat.st_mtime)))  # ← AGORA FUNCIONA
    table.add_row("Permissões", oct(stat.st_mode)[-3:])
    table.add_row("Caminho completo", str(file_path.resolve()))
    
    console.print(table)
    input("\nPressione Enter...")


def git_status_visual():
    """Mostra status do Git de forma visual"""
    try:
        result = subprocess.run(
            ['git', 'status', '--short'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            syntax = Syntax(result.stdout, "diff", theme="monokai")
            console.print("\n[bold cyan]📊 Git Status:[/bold cyan]")
            console.print(syntax)
        else:
            console.print("[yellow]Não é um repositório Git[/yellow]")
    except FileNotFoundError:
        console.print("[red]Git não instalado[/red]")
    
    input("\nPressione Enter...")

def show_extended_menu(ide_instance):
    """Menu com comandos avançados"""
    while True:
        ide_instance.clear_screen()
        
        console.print(Panel(
            "[bold cyan]🛠️  MENU AVANÇADO[/bold cyan]",
            style="bold white on blue"
        ))
        
        options = [
            ("1", "📊", "Informações do arquivo"),
            ("2", "🔍", "Buscar em arquivos"),
            ("3", "📋", "Git status"),
            ("4", "📤", "Compartilhar arquivo (Termux)"),
            ("5", "📋", "Copiar caminho"),
            ("6", "🧹", "Limpar cache Python"),
            ("7", "🔙", "Voltar")
        ]
        
        for key, icon, desc in options:
            color = "cyan" if key != "7" else "yellow"
            console.print(f"  [{color}]{key}. {icon} {desc}[/{color}]")
        
        choice = Prompt.ask("\n> ", default="7")
        
        if choice == "1" and ide_instance.current_file:
            show_file_info(ide_instance.current_file)
        elif choice == "2":
            term = Prompt.ask("Buscar por")
            if term:
                quick_search_in_files(ide_instance.start_path, term)
        elif choice == "3":
            git_status_visual()
        elif choice == "4" and ide_instance.current_file:
            termux_share_file(ide_instance.current_file)
            input("\nPressione Enter...")
        elif choice == "5" and ide_instance.current_file:
            path_str = str(ide_instance.current_file.resolve())
            if is_termux():
                termux_clipboard_copy(path_str)
            else:
                console.print(f"\n[cyan]{path_str}[/cyan]")
            input("\nPressione Enter...")
        elif choice == "6":
            clean_python_cache(ide_instance.start_path)
        elif choice == "7":
            break

def get_best_editor():
    """Retorna o editor escolhido pelo usuário ou o melhor disponível"""
    # 1. Se o usuário definiu EDITOR no sistema, respeita
    env_editor = os.environ.get("EDITOR")
    if env_editor:
        return env_editor
    # 2. Se estiver no Termux, prioriza micro > nano > vim
    if is_termux():
        editors = ['micro', 'nano', 'vim', 'vi']
    else:
        if os.name == 'nt':
            editors = ['notepad++.exe', 'code', 'notepad.exe']
        else:
            editors = ['code', 'gedit', 'nano', 'vim']
    for editor in editors:
        try:
            subprocess.run(
                ['which', editor] if os.name != 'nt' else ['where', editor],
                capture_output=True,
                check=True
            )
            return editor
        except Exception:
            continue
    return 'nano'

