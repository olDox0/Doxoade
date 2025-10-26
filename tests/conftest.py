# tests/conftest.py
import pytest
from click.testing import CliRunner

@pytest.fixture(scope='module')
def runner():
    """
    Fornece uma instância de CliRunner configurada para testes.
    
    echo_stdin=False impede que a saída seja truncada, garantindo
    que possamos fazer asserções no conteúdo completo do output.
    """
    yield CliRunner(echo_stdin=False)