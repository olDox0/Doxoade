# tests/test_canonize_command.py
import os
import sys
import json
from click.testing import CliRunner

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from doxoade.doxoade import cli

def test_canonize_all_creates_project_snapshot(tmp_path, monkeypatch):
    """
    Verifica se `canonize --all` cria um snapshot JSON do projeto atual.
    """
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)

    # 1. Setup: Cria um projeto falso e ISOLADO
    (project_dir / "main.py").write_text("import os", encoding="utf-8")
    (project_dir / "regression_tests" / "canon").mkdir(parents=True)
    
    # --- A CORREÇÃO CRUCIAL ---
    # Cria um pyproject.toml local para isolar o teste
    (project_dir / "pyproject.toml").write_text(
        '[tool.doxoade]\nsource_dir = "."\n', 
        encoding='utf-8'
    )
    # -------------------------
    
    # Simula um repositório git para que o hash seja encontrado
    os.system("git init > nul 2>&1")
    os.system("git add .")
    os.system('git commit -m "initial commit" > nul 2>&1')

    runner = CliRunner()
    result = runner.invoke(cli, ['canonize', '--all'], catch_exceptions=False)
    
    assert result.exit_code == 0, f"O comando falhou com a saída: {result.output}"
    
    snapshot_file = project_dir / "regression_tests" / "canon" / "project_snapshot.json"
    assert snapshot_file.is_file(), "O arquivo project_snapshot.json não foi criado."
    
    with open(snapshot_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    assert "git_hash" in data
    report = data["report"]
    
    # Afirma que o relatório agora contém a análise do nosso arquivo de teste
    assert "file_reports" in report
    assert "main.py" in report["file_reports"], "O relatório não contém 'main.py'"
    
    findings = report["file_reports"]["main.py"]["static_analysis"]["findings"]
    assert len(findings) == 1
    assert "'os' imported but unused" in findings[0]["message"]