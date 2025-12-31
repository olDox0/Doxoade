# doxoade/diagnostic/check_diagnose.py
import os
from rich.console import Console
from rich.table import Table
from ..commands.check import run_check_logic

def verificar_integridade_sondas():
    """Valida a sensibilidade das sondas contra o arquivo de exame."""
    console = Console()
    exame = os.path.join(os.path.dirname(__file__), "check_exame.py")
    
    results = run_check_logic(exame, fix=False, fast=False, no_cache=True, 
                              clones=False, continue_on_error=True, exclude_categories=[])
    
    findings = results.get('findings', [])
    categorias_detectadas = [f['category'].upper() for f in findings]
    
    check_map = {
        "DEADCODE": "os" in str(findings),
        "COMPLEXITY": "funcao_complexa" in str(findings),
        "SECURITY": "eval" in str(findings),
        "RUNTIME-RISK": "variavel_inexistente" in str(findings),
        "RISK-MUTABLE": "argumento_mutavel" in str(findings)
    }
    
    table = Table(title="🛡️ Diagnóstico de Saúde das Sondas")
    table.add_column("Sonda / Detector", style="cyan")
    table.add_column("Status", justify="center")
    
    for nome, status in check_map.items():
        table.add_row(nome, "[green]OK[/green]" if status else "[red]FALHA[/red]")
        
    console.print(table)
    return all(check_map.values())