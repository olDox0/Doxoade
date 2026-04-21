# doxoade/doxoade/commands/regression_test.py
"""
Regression Test - The Guardian of Progress v41.3.
Provides detailed evidence-based comparison.
Compliance: MPoT-4, MPoT-5, PASC-6.
"""
import os
import sys
from click import command, option, echo
from doxoade.tools.doxcolors import Style, Fore
from typing import Dict, Optional
from doxoade.shared_tools import CANON_DIR
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
__all__ = ['regression_test']

def _load_canon() -> Optional[Dict]:
    """Carrega o snapshot sagrado do projeto (MPoT-7)."""
    import json
    snapshot_path = os.path.join(CANON_DIR, 'project_snapshot.json')
    if not os.path.exists(snapshot_path):
        return None
    try:
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def _run_audit_pipeline(canon: dict, verbose: bool) -> dict:
    """Executa e compara os dados atuais contra o cânone (MPoT-5)."""
    if not canon or 'static_analysis' not in canon:
        raise ValueError('Invalid Canon data provided to audit pipeline.')
    from .check import run_check_logic
    from subprocess import run as sub_run
    current_check = run_check_logic('.', fix=False, fast=True, no_cache=True, clones=False, continue_on_error=True)

    def get_hashes(findings):
        return {f.get('hash') for f in findings if f.get('hash')}
    old_hashes = get_hashes(canon['static_analysis'].get('findings', []))
    new_hashes = get_hashes(current_check.get('findings', []))
    pt_res = sub_run([sys.executable, '-m', 'pytest', '-q', '--tb=short'], capture_output=True, text=True, shell=False)
    return {'new_lint_errors': list(new_hashes - old_hashes), 'lint_total': len(new_hashes), 'test_exit_code': pt_res.returncode, 'canon_test_exit': canon.get('test_execution', {}).get('exit_code', 0), 'test_output': pt_res.stdout, 'verbose': verbose}

def _render_final_verdict(ev: dict):
    """Apresenta o laudo de evidências simétrico (MPoT-4)."""
    if not ev:
        raise ValueError('Evidence data required for rendering.')
    if ev['new_lint_errors']:
        echo(f"\n{Fore.RED}✘ REGRESSÃO ESTÁTICA: {len(ev['new_lint_errors'])} novos bugs detectados.")
        for h in ev['new_lint_errors'][:3]:
            echo(f'   > Hash: {h}')
    else:
        echo(f"\n{Fore.GREEN}✔ Estabilidade Estática: Nenhuma regressão ({ev['lint_total']} ativos).")
    status_map = {0: 'PASS', 1: 'FAIL', 2: 'ERROR', 5: 'NO_TESTS'}
    curr_status = status_map.get(ev['test_exit_code'], 'UNKNOWN')
    canon_status = status_map.get(ev['canon_test_exit'], 'UNKNOWN')
    if ev['test_exit_code'] == ev['canon_test_exit']:
        color = Fore.GREEN if ev['test_exit_code'] == 0 else Fore.YELLOW
        echo(f'{color}✔ Estabilidade Comportamental: Consistente com Cânone [{curr_status}].')
    else:
        echo(f'{Fore.RED}✘ REGRESSÃO DE TESTES: O sistema PIOROU! [{curr_status}] (Era: {canon_status})')
        if ev['verbose']:
            echo(f"\n{ev['test_output']}")
    echo('-' * 50)
    is_unstable = ev['new_lint_errors'] or (ev['test_exit_code'] != 0 and ev['test_exit_code'] > ev['canon_test_exit'])
    if is_unstable:
        echo(f'{Fore.RED}{Style.BRIGHT}VEREDITO: PROJETO INSTÁVEL. REVISE AS REGRESSÕES.')
        sys.exit(1)
    else:
        echo(f'{Fore.GREEN}{Style.BRIGHT}VEREDITO: PROJETO ESTÁVEL. PRONTO PARA CONSOLIDAÇÃO.')

@command('regression-test')
@option('--verbose', '-v', 'verbose', is_flag=True, help='Exibe detalhes técnicos dos erros.')
def regression_test(verbose: bool):
    """Verifica a saúde do projeto comparando com o 'Cânone' (MPoT-5)."""
    canon = _load_canon()
    if not canon:
        echo(Fore.RED + "[ERRO] Cânone não encontrado. Execute 'doxoade canonize --all' primeiro.")
        return
    with ExecutionLogger('regression-test', '.', {'verbose': verbose}) as _:
        echo(f'{Fore.CYAN}{Style.BRIGHT}--- [REGRESSION] Auditoria de Qualidade Chief-Gold ---{Style.RESET_ALL}')
        evidence = _run_audit_pipeline(canon, verbose)
        _render_final_verdict(evidence)
