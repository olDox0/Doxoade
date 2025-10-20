import pytest
from click.testing import CliRunner

# Importamos o ponto de entrada principal da nossa aplicação
from doxoade.doxoade import cli

# O "fixture" é uma função de setup que o pytest executa antes de cada teste.
# Aqui, ele cria uma instância do nosso "runner" de testes.
@pytest.fixture
def runner():
    return CliRunner()

def test_cli_invocation_help(runner):
    """
    Testa se a chamada 'doxoade --help' funciona e termina com sucesso.
    """
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output

def test_doctor_invocation_help(runner):
    """
    Testa se o comando 'doxoade doctor --help' funciona.
    Isso prova que o plugin foi carregado corretamente.
    """
    result = runner.invoke(cli, ['doctor', '--help'])
    assert result.exit_code == 0
    assert "Executa um diagnóstico e reparo do ambiente do projeto." in result.output

def test_tutorial_group_invocation_help(runner):
    """
    Testa se o grupo de comandos 'tutorial' foi carregado
    e responde ao --help.
    """
    result = runner.invoke(cli, ['tutorial', '--help'])
    assert result.exit_code == 0
    assert "Comandos para aprender o workflow do doxoade." in result.output