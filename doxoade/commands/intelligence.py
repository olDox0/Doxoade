# -*- coding: utf-8 -*-
"""
Comando Intelligence - v41.5 Gold.
Gera Dossiês de Arquitetura em qualquer projeto (Path Sovereignty).
"""
import os
import json
# [DOX-UNUSED] import sys
from datetime import datetime, timezone
import click
from rich.console import Console

from ..shared_tools import ExecutionLogger, _find_project_root
from ..dnm import DNM
from .intelligence_utils import get_ignore_spec
from .intelligence_systems.intelligence_logic import analyze_file_chief

@click.command('intelligence')
@click.option('--output', '-o', default='chief_dossier.json', help="Saída do dossiê.")
@click.option('--concatenate', '-c', is_flag=True, help="Minifica o JSON final.")
@click.pass_context
def intelligence(ctx, output, concatenate):
    """Gera um Dossiê de Inteligência Topológica (Chief Standard)."""
    # 1. Âncora de Soberania (Onde o projeto realmente começa?)
    # Se o usuário está em uma subpasta, o Doxoade encontra a raiz.
    root = _find_project_root(os.getcwd())
    console = Console()
    
    with ExecutionLogger('intelligence', root, ctx.params) as _:
        console.print("[bold gold3]🧐 Doxoade Chief Insight v41.5[/bold gold3]")
        console.print(f"[dim]Ancorado em: {root}[/dim]\n")
        
        # 2. DNM configurado com a raiz do projeto alvo
        dnm = DNM(root)
        spec = get_ignore_spec(root)
        
        # Filtra os arquivos respeitando o .gitignore e o toml do projeto ALVO
        all_files = dnm.scan()
        filtered_files = [f for f in all_files if not (spec and spec.match_file(os.path.relpath(f, root)))]
        
        dossier_files = []
        with click.progressbar(filtered_files, label='Escaneando Topologia') as bar:
            for f in bar:
                res = analyze_file_chief(f, root)
                if res: dossier_files.append(res)

        # 3. Geração do Relatório
        _save_chief_report(dossier_files, output, root, concatenate, console)

def _save_chief_report(files, output, root, concat, console):
    """Salva o relatório no diretório atual de trabalho."""
    report = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project": os.path.basename(root),
            "mode": "concatenated" if concat else "verbose"
        },
        "executive_summary": {
            "files_count": len(files),
            "total_loc": sum(f.get('loc', 0) for f in files if 'loc' in f),
            "doc_files": len([f for f in files if f.get('type') == 'documentation'])
        },
        "codebase": files
    }
    
    json_kwargs = {"indent": None if concat else 2, "separators": (',', ':') if concat else (', ', ': '), "ensure_ascii": False}
    
    try:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(report, f, **json_kwargs)
        console.print(f"\n[bold green]✅ Dossiê salvo em: {output}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao salvar: {e}[/bold red]")