# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/crash_signatures.py
""" Assinaturas de Falha e Sinais de Hardware (Lazarus Knowledge Base). """

# NTSTATUS Sinais do Windows (Hardware)
WIN_SIGNALS = {
  0xc0000005: ("AccessViolation",   "Ponteiro Inválido: Tentativa ilegal de acessar RAM."),
  0xc0000094: ("DivideByZero",      "Erro Aritmético: Divisão por zero detectada."),
  0xc0000409: ("StackBufferOverrun","Stack Smashing: integridade da pilha de execução foi destruída."),
  0xc00000fd: ("StackOverflow",     "pilha de recursão explodiu."),
}
# Dicionário de Exceções Python
PYTHON_EXCEPTIONS = {
  "ZeroDivisionError":  ("Erro Aritmético",      "Divisão por zero detectada na lógica Python."),
  "UnboundLocalError":  ("Escopo Inválido",      "Tentativa de acessar variável local antes de sua atribuição."),
  "NameError":          ("Símbolo Indefinido",   "Uso de variável ou função que não existe."),
  "TypeError":          ("Incompatibilidade",    "Operação entre tipos incompatíveis."),
  "ModuleNotFoundError":("Dependência Ausente",  "Sistema tentou carregar módulo não está instalado."),
  "SyntaxError":        ("Violação de Gramática","Código Python possui erro de escrita que impede a execução."),
  "ValueError":         ("Valor Inválido",       "Função recebeu argumento com o tipo correto, mas valor inapropriado."),
  "ImportError":        ("Falha de Importação",  "Não foi possível importar uma lib vital do sistema."),
  "RecursionError": ("Estouro de Córtex", "Loop infinito de chamadas detectado.")
}
# Assinaturas de Pânico Vulcan/C
NATIVE_LOGIC_PATTERNS = [
  ("CORRUPTION", "HadesSentinel: Memory Corruption","Sistema detectou corrupção de memória."),
  ("CONCURRENCY","ConcurrencyHazard",               "Condição de Corrida detectada."),
  ("OOM", "ArenaOverflow", "Estouro de Arena: Pool de memória Vulcan exaurido.")
]

def get_python_fix_hint(exc_type, message):
    if exc_type == "ModuleNotFoundError" or exc_type == "ImportError":
        if "setuptools" in message:
            return "DICA: O Vulcan exige o setuptools. Rode: 'pip install setuptools'."
        if "Cython" in message:
            return "DICA: O motor de compilação exige Cython. Rode: 'pip install Cython'."
    return None
    
def get_tactical_advice(exc_type, message):
    """Retorna sugestões de correção imediata."""
    msg = message.lower()
    if "access violation" in msg: # Caso 1: Access Violation (O seu erro atual)
        return (
            "• Se o erro ocorre em 'ctypes', verifique se o ponteiro é nulo antes de usar.\n"
            "• Se ocorre em 'vulcan', rode 'doxoade vulcan doctor' para checar a ABI do binário.\n"
            "• Verifique se o buffer de destino tem tamanho suficiente para a operação." )
    if "unboundlocalerror" in exc_type.lower(): # Caso 2: UnboundLocalError (O seu erro anterior)
        return "A variável foi lida antes de ser definida no escopo local. Adicione 'global <var>' ou inicialize-a no topo da função."
    if "recursion" in msg: # Caso 3: Erro de Recursão (Visto no seu Hades Engine)
        return "Loop infinito detectado. Refatore para usar um laço 'while' ou verifique o critério de parada da função."

    if "setuptools" in msg:
        return "RECOMENDAÇÃO: O Vulcan exige o setuptools para compilar C. Rode: 'pip install setuptools'"
    if "cython" in msg:
        return "RECOMENDAÇÃO: Motor de compilação ausente. Rode: 'pip install Cython'"
    if "division by zero" in msg:
        return "RECOMENDAÇÃO: Proteja a operação com 'if divisor != 0:' ou um bloco try/except."

    if "double_free" in msg or "double free" in msg:
        return (
            "• Verifique se a mesma variável está sendo passada para free() em caminhos lógicos diferentes.\n"
            "• DICA: Após o free(ptr), defina 'ptr = NULL;' para evitar liberações duplas acidentais." )

    if "access violation" in msg:
        return "Verifique se o ponteiro foi inicializado ou se o array ultrapassou o tamanho alocado (index out of bounds)."

    return None