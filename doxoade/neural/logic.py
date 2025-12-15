"""
Neuro-Symbolic Logic Monitor v6.0 (Flow Control).
Suporta IF, ELSE e Operadores de Comparação.
"""

class ArquitetoLogico:
    def __init__(self):
        self.memoria_variaveis = set()
        self.pilha_parenteses = 0 
        self.estado = "DEF" 
        self.ultimo_token = ""
        self.complexidade_expressao = 0
        
        self.keywords = ["def", "return", "if", "else"] # Adicionado if/else
        self.operadores = ["+", "-", "*", "/", "%", "="]
        self.comparadores = [">", "<", "==", "!=", ">=", "<="] # Novos
        
    def reset(self):
        self.__init__()

    def observar(self, token):
        self.ultimo_token = token
        
        if token == "def": self.estado = "NOME"
        elif self.estado == "NOME" and token not in ["(", "def"]: self.estado = "ARGS_PRE"
        elif token == "(": self.estado = "ARGS"; self.pilha_parenteses += 1
        elif token == ")": 
            self.pilha_parenteses -= 1
            if self.pilha_parenteses == 0: self.estado = "TRANSICAO" 
        elif token == ":": 
            # Se vier depois de um if/else, continuamos no corpo
            if self.estado != "TRANSICAO": self.estado = "CORPO"
            else: self.estado = "CORPO"
        elif token == "return": 
            self.estado = "RETORNO"
            self.complexidade_expressao = 0
        elif token == "ENDMARKER": self.estado = "FIM"

        if self.estado == "ARGS" and token.isalnum() and token not in self.keywords:
            self.memoria_variaveis.add(token)
            
        if self.estado == "RETORNO" and token != "return":
            self.complexidade_expressao += 1

    def validar(self, token):
        is_op = token in self.operadores
        is_comp = token in self.comparadores
        is_var = token in self.memoria_variaveis
        is_num = token.isdigit()
        is_alpha = token.isalnum() and not is_num
        
        # Permitir IF e ELSE no corpo
        if self.estado == "CORPO":
            if token in ["if", "else", "return"]: return True, "OK"
            if token == ":": return True, "OK" # Para o final do if/else
        
        # Regras de Comparação
        if is_comp:
            if self.ultimo_token not in self.memoria_variaveis and not self.ultimo_token.isdigit():
                return False, "Comparação sem valor à esquerda"

        # Regra de Adjacência (Expandida para aceitar 'if' e 'else')
        last_was_value = (self.ultimo_token in self.memoria_variaveis) or self.ultimo_token.isdigit()
        curr_is_value = is_var or is_num
        
        if self.estado in ["CORPO", "RETORNO"] and last_was_value and curr_is_value:
             # Exceção: "return x if..." (Ternário)
             if token != "if":
                 return False, "Valores adjacentes"

        # Regras Padrão (Mantidas)
        if self.estado == "ARGS_PRE" and token != "(": return False, "Esperando '('"
        if self.estado == "ARGS" and is_var: return False, "Argumento duplicado"
        if token == ")" and self.pilha_parenteses <= 0: return False, "Pilha vazia"
        
        # Anti-Alucinação
        if self.estado in ["CORPO", "RETORNO"] and is_alpha and token not in self.keywords:
            if not is_var and token not in ["if", "else"]: # Permite keywords novas
                return False, f"Alucinação: Variável '{token}' não definida"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        
        # Se travou no corpo, sugere return ou if
        if self.estado == "CORPO": return "return"
        
        if self.pilha_parenteses > 0 and self.ultimo_token not in [",", "("]: return ")"
        if self.estado == "RETORNO" and self.complexidade_expressao >= 1:
            if self.ultimo_token in self.memoria_variaveis or self.ultimo_token.isdigit():
                return "ENDMARKER"
        return None
