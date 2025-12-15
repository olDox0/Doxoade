# doxoade/neural/logic.py
"""
Neuro-Symbolic Logic Monitor v8.2 (Stability Patch).
Fix: Inicialização de atributos e proibição de keywords em argumentos.
"""

class ArquitetoLogico:
    def __init__(self):
        self.memoria_variaveis = set()
        self.variaveis_usadas = set() # <--- CORREÇÃO DO CRASH
        self.pilha_parenteses = 0 
        self.estado = "DEF" 
        self.ultimo_token = ""
        self.complexidade_expressao = 0
        
        self.keywords = ["def", "return", "if", "else", "elif", "and", "or", "not"]
        self.operadores = ["+", "-", "*", "/", "%", "="]
        self.comparadores = [">", "<", "==", "!=", ">=", "<="]
        self.pontuacao = ["(", ")", ":", ","]
        self.especiais = ["ENDMARKER"]
        
    def reset(self):
        self.__init__()

    @property
    def variaveis_pendentes(self):
        # Retorna variáveis definidas que ainda não foram usadas no corpo
        return self.memoria_variaveis - self.variaveis_usadas

    def observar(self, token):
        self.ultimo_token = token
        
        if token == "def": self.estado = "NOME"
        elif self.estado == "NOME" and token not in ["(", "def"]: self.estado = "ARGS_PRE"
        elif token == "(": self.estado = "ARGS"; self.pilha_parenteses += 1
        elif token == ")": 
            self.pilha_parenteses -= 1
            if self.pilha_parenteses == 0: self.estado = "TRANSICAO" 
        elif token == ":": self.estado = "CORPO"
        elif token == "return": 
            self.estado = "RETORNO"
            self.complexidade_expressao = 0
            # Não limpamos variaveis_usadas aqui para manter o histórico do corpo todo se precisar
        elif token == "ENDMARKER": self.estado = "FIM"

        if self.estado == "ARGS" and token.isalnum() and token not in self.keywords:
            self.memoria_variaveis.add(token)
            
        if self.estado in ["CORPO", "RETORNO"] and token in self.memoria_variaveis:
            self.variaveis_usadas.add(token)
            
        if self.estado == "RETORNO" and token != "return":
            self.complexidade_expressao += 1

    def validar(self, token):
        # 1. WHITELIST CHECK
        eh_conhecido = (
            token in self.keywords or token in self.operadores or
            token in self.comparadores or token in self.pontuacao or
            token in self.especiais or token in self.memoria_variaveis or
            token.isdigit()
        )
        if self.estado == "NOME": eh_conhecido = token.isalnum()
        if self.estado == "ARGS": eh_conhecido = token.isalnum() or token == ","

        if not eh_conhecido: return False, f"Token desconhecido: '{token}'"

        # 2. Regras de Estado
        if self.estado == "ARGS_PRE" and token != "(": return False, "Esperando '('"
        if token == ":" and self.estado != "TRANSICAO" and self.estado != "CORPO": return False, "Dois pontos fora de lugar"
        
        # Correção: Proibir keywords nos argumentos (ex: def soma(else, if))
        if self.estado == "ARGS" and token in self.keywords:
            return False, f"Keyword '{token}' não pode ser nome de variável"

        # 3. Regra de Adjacência de Valores
        last_val = (self.ultimo_token.isalnum() and self.ultimo_token not in self.keywords)
        curr_val = (token.isalnum() and token not in self.keywords)
        
        if (self.estado == "ARGS" or self.estado in ["CORPO", "RETORNO"]) and last_val and curr_val:
             if token not in ["if", "else", "and", "or"]:
                 return False, "Valores adjacentes (falta operador ou vírgula)"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        if self.estado == "CORPO": return "return"
        if self.pilha_parenteses > 0 and self.ultimo_token not in [",", "("]: return ")"
        
        if self.estado == "RETORNO":
            # Tenta usar variáveis esquecidas
            pendentes = list(self.variaveis_pendentes)
            if pendentes:
                if self.ultimo_token in self.operadores:
                    return pendentes[0]
                return "+"
            # Se já usou tudo, tenta finalizar
            elif self.complexidade_expressao >= 1:
                if self.ultimo_token not in self.operadores:
                    return "ENDMARKER"
                
        return None
