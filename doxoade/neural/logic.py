# doxoade/neural/logic.py
"""
Neuro-Symbolic Logic Monitor (The Architect).
Aplica regras gramaticais estritas sobre a saída da rede neural para evitar alucinações.
"""

class ArquitetoLogico:
    def __init__(self):
        self.memoria_variaveis = set()
        self.pilha_parenteses = 0 
        self.estado = "DEF" 
        self.ultimo_token = ""
        # Whitelist de tokens seguros que não requerem validação de existência
        self.whitelist = ["def", "return", "(", ")", ":", ",", "+", "-", "*", "/", "%", "="]
        
    def reset(self):
        self.__init__()

    def observar(self, token):
        """Atualiza o estado da máquina baseado no que foi escrito."""
        self.ultimo_token = token
        
        # Gestão de Variáveis (Aprendizado em Tempo Real)
        if self.estado == "ARGS" and token.isalnum() and token != "def":
            self.memoria_variaveis.add(token)
            
        # Máquina de Estados
        if token == "def": self.estado = "NOME"
        elif self.estado == "NOME" and token not in ["(", "def"]: self.estado = "ARGS_PRE"
        elif token == "(": 
            self.estado = "ARGS"
            self.pilha_parenteses += 1
        elif token == ")": 
            self.pilha_parenteses -= 1
            if self.pilha_parenteses == 0 and self.estado == "ARGS":
                self.estado = "TRANSICAO" 
        elif token == ":": self.estado = "CORPO"
        elif token == "return": self.estado = "RETORNO"
        
    def validar(self, token):
        """Retorna (True/False, Motivo)."""
        is_op = token in ["+", "-", "*", "/", "%", "="]
        is_var = token in self.memoria_variaveis
        is_num = token.isdigit()
        
        # --- NOVA REGRA: ADJACÊNCIA DE VALORES ---
        # Se o último foi Variável ou Número, o atual NÃO PODE ser Variável ou Número
        # (Exceto se estivermos definindo argumentos com vírgula)
        last_was_value = (self.ultimo_token in self.memoria_variaveis) or self.ultimo_token.isdigit()
        curr_is_value = is_var or is_num

        if self.estado == "CORPO" and last_was_value and curr_is_value:
            return False, "Sintaxe: Variável seguida de Variável sem operador"

        # Regra do Fim (<EOS>)
        if token == "<EOS>":
            if self.pilha_parenteses > 0: return False, "Pilha aberta"
            if self.estado != "RETORNO": return False, "Fim prematuro"
            return True, "FIM"

        # 1. Regra da Pilha
        if token == "(":
            if self.ultimo_token.isalnum() and self.ultimo_token not in ["if", "return", "def"]: return False, "Chamada func inválida"
        
        if token == ")":
            if self.pilha_parenteses <= 0: return False, "Pilha vazia"
            if self.ultimo_token in ["(", ",", "+", "-", "*", "/"]: return False, "Fechamento prematuro"

        # 2. Regra da Transição
        if token == ":":
            if self.pilha_parenteses > 0: return False, "Parenteses abertos"
            if self.estado != "TRANSICAO": return False, "Lugar errado para :"

        # 3. Regra de Operadores
        if is_op:
            if self.ultimo_token in ["(", "return", ",", "def", ":"]: return False, "Sem operando esquerdo"
            if self.ultimo_token in ["+", "-", "*", "/", "%"]: return False, "Operador duplicado"

        # 4. Regra de Variáveis (Anti-Alucinação)
        if self.estado in ["CORPO", "RETORNO"] and token.isalnum():
            if token not in ["return", "def"] and not token.isdigit():
                if not is_var: return False, f"Alucinação: {token} desconhecido"

        return True, "OK"