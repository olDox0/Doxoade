@click.group()
def oline():
    """Gerenciamento da Inteligência OLINE v4.0."""
    pass

@oline.command()
@click.argument('query')
def search(query):
    """Busca híbrida: ZIM -> Local Index -> Web."""
    # 1. Busca no ZIM (KiwixSearcher)
    # 2. Busca no Índice Binário (BM25)
    # 3. Se resultados < 3, aciona OrnCrawler.search(query)