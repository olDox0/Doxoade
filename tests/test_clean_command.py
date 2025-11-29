# tests/test_clean_command.py
import os
import sys
from click.testing import CliRunner

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.cli import cli

def test_clean_removes_artifacts(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade clean --force' remove os artefatos de build e cache.
    """
    # FLUXO 1: Preparar um Projeto "Sujo"
    project_dir = tmp_path
    monkeypatch.chdir(project_dir)

    # Cria artefatos de build e cache
    pycache_dir = project_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "test.pyc").touch()

    build_dir = project_dir / "build"
    build_dir.mkdir()
    (build_dir / "artifact.bin").touch()

    dist_dir = project_dir / "dist"
    dist_dir.mkdir()
    (dist_dir / "package.whl").touch()

    # Cria um arquivo que NÃO deve ser removido
    (project_dir / "main.py").touch()
    
    # FLUXO 2: Executar o Comando 'clean --force'
    result = runner.invoke(cli, ['clean', '--force'], catch_exceptions=False)

    # FLUXO 3: Validar que a Limpeza foi Feita
    assert result.exit_code == 0, f"O comando clean falhou. Saída: {result.output}"
    
    assert not pycache_dir.exists(), "O diretório __pycache__ não foi removido."
    assert not build_dir.exists(), "O diretório build/ não foi removido."
    assert not dist_dir.exists(), "O diretório dist/ não foi removido."
    assert (project_dir / "main.py").exists(), "O comando clean removeu um arquivo-fonte indevidamente."