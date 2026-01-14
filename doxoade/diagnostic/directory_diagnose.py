# doxoade/diagnostic/directory_diagnose.py
import os
import sys
import shutil
from pathlib import Path
from rich.console import Console
from rich.table import Table
from ..dnm import DNM
from ..probes.manager import ProbeManager
from ..commands.check import _get_probe_path

def executar_diagnostico_diretorio():
    console = Console()
    console.print("\n[bold cyan]📂 Doxoade Directory Inspector: Auditoria de Acesso e Profundidade[/bold cyan]")
    
    # 1. Cria Ambiente de Teste (Ninho de Águia)
    root_test = Path("temp_dir_audit").absolute()
    sub_dir = root_test / "level1" / "level2"
    sub_dir.mkdir(parents=True, exist_ok=True)
    
    # Arquivo na Raiz
    file_root = root_test / "main_node.py"
    file_root.write_text("def root_func(): pass", encoding='utf-8')
    
    # Arquivo Profundo
    file_deep = sub_dir / "deep_node.py"
    file_deep.write_text("from main_node import root_func\ndef caller(): root_func()", encoding='utf-8')

    python_exe = sys.executable
    manager = ProbeManager(python_exe, str(root_test))

    # --- TESTE 1: DNM RECURSIVO ---
    console.print("\n[bold]Fase 1: Scanner de Visibilidade (DNM)[/bold]")
    dnm = DNM(str(root_test))
    arquivos_vistos = dnm.scan(extensions=['.py'])
    
    v_root = any("main_node.py" in f for f in arquivos_vistos)
    v_deep = any("deep_node.py" in f for f in arquivos_vistos)
    
    console.print(f"  - Raiz detectada: {'[green]SIM[/green]' if v_root else '[red]NÃO[/red]'}")
    console.print(f"  - Subpasta detectada: {'[green]SIM[/green]' if v_deep else '[red]NÃO[/red]'}")

    # --- TESTE 2: NORMALIZAÇÃO DE PROBES (XREF Profundo) ---
    console.print("\n[bold]Fase 2: Comunicação Cross-Folder (XREF Probe)[/bold]")
    
    # Tentamos rodar o XREF no labirinto
    c_files = [str(file_root).replace('\\', '/'), str(file_deep).replace('\\', '/')]
    res = manager.execute(_get_probe_path('xref_probe.py'), target_file=str(root_test), payload={"files": c_files})
    
    # Se o XREF funcionar, ele não deve achar erro de import (significa que ele resolveu o caminho)
    xref_ok = res['success'] and "[]" in res['stdout']
    
    console.print(f"  - Sonda XREF acessou níveis: {'[green]SIM[/green]' if xref_ok else '[red]NÃO[/red]'}")
    if not xref_ok:
        console.print(f"    [dim]Erro retornado: {res['error'] or res['stdout']}[/dim]")

    # --- LIMPEZA ---
    shutil.rmtree(root_test)
    
    return v_root and v_deep and xref_ok