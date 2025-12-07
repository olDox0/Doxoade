# doxoade/indexer/text_matcher.py
"""
Matcher de Texto Inteligente.

Responsabilidades:
- Normalização de termos (plural/singular, variações)
- Fuzzy matching para correção de typos
- Mapeamento de sinônimos programáticos

Filosofia MPoT:
- Métodos estáticos (sem estado)
- Assertions em validações
- Contratos claros
"""

from typing import Set
from difflib import SequenceMatcher


class TextMatcher:
    """
    Matcher de texto com fuzzy matching e normalização.
    
    Exemplos:
        # Normalização
        variations = TextMatcher.normalize_term('post-mortems')
        # {'postmortems', 'post mortems', 'post_mortems', ...}
        
        # Fuzzy matching
        is_similar = TextMatcher.fuzzy_match('excution', 'execution')
        # True (similaridade > 0.6)
        
        # Match com normalização
        found = TextMatcher.match_text('database', 'conectando ao db...')
        # True ('db' é sinônimo de 'database')
    """
    
    # Mapa de sinônimos programáticos
    NORMALIZATIONS = {
        'postmortems': ['post-mortems', 'postmortem', 'post_mortems'],
        'database': ['db', 'banco', 'bd'],
        'function': ['func', 'funcao', 'função'],
        'class': ['classe'],
        'error': ['erro', 'exception'],
    }
    
    @staticmethod
    def normalize_term(term: str) -> Set[str]:
        """
        Gera variações normalizadas de um termo.
        
        Args:
            term: Termo a normalizar
        
        Returns:
            Set com termo original + variações
        
        Raises:
            AssertionError: Se term estiver vazio
        """
        assert term, "Termo não pode estar vazio"
        
        variations = {term.lower()}
        
        # Remove hífens e underscores
        variations.add(term.replace('-', '').replace('_', ''))
        
        # Substitui por espaços
        variations.add(term.replace('-', ' ').replace('_', ' '))
        
        # Adiciona sinônimos
        term_lower = term.lower()
        for canonical, aliases in TextMatcher.NORMALIZATIONS.items():
            if term_lower == canonical or term_lower in aliases:
                variations.add(canonical)
                variations.update(aliases)
        
        return variations
    
    @staticmethod
    def fuzzy_match(query: str, target: str, threshold: float = 0.6) -> bool:
        """
        Verifica se query é similar a target.
        
        Args:
            query: Termo buscado
            target: Termo alvo
            threshold: Similaridade mínima (0.0 a 1.0)
        
        Returns:
            True se similaridade >= threshold
        
        Raises:
            AssertionError: Se parâmetros inválidos
        """
        assert query and target, "Query e target não podem estar vazios"
        assert 0.0 <= threshold <= 1.0, "Threshold deve estar entre 0.0 e 1.0"
        
        ratio = SequenceMatcher(None, query.lower(), target.lower()).ratio()
        return ratio >= threshold
    
    @staticmethod
    def match_text(query: str, text: str, fuzzy: bool = False) -> bool:
        """
        Verifica se query está presente em text.
        
        Estratégia:
        1. Normaliza query (gera variações)
        2. Busca match exato nas variações
        3. Se fuzzy=True, tenta fuzzy match em cada palavra
        
        Args:
            query: Termo buscado
            text: Texto onde buscar
            fuzzy: Se True, usa fuzzy matching
        
        Returns:
            True se houver match
        """
        assert query is not None and text is not None, "Query e text não podem ser None"
        
        if not query or not text:
            return False
        
        # Match exato (após normalização)
        query_variations = TextMatcher.normalize_term(query)
        text_lower = text.lower()
        
        for variation in query_variations:
            if variation in text_lower:
                return True
        
        # Fuzzy match (opcional)
        if fuzzy:
            words = text_lower.split()
            for word in words:
                if TextMatcher.fuzzy_match(query, word):
                    return True
        
        return False