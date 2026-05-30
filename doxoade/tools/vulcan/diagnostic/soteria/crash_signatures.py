# -*- coding: utf-8 -*-
# doxoade/tools/vulcan/diagnostic/soteria/crash_signatures.py
""" Assinaturas de Falha e Sinais de Hardware (Lazarus Knowledge Base). """

# NTSTATUS Sinais do Windows
WIN_SIGNALS = {
    0xc0000005: ("AccessViolation", "Ponteiro Inválido: Tentativa ilegal de acessar a RAM."),
    0xc0000094: ("DivideByZero", "Erro Aritmético: Divisão por zero no hardware."),
    0xc0000409: ("StackBufferOverrun", "Stack Smashing: Integridade da pilha destruída."),
    0xc00000fd: ("StackOverflow", "Recursão Infinita: A pilha de execução explodiu.")
}

# Assinaturas Python
PYTHON_EXCEPTIONS = {
    "ZeroDivisionError": ("Erro Aritmético", "Divisão por zero detectada na lógica Python."),
    "NameError": ("Símbolo Indefinido", "Uso de variável ou função que não existe."),
    "TypeError": ("Incompatibilidade", "Operação entre tipos incompatíveis."),
    "AttributeError": ("Atributo Ausente", "O objeto não possui o método chamado."),
    "ModuleNotFoundError": ("Módulo Ausente", "Dependência não instalada no ambiente.")
}

# Padrões Nativo C/Vulcan
NATIVE_LOGIC_PATTERNS = [
    ("CORRUPTION", "HadesSentinel: Memory Corruption", "O sistema detectou que dados foram escritos fora do limite permitido."),
    ("CONCURRENCY", "ConcurrencyHazard", "Condição de Corrida: Múltiplas threads acessando a mesma RAM."),
    ("OOM", "ArenaOverflow", "Estouro de Arena: Pool de memória Vulcan exaurido."),
    ("RACE", "ConcurrencyHazard", "Falha de Sincronismo: Acesso simultâneo de threads.")
]