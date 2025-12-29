"""
DOXOADE VECTOR MEMORY.
Implementação de Banco de Dados Vetorial usando apenas NumPy.
Permite busca semântica (por significado) em vez de exata.
"""
import numpy as np
import json
import os
import pickle
from doxoade.neural.core import load_json, save_json

MEMORY_PATH = os.path.expanduser("~/.doxoade/vector_db.json")

class VectorDB:
    def __init__(self):
        self.vectors = [] # Lista de vetores (numpy arrays)
        self.payloads = [] # Lista de dados (código, metadados)
        self.load()

    def _cosine_similarity(self, v1, v2):
        """Calcula o ângulo entre dois vetores."""
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        return dot_product / (norm_v1 * norm_v2 + 1e-8)

    def add(self, vector, payload):
        """Adiciona uma memória."""
        # Normaliza o vetor para otimizar busca futura (L2 norm)
        # vector = vector / (np.linalg.norm(vector) + 1e-8)
        self.vectors.append(vector.tolist()) # Salva como lista para JSON
        self.payloads.append(payload)
        self.save()

    def search(self, query_vector, limit=1, threshold=0.85):
        """Busca o vizinho mais próximo (Nearest Neighbor)."""
        if not self.vectors: return None

        query_vector = np.array(query_vector)
        best_score = -1.0
        best_payload = None

        # Busca Linear (Rápida o suficiente para < 100k itens)
        for i, vec in enumerate(self.vectors):
            db_vec = np.array(vec)
            score = self._cosine_similarity(query_vector, db_vec)
            
            if score > best_score:
                best_score = score
                best_payload = self.payloads[i]

        if best_score >= threshold:
            print(f"   🧠 Memória Semântica: Match {best_score:.2f}")
            return best_payload
            
        return None

    def save(self):
        data = {"vectors": self.vectors, "payloads": self.payloads}
        save_json(data, MEMORY_PATH)

    def load(self):
        if os.path.exists(MEMORY_PATH):
            try:
                data = load_json(MEMORY_PATH)
                self.vectors = data["vectors"]
                self.payloads = data["payloads"]
            except Exception: pass