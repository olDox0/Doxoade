"""
Neural Adapter v3.0 (Binary Turbo).
Implementa Cache Binário (.npy) e Lazy Loading para treinamento instantâneo.
"""
import sqlite3
import random
import os
import numpy as np
from ..database import get_db_connection
from .codex_gen import gerar_funcao_simples, gerar_funcao_condicional

CACHE_DIR = ".doxoade_cache/neural_data"

class BrainLoader:
    def __init__(self):
        try:
            self.conn = get_db_connection()
            self.cursor = self.conn.cursor()
        except Exception:
            self.conn = None

    def _load_lab_data(self):
        lab_data = []
        pep_file = os.path.join(".dox_lab", "peps_dataset.txt")
        if os.path.exists(pep_file):
            print(f"   📂 Ingerindo dados do Laboratório...")
            with open(pep_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(':', 1)
                    if len(parts) == 2:
                        lab_data.append((parts[0].strip(), parts[1].strip() + " ENDMARKER"))
        return lab_data

    def get_training_data(self):
        dataset = []
        if self.conn:
            try:
                self.cursor.execute("SELECT problem_pattern, solution_template FROM solution_templates WHERE confidence > 0")
                for row in self.cursor.fetchall():
                    pattern = row[0].replace('<VAR>', 'var').replace('<MODULE>', 'mod')
                    dataset.append((pattern, row[1] + " ENDMARKER"))
            except sqlite3.Error: pass

        synthetic = self._generate_synthetic_batch(100) # Aumentei para 100
        lab_data = self._load_lab_data()
        
        return dataset + synthetic + lab_data

    def _generate_synthetic_batch(self, count):
        data = []
        for _ in range(count):
            # 50% chance de ser condicional (if/else), 50% simples
            if random.random() < 0.5:
                full_code = gerar_funcao_condicional()
            else:
                full_code = gerar_funcao_simples()
            
            tokens = full_code.split()
            # Random split para ensinar a completar em qualquer ponto
            if len(tokens) > 3:
                split_point = random.randint(2, len(tokens) - 1)
                inp = " ".join(tokens[:split_point])
                out = " ".join(tokens[split_point:])
                data.append((inp, out + " ENDMARKER"))
            
        return data
