# tests/test_save_command.py
import os
import sys
import subprocess
from click.testing import CliRunner

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock
from doxoade.cli import cli

def _get_commit_count(repo_path):
    """Função auxiliar para contar o número de commits em um repositório."""
    result = subprocess.run(
        ['git', 'rev-list', '--count', 'HEAD'],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return int(result.stdout.strip()) if result.returncode == 0 else 0

def test_save_aborts_on_check_failure(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade save' aborta o commit se o 'doxoade check' falhar.
    """
    # FLUXO 1: Preparar um Projeto Git "Doente"
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)

    # Inicializa um repositório Git
    subprocess.run(['git', 'init', '-b', 'main'], check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
    (project_dir / "README.md").write_text("Initial commit", encoding="utf-8")
    subprocess.run(['git', 'add', '.'], check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
    
    assert _get_commit_count(project_dir) == 1

    # Introduz um arquivo com erro de sintaxe
    (project_dir / "broken.py").write_text("def func()\n pass", encoding="utf-8")
    
    # Mock para o runner do doxoade, garantindo que o `check` seja executável
    monkeypatch.setenv("PATH", os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""), prepend=os.pathsep)

    # FLUXO 2: Executar o Comando 'save'
    result = runner.invoke(cli, ['save', 'attempting broken commit'], catch_exceptions=True)

    # FLUXO 3: Validar que o Commit foi Abortado
    assert result.exit_code != 0, "O comando 'save' deveria falhar."
    assert "Commit abortado" in result.output
    
    # A validação mais importante: o número de commits não aumentou.
    assert _get_commit_count(project_dir) == 1, "Um novo commit foi criado indevidamente."
    
# tests/test_save_command.py

def test_save_succeeds_on_clean_code(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade save' cria um commit quando o 'check' passa.
    """
    # FLUXO 1: Preparar um Projeto Git com Alterações
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)

    # Inicializa um repositório Git com um commit inicial
    subprocess.run(['git', 'init', '-b', 'main'], check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
    (project_dir / "README.md").write_text("Initial", encoding="utf-8")
    subprocess.run(['git', 'add', 'README.md'], check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial'], check=True)
    
    assert _get_commit_count(project_dir) == 1

    # Faz uma nova alteração para ser commitada
    (project_dir / "new_file.py").write_text("print('hello')", encoding="utf-8")
    
    # --- Mocking da Verificação de Qualidade ---
    # Simulamos um resultado de 'doxoade check' bem-sucedido
    mock_check_result = MagicMock()
    mock_check_result.returncode = 0
    mock_check_result.stdout = "[OK] Verificação de qualidade concluída."
    # Substituímos a função real por uma que retorna nosso resultado simulado
    monkeypatch.setattr(
        "doxoade.commands.save._run_quality_check",
        lambda logger: (mock_check_result, "")
    )

    # FLUXO 2: Executar o Comando 'save'
    result = runner.invoke(cli, ['save', 'added new file'], catch_exceptions=False)

    # FLUXO 3: Validar que o Commit foi Criado
    assert result.exit_code == 0, f"O comando 'save' deveria ter sucesso. Saída: {result.output}"
    assert "Alterações salvas com sucesso!" in result.output
    
    # A validação final: o número de commits aumentou para 2.
    assert _get_commit_count(project_dir) == 2, "O novo commit não foi criado."