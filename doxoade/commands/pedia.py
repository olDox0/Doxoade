# doxoade/commands/pedia.py
import click
import json
import os
import glob
from colorama import Fore, Style, Back
from ..shared_tools import _run_git_command

# Configuração de Caminhos
DOCS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')
LIBRARY_DIR = os.path.join(DOCS_ROOT, 'library')
INTERNALS_DIR = os.path.join(DOCS_ROOT, 'internals')
# Fallback legado
LEGACY_FILE = os.path.join(DOCS_ROOT, 'articles.json')

def load_articles():
    """
    Carrega e unifica artigos de múltiplas fontes:
    1. Arquivos JSON em docs/library/
    2. Arquivos Markdown em docs/internals/ (convertidos para estrutura de artigo)
    3. articles.json legado (se existir e a library estiver vazia)
    """
    articles = {}
    
    # 1. Carrega JSONs modulares (Library)
    json_files = glob.glob(os.path.join(LIBRARY_DIR, '*.json'))
    if json_files:
        for jf in json_files:
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    articles.update(data)
            except Exception as e:
                click.echo(Fore.RED + f"[PEDIA] Erro ao carregar {os.path.basename(jf)}: {e}")
    elif os.path.exists(LEGACY_FILE):
        # Fallback para o arquivo antigo se a library nova estiver vazia
        try:
            with open(LEGACY_FILE, 'r', encoding='utf-8') as f:
                articles.update(json.load(f))
        except: pass

    # 2. Carrega Internals (Markdown)
    # Mapeia nome do arquivo (sem extensão) para um artigo
    md_files = glob.glob(os.path.join(INTERNALS_DIR, '*.md'))
    for md in md_files:
        filename = os.path.splitext(os.path.basename(md))[0]
        try:
            with open(md, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Tenta extrair um título da primeira linha (# Título)
            lines = content.splitlines()
            title = filename
            if lines and lines[0].startswith('# '):
                title = lines[0].replace('# ', '').strip()
            
            articles[filename] = {
                'title': f"[INTERNAL] {title}",
                'content': content,
                'source': 'internal',
                'date': 'Viva'
            }
        except Exception as e:
            click.echo(Fore.RED + f"[PEDIA] Erro ao ler internal {filename}: {e}")

    return articles

def _search_commands(term):
    from ..cli import cli
    """Busca no help string de todos os comandos registrados."""
    results = []
    ctx = click.Context(cli)
    
    for cmd_name, cmd_obj in cli.commands.items():
        help_text = cmd_obj.get_help(ctx)
        if term in cmd_name.lower() or (help_text and term in help_text.lower()):
            short_desc = cmd_obj.short_help or (cmd_obj.help.split('\n')[0] if cmd_obj.help else "Sem descrição")
            results.append((f"cmd:{cmd_name}", short_desc))
            
    return results

def _search_git_history(term):
    """Busca no histórico de commits."""
    try:
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
    except:
        return []

@click.group('pedia')
def pedia():
    """Base de Conhecimento Integrada (Doxoadepédia)."""
    pass

@pedia.command('list')
def list_articles():
    """Lista todos os artigos disponíveis (Conceitos, Comandos e Internals)."""
    articles = load_articles()
    click.echo(Fore.CYAN + "\n--- Doxoadepédia: Índice ---")
    
    # Separa por tipo para melhor visualização
    internals = {k: v for k, v in articles.items() if v.get('source') == 'internal'}
    standards = {k: v for k, v in articles.items() if v.get('source') != 'internal'}
    
    if standards:
        click.echo(Fore.WHITE + Style.BRIGHT + "\n[Biblioteca Geral]")
        for key in sorted(standards.keys()):
            data = standards[key]
            click.echo(f"{Fore.YELLOW}{key:<20}{Fore.WHITE} : {data.get('title', 'Sem Título')}")

    if internals:
        click.echo(Fore.WHITE + Style.BRIGHT + "\n[Doxoade Internals]")
        for key in sorted(internals.keys()):
            data = internals[key]
            click.echo(f"{Fore.MAGENTA}{key:<20}{Fore.WHITE} : {data.get('title')}")

    click.echo(Style.DIM + "\nUse 'doxoade pedia read <nome>' para ler.")

@pedia.command('read')
@click.argument('topic')
def read_article(topic):
    """Lê um artigo específico."""
    articles = load_articles()
    # Tenta match exato ou case-insensitive
    article = articles.get(topic) or articles.get(topic.lower())
    
    if not article:
        matches = [k for k in articles.keys() if topic.lower() in k.lower()]
        if matches:
            click.echo(Fore.YELLOW + f"Artigo '{topic}' não encontrado. Você quis dizer: {', '.join(matches)}?")
        else:
            click.echo(Fore.RED + "Artigo não encontrado. Use 'list' para ver o índice.")
        return

    title = article.get('title', 'Sem Título')
    content = article.get('content') or article.get('body', '')
    date = article.get('date', '')

    click.echo(Back.BLUE + Fore.WHITE + Style.BRIGHT + f" {title} " + Style.RESET_ALL)
    if date:
        click.echo(Style.DIM + f"Atualizado em: {date}")
    click.echo("") # Linha em branco
    
    # Renderização simples de Markdown (apenas cores para headers)
    for line in content.splitlines():
        if line.startswith('# '): # H1
            click.echo(Fore.CYAN + Style.BRIGHT + line)
        elif line.startswith('## '): # H2
            click.echo(Fore.GREEN + Style.BRIGHT + line)
        elif line.startswith('### '): # H3
            click.echo(Fore.YELLOW + line)
        elif line.startswith('```') or line.startswith('    '): # Code block
            click.echo(Fore.WHITE + Style.DIM + line)
        else:
            click.echo(Fore.WHITE + line)

@pedia.command('search')
@click.argument('term')
def search_articles(term):
    """Busca Universal: Artigos, Internals, Comandos e Git."""
    term = term.lower()
    
    articles = load_articles()
    found_articles = []
    for key, data in articles.items():
        title = data.get('title', '').lower()
        content = data.get('content', '') or data.get('body', '')
        
        if term in key.lower() or term in title or term in content.lower():
            tag = "INT" if data.get('source') == 'internal' else "DOC"
            found_articles.append((f"{tag}:{key}", data['title']))
    
    found_commands = _search_commands(term)
    found_git = _search_git_history(term)
    
    total = len(found_articles) + len(found_commands) + len(found_git)
    
    if total == 0:
        click.echo(Fore.YELLOW + f"Nenhum resultado encontrado para '{term}'.")
        return

    click.echo(Fore.CYAN + f"--- Resultados da Busca Universal por '{term}' ({total}) ---")
    
    if found_articles:
        click.echo(Style.BRIGHT + "\n[Doxoadepédia]")
        for key, title in found_articles:
            color = Fore.MAGENTA if "INT:" in key else Fore.YELLOW
            click.echo(f"  {color}{key:<20}{Fore.WHITE} : {title}")

    if found_commands:
        click.echo(Style.BRIGHT + "\n[Comandos CLI]")
        for key, desc in found_commands:
            click.echo(f"  {Fore.GREEN}{key:<20}{Fore.WHITE} : {desc}")
            
    if found_git:
        click.echo(Style.BRIGHT + "\n[Memória Git]")
        for key, msg in found_git:
            if len(msg) > 60: msg = msg[:57] + "..."
            click.echo(f"  {Fore.MAGENTA}{key:<20}{Fore.WHITE} : {msg}")
            
@pedia.command('comments')
@click.argument('term')
def search_comments(term):
    """Busca por um termo nos comentários do código fonte."""
    from ..shared_tools import _get_project_config
    config = _get_project_config(None)
    ignore_list = set(config.get('ignore', []))
    ignore_list.update(['venv', '.git', '__pycache__', '.doxoade_cache', 'Vers', 'build', 'dist'])
    ignore_list = {os.path.normcase(p) for p in ignore_list}
    project_root = config.get('root_path', '.')
    
    click.echo(Fore.CYAN + f"--- Buscando '{term}' nos comentários em {project_root} ---")
    
    count = 0
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if os.path.normcase(d) not in ignore_list]
        for file in files:
            if not file.endswith('.py'): continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f):
                        if '#' in line:
                            comment = line.split('#', 1)[1]
                            if term.lower() in comment.lower():
                                rel = os.path.relpath(file_path, project_root)
                                click.echo(f"{Fore.BLUE}{rel}:{i+1} {Fore.WHITE}{line.strip()}")
                                count += 1
            except: pass
    
    if count == 0: click.echo(Fore.YELLOW + "Nenhum comentário encontrado.")