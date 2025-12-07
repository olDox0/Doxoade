# doxoade/indexer/__init__.py
"""
Sistema de Indexação de Código Python.

Módulos:
- code_indexer: Indexação via AST
- text_matcher: Normalização e fuzzy matching
- call_graph: Análise de dependências
- cache: Persistência em SQLite

Versão: 2.0
"""

from .code_indexer import CodeIndexer
from .text_matcher import TextMatcher
from .cache import IndexCache

__all__ = ['CodeIndexer', 'TextMatcher', 'IndexCache']
