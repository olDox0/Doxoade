# -*- coding: utf-8 -*-
import pytest
import os
from doxoade.commands.intelligence import (
    InsightVisitor, 
    _extract_todos, 
    _read_file_safely
)
import ast

def test_insight_visitor_extraction():
    """Garante que o Visitor extrai classes e funções corretamente."""
    code = """
class MinhaClasse:
    def meu_metodo(self, a):
        return a

def minha_funcao(x, y=10):
    # TODO: teste
    return x + y
    """
    tree = ast.parse(code)
    visitor = InsightVisitor()
    visitor.visit(tree)
    
    assert len(visitor.classes) == 1
    assert visitor.classes[0]['name'] == 'MinhaClasse'
    assert 'meu_metodo' in visitor.classes[0]['methods']
    
    assert len(visitor.functions) == 2 # Método + Função Global
    assert any(f['name'] == 'minha_funcao' for f in visitor.functions)

def test_todo_extraction_regex():
    """Valida a detecção de tags de dívida técnica."""
    content = """
    # TODO: Implementar isso
    x = 10 # FIXME corrigir bug
    # hack: ajuste temporário
    """
    todos = _extract_todos(content)
    tags = [t['tag'] for t in todos]
    
    assert "TODO" in tags
    assert "FIXME" in tags
    assert "HACK" in tags
    assert todos[0]['text'] == "Implementar isso"

def test_read_file_safely_encodings(tmp_path):
    """Testa a resiliência de leitura em diferentes encodings."""
    d = tmp_path / "subdir"
    d.mkdir()
    
    # Criar arquivo em Latin-1
    p = d / "latin.txt"
    p.write_text("texto com acentuação", encoding="latin-1")
    
    content = _read_file_safely(str(p))
    assert "acentuação" in content

def test_complexity_estimation():
    """Verifica se a estimativa de complexidade ciclomática básica funciona."""
    code = """
def complexo(a):
    if a > 10:
        for i in range(a):
            try:
                print(i)
            except:
                pass
    return a
    """
    tree = ast.parse(code)
    visitor = InsightVisitor()
    visitor.visit(tree)
    
    # Complexidade esperada: 1 (base) + 1 (if) + 1 (for) + 1 (except) = 4
    assert visitor.functions[0]['complexity'] == 4