"""
Neuro-Symbolic Logic Monitor v13.0 (Constraint Enforcer).
Suporta restrições numéricas de argumentos (Aridade Mínima).
"""

class ArquitetoLogico:
    def __init__(self):
        self.memoria_variaveis = set()
        self.variaveis_usadas = set()
        self.pilha_parenteses = 0 
        self.estado = "DEF" 
        self.ultimo_token = ""
        self.complexidade_expressao = 0
        self.min_args = 0 # NOVO: Restrição de aridade
        
        self.keywords = ["def", "return", "if", "else", "elif", "and", "or", "not"]
        self.operadores = ["+", "-", "*", "/", "%", "==", "!=", ">", "<", ">=", "<="]
        self.pontuacao = ["(", ")", ":", ","]
        self.especiais = ["ENDMARKER"]
        
    def reset(self):
        self.__init__()

    def set_constraints(self, min_args=0):
        """Define regras específicas para a tarefa atual."""
        self.min_args = min_args

    @property
    def variaveis_pendentes(self):
        return self.memoria_variaveis - self.variaveis_usadas

    def observar(self, token):
        self.ultimo_token = token
        
        if token == "def": self.estado = "NOME"
        elif self.estado == "NOME" and token not in ["(", "def"]: self.estado = "ARGS_PRE"
        elif token == "(": self.estado = "ARGS"; self.pilha_parenteses += 1
        elif token == ")": 
            self.pilha_parenteses -= 1
            if self.pilha_parenteses == 0: self.estado = "TRANSICAO" 
        elif token == ":": 
            self.estado = "CORPO"
        elif token == "return": 
            self.estado = "RETORNO"
            self.complexidade_expressao = 0
        elif token == "ENDMARKER": self.estado = "FIM"

        if self.estado == "ARGS" and token.isalnum() and token not in self.keywords:
            self.memoria_variaveis.add(token)
            
        if self.estado in ["CORPO", "RETORNO"] and token in self.memoria_variaveis:
            self.variaveis_usadas.add(token)
            
        if self.estado == "RETORNO" and token != "return":
            self.complexidade_expressao += 1

    def validar(self, token):
        # 1. WHITELIST
        eh_conhecido = (
            token in self.keywords or token in self.operadores or
            token in self.pontuacao or token in self.especiais or 
            token in self.memoria_variaveis or token.isdigit() or token == "="
        )
        if self.estado == "NOME": eh_conhecido = token.isalnum()
        if self.estado == "ARGS": eh_conhecido = token.isalnum() or token == ","

        if not eh_conhecido: return False, f"Token desconhecido: '{token}'"

        # 2. REGRAS DE ARIDADE (NOVO)
        if token == ")" and self.estado == "ARGS":
            if len(self.memoria_variaveis) < self.min_args:
                return False, f"Preciso de {self.min_args} argumentos, tenho {len(self.memoria_variaveis)}"

        # 3. REGRAS ESTRUTURAIS
        if self.estado == "ARGS_PRE" and token != "(": return False, "Esperando '('"
        if self.estado == "TRANSICAO" and token != ":": return False, "Esperando ':'"
        if token == ":" and self.estado != "TRANSICAO": return False, "Dois pontos fora de lugar"
        
        # 4. REGRAS DO RETORNO
        if self.estado == "RETORNO":
            if token == "=": return False, "Atribuição no return"
            if token in ["def", "return", "class", "import"]: return False, "Comando ilegal"
            if self.ultimo_token == "return" and token in self.operadores: return False, "Operador após return"
            if token == "ENDMARKER" and self.ultimo_token in self.operadores: return False, "Termina com operador"

        # 5. ADJACÊNCIA
        last_val = (self.ultimo_token.isalnum() and self.ultimo_token not in self.keywords)
        curr_val = (token.isalnum() and token not in self.keywords)
        if (self.estado == "ARGS" or self.estado in ["CORPO", "RETORNO"]) and last_val and curr_val:
             if token not in ["if", "else", "and", "or"]: return False, "Valores adjacentes"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        if self.estado == "CORPO": return "return"
        if self.pilha_parenteses > 0 and self.ultimo_token not in [",", "("]: return ")"
        
        # Sugestão inteligente para argumentos
        if self.estado == "ARGS":
            if len(self.memoria_variaveis) < self.min_args:
                if self.ultimo_token.isalnum(): return ","
        
        if self.estado == "RETORNO":
            if self.variaveis_pendentes:
                if self.ultimo_token in self.operadores: return list(self.variaveis_pendentes)[0]
                if self.ultimo_token == "return": return list(self.variaveis_pendentes)[0]
                return "+"
            elif self.complexidade_expressao >= 1:
                if self.ultimo_token not in self.operadores: return "ENDMARKER"
                
        return None