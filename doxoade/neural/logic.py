# doxoade/neural/logic.py
"""
Neuro-Symbolic Logic Monitor v12.0 (The Firewall).
Bloqueio total de sintaxe inválida em expressões matemáticas.
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
            if self.estado == "TRANSICAO" or self.estado == "ARGS": self.estado = "CORPO"
            else: self.estado = "CORPO"
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
        # 1. WHITELIST BÁSICA
        eh_conhecido = (
            token in self.keywords or token in self.operadores or
            token in self.pontuacao or token in self.especiais or 
            token in self.memoria_variaveis or token.isdigit() or token == "="
        )
        if self.estado == "NOME": eh_conhecido = token.isalnum()
        if self.estado == "ARGS": eh_conhecido = token.isalnum() or token == ","

        if not eh_conhecido: return False, f"Token desconhecido: '{token}'"

        # 2. REGRAS ESTRUTURAIS RÍGIDAS
        if self.estado == "ARGS_PRE" and token != "(": return False, "Esperando '('"
        if self.estado == "TRANSICAO" and token != ":": return False, "Esperando ':'"
        
        # 3. REGRAS DO CORPO/RETORNO (Onde estava falhando)
        if self.estado == "RETORNO":
            # Não pode fechar parenteses se não abriu (evita 'return )')
            if token == ")" and self.pilha_parenteses <= 0: return False, "Fecha parenteses sem abrir"
            
            # Não pode começar expressão com operador ou pontuação (exceto '(')
            if self.ultimo_token == "return":
                if token in self.operadores or token in [")", ":", ","]:
                    return False, "Operador/Pontuação após return"
            
            # Não pode ter dois operadores seguidos (evita '+ /')
            if self.ultimo_token in self.operadores and token in self.operadores:
                return False, "Operadores adjacentes"

            # Não pode ter variável seguida de variável (evita 'a b')
            if (self.ultimo_token in self.memoria_variaveis or self.ultimo_token.isdigit()) and \
               (token in self.memoria_variaveis or token.isdigit()):
                return False, "Variáveis adjacentes"

        # 4. Regras Gerais
        if token == ":" and self.estado != "TRANSICAO" and self.estado != "CORPO": return False, "Dois pontos perdido"
        if self.estado == "ARGS" and token in self.keywords: return False, "Keyword em args"

        return True, "OK"

    def sugerir_correcao(self):
        if self.estado == "ARGS_PRE": return "("
        if self.estado == "TRANSICAO": return ":"
        if self.estado == "CORPO": return "return"
        if self.pilha_parenteses > 0 and self.ultimo_token not in [",", "("]: return ")"
        
        if self.estado == "RETORNO":
            # Se acabou de dar return, PRECISA de uma variável
            if self.ultimo_token == "return":
                 if self.memoria_variaveis: return list(self.memoria_variaveis)[0]
            
            # Se acabou de dar operador, PRECISA de uma variável
            if self.ultimo_token in self.operadores:
                 # Pega uma pendente ou a primeira
                 if self.variaveis_pendentes: return list(self.variaveis_pendentes)[0]
                 if self.memoria_variaveis: return list(self.memoria_variaveis)[0]
            
            # Se acabou de dar variável, PRECISA de operador ou FIM
            if self.ultimo_token in self.memoria_variaveis:
                 if self.variaveis_pendentes: return "+" # Operador padrão
                 return "ENDMARKER"
                
        return None