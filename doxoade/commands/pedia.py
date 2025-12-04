# doxoade/commands/pedia.py
import click
import json
import os
import glob
import shutil
import textwrap
import re
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
        except Exception: pass

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
    except Exception:
        return []

@click.group('pedia')
def pedia():
    """Base de Conhecimento Integrada (Doxoadepédia)."""
    pass

def _render_markdown(content):
    """Renderiza conteúdo Markdown com cores de alta intensidade (Neon)."""
    
    bold_pattern = re.compile(r'\*\*(.*?)\*\*')
    code_pattern = re.compile(r'`(.*?)`')

    for line in content.splitlines():
        stripped = line.strip()
        
        # --- BLOCOS DE CÓDIGO ---
        if line.startswith('    ') or line.startswith('\t'):
            # Cinza claro para blocos
            click.echo(Fore.LIGHTBLACK_EX + "    │ " + stripped + Fore.RESET)
            continue
            
        # --- CABEÇALHOS (H1, H2, H3) ---
        if line.startswith('# '):
            title = line[2:]
            # Cyan Claro + Negrito
            click.echo(Fore.LIGHTCYAN_EX + Style.BRIGHT + "\n" + title.upper())
            click.echo(Fore.LIGHTCYAN_EX + Style.DIM + "=" * len(title) + Style.RESET_ALL)
            continue
        elif line.startswith('## '):
            # Vermelho Claro
            click.echo(Fore.LIGHTRED_EX + Style.BRIGHT + "\n" + line[3:] + Style.RESET_ALL)
            continue
        elif line.startswith('### '):
            # Verde Claro
            click.echo(Fore.LIGHTGREEN_EX + Style.BRIGHT + "\n" + line[4:] + Style.RESET_ALL)
            continue

        # --- LISTAS ---
        prefix = ""
        if stripped.startswith('* '):
            indent_level = len(line) - len(line.lstrip())
            indent = " " * (indent_level + 2)
            # Amarelo Claro (O que você quer!)
            prefix = f"{indent}{Fore.LIGHTYELLOW_EX}● {Fore.RESET}" 
            line = stripped[2:] 
        else:
            prefix = Fore.RESET
            
        # --- FORMATAÇÃO INLINE ---
        
        # Negrito -> Cyan Claro
        line = bold_pattern.sub(lambda m: f"{Fore.LIGHTCYAN_EX}{m.group(1)}{Fore.RESET}", line)
        
        # Código Inline -> Amarelo Claro (Destaque forte)
        line = code_pattern.sub(lambda m: f"{Fore.LIGHTYELLOW_EX}{m.group(1)}{Fore.RESET}", line)
        
        # --- METADADOS ---
        if ':' in line and not line.startswith(' ') and not prefix.strip():
            key, val = line.split(':', 1)
            if len(key) < 20 and 'http' not in key:
                # Azul Claro para chaves
                click.echo(f"{Fore.LIGHTBLUE_EX}{key}:{Fore.RESET}{val}")
                continue

        # Imprime
        click.echo(f"{prefix}{line}")

def _print_wrapped(key, title, max_key_len, color_key):
    """Imprime chave e título com quebra de linha inteligente."""
    cols, _ = shutil.get_terminal_size()
    prefix_len = max_key_len + 3
    desc_width = max(20, cols - prefix_len)
    wrapper = textwrap.TextWrapper(width=desc_width)
    lines = wrapper.wrap(title)
    if not lines: return
    click.echo(f"{color_key}{key:<{max_key_len}}{Fore.WHITE} : {lines[0]}")
    for line in lines[1:]:
        padding = " " * (max_key_len + 3)
        click.echo(f"{padding}{Fore.WHITE}{line}")

@pedia.command('list')
def list_articles():
    """Lista todos os artigos disponíveis (Conceitos, Comandos e Internals)."""
    articles = load_articles()
    click.echo(Fore.CYAN + "\n--- Doxoadepédia: Índice ---")
    
    internals = {k: v for k, v in articles.items() if v.get('source') == 'internal'}
    standards = {k: v for k, v in articles.items() if v.get('source') != 'internal'}
    
    all_keys = list(articles.keys())
    if not all_keys:
        click.echo("Nenhum artigo encontrado.")
        return
        
    max_len = max(len(k) for k in all_keys) + 2 
    
    if standards:
        click.echo(Fore.WHITE + Style.BRIGHT + "\n[Biblioteca Geral]")
        for key in sorted(standards.keys()):
            data = standards[key]
            _print_wrapped(key, data.get('title', 'Sem Título'), max_len, Fore.YELLOW)

    if internals:
        click.echo(Fore.WHITE + Style.BRIGHT + "\n[Doxoade Internals]")
        for key in sorted(internals.keys()):
            data = internals[key]
            title = data.get('title', '').replace('[INTERNAL] ', '')
            _print_wrapped(key, title, max_len, Fore.MAGENTA)

    click.echo(Style.DIM + "\nUse 'doxoade pedia read <nome>' para ler.")

@pedia.command('read')
@click.argument('topic')
def read_article(topic):
    """Lê um artigo específico."""
    articles = load_articles()
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
    click.echo("") 
    
    _render_markdown(content)

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
            except Exception: pass
    
    if count == 0: click.echo(Fore.YELLOW + "Nenhum comentário encontrado.")