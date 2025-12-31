# -*- coding: utf-8 -*-
import pytest
import os
import json
from click.testing import CliRunner
from doxoade.cli import cli

def test_style_check_long_function():
    """Garante que o style detecta funções que violam o MPoT-4 (tamanho)."""
    runner = CliRunner()
    
    # Criar um arquivo com uma função gigante (> 60 linhas)
    bad_code = "def giant_function():\n" + "    print('line')\n" * 70
    
    with runner.isolated_filesystem():
        with open("heavy.py", "w") as f:
            f.write(bad_code)
        
        # O comando deve rodar e encontrar o aviso
        result = runner.invoke(cli, ['style', 'heavy.py'])
        assert result.exit_code == 0
        assert "tamanho" in result.output.lower() or "linhas" in result.output.lower()

def test_style_documentation_mode():
    """Verifica se o modo --comment ignora lógica e foca em docstrings."""
    runner = CliRunner()
    
    # Código sem docstring
    no_doc_code = "def undocumented():\n    return 1"
    
    with runner.isolated_filesystem():
        with open("no_doc.py", "w") as f:
            f.write(no_doc_code)
            
        result = runner.invoke(cli, ['style', 'no_doc.py', '--comment'])
        assert result.exit_code == 0
        assert "documentação" in result.output.lower() or "docstring" in result.output.lower()

def test_style_valid_code():
    """Garante que código limpo retorna [OK]."""
    runner = CliRunner()
    clean_code = '"""Módulo limpo."""\ndef small():\n    """Doc."""\n    return True'
    
    with runner.isolated_filesystem():
        with open("clean.py", "w") as f:
            f.write(clean_code)
            
        result = runner.invoke(cli, ['style', 'clean.py'])
        assert result.exit_code == 0
        assert "OK" in result.output