# doxoade/commands_test/teste_flow.py
import time

def processar_dados():
    total = 0
    print('Iniciando processamento...')
    for i in range(3):
        total += i * 10
        time.sleep(0.2)
        y = total / 2
    print('Operação pesada...')
    time.sleep(1.1)
    print('Fim')
processar_dados()