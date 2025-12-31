# -*- coding: utf-8 -*-
import pytest
import os
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from doxoade.cli import cli

@patch('doxoade.commands.save._run_git_command')
def test_save_no_changes(mock_git):
    """Garante que o save avisa quando não há nada para comitar."""
    runner = CliRunner()
    # Mock status vazio
    mock_git.side_effect = ["", ""] 
    
    result = runner.invoke(cli, ['save', 'test commit'])
    assert "Nada para salvar" in result.output

@patch('doxoade.commands.save._run_git_command')
@patch('doxoade.commands.save.run_check_logic')
def test_save_blocks_on_error(mock_check, mock_git):
    """Verifica se o save interrompe o commit quando há erros."""
    runner = CliRunner()
    
    # Mock: Tem mudanças, tem arquivos .py, e o check retorna erro
    mock_git.side_effect = [None, "M main.py", "/root", "/root/main.py"]
    mock_check.return_value = {
        'summary': {'errors': 1, 'critical': 0},
        'findings': []
    }
    
    result = runner.invoke(cli, ['save', 'bad commit'])
    assert result.exit_code == 1
    assert "Qualidade insuficiente" in result.output

def test_template_learning_logic():
    """Valida a extração de templates a partir de mensagens de erro."""
    from doxoade.commands.save import _get_template_for_message
    
    # Caso 1: Erro conhecido
    msg = "'os' imported but unused"
    pattern, template, category = _get_template_for_message(msg)
    assert pattern == "'<MODULE>' imported but unused"
    assert template == "FIX_UNUSED_IMPORT"
    
    # Caso 2: Erro desconhecido (Contrato Gold: Retorna tupla de strings vazias, não None)
    msg_unknown = "Erro bizarro que eu inventei agora"
    res = _get_template_for_message(msg_unknown)
    assert res == ("", "", "") # FIX: Ajustado para o novo contrato de consistência