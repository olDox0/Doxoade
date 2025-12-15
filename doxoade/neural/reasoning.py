"""
SHERLOCK v4.1 (API Repair).
Restaura métodos de compatibilidade para evitar crash no Agente.
"""
import numpy as np
import os
import pickle
import re

MEMORY_FILE = ".doxoade_bayes.pkl"

class Sherlock:
    def __init__(self):
        # Matriz de Crenças: P(Operador | Intenção)
        self.beliefs = {
            "soma": {"+": 0.9, "*": 0.05, "-": 0.05, "/": 0.0},
            "add":  {"+": 0.9, "*": 0.05, "-": 0.05},
            "sub":  {"-": 0.9, "+": 0.05, "/": 0.05},
            "mult": {"*": 0.9, "+": 0.1, "/": 0.0},
            "div":  {"/": 0.9, "%": 0.1, "-": 0.0},
            "maior": {">": 0.8, ">=": 0.2},
            "generic": {"+": 0.25, "-": 0.25, "*": 0.25, "/": 0.25}
        }
        self.load_memory()

    def load_memory(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, 'rb') as f:
                    saved_beliefs = pickle.load(f)
                    self.beliefs.update(saved_beliefs)
            except: pass

    def save_memory(self):
        with open(MEMORY_FILE, 'wb') as f:
            pickle.dump(self.beliefs, f)

    def get_priors(self, prompt):
        """Retorna as probabilidades dos operadores para este prompt."""
        prompt = prompt.lower()
        intent = "generic"
        for key in self.beliefs:
            if key != "generic" and key in prompt:
                intent = key
                break
        return self.beliefs[intent], intent

    def atualizar_crenca(self, intent, operador_usado, sucesso):
        """Atualização Bayesiana."""
        if intent not in self.beliefs: return
        if operador_usado not in self.beliefs[intent]: return

        current_p = self.beliefs[intent][operador_usado]
        alpha = 0.2 
        
        if sucesso:
            new_p = current_p + alpha * (1.0 - current_p)
        else:
            new_p = current_p * (1.0 - alpha)
            
        self.beliefs[intent][operador_usado] = new_p
        
        # Renormalizar
        total = sum(self.beliefs[intent].values())
        if total > 0:
            for k in self.beliefs[intent]:
                self.beliefs[intent][k] /= total
                
        self.save_memory()

    def analisar_falha(self, codigo, erro_stdout, erro_stderr):
        """Abdução de Erros."""
        if "SyntaxError" in erro_stderr: return "Erro de Sintaxe."
        if "NameError" in erro_stderr:
            m = re.search(r"name '(.+?)' is not defined", erro_stderr)
            if m: return f"Alucinação de variável: '{m.group(1)}'."
            return "Erro de Nome (Variável não definida)."
        if "FALHA_ASSERT" in erro_stdout: return "Lógica incorreta (Erro Bayesiano registrado)."
        if "IndentationError" in erro_stderr: return "Erro de Formatação."
        return "Erro desconhecido."

    def verificar_analogia(self, codigo_gerado, requisitos_ignorados=None):
        """
        Método de Compatibilidade (Legacy Support).
        O Agente v9 chama isso esperando (Bool, Msg).
        """
        # Verificação básica de sanidade
        if "return" in codigo_gerado:
            # Não permite operadores duplicados grosseiros
            if "+ +" in codigo_gerado or "- -" in codigo_gerado:
                return False, "Operadores duplicados adjacentes"
            
            # Se a função for muito curta e tiver return vazio
            if codigo_gerado.strip().endswith("return"):
                return False, "Return vazio"

        return True, "Estrutura plausível"

    def verificar_coerencia(self, codigo, priors):
        ops_in_code = [op for op in ["+", "-", "*", "/", ">", "<"] if f" {op} " in codigo]
        if not ops_in_code:
            if max(priors.values()) > 0.5:
                 return False, "Código não contém operações lógicas esperadas."
        return True, "Probabilidade OK"