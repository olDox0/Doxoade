# -*- coding: utf-8 -*-
"""
Canonization Module - Gold Standard Snapshot.
Compliance: MPoT-5, PASC-6.
"""
import os
import sys
import datetime
from json import dumps, loads
from click import command, option, echo
from colorama import Style, Fore
from pathlib import Path

from ..shared_tools import _get_git_commit_hash, CANON_DIR, ExecutionLogger

__all__ = ['canonize']

@command('canonize')
@option('--all', 'all_project', is_flag=True, help="Canoniza o estado total do projeto.")
@option('--run-tests', is_flag=True, default=True, help="Executa testes antes de salvar.")
def canonize(all_project: bool, run_tests: bool):
    """Cria um snapshot 'Sagrado' do projeto (Lint + Testes + Estrutura)."""
    if not all_project:
        echo(Fore.YELLOW + "⚠ Use --all para confirmar a canonização total do projeto.")
        return

    os.makedirs(CANON_DIR, exist_ok=True)
    git_hash = _get_git_commit_hash('.')

    with ExecutionLogger('canonize', '.', {'all': all_project}) as _:
        echo(f"{Fore.CYAN}{Style.BRIGHT}--- [CANONIZE] Gerando Snapshot 'Gold' ---")
        
        # 1. Análise Estática
        echo(f"{Fore.WHITE}  > Fase 1: Análise Estática (Check)...")
        from .check import run_check_logic
        static_results = run_check_logic('.', fix=False, fast=True, no_cache=True, clones=False, continue_on_error=True)
        
        # 2. Estrutura de Testes
        echo(f"{Fore.WHITE}  > Fase 2: Mapeamento de Testes...")
        from .test_mapper import TestMapper
        test_matrix = TestMapper('.').scan()

        # 3. Execução Comportamental
        test_results = {"status": "SKIPPED", "exit_code": 0}
        if run_tests:
            echo(f"{Fore.WHITE}  > Fase 3: Execução de Testes (Pytest)...")
            from subprocess import run as sub_run # nosec
            pt_res = sub_run([sys.executable, "-m", "pytest", "-q", "--tb=no"], capture_output=True, text=True, shell=False)
            test_results = {
                "exit_code": pt_res.returncode,
                "status": "PASS" if pt_res.returncode == 0 else "FAIL",
                "summary": pt_res.stdout.splitlines()[-1] if pt_res.stdout else "No output"
            }

        # 4. Consolidação
        snapshot_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'git_hash': git_hash,
            'static_analysis': static_results,
            'test_structure': test_matrix,
            'test_execution': test_results
        }

        with open(os.path.join(CANON_DIR, "project_snapshot.json"), 'w', encoding='utf-8') as f:
            from json import dump
            dump(snapshot_data, f, indent=2, ensure_ascii=False)

        _render_canon_summary(snapshot_data)

def _render_canon_summary(data: dict):
    """Exibe evidências do que foi salvo (MPoT-4)."""
    echo(f"\n{Fore.GREEN}{Style.BRIGHT}✔ Snapshot 'Gold' Consolidado!")
    echo(f"   {Fore.WHITE}Commit:   {Fore.YELLOW}{data['git_hash'][:7]}")
    echo(f"   {Fore.WHITE}Lint:     {Fore.YELLOW}{len(data['static_analysis'].get('findings', []))} problemas conhecidos.")
    echo(f"   {Fore.WHITE}Testes:   [{data['test_execution']['status']}] {data['test_execution'].get('summary')}")