# Promove o objeto 'cli' do módulo principal para o nível do pacote,
# tornando-o o ponto de entrada principal e resolvendo ambiguidades de importação.
from .doxoade import cli

__all__ = ['cli']