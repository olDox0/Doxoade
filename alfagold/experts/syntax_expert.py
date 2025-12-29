# alfagold/experts/syntax_expert.py

"""
Syntax Expert (Antigo ArquitetoLogico).
Responsável por garantir a integridade gramatical do código gerado.
"""

class SyntaxExpert: # <--- Renomeado de ArquitetoLogico
    def __init__(self):
        self.memoria_variaveis = set()
        self.pilha_parenteses = 0 
        self.estado = "INICIO" 
        self.ultimo_token = ""
        self.assinatura_concluida = False
        
        self.pontuacao = ["(", ")", ":", ",", "."]
        self.keywords = ["def", "return", "if", "else", "with", "open", "as", "pass", "import"]
        
    def reset(self):
        self.__init__()

    def observing(self, token): # Renomeado de 'observar' para inglês técnico no futuro? Mantendo 'observar' por compatibilidade se preferir, ou padronizando.
        # Vamos manter os nomes de métodos compatíveis com a lógica antiga por enquanto
        self.observar(token)

    def observar(self, token):
        token = token.strip()
        if not token: return
        
        if token == "def": 
            self.estado = "NOME"
            self.assinatura_concluida = False
        
        for char in token:
            if char == "(": 
                self.pilha_parenteses += 1
                if self.estado in ["NOME", "ARGS_PRE"]: self.estado = "ARGS"
            elif char == ")": 
                if self.pilha_parenteses > 0: self.pilha_parenteses -= 1
                if self.pilha_parenteses == 0 and self.estado == "ARGS": 
                    self.estado = "TRANSICAO" 
            elif char == ":": 
                if self.estado == "TRANSICAO": 
                    self.estado = "CORPO"
                    self.assinatura_concluida = True

        self.ultimo_token = token

    def validar(self, token):
        token = token.strip()
        if not token: return True, "Espaço"

        if not self.assinatura_concluida:
            if self.estado == "NOME":
                if not token.isidentifier() and "(" not in token: return False, "Nome inválido"
                if any(c in ":.," for c in token): return False, "Pontuação no nome"

        if self.estado == "ARGS":
            if token in self.keywords: return False, "Keyword em argumento"
            last_was_var = self.ultimo_token.isidentifier() and self.ultimo_token not in self.keywords
            if last_was_var:
                if token.isidentifier(): return False, "Variável duplicada"
                if token not in [",", ")"]: return False, "Esperando separador"

        if self.estado == "TRANSICAO":
            if ":" not in token: return False, "Esperando ':'"

        if self.estado == "CORPO":
            if self.ultimo_token == ":" or self.ultimo_token.endswith(":"):
                if token in [".", ",", ")", "]", "}"] or token == "(": return False, "Início de bloco inválido"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        if self.estado == "ARGS":
            if self.ultimo_token.isidentifier() and self.ultimo_token not in self.keywords: return ")"
        if self.estado == "CORPO" and (self.ultimo_token == ":" or self.ultimo_token.endswith(":")): return "with" 
        return None