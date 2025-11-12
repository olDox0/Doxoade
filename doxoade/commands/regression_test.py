# doxoade/commands/regression_test.py
import os
import sys
import toml
import json
import click
from colorama import Fore, Style
import jsondiff

from .check import run_check_logic
from ..shared_tools import (
    _sanitize_json_output, 
    _print_finding_details, 
#    _get_code_snippet,
    _run_git_command, # Importa a função para executar comandos git
    REGRESSION_BASE_DIR, 
    FIXTURES_DIR, 
    CANON_DIR, 
    CONFIG_FILE
)

def _get_all_findings(results_report):
    all_findings = []
    if not results_report or 'file_reports' not in results_report:
        return []
    for file_path, report in results_report['file_reports'].items():
        for finding in report.get('static_analysis', {}).get('findings', []):
            finding['full_path_for_diff'] = file_path 
            all_findings.append(finding)
    return all_findings

# Dentro de doxoade/commands/regression_test.py

def _present_regression_diff(canonical_report, current_report, canonical_hash, project_name):
    """
    (Versão Polida) Analisa a diferença e apresenta um relatório comparativo
    com alinhamento perfeito.
    """
    canonical_findings = _get_all_findings(canonical_report)
    current_findings = _get_all_findings(current_report)
    
    canonical_hashes = {f['hash'] for f in canonical_findings}
    current_hashes = {f['hash'] for f in current_findings}

    new_hashes = current_hashes - canonical_hashes
    resolved_hashes = canonical_hashes - current_hashes
    
    if new_hashes:
        click.echo(Fore.RED + Style.BRIGHT + "\n--- [!] NOVOS PROBLEMAS (REGRESSÕES) DETECTADOS ---")
        new_findings = [f for f in current_findings if f['hash'] in new_hashes]
        for finding in new_findings:
            click.echo("\n" + ("-"*20))
            
            # Apresenta o novo erro com seu snippet completo (sem mudanças aqui)
            _print_finding_details(finding)
            
            file_path = finding.get('full_path_for_diff')
            line_num = finding.get('line')
            snippet = finding.get('snippet')
            
            if not all([file_path, line_num, snippet]):
                continue

            relative_file_path = os.path.join(REGRESSION_BASE_DIR, "fixtures", project_name, file_path)
            
            old_content = _run_git_command(
                ['show', f'{canonical_hash}:{relative_file_path.replace("\\", "/")}'], 
                capture_output=True, 
                silent_fail=True
            )
            
            if old_content:
                click.echo(Fore.CYAN + f"  > VERSÃO ESTÁVEL (Canônico - {canonical_hash[:7]}):")
                old_lines = old_content.splitlines()
                
                line_numbers_in_snippet = [int(k) for k in snippet.keys()]
                start_line = min(line_numbers_in_snippet)
                end_line = max(line_numbers_in_snippet)

                for i in range(start_line - 1, end_line):
                    if 0 <= i < len(old_lines):
                        line_to_print = old_lines[i]
                        current_line_num = i + 1
                        
                        # --- A CORREÇÃO DE ALINHAMENTO ESTÁ AQUI ---
                        # Adicionamos os espaços corretos para espelhar a formatação de _print_finding_details
                        if current_line_num == line_num:
                            click.echo(Fore.WHITE + Style.BRIGHT + f"      > {current_line_num:4}: {line_to_print}")
                        else:
                            click.echo(Style.DIM + f"        {current_line_num:4}: {line_to_print}")

    if resolved_hashes:
        click.echo(Fore.GREEN + "\n--- [+] PROBLEMAS RESOLVIDOS ---")
        resolved_findings = [f for f in canonical_findings if f['hash'] in resolved_hashes]
        for finding in resolved_findings:
            click.echo(Fore.GREEN + f"  - [RESOLVIDO] {finding['message']} (em {finding['full_path_for_diff']})")


@click.command('regression-test')
def regression_test():
    """Compara a saída JSON atual dos comandos com os snapshots canônicos."""
    click.echo(Fore.CYAN + "--- [REGRESSION-TEST] Iniciando a verificação de regressões (modo JSON) ---")

    if not os.path.exists(CONFIG_FILE):
        click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        test_config = toml.load(f)
    
    test_cases = test_config.get('test_case', [])
    failures = 0

    for case in test_cases:
        case_id = case.get('id')
        project_name = case.get('project')
        project_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name))
        
        click.echo(Fore.WHITE + f"  > Verificando teste '{case_id}'...")

        current_results = run_check_logic(path=project_path, cmd_line_ignore=[], fix=False, debug=False)
        sanitized_current_report = _sanitize_json_output(current_results, project_path)

        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.json")
        if not os.path.exists(snapshot_path):
            click.echo(Fore.YELLOW + f"    [AVISO] Snapshot canônico '{snapshot_path}' não encontrado.")
            continue

        with open(snapshot_path, 'r', encoding='utf-8') as f:
            snapshot_data = json.load(f)
            canonical_hash = snapshot_data.get('git_hash')
            sanitized_canonical_report = snapshot_data.get('report')

        # Compara apenas os relatórios, não o objeto inteiro (que inclui o hash)
        diff = jsondiff.diff(sanitized_canonical_report, sanitized_current_report)

        if not diff:
            click.echo(Fore.GREEN + f"    [OK] Teste '{case_id}' passou.")
        else:
            failures += 1
            click.echo(Fore.RED + Style.BRIGHT + f"    [FALHA] Regressão detectada em '{case_id}'!")
            
            # Passa todos os argumentos necessários para a apresentação
            _present_regression_diff(sanitized_canonical_report, sanitized_current_report, canonical_hash, project_name)
            
    click.echo(Fore.CYAN + "\n--- Concluído ---")
    if failures > 0:
        click.echo(Fore.RED + f"{failures} teste(s) de regressão falharam.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + "Todos os testes de regressão passaram com sucesso.")