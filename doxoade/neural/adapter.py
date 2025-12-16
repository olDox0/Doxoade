"""
Neural Adapter v5.0 (Curriculum Engine).
Serve dados baseados no nível de dificuldade solicitado.
"""
import sqlite3
import random
import os
from ..database import get_db_connection
from .codex_gen import gerar_sintaxe_basica, gerar_funcao_simples, gerar_funcao_condicional

class BrainLoader:
    def __init__(self):
        try:
            self.conn = get_db_connection()
            self.cursor = self.conn.cursor()
        except Exception:
            self.conn = None

    def get_training_data(self, limit=200, difficulty=1):
        """
        Gera dados baseados no nível de dificuldade (Curriculum Learning).
        """
        print(f"   🎓 Gerando currículo Nível {difficulty} ({limit} amostras)...")
        return self._generate_curriculum_batch(limit, difficulty)

    def _generate_curriculum_batch(self, count, level):
        data = []
        
        for _ in range(count):
            r = random.random()
            
            if level == 1:
                # FASE 1: 100% Sintaxe Básica
                full_code = gerar_sintaxe_basica()
                
            elif level == 2:
                # FASE 2: 20% Sintaxe, 80% Matemática Linear
                if r < 0.2: full_code = gerar_sintaxe_basica()
                else: full_code = gerar_funcao_simples()
                
            elif level >= 3:
                # FASE 3: Mistura Total
                if r < 0.1: full_code = gerar_sintaxe_basica()
                elif r < 0.5: full_code = gerar_funcao_simples()
                else: full_code = gerar_funcao_condicional()
            
            tokens = full_code.split()
            if len(tokens) > 3:
                split_point = random.randint(2, len(tokens) - 1)
                inp = " ".join(tokens[:split_point])
                out = " ".join(tokens[split_point:])
                data.append((inp, out + " ENDMARKER"))
            
        return data
