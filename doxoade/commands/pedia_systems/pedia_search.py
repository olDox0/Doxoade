# -*- coding: utf-8 -*-
# doxoade/commands/pedia_systems/pedia_search.py
from typing import Dict, List
class PediaSearch:
    """Motor de Busca Semântica Simples (Thoth)."""
    
    def __init__(self, articles_db: Dict):
        self.db = articles_db
    def rank_articles(self, query: str, limit: int = 10) -> List:
        query = query.lower().strip()
        query_words = set(query.split())
        
        results =[]
        for key, art in self.db.items():
            score = 0
            art_title_low = art.title.lower()
            
            # 1. Match Exato (Maior peso)
            if query == key:
                score += 100
            elif query == art_title_low:
                score += 90
            
            # 2. Match Parcial no Título/Chave
            elif query in key or query in art_title_low:
                score += 50
                
            # 3. Match de Palavras no Título
            word_hits = sum(1 for w in query_words if w in art_title_low)
            if word_hits > 0:
                score += (word_hits * 10)
                
            # 4. Match no Conteúdo (Peso menor, mas acumula)
            content_low = art.content.lower()
            if query in content_low:
                score += 20
                
            # Frequência de palavras no conteúdo (Capado para não distorcer)
            content_hits = sum(content_low.count(w) for w in query_words)
            score += min(content_hits * 2, 30)
            
            if score > 0:
                results.append({'article': art, 'score': score})
                
        # Ordena por score descendente
        results.sort(key=lambda x: x, reverse=True)
        return results