import asyncio
import random

# Dicionário global que guardará todos os buffers criados pelo sistema
_gerenciador_de_buffers = {}

def fazer_buffer(nome: str, tamanho_maximo: int):
    """Cria um buffer assíncrono com um nome e tamanho limite de itens."""
    _gerenciador_de_buffers[nome] = asyncio.Queue(maxsize=tamanho_maximo)
    print(f"Buffer '{nome}' criado com sucesso (Capacidade: {tamanho_maximo} itens).")

async def colocar_no_buffer(nome: str, item):
    """Adiciona um item ao buffer especificado. 
    Se o buffer estiver cheio, espera asincronicamente até liberar espaço."""
    if nome not in _gerenciador_de_buffers:
        raise ValueError(f"O buffer '{nome}' não existe!")
    await _gerenciador_de_buffers[nome].put(item)

async def pegar_do_buffer(nome: str):
    """Remove e retorna um item do buffer especificado.
    Se o buffer estiver vazio, espera asincronicamente até chegar um novo item."""
    if nome not in _gerenciador_de_buffers:
        raise ValueError(f"O buffer '{nome}' não existe!")
    item = await _gerenciador_de_buffers[nome].get()
    _gerenciador_de_buffers[nome].task_done()
    return item

# -------------------------------------------------------------
# Exemplo Prático de Uso
# -------------------------------------------------------------
#async def produtor():
#    for i in range(10):
#        random_number = random.random()
#        await asyncio.sleep(0.5)  # Simula tempo gerando um dado
#        await colocar_no_buffer("buffer_1", f"Dado {random_number}")
#        print(f"-> Produzido e enviado para buffer_1: Dado {random_number}")
#
#async def consumidor():
#    for _ in range(5):
#        dado = await pegar_do_buffer("buffer_1")
#        print(f"<- Consumido de buffer_1: {dado}")
#
#async def main():
#    # Cria o buffer exatamente como você exemplificou
#    fazer_buffer("buffer_1", 4069)
#    
#    # Roda o produtor e o consumidor ao mesmo tempo de forma assíncrona
#    await asyncio.gather(produtor(), consumidor())
#
# Inicia o loop assíncrono do Python
#asyncio.run(main())
