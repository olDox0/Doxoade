import click
import json
import sys
import os
from colorama import Fore

# Importa a lógica do probe que criamos
from ..probes.ast_diff_lab import analyze_transformation

@click.command('lab-ast')
@click.argument('file_old', type=click.Path(exists=True))
@click.argument('file_new', type=click.Path(exists=True))
def lab_ast(file_old, file_new):
    """
    (Experimental) Analisa a transformação semântica entre duas versões de um arquivo.
    Usa AST Diffing para detectar padrões como WRAP (Try/If).
    """
    click.echo(Fore.CYAN + f"--- [LAB-AST] Comparando Estruturas ---")
    click.echo(f"   > Base: {file_old}")
    click.echo(f"   > Alvo: {file_new}")
    
    try:
        with open(file_old, 'r', encoding='utf-8') as f: code_old = f.read()
        with open(file_new, 'r', encoding='utf-8') as f: code_new = f.read()
        
        result = analyze_transformation(code_old, code_new)
        
        if result.get('confidence', 0) > 0:
            click.echo(Fore.GREEN + "\n[SUCESSO] Transformação Detectada:")
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(Fore.YELLOW + "\n[NEUTRO] Nenhuma transformação estrutural conhecida detectada.")
            click.echo("(Pode ser apenas uma mudança textual ou lógica não suportada ainda)")
            
    except Exception as e:
        click.echo(Fore.RED + f"[ERRO] Falha na análise: {e}")