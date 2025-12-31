# -*- coding: utf-8 -*-
"""
Módulo de Auditoria Arquitetural (Style).
Valida o código fonte contra as regras do Modern Power of Ten (MPoT).
Otimizado para manter funções curtas e coesas (< 60 linhas).
"""

import click
import os
import json
import sys
import subprocess # nosec
from rich.console import Console
from rich.table import Table

from ..shared_tools import (
    ExecutionLogger, 
    collect_files_to_analyze, 
    _get_project_config, 
    _get_code_snippet
)

def _get_probe_path(probe_name: str) -> str:
    """Localiza o caminho absoluto da sonda de forma robusta."""
    from importlib import resources
    try:
        with resources.path('doxoade.probes', probe_name) as probe_path:
            return str(probe_path)
    except (AttributeError, ModuleNotFoundError, ImportError):
        from pkg_resources import resource_filename
        return resource_filename('doxoade', f'probes/{probe_name}')

def _execute_probe(probe_path: str, files: list, comment: bool) -> list:
    """
    Executa a sonda em um subprocesso isolado (Protocolo Aegis).
    Retorna a lista de achados (findings).
    """
    payload = {
        'files': [os.path.abspath(f) for f in files],
        'comments_only': comment
    }
    
    # B603: subprocess call - verificado como seguro (Aegis)
    result = subprocess.run(
        [sys.executable, probe_path],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=60,
        shell=False # nosec
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Falha na sonda: {result.stderr}")
        
    return json.loads(result.stdout)

def _render_findings(findings: list, logger: ExecutionLogger):
    """
    Renderiza os resultados em uma tabela Rich e registra no logger.
    
    MPoT-5: Contrato de validação para garantir integridade dos dados.
    """
    if findings is None:
        raise ValueError("A lista de achados (findings) não pode ser nula.")
    if logger is None:
        raise ValueError("O logger de execução é obrigatório para o registro.")

    console = Console()
    table = Table(title="Violações de Estilo Detectadas", show_lines=True)
    table.add_column("Local", style="dim")
    table.add_column("Categoria", style="magenta")
    table.add_column("Mensagem", style="yellow")

    for f in findings:
        logger.add_finding(
            severity=f['severity'],
            category=f['category'],
            message=f['message'],
            file=f['file'],
            line=f['line'],
            snippet=_get_code_snippet(f['file'], f['line'])
        )
        
        rel_file = os.path.relpath(f['file'], os.getcwd())
        table.add_row(f"{rel_file}:{f['line']}", f['category'], f['message'])

    console.print(table)
    console.print(f"\n[bold cyan]Resumo:[/bold cyan] [bold yellow]{len(findings)}[/bold yellow] aviso(s).")

@click.command('style')
@click.pass_context
@click.argument('path', type=click.Path(exists=True), default='.')
@click.option('--comment', is_flag=True, help="Foca exclusivamente em documentação.")
@click.option('--ignore', multiple=True, help="Pastas para ignorar.")
def style(ctx, path: str, comment: bool, ignore: tuple):
    """Analisa o estilo arquitetural baseado no Modern Power of Ten."""
    if not path:
        raise ValueError("Caminho inválido.")

    console = Console()
    target_is_file = os.path.isfile(path)
    root_path = os.path.dirname(os.path.abspath(path)) if target_is_file else path
    
    with ExecutionLogger('style', root_path, ctx.params) as logger:
        console.print(f"[bold cyan]--- [STYLE] Analisando '{path}' ---[/bold cyan]")

        files = [path] if target_is_file else collect_files_to_analyze(
            _get_project_config(logger, start_path=path), ignore
        )
        
        if not files:
            console.print("[yellow]Nenhum arquivo encontrado.[/yellow]")
            return

        try:
            findings = _execute_probe(_get_probe_path('style_probe.py'), files, comment)
            
            if not findings:
                console.print("[bold green][OK] Conformidade total.[/bold green]")
                return

            _render_findings(findings, logger)

        except Exception as e:
            console.print(f"[bold red][ERRO][/bold red] {str(e)}")