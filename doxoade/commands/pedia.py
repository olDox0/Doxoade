# doxoade/commands/pedia.py
import click
import json
import os
from colorama import Fore, Style, Back

# Caminho para o arquivo JSON
DOCS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'articles.json')

def load_articles():
    """Carrega artigos do arquivo JSON ou usa fallback."""
    if os.path.exists(DOCS_PATH):
        try:
            with open(DOCS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            click.echo(Fore.RED + f"[ERRO PEDIA] Falha ao ler articles.json: {e}")
    
    # Fallback Mínimo se o arquivo sumir
    return {
        "erro": {
            "title": "Erro de Carregamento",
            "content": "Não foi possível carregar a base de conhecimento externa."
        }
    }

@click.group('pedia')
def pedia():
    """Base de Conhecimento Integrada (Doxoadepédia)."""
    pass

@pedia.command('list')
def list_articles():
    """Lista todos os artigos disponíveis."""
    articles = load_articles()
    click.echo(Fore.CYAN + "\n--- Doxoadepédia: Índice ---")
    # Ordena por chave
    for key in sorted(articles.keys()):
        data = articles[key]
        click.echo(f"{Fore.YELLOW}{key:<15}{Fore.WHITE} : {data.get('title', 'Sem Título')}")
    click.echo(Style.DIM + "\nUse 'doxoade pedia read <nome>' para ler.")

@pedia.command('read')
@click.argument('topic')
def read_article(topic):
    """Lê um artigo específico."""
    articles = load_articles()
    article = articles.get(topic.lower())
    
    if not article:
        matches = [k for k in articles.keys() if topic.lower() in k]
        if matches:
            click.echo(Fore.YELLOW + f"Artigo '{topic}' não encontrado. Você quis dizer: {', '.join(matches)}?")
        else:
            click.echo(Fore.RED + "Artigo não encontrado. Use 'list' para ver o índice.")
        return

    title = article.get('title', 'Sem Título')
    # Suporta 'content' ou 'body' (para compatibilidade com meu exemplo anterior)
    content = article.get('content') or article.get('body', '')

    click.echo(Back.BLUE + Fore.WHITE + Style.BRIGHT + f" {title} " + Style.RESET_ALL)
    click.echo(Fore.WHITE + content)