# doxoade/doxoade/shared_tools.py
"""
Módulo de Fachada (Facade) para Ferramentas Compartilhadas.
Este módulo existe para manter a retrocompatibilidade com comandos antigos
que importam de `doxoade.shared_tools`. Ele redireciona as chamadas para
a nova estrutura modular em `doxoade.tools.*`.
IMPORTANTE: Novos desenvolvimentos devem importar diretamente de `doxoade.tools`.
"""
from doxoade.tools.git import _run_git_command, _get_git_commit_hash
from doxoade.tools.analysis import _get_all_findings, _get_code_snippet, _get_code_snippet_from_string, _extract_function_parameters, _find_returns_and_risks_in_function, _analyze_function_flow, _get_complexity_rank, analyze_file_structure, _mine_traceback, _analyze_runtime_error, _get_file_hash, _sanitize_json_output
from doxoade.tools.display import _present_results, _print_finding_details, _print_summary, _present_diff_output, _format_timestamp
from doxoade.tools.db_utils import _log_execution, _update_open_incidents
from doxoade.tools.genesis import _enrich_with_dependency_analysis, _enrich_findings_with_solutions
import os
REGRESSION_BASE_DIR = 'regression_tests'
FIXTURES_DIR = os.path.join(REGRESSION_BASE_DIR, 'fixtures')
CANON_DIR = os.path.join(REGRESSION_BASE_DIR, 'canon')
CONFIG_FILE = os.path.join(REGRESSION_BASE_DIR, 'canon.toml')
__all__ = ['_run_git_command', '_get_git_commit_hash', '_find_project_root', '_get_project_config', '_get_venv_python_executable', '_is_path_ignored', 'collect_files_to_analyze', '_get_all_findings', '_get_code_snippet', '_get_code_snippet_from_string', '_extract_function_parameters', '_find_returns_and_risks_in_function', '_analyze_function_flow', '_get_complexity_rank', 'analyze_file_structure', '_mine_traceback', '_analyze_runtime_error', '_get_file_hash', '_sanitize_json_output', '_present_results', '_print_finding_details', '_print_summary', '_present_diff_output', '_format_timestamp', '_log_execution', '_update_open_incidents', 'ExecutionLogger', '_enrich_with_dependency_analysis', '_enrich_findings_with_solutions']
