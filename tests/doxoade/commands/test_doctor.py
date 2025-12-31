# -*- coding: utf-8 -*-
import pytest
import sys
from doxoade.commands.doctor import _verify_environment, detect_windows_store_alias

def test_verify_environment_no_venv(tmp_path):
    """Garante que o doctor detecta quando o venv não existe."""
    res = _verify_environment(str(tmp_path))
    assert res['status'] == 'error'
    assert 'não encontrado' in res['message'].lower()

def test_detect_windows_store_alias_fake():
    """Valida que o detector de alias não quebra em outros sistemas."""
    if sys.platform != "win32":
        assert detect_windows_store_alias() is False
    else:
        # Apenas garante que a função retorna um booleano no Windows
        assert isinstance(detect_windows_store_alias(), bool)

def test_gitignore_logic_repair(tmp_path):
    """Verifica se o doctor reorganiza regras de negação no gitignore com encoding correto."""
    from doxoade.commands.doctor import _verify_gitignore_logic
    from doxoade.tools.logger import ExecutionLogger

    git_file = tmp_path / ".gitignore"
    # Escreve com encoding explícito
    git_file.write_text("!excecao.txt\n*.log\n/venv/", encoding="utf-8")
    
    with ExecutionLogger('test', str(tmp_path), {}) as logger:
        _verify_gitignore_logic(str(tmp_path), logger)
    
    # LER com encoding explícito utf-8 para evitar mangling no Windows
    content = git_file.read_text(encoding="utf-8")
    lines = content.strip().splitlines()
    
    # A regra de negação deve ter ido para o final
    assert lines[-1] == "!excecao.txt"
    assert "Exceções" in content # Agora o match de string vai funcionar