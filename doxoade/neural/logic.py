# doxoade/neural/logic.py
from .patterns import match_pattern

class ArquitetoLogico:
    def __init__(self):
        self.history = [] # Memória de curto prazo dos tokens
        self.suggestion = None
        
    def reset(self):
        self.history = []
        self.suggestion = None

    def set_constraints(self, min_args=0):
        pass # Não usado nesta versão focada em padrão

    def observar(self, token):
        token = token.strip()
        if not token: return
        self.history.append(token)
        
        # Limita histórico para não estourar memória (contexto local)
        if len(self.history) > 20:
            self.history.pop(0)

    def validar(self, token):
        # A validação agora é proativa via sugerir_correcao
        # Se houver uma sugestão forte do padrão, bloqueamos qualquer outra coisa
        expected = match_pattern(self.history)
        
        if expected:
            # Se o padrão exige um token estrutural específico (ex: ':', '(', 'as')
            if expected not in ["<ID>", "<ARGS>", "<STR>", "<EXPR>"]:
                # Se o token atual não contém o esperado
                if expected not in token:
                    return False, f"Quebra de Padrão: Esperava '{expected}'"
        
        return True, "OK"

    def sugerir_correcao(self):
        """
        Usa o Sistema de Espelho para prever o próximo token estrutural.
        """
        expected = match_pattern(self.history)
        
        if expected:
            # Se o próximo é um token fixo (não genérico), sugere ele!
            if expected not in ["<ID>", "<ARGS>", "<STR>", "<EXPR>"]:
                return expected
            
            # Se for genérico, podemos dar uma dica (opcional, mas o modelo gera bem nomes)
            if expected == "<ARGS>" and self.history[-1] == "(":
                # Se acabou de abrir parenteses, não sugere nada, deixa gerar var
                pass
                
        return None