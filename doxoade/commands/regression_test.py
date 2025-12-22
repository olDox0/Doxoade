# doxoade/commands/regression_test.py
import os
import sys
import json
import click
import subprocess
import jsondiff
import shlex
from colorama import Fore, Style
from ..shared_tools import CANON_DIR, _sanitize_json_output, _run_git_command, _get_all_findings, _print_finding_details, FIXTURES_DIR
from .test_mapper import TestMapper

def _load_canon():
    snapshot_path = os.path.join(CANON_DIR, "project_snapshot.json")
    if not os.path.exists(snapshot_path):
        return None
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _present_regression_diff(canonical_report, current_report, canonical_hash, project_name):
    """
    Analisa a diferença e apresenta um relatório comparativo legível.
    """
    canonical_findings = _get_all_findings(canonical_report)
    current_findings = _get_all_findings(current_report)
    
    canonical_hashes = {f['hash'] for f in canonical_findings}
    current_hashes = {f['hash'] for f in current_findings}

    new_hashes = current_hashes - canonical_hashes

    if new_hashes:
        click.echo(Fore.RED + Style.BRIGHT + "\n--- [!] NOVOS PROBLEMAS (REGRESSÕES) DETECTADOS ---")
        new_findings = [f for f in current_findings if f['hash'] in new_hashes]
        for finding in new_findings:
            click.echo("\n" + ("-"*20))
            _print_finding_details(finding)
            
            # Tenta recuperar contexto do Git se possível
            file_path = finding.get('path_for_diff') or finding.get('file')
            if file_path and canonical_hash:
                git_obj = f'{canonical_hash}:{file_path.replace("\\", "/")}'
                old_content = _run_git_command(['show', git_obj], capture_output=True, silent_fail=True)
                if old_content:
                    click.echo(Fore.CYAN + f"  > VERSÃO ESTÁVEL ({canonical_hash[:7]}):")
                    # (Lógica simplificada de exibição para brevidade)
                    click.echo(Fore.WHITE + "    (Conteúdo anterior disponível no histórico)")

@click.command('regression-test')
@click.option('--gen-missing', is_flag=True, help="Gera testes automaticamente para arquivos órfãos (novos).")
@click.option('--verbose', '-v', is_flag=True, help="Mostra a saída detalhada dos testes (stdout/stderr).") # <--- NOVO
def regression_test(gen_missing, verbose): # <--- NOVO PARAMETRO
    """
    Verifica a saúde do projeto comparando com o 'Cânone'.
    Detecta: Novos bugs, Perda de testes, Quebra de execução.
    """
    click.echo(Fore.CYAN + "--- [REGRESSION] Auditoria de Qualidade ---")
    
    canon = _load_canon()
    if not canon:
        click.echo(Fore.RED + "Cânone não encontrado. Execute 'doxoade canonize --all' primeiro.")
        sys.exit(1)

    failures = 0
    doxoade_executable = os.path.join(os.path.dirname(sys.executable), 'doxoade')

    # --- 1. Verificação Estática (Lint) ---
    click.echo(Fore.WHITE + "1. Verificando Análise Estática...")
    
    # [FIX] Invocação robusta
    check_cmd = [sys.executable, '-m', 'doxoade', 'check', '.', '--format=json']
    
    res = subprocess.run(check_cmd, capture_output=True, text=True, encoding='utf-8')
    try:
        current_check = _sanitize_json_output(json.loads(res.stdout), '.')
        canon_check = canon.get('static_analysis', {})
        
        # Comparação de hashes
        def get_hashes(report):
            hashes = set()
            if 'file_reports' in report:
                for fdat in report['file_reports'].values():
                    for finding in fdat.get('static_analysis', {}).get('findings', []):
                        hashes.add(finding.get('hash'))
            return hashes

        old_hashes = get_hashes(canon_check)
        new_hashes = get_hashes(current_check)
        
        diff = new_hashes - old_hashes
        if diff:
            click.echo(Fore.RED + f"   [FALHA] {len(diff)} novos problemas estáticos detectados.")
            _present_regression_diff(canon_check, current_check, canon.get('git_hash'), '.')
            failures += 1
        else:
            click.echo(Fore.GREEN + "   [OK] Nenhuma regressão estática.")

    except Exception as e:
        click.echo(Fore.RED + f"   [ERRO] Falha ao comparar lint: {e}")

    # --- 2. Verificação Estrutural (Cobertura) ---
    click.echo(Fore.WHITE + "2. Verificando Mapa de Testes...")
    mapper = TestMapper('.')
    current_map = mapper.scan()
    canon_map = canon.get('test_structure', {})
    
    canon_orphans = set(canon_map.get('orphans', []))
    current_orphans = set(current_map.get('orphans', []))
    
    new_orphans = current_orphans - canon_orphans
    
    if new_orphans:
        click.echo(Fore.YELLOW + f"   [ALERTA] {len(new_orphans)} novos arquivos sem teste detectados.")
        for f in list(new_orphans)[:5]:
            click.echo(f"      - {f}")
        if len(new_orphans) > 5:
            click.echo(f"      ... e mais {len(new_orphans)-5}.")
            
        if gen_missing:
            click.echo(Fore.CYAN + "   > Gerando testes para novos órfãos...")
            subprocess.run([sys.executable, '-m', 'doxoade', 'test-map', '--generate'])
    else:
        click.echo(Fore.GREEN + "   [OK] Cobertura estrutural mantida.")

    # --- 3. Verificação Comportamental (Pytest) ---
    click.echo(Fore.WHITE + "3. Executando Testes de Regressão (Pytest)...")
    
    # Se verbose, não captura output (mostra na tela), mas precisamos capturar para saber o returncode com segurança
    # Estratégia: Capturar sempre, imprimir se verbose
    pt_res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short"], capture_output=True, text=True)
    
    current_exit_code = pt_res.returncode
    canon_exit_code = canon.get('test_execution', {}).get('exit_code', 0)
    
    if current_exit_code == 0:
        click.echo(Fore.GREEN + "   [OK] Todos os testes passaram.")
    elif current_exit_code == canon_exit_code:
        click.echo(Fore.YELLOW + "   [AVISO] Testes falharam, mas o estado é consistente com o Cânone.")
        click.echo(Fore.WHITE + "           (Nenhuma NOVA regressão comportamental detectada)")
    else:
        click.echo(Fore.RED + "   [FALHA] O comportamento dos testes PIOROU em relação ao Cânone!")
        click.echo(Fore.RED + f"           Exit Code Atual: {current_exit_code} vs Cânone: {canon_exit_code}")
        failures += 1

    # --- EXIBIÇÃO DE DETALHES (Se solicitado ou se falhou feio) ---
    if verbose or failures > 0:
        click.echo(Fore.WHITE + "\n--- DETALHES DO PYTEST ---")
        if pt_res.stdout:
            click.echo(pt_res.stdout)
        if pt_res.stderr:
            click.echo(Fore.RED + pt_res.stderr)

    # Conclusão
    print("-" * 40)
    if failures > 0:
        click.echo(Fore.RED + "PROJETO COM REGRESSÕES. CORRIJA ANTES DE COMMITAR.")
        sys.exit(1)
    else:
        click.echo(Fore.GREEN + "PROJETO ESTÁVEL. PRONTO PARA SYNC.")