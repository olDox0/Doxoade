# doxoade/commands/regression_test.py
import os
import sys
import toml
import json
import click
import shlex
import subprocess
from colorama import Fore, Style
import jsondiff

from ..shared_tools import (
    _sanitize_json_output, 
    _print_finding_details, 
    _run_git_command, 
#    REGRESSION_BASE_DIR, 
    FIXTURES_DIR, 
    CANON_DIR, 
    CONFIG_FILE
)

def _get_all_findings(results_report):
    """Extrai uma lista plana de todos os findings de um relatório de 'check'."""
    all_findings = []
    if not results_report or 'file_reports' not in results_report:
        return []
    for file_path, report in results_report['file_reports'].items():
        for finding in report.get('static_analysis', {}).get('findings', []):
            finding['path_for_diff'] = file_path 
            all_findings.append(finding)
    return all_findings

def _present_regression_diff(canonical_report, current_report, canonical_hash, project_name, project_path):
    """
    (Versão Final e Corrigida) Analisa a diferença e apresenta um relatório
    comparativo legível com contexto do Git.
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
            
            _print_finding_details(finding)
            
            file_path_relative_to_project = finding.get('path_for_diff')
            line_num = finding.get('line')
            snippet = finding.get('snippet')

            if not all([file_path_relative_to_project, line_num, snippet]):
                continue

            # Constrói o caminho relativo a partir da raiz do git
            git_root = _run_git_command(['rev-parse', '--show-toplevel'], capture_output=True, silent_fail=True)
            if not git_root: continue

            if project_name == '.':
                # No modo --all, o caminho do 'finding' já é relativo à raiz do projeto
                full_file_path = os.path.abspath(file_path_relative_to_project)
            else:
                # No modo fixture, construímos o caminho completo
                full_file_path = os.path.abspath(os.path.join(FIXTURES_DIR, project_name, file_path_relative_to_project))
            
            relative_path_for_git = os.path.relpath(full_file_path, git_root)
            git_object_path = f'{canonical_hash}:{relative_path_for_git.replace("\\", "/")}'
            
            old_content = _run_git_command(['show', git_object_path], capture_output=True, silent_fail=True)
            
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
                        
                        if current_line_num == line_num:
                            click.echo(Fore.WHITE + Style.BRIGHT + f"      > {current_line_num:4}: {line_to_print}")
                        else:
                            click.echo(Style.DIM + f"        {current_line_num:4}: {line_to_print}")

    if resolved_hashes:
        click.echo(Fore.GREEN + "\n--- [+] PROBLEMAS RESOLVIDOS ---")
        resolved_findings = [f for f in canonical_findings if f['hash'] in resolved_hashes]
        for finding in resolved_findings:
            click.echo(Fore.GREEN + f"  - [RESOLVIDO] {finding['message']} (em {finding.get('path_for_diff', 'arquivo desconhecido')})")

@click.command('regression-test')
@click.option('--all', 'all_project', is_flag=True, help="Testa o estado do projeto atual contra o snapshot.")
def regression_test(all_project):
    """Compara a saída JSON atual dos comandos com os snapshots canônicos."""
    click.echo(Fore.CYAN + "--- [REGRESSION-TEST] Iniciando a verificação de regressões (modo JSON) ---")
    
    test_cases = []
    if all_project:
        test_cases.append({'id': 'project_snapshot', 'command': 'doxoade check .', 'project': '.'})
    else:
        if not os.path.exists(CONFIG_FILE):
            click.echo(Fore.RED + f"[ERRO] Arquivo de configuração '{CONFIG_FILE}' não encontrado.")
            sys.exit(1)
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            test_config = toml.load(f)
        test_cases = test_config.get('test_case', [])
        
    doxoade_executable = os.path.join(os.path.dirname(sys.executable), 'doxoade')
    failures = 0

    for case in test_cases:
        case_id = case.get('id')
        command = case.get('command')
        project_name = case.get('project')
        
        project_path = os.path.abspath(project_name) if project_name == '.' else os.path.abspath(os.path.join(FIXTURES_DIR, project_name))

        if '--format=json' not in command:
            command += ' --format=json'
        
        command_parts = shlex.split(command)
        command_parts[0] = doxoade_executable
        
        click.echo(Fore.WHITE + f"  > Verificando teste '{case_id}'...")

        result = subprocess.run(
            command_parts, 
            cwd=project_path, 
            capture_output=True, 
            text=True, 
            shell=False, 
            encoding='utf-8', 
            errors='replace'
        )

        try:
            current_results_raw = json.loads(result.stdout)
        except json.JSONDecodeError:
            failures += 1
            click.echo(Fore.RED + Style.BRIGHT + f"    [FALHA] A saída para '{case_id}' não é um JSON válido!")
            click.echo(Style.DIM + f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}")
            continue

        snapshot_path = os.path.join(CANON_DIR, f"{case_id}.json")
        if not os.path.exists(snapshot_path):
            click.echo(Fore.YELLOW + f"    [AVISO] Snapshot canônico '{snapshot_path}' não encontrado.")
            continue

        with open(snapshot_path, 'r', encoding='utf-8') as f:
            snapshot_data = json.load(f)
        
        canonical_hash = snapshot_data.get('git_hash')
        canonical_report_raw = snapshot_data.get('report')

        sanitized_current = _sanitize_json_output(current_results_raw, project_path)
        sanitized_canonical = _sanitize_json_output(canonical_report_raw, project_path)
        
        diff = jsondiff.diff(sanitized_canonical, sanitized_current)

        if not diff:
            click.echo(Fore.GREEN + f"    [OK] Teste '{case_id}' passou.")
        else:
            failures += 1
            click.echo(Fore.RED + Style.BRIGHT + f"    [FALHA] Regressão detectada em '{case_id}'!")
            
            _present_regression_diff(canonical_report_raw, current_results_raw, canonical_hash, project_name, project_path)
            
    click.echo(Fore.CYAN + "\n--- Concluído ---")
    if failures > 0:
        click.echo(Fore.RED + f"{failures} teste(s) de regressão falharam.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + "Todos os testes de regressão passaram com sucesso.")