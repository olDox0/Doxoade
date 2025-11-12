# tests/test_regression_logic.py
import os
import sys
from pathlib import Path

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.commands.check import _analyze_single_file_statically, _get_venv_python_executable
from doxoade.shared_tools import ExecutionLogger, _get_project_config

def test_regression_detection_in_isolation(tmp_path):
    """
    Este teste simula todo o fluxo de regressão em um ambiente controlado,
    provando que a lógica de análise do 'check' funciona.
    """
    project_dir = tmp_path
    file_to_test = project_dir / "main.py"
    
    # --- ETAPA 1: O ESTADO "SAUDÁVEL" ---
    
    # Cria um arquivo limpo
    file_to_test.write_text('if __name__ == "__main__":\n    print("hello")\n', encoding='utf-8')
    
    # Simula a configuração mínima necessária
    logger = ExecutionLogger('test', str(project_dir), {})
    config = _get_project_config(logger, start_path=str(project_dir))
    python_executable = _get_venv_python_executable()
    
    # Analisa o arquivo limpo
    findings_clean, _ = _analyze_single_file_statically(str(file_to_test), python_executable)
    
    # Afirmação: O arquivo limpo não deve ter nenhum 'finding'
    assert len(findings_clean) == 0, "O arquivo limpo não deveria ter gerado findings."

    # --- ETAPA 2: INTRODUZIR A REGRESSÃO ---

    # Adiciona um import não utilizado (a regressão)
    file_to_test.write_text('import os\n\nif __name__ == "__main__":\n    print("hello")\n', encoding='utf-8')

    # --- ETAPA 3: DETECTAR A REGRESSÃO ---
    
    # Analisa o arquivo modificado
    findings_dirty, _ = _analyze_single_file_statically(str(file_to_test), python_executable)
    
    # Afirmação Final: O arquivo modificado DEVE ter um 'finding'
    assert len(findings_dirty) == 1, "A regressão (import não utilizado) não foi detectada."
    
    finding = findings_dirty[0]
    assert "'os' imported but unused" in finding['message'], "A mensagem do finding de regressão está incorreta."