# doxoade/commands/pedia.py
import click
import json
import os
from colorama import Fore, Style, Back
from ..shared_tools import _run_git_command

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


def _search_commands(term):
    from ..cli import cli
    """Busca no help string de todos os comandos registrados."""
    results = []
    ctx = click.Context(cli)
    
    for cmd_name, cmd_obj in cli.commands.items():
        help_text = cmd_obj.get_help(ctx)
        # Busca no nome ou no texto de ajuda
        if term in cmd_name.lower() or (help_text and term in help_text.lower()):
            # Pega a primeira linha do help como descrição curta
            short_desc = cmd_obj.short_help or (cmd_obj.help.split('\n')[0] if cmd_obj.help else "Sem descrição")
            results.append((f"cmd:{cmd_name}", short_desc))
            
    return results

def _search_git_history(term):
    """Busca no histórico de commits (mensagens)."""
    try:
        # git log --oneline --grep="term" -n 10
        output = _run_git_command(
            ['log', '--oneline', f'--grep={term}', '-n', '5', '--no-merges'], 
            capture_output=True, silent_fail=True
        )
        if not output: return []
        
        results = []
        for line in output.splitlines():
            hash_val, msg = line.split(' ', 1)
            results.append((f"git:{hash_val}", msg))
        return results
    except Exception:
        return []

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

@pedia.command('search')
@click.argument('term')
def search_articles(term):
    """
    Busca Universal: Artigos, Comandos e Git.
    """
    term = term.lower()
    
    # 1. Busca em Artigos
    articles = load_articles()
    found_articles = []
    for key, data in articles.items():
        title = data.get('title', '').lower()
        content = data.get('content', '') or data.get('body', '')
        
        if term in key or term in title or term in content.lower():
            found_articles.append((f"doc:{key}", data['title']))
    
    # 2. Busca em Comandos
    found_commands = _search_commands(term)
    
    # 3. Busca no Git
    found_git = _search_git_history(term)
    
    total = len(found_articles) + len(found_commands) + len(found_git)
    
    if total == 0:
        click.echo(Fore.YELLOW + f"Nenhum resultado encontrado para '{term}' em nenhuma fonte.")
        return

    click.echo(Fore.CYAN + f"--- Resultados da Busca Universal por '{term}' ({total}) ---")
    
    if found_articles:
        click.echo(Style.BRIGHT + "\n[Doxoadepédia]")
        for key, title in found_articles:
            click.echo(f"  {Fore.YELLOW}{key:<15}{Fore.WHITE} : {title}")

    if found_commands:
        click.echo(Style.BRIGHT + "\n[Comandos CLI]")
        for key, desc in found_commands:
            click.echo(f"  {Fore.GREEN}{key:<15}{Fore.WHITE} : {desc}")
            
    if found_git:
        click.echo(Style.BRIGHT + "\n[Memória Git]")
        for key, msg in found_git:
            # Trunca mensagem longa
            if len(msg) > 60: msg = msg[:57] + "..."
            click.echo(f"  {Fore.MAGENTA}{key:<15}{Fore.WHITE} : {msg}")

    click.echo(Style.DIM + "\nDica: Use 'doxoade pedia read <nome>' para ler artigos ou '<cmd> --help' para comandos.")
    
@pedia.command('comments')
@click.argument('term')
def search_comments(term):
    """Busca por um termo nos comentários do código fonte do projeto."""
    from ..shared_tools import _get_project_config
    
    # Carrega configuração para saber o que ignorar
    config = _get_project_config(None) # Logger None é seguro agora com o hotfix
    
    # Pastas padrão para ignorar (além das do config)
    ignore_list = set(config.get('ignore', []))
    ignore_list.update(['venv', '.git', '__pycache__', '.doxoade_cache', 'Vers', 'build', 'dist'])
    
    # Normaliza para comparação
    ignore_list = {os.path.normcase(p) for p in ignore_list}
    
    project_root = config.get('root_path', '.')
    term = term.lower()
    
    click.echo(Fore.CYAN + f"--- Buscando '{term}' nos comentários do código em {project_root} ---")
    
    count = 0
    for root, dirs, files in os.walk(project_root):
        # Filtra diretórios
        # Modifica dirs in-place para o os.walk não entrar nelas
        dirs[:] = [d for d in dirs if os.path.normcase(d) not in ignore_list and not any(ign in os.path.normcase(d) for ign in ignore_list)]
        
        for file in files:
            if not file.endswith('.py'): continue
            
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(lines):
                    if '#' in line:
                        # Pega apenas o que vem depois do #
                        comment_part = line.split('#', 1)[1]
                        if term in comment_part.lower():
                            rel_path = os.path.relpath(file_path, project_root)
                            # Exibe o resultado
                            click.echo(f"{Fore.BLUE}{rel_path}:{i+1} {Fore.WHITE}{line.strip()}")
                            count += 1
            except Exception: pass

    if count == 0:
        click.echo(Fore.YELLOW + "Nenhum comentário encontrado.")
    else:
        click.echo(Style.DIM + f"\nEncontradas {count} ocorrências.")