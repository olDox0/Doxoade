"""
Neuro-Symbolic Logic Monitor v11.1 (The Dictator).
Força 'return' imediatamente após a definição da função.
"""

class ArquitetoLogico:
    def __init__(self):
        self.memoria_variaveis = set()
        self.variaveis_usadas = set()
        self.pilha_parenteses = 0 
        self.estado = "DEF" 
        self.ultimo_token = ""
        self.complexidade_expressao = 0
        
        self.keywords = ["def", "return", "if", "else", "elif", "and", "or", "not"]
        self.operadores = ["+", "-", "*", "/", "%", "==", "!=", ">", "<", ">=", "<="]
        self.pontuacao = ["(", ")", ":", ","]
        self.especiais = ["ENDMARKER"]
        
    def reset(self):
        self.__init__()

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
        # 1. REGRA DO DITADOR (CORPO)
        # Após ':', só aceitamos 'return'. Nada de variáveis soltas.
        if self.estado == "CORPO":
            if token != "return": return False, "Esperando 'return'"
            return True, "OK"

        # 2. Whitelist Básica
        eh_conhecido = (
            token in self.keywords or token in self.operadores or
            token in self.pontuacao or token in self.especiais or 
            token in self.memoria_variaveis or token.isdigit() or token == "="
        )
        if self.estado == "NOME": eh_conhecido = token.isalnum()
        if self.estado == "ARGS": eh_conhecido = token.isalnum() or token == ","

        if not eh_conhecido: return False, f"Token desconhecido: '{token}'"

        # 3. Regras de Estado
        if self.estado == "ARGS_PRE" and token != "(": return False, "Esperando '('"
        if self.estado == "TRANSICAO" and token != ":": return False, "Esperando ':'"
        if token == ":" and self.estado != "TRANSICAO": return False, "Dois pontos fora de lugar"
        if self.estado == "ARGS" and token in self.keywords: return False, "Keyword em args"

        # 4. Regras do Retorno
        if self.estado == "RETORNO":
            if token == "=": return False, "Atribuição no return"
            if token in ["def", "return", "class", "import"]: return False, "Comando ilegal"
            
            # Anti-Alucinação Estrita
            is_alpha = token.isalnum() and not token.isdigit()
            if is_alpha and token not in self.memoria_variaveis and token not in ["if", "else", "and", "or"]:
                return False, f"Alucinação: '{token}' não existe"

        # 5. Adjacência
        last_val = (self.ultimo_token.isalnum() and self.ultimo_token not in self.keywords)
        curr_val = (token.isalnum() and token not in self.keywords)
        
        if (self.estado == "ARGS" or self.estado in ["RETORNO"]) and last_val and curr_val:
             if token not in ["if", "else"]:
                 return False, "Valores adjacentes"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        
        # AQUI: Se estiver no corpo, force o return
        if self.estado == "CORPO": return "return"
        
        if self.pilha_parenteses > 0 and self.ultimo_token not in [",", "("]: return ")"
        
        if self.estado == "RETORNO":
            if self.variaveis_pendentes:
                if self.ultimo_token in self.operadores:
                    return list(self.variaveis_pendentes)[0]
                if self.ultimo_token == "return":
                    return list(self.variaveis_pendentes)[0]
                return "+"
            elif self.complexidade_expressao >= 1:
                if self.ultimo_token not in self.operadores:
                    return "ENDMARKER"
                
        return None
