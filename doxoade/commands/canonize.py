# doxoade/commands/canonize.py
import os
import sys
import json
import click
import subprocess
from colorama import Fore, Style
from ..shared_tools import _sanitize_json_output, _get_git_commit_hash, CANON_DIR
from .test_mapper import TestMapper

@click.command('canonize')
@click.option('--all', 'all_project', is_flag=True, help="Canoniza o estado do projeto atual.")
@click.option('--run-tests', is_flag=True, default=True, help="Executa pytest para salvar o status dos testes.")
def canonize(all_project, run_tests):
    """Cria um snapshot 'Sagrado' do projeto (Lint + Testes + Estrutura)."""
    if not all_project:
        click.echo(Fore.YELLOW + "Use --all para canonizar o projeto todo.")
        return

    os.makedirs(CANON_DIR, exist_ok=True)
    git_hash = _get_git_commit_hash('.')
    
    # [FIX] Invocação robusta via módulo python em vez de buscar executável
    # Isso evita problemas de extensão (.exe) no Windows sem shell=True

    click.echo(Fore.CYAN + "--- [CANONIZE] Criando snapshot do projeto ---")
    click.echo(Fore.WHITE + f"  > Commit Base: {git_hash[:7]}")

    # 1. Coleta Dados Estáticos (Check)
    click.echo(Fore.WHITE + "  > Executando Análise Estática (Check)...")
    
    # [FIX] sys.executable -m doxoade
    command_parts = [sys.executable, '-m', 'doxoade', 'check', '.', '--format=json']
    
    result = subprocess.run(command_parts, capture_output=True, text=True, shell=False, encoding='utf-8', errors='replace')
    
    try:
        check_report = json.loads(result.stdout)
    except json.JSONDecodeError:
        click.echo(Fore.RED + "Erro fatal: Saída do check inválida.")
        # Debug output para ajudar se falhar de novo
        if result.stderr:
            click.echo(Fore.YELLOW + f"STDERR: {result.stderr}")
        sys.exit(1)

    # 2. Coleta Mapa de Testes (Estrutura)
    click.echo(Fore.WHITE + "  > Mapeando Cobertura de Testes...")
    mapper = TestMapper('.')
    test_matrix = mapper.scan()

    # 3. Executa Testes (Comportamento)
    test_results = {"passed": 0, "failed": 0, "total": 0, "details": []}
    if run_tests:
        click.echo(Fore.WHITE + "  > Executando Pytest (Isso pode demorar)...")
        try:
            # -q: quiet, --tb=line: traceback curto
            pytest_cmd = [sys.executable, "-m", "pytest", "-q", "--tb=line"]
            pt_res = subprocess.run(pytest_cmd, capture_output=True, text=True, encoding='utf-8')
            
            test_results['exit_code'] = pt_res.returncode
            test_results['output_summary'] = pt_res.stdout.splitlines()[-1] if pt_res.stdout else "Sem output"
            
            if pt_res.returncode == 0:
                test_results['status'] = "PASS"
            else:
                test_results['status'] = "FAIL"
                
        except Exception as e:
            test_results['status'] = "ERROR"
            test_results['error'] = str(e)

    # 4. Consolida o Cânone
    sanitized_check = _sanitize_json_output(check_report, '.')
    
    snapshot_data = {
        'timestamp': str(os.path.getmtime('.')),
        'git_hash': git_hash,
        'static_analysis': sanitized_check,
        'test_structure': test_matrix,
        'test_execution': test_results
    }
    
    snapshot_path = os.path.join(CANON_DIR, "project_snapshot.json")
    
    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot_data, f, indent=2, ensure_ascii=False)
    
    click.echo(Fore.GREEN + f"    [OK] Snapshot salvo em '{snapshot_path}'.")
    if test_results.get('status') == 'FAIL':
        click.echo(Fore.YELLOW + "    [AVISO] O snapshot foi salvo com testes falhando. Isso será o novo normal.")