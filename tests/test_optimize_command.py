# tests/test_optimize_command.py
import os
import sys
import json
from unittest.mock import MagicMock

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.commands.optimize import _find_unused_packages

def test_find_unused_packages_logic(monkeypatch, tmp_path):
    """
    Valida a lógica de resolução de dependências do _find_unused_packages (Teste de Unidade Puro).
    """
    # FLUXO 1: Preparar o Projeto "Doente" e os Mocks
    project_dir = tmp_path
    (project_dir / "src").mkdir()
    (project_dir / "src" / "main.py").write_text("import flask", encoding="utf-8")
    
    # Simula a saída da "Sonda de Ambiente"
    probe_results = {
        "package_deps": {
            "flask": ["werkzeug", "jinja2", "itsdangerous", "click"],
            "werkzeug": [],
            "jinja2": ["markupsafe"],
            "itsdangerous": [],
            "click": [],
            "markupsafe": [],
            "pytest": ["iniconfig", "pluggy"], # Pacote não utilizado com dependências
            "iniconfig": [],
            "pluggy": []
        },
        "module_map": {
            "flask": ["flask"],
            "werkzeug": ["werkzeug"],
            "jinja2": ["jinja2"],
            "itsdangerous": ["itsdangerous"],
            "click": ["click"],
            "markupsafe": ["markupsafe"],
            "pytest": ["pytest"],
            "iniconfig": ["iniconfig"],
            "pluggy": ["pluggy"]
        }
    }
    
    # Mock para _get_project_config
    mock_config = {
        'search_path_valid': True,
        'search_path': str(project_dir / "src"),
        'ignore': [],
        'keep': []
    }
    monkeypatch.setattr("doxoade.commands.optimize._get_project_config", lambda logger: mock_config)

    # Mock para o subprocess.run que executa a sonda
    mock_run_result = MagicMock()
    mock_run_result.stdout = json.dumps(probe_results)
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_run_result)

    # FLUXO 2: Executar a Função Alvo Diretamente
    unused_packages = _find_unused_packages(MagicMock(), "dummy_python_exe")

    # FLUXO 3: Validar os Resultados
    assert unused_packages is not None
    # 'pytest' e suas dependências devem ser os únicos não utilizados
    assert set(unused_packages) == {"pytest", "iniconfig", "pluggy"}