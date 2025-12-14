# doxoade/neural/adapter.py
"""
Neural Adapter.
Converte a memória bruta do SQLite em alimento para a IA.
"""
import sqlite3
import random
from ..database import get_db_connection

class BrainLoader:
    def __init__(self):
        try:
            self.conn = get_db_connection()
            self.cursor = self.conn.cursor()
        except Exception:
            self.conn = None

    def get_training_data(self):
        """
        Retorna pares (entrada, saida) para treino.
        Combina:
        1. Templates aprendidos (Gênese Simbólica).
        2. Dados sintéticos (Sintaxe Python).
        """
        dataset = []
        
        if self.conn:
            try:
                # Aprende com os templates de solução consolidados
                self.cursor.execute("SELECT problem_pattern, solution_template FROM solution_templates WHERE confidence > 0")
                rows = self.cursor.fetchall()
                for row in rows:
                    # Treina a rede para completar o template
                    # Ex: Input "undefined name" -> Output "REPLACE_WITH_UNDERSCORE"
                    pattern = row[0].replace('<VAR>', 'var').replace('<MODULE>', 'mod')
#                    dataset.append((pattern, row[1]))
                    dataset.append((pattern, row[1] + " ENDMARKER")) 
                    #dataset.append((pattern, row[1] + " <EOS>")) 
            except sqlite3.Error:
                pass

        # Garante dados sintéticos para que o cérebro sempre tenha sintaxe básica
        synthetic = self._generate_synthetic_batch(50)
        return dataset + synthetic

    def _generate_synthetic_batch(self, count):
        data = []
        funcs = ["soma", "sub", "calc", "process", "check"]
        vars_ = ["x", "y", "a", "b", "val", "data"]
        ops = ["+", "-", "*", "/"]
        
        for _ in range(count):
            f = random.choice(funcs)
            v1 = random.choice(vars_)
            v2 = random.choice(vars_)
            while v2 == v1: v2 = random.choice(vars_)
            op = random.choice(ops)
            
            # Input: Início da função
            # Output: Corpo lógico
            full_code = f"def {f} ( {v1} , {v2} ) : return {v1} {op} {v2}"
            
            # Corta em pontos aleatórios para treinar preenchimento (Masked Language Modeling simplificado)
            tokens = full_code.split()
            split_point = random.randint(2, len(tokens) - 1)
            
            inp = " ".join(tokens[:split_point])
            out = " ".join(tokens[split_point:])
            
            data.append((inp, out + " <EOS>"))
            
        return data
