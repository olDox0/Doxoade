"""
Neural Adapter v4.1 (Dynamic Volume).
Permite configurar a quantidade de dados sintéticos gerados.
"""
import sqlite3
import random
import os
from ..database import get_db_connection
from .codex_gen import gerar_funcao_simples, gerar_funcao_condicional

class BrainLoader:
    def __init__(self):
        pass 

    def get_training_data(self, limit=200):
        """
        Gera dados de treino com limite configurável.
        """
        print(f"   🧪 Gerando {limit} exemplos sintéticos de alta pureza...")
        return self._generate_synthetic_batch(limit)

    def _generate_synthetic_batch(self, count):
        data = []
        # Currículo Básico (Garante que sempre existam, independente do count)
        data.append(("def soma ( a , b ) :", "return a + b ENDMARKER"))
        data.append(("def sub ( x , y ) :", "return x - y ENDMARKER"))
        data.append(("def maior ( a , b ) :", "if a > b : return a else : return b ENDMARKER"))
        
        # Se count for muito pequeno, garante pelo menos o básico
        remaining = max(0, count - 3)
        
        for _ in range(remaining):
            if random.random() < 0.4:
                full_code = gerar_funcao_condicional()
            else:
                full_code = gerar_funcao_simples()
            
            tokens = full_code.split()
            if len(tokens) > 4:
                split_point = random.randint(3, len(tokens) - 1)
                inp = " ".join(tokens[:split_point])
                out = " ".join(tokens[split_point:])
                data.append((inp, out + " ENDMARKER"))
            
        return data