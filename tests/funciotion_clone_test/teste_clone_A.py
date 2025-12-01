def funcao_complexa_duplicada(x, y):
    """Eu sou o original."""
    resultado = 0
    lista = [1, 2, 3, 4, 5]
    for i in lista:
        if x > y:
            resultado += (x * i)
        else:
            resultado -= (y * i)
    return resultado