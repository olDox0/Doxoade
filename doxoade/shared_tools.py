# doxoade/shared_tools.py
# (FACADE: Mantém compatibilidade com comandos antigos redirecionando para doxoade.tools)

# 1. GIT
from .tools.git import (
    _run_git_command, 
    _get_git_commit_hash
)

# 2. FILESYSTEM & CONFIG
from .tools.filesystem import (
    _find_project_root, 
    _get_project_config, 
    _get_venv_python_executable, 
    _is_path_ignored, 
    collect_files_to_analyze
)

# 3. ANALYSIS & AST
from .tools.analysis import (
    _get_all_findings,
    _get_code_snippet,
    _get_code_snippet_from_string,
    _extract_function_parameters,
    _find_returns_and_risks_in_function,
    _analyze_function_flow,
    _get_complexity_rank,
    analyze_file_structure,
    _mine_traceback,
    _analyze_runtime_error,
    _get_file_hash,
    _sanitize_json_output
)

# 4. DISPLAY & UI
from .tools.display import (
    _present_results, 
    _print_finding_details, 
    _print_summary,
    _present_diff_output,
    _format_timestamp  # <--- ADICIONADO AQUI
)

# 5. DATABASE UTILS
from .tools.db_utils import (
    _log_execution, 
    _update_open_incidents
)

# 6. LOGGER (Core)
from .tools.logger import ExecutionLogger

# 7. GÊNESE & ABDUÇÃO (Intelligence)
from .tools.genesis import (
    _enrich_with_dependency_analysis,
    _enrich_findings_with_solutions
)

# Constantes de Diretório (Mantidas aqui por compatibilidade)
import os
REGRESSION_BASE_DIR = "regression_tests"
FIXTURES_DIR = os.path.join(REGRESSION_BASE_DIR, "fixtures")
CANON_DIR = os.path.join(REGRESSION_BASE_DIR, "canon")
CONFIG_FILE = os.path.join(REGRESSION_BASE_DIR, "canon.toml")