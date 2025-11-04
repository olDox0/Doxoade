# tests/test_utils_commands.py
import os
import sys
import json
from pathlib import Path
from click.testing import CliRunner

# Garante que o pacote 'doxoade' seja importável
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from doxoade.doxoade import cli

def test_log_command_reads_last_n_lines(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade log -n' lê e exibe o número correto de linhas do log.
    """
    # FLUXO 1: Preparar um Ambiente com um Arquivo de Log Falso
    fake_home = tmp_path
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    
    log_dir = fake_home / ".doxoade"
    log_dir.mkdir()
    log_file = log_dir / "doxoade.log"

    log_entries = [
        {"timestamp": "2025-01-01T10:00:00Z", "command": "command1", "summary": {"errors": 1}},
        {"timestamp": "2025-01-01T11:00:00Z", "command": "command2", "summary": {"errors": 0}},
        {"timestamp": "2025-01-01T12:00:00Z", "command": "command3", "summary": {"errors": 0}},
    ]
    # --- A CORREÇÃO CHAVE ---
    # Usa uma quebra de linha real ('\n') para separar as entradas JSON.
    with open(log_file, "w", encoding="utf-8") as f:
        for entry in log_entries:
            f.write(json.dumps(entry) + '\n')

    # FLUXO 2: Executar o Comando 'log'
    result = runner.invoke(cli, ['log', '-n', '2'], catch_exceptions=False)

    # FLUXO 3: Validar a Saída
    assert result.exit_code == 0, f"O comando log falhou. Saída: {result.output}"
    
    assert "Comando: command2" in result.output
    assert "Comando: command3" in result.output
    assert "Comando: command1" not in result.output

def test_mk_creates_files_and_folders(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade mk' cria arquivos e pastas, incluindo a expansão de chaves.
    """
    # FLUXO 1: Preparar o Ambiente
    base_dir = tmp_path
    monkeypatch.chdir(base_dir)

    # FLUXO 2: Executar o Comando
    result = runner.invoke(cli, ['mk', 'src/', 'src/{models.py,views.py}'], catch_exceptions=False)

    # FLUXO 3: Validar a Estrutura Criada
    assert result.exit_code == 0, f"O comando mk falhou. Saída: {result.output}"
    assert (base_dir / "src").is_dir()
    assert (base_dir / "src" / "models.py").is_file()
    assert (base_dir / "src" / "views.py").is_file()

def test_create_pipeline_writes_file(runner: CliRunner, tmp_path, monkeypatch):
    """
    Valida se 'doxoade create-pipeline' cria o arquivo com o conteúdo correto.
    """
    # FLUXO 1: Preparar o Ambiente
    base_dir = tmp_path
    monkeypatch.chdir(base_dir)
    filename = "test_pipeline.dox"
    commands = ['"doxoade check ."', '"doxoade health"']

    # FLUXO 2: Executar o Comando
    result = runner.invoke(cli, ['create-pipeline', filename] + commands, catch_exceptions=False)

    # FLUXO 3: Validar o Arquivo Criado
    assert result.exit_code == 0, f"O comando create-pipeline falhou. Saída: {result.output}"
    
    pipeline_file = base_dir / filename
    assert pipeline_file.is_file()
    
    content = pipeline_file.read_text(encoding="utf-8")
    assert "doxoade check ." in content
    assert "doxoade health" in content