# debug_flow_test.py
def processar_dados(n):
    resultado = n * 2
    return resultado

def main():
    contador = 0
    nome = "Iniciando"
    
    for i in range(3):
        contador += 1
        nome = f"Passo {i}"
        val = processar_dados(contador)
        print(f"Log: {nome} -> {val}")

if __name__ == "__main__":
    main()