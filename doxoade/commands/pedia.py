# doxoade/commands/pedia.py
import click
import json
import os
# [DOX-UNUSED] import glob
import shutil
import textwrap
import re
from pathlib import Path
from typing import Dict, List, Tuple
from colorama import Fore, Style, Back
from ..shared_tools import _run_git_command
# === CONFIGURAÇÃO ===
DOCS_ROOT = Path(__file__).parent.parent / 'docs'
LIBRARY_DIR = DOCS_ROOT / 'library'
INTERNALS_DIR = DOCS_ROOT / 'internals'
LEGACY_FILE = DOCS_ROOT / 'articles.json'

# === CLASSES DE DADOS ===
class Article:
    """Representa um artigo da Doxoadepédia."""
    def __init__(self, key: str, title: str, content: str, 
                 source: str = 'library', date: str = ''):
        self.key = key
        self.title = title
        self.content = content
        self.source = source
        self.date = date
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'content': self.content,
            'source': self.source,
            'date': self.date
        }

# === CARREGAMENTO DE DADOS ===
def load_articles() -> Dict[str, dict]:
    """
    Carrega artigos de múltiplas fontes com tratamento robusto de erros.

    Ordem de prioridade:
    1. docs/library/*.json (modular)
    2. docs/internals/*.md (internals)
    3. docs/articles.json (legacy fallback)
    """
    articles = {}
    # 1. Library (JSONs modulares)
    articles.update(_load_library_jsons())
    # 2. Internals (Markdown)
    articles.update(_load_internal_mds())
    # 3. Legacy fallback
    if not articles and LEGACY_FILE.exists():
        articles.update(_load_legacy_json())
    return articles

def _load_library_jsons() -> Dict[str, dict]:
    """Carrega JSONs da library/ com encoding robusto."""
    articles = {}
    
    if not LIBRARY_DIR.exists():
        return articles
    for json_path in LIBRARY_DIR.glob('*.json'):
        try:
            # Tenta UTF-8, depois CP1252 (Windows)
            content = None
            for encoding in ['utf-8', 'cp1252', 'latin-1']:
                try:
                    content = json_path.read_text(encoding=encoding)
                    data = json.loads(content)
                    articles.update(data)
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            if content is None:
                raise ValueError(f"Não foi possível decodificar {json_path.name}")
        except Exception as e:
            click.echo(Fore.RED + f"[PEDIA] Erro ao carregar {json_path.name}: {e}")
    return articles

def _load_internal_mds() -> Dict[str, dict]:
    """Carrega Markdown dos internals/ com extração de metadados."""
    articles = {}
    if not INTERNALS_DIR.exists():
        return articles
    for md_path in INTERNALS_DIR.glob('*.md'):
        try:
            content = md_path.read_text(encoding='utf-8', errors='ignore')
            # Extrai título da primeira linha (# Título)
            lines = content.splitlines()
            title = md_path.stem
            if lines and lines[0].startswith('# '):
                title = lines[0][2:].strip()
            # Extrai data se houver padrão "Atualizado em: YYYY-MM-DD"
            date_match = re.search(r'Atualizado em:\s*(\d{4}-\d{2}-\d{2})', content)
            date = date_match.group(1) if date_match else 'Viva'
            articles[md_path.stem] = {
                'title': f"[INTERNAL] {title}",
                'content': content,
                'source': 'internal',
                'date': date
            }
        except Exception as e:
            click.echo(Fore.RED + f"[PEDIA] Erro ao ler {md_path.name}: {e}")
    return articles

def _load_legacy_json() -> Dict[str, dict]:
    """Fallback para articles.json antigo."""
    try:
        content = LEGACY_FILE.read_text(encoding='utf-8')
        return json.loads(content)
    except Exception:
        return {}

# === RENDERIZAÇÃO MARKDOWN ===
class MarkdownRenderer:
    """Renderizador de Markdown com suporte a syntax highlight neon."""
    # Padrões regex compilados
    BOLD = re.compile(r'\*\*(.*?)\*\*')
    ITALIC = re.compile(r'\*(.*?)\*')
    CODE = re.compile(r'`(.*?)`')
    LINK = re.compile(r'\[(.*?)\]\((.*?)\)')
    # Estados do parser
    in_code_block = False
    code_block_indent = 0
    def render(self, content: str):
        """Renderiza conteúdo Markdown linha por linha."""
        self.in_code_block = False
        for line in content.splitlines():
            self._render_line(line)
    
    def _render_line(self, line: str):
        """Renderiza uma linha individual."""
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        # Blocos de código (4 espaços ou tab)
        if line.startswith('    ') or line.startswith('\t'):
            click.echo(Fore.LIGHTBLACK_EX + "    │ " + stripped + Fore.RESET)
            return
        # Blocos de código cercados (```)
        if stripped.startswith('```'):
            self.in_code_block = not self.in_code_block
            lang = stripped[3:].strip() if not self.in_code_block else ''
            color = Fore.LIGHTBLACK_EX + Style.DIM
            if not self.in_code_block:
                click.echo(color + "    ╰" + "─" * 54 + Fore.RESET)
            else:
                click.echo(color + f"    ╭─ {lang or 'code'} " + "─" * 50 + Fore.RESET)
            return
        if self.in_code_block:
            click.echo(Fore.LIGHTBLACK_EX + "    │ " + line + Fore.RESET)
            return
        # Headers
        if line.startswith('# '):
            self._render_h1(line[2:])
            return
        elif line.startswith('## '):
            self._render_h2(line[3:])
            return
        elif line.startswith('### '):
            self._render_h3(line[4:])
            return
        # Blockquotes (> texto)
        if stripped.startswith('> '):
            quote_text = self._apply_inline_formatting(stripped[2:])
            click.echo(f"{Fore.LIGHTBLACK_EX}┃ {Fore.LIGHTCYAN_EX}{quote_text}{Fore.RESET}")
            return
        # Listas
        if stripped.startswith('* ') or stripped.startswith('- '):
            self._render_list_item(line, indent)
            return
        # Linha normal com formatação inline
        formatted = self._apply_inline_formatting(line)
        # Metadados (key: value) - com destaque especial
        if ':' in stripped and not line.startswith(' '):
            parts = stripped.split(':', 1)
            if len(parts[0]) < 20 and 'http' not in parts[0]:
                key, val = parts
                # Destaca campos importantes
                if key in ['Origem', 'Arquivos', 'Padrão', 'Risco', 'Categoria', 
                          'Severidade', 'Sintoma', 'Causa Raiz', 'Solução', 'Status']:
                    click.echo(f"{Fore.LIGHTCYAN_EX}{Style.BRIGHT}{key}:{Style.NORMAL}{Fore.WHITE}{val}{Fore.RESET}")
                    return
                else:
                    click.echo(f"{Fore.LIGHTBLUE_EX}{key}:{Fore.RESET}{val}")
                    return
        
        click.echo(formatted)
    
    def _render_h1(self, text: str):
        """Renderiza H1 com underline."""
        click.echo(Fore.LIGHTCYAN_EX + Style.BRIGHT + "\n" + text.upper())
        click.echo(Fore.LIGHTCYAN_EX + Style.DIM + "═" * len(text) + Style.RESET_ALL)
    
    def _render_h2(self, text: str):
        click.echo(Fore.LIGHTRED_EX + Style.BRIGHT + "\n" + text + Style.RESET_ALL)
    
    def _render_h3(self, text: str):
        click.echo(Fore.LIGHTGREEN_EX + Style.BRIGHT + "\n" + text + Style.RESET_ALL)
    
    def _render_list_item(self, line: str, indent: int):
        """Renderiza item de lista com bullet colorido."""
        stripped = line.lstrip()
        content = stripped[2:]  # Remove '* ' ou '- '
        indent_str = " " * (indent + 2)
        bullet = f"{Fore.LIGHTYELLOW_EX}● {Fore.RESET}"
        formatted = self._apply_inline_formatting(content)
        click.echo(f"{indent_str}{bullet}{formatted}")
    
    def _apply_inline_formatting(self, text: str) -> str:
        """Aplica formatação inline (bold, code, italic, links)."""
        # Bold
        text = self.BOLD.sub( lambda m: f"{Fore.LIGHTCYAN_EX}{m.group(1)}{Fore.RESET}", text )
        
        # Italic
        text = self.ITALIC.sub( lambda m: f"{Style.DIM}{m.group(1)}{Style.RESET_ALL}", text )
        
        # Code inline
        text = self.CODE.sub( lambda m: f"{Fore.LIGHTYELLOW_EX}{m.group(1)}{Fore.RESET}", text )
        
        # Links [text](url)
        text = self.LINK.sub(
            lambda m: f"{Fore.LIGHTBLUE_EX}{m.group(1)}{Fore.RESET} ({Style.DIM}{m.group(2)}{Style.RESET_ALL})", text )
        
        return text

# === BUSCA ===
def _search_commands(term: str) -> List[Tuple[str, str]]:
    """Busca em comandos CLI registrados."""
    from ..cli import cli
    results = []
    ctx = click.Context(cli)
    
    for cmd_name, cmd_obj in cli.commands.items():
        help_text = cmd_obj.get_help(ctx)
        if term in cmd_name.lower() or (help_text and term in help_text.lower()):
            short_desc = cmd_obj.short_help or (
                cmd_obj.help.split('\n')[0] if cmd_obj.help else "Sem descrição"
            )
            results.append((f"cmd:{cmd_name}", short_desc))
    
    return results

def _search_git_history(term: str) -> List[Tuple[str, str]]:
    """Busca no histórico de commits."""
    try:
        output = _run_git_command(
            ['log', '--oneline', f'--grep={term}', '-n', '5', '--no-merges'],
            capture_output=True,
            silent_fail=True
        )
        if not output:
            return []
        
        results = []
        for line in output.splitlines():
            parts = line.split(' ', 1)
            if len(parts) == 2:
                hash_val, msg = parts
                results.append((f"git:{hash_val}", msg))
        return results
    except Exception:
        return []

# === COMANDOS CLI ===
@click.group('pedia')
def pedia():
    """Base de Conhecimento Integrada (Doxoadepédia)."""
    pass

@pedia.command('list')
def list_articles():
    """Lista todos os artigos disponíveis."""
    articles = load_articles()
    
    if not articles:
        click.echo(Fore.YELLOW + "Nenhum artigo encontrado.")
        return
    
    # Separa por fonte
    internals = {k: v for k, v in articles.items() if v.get('source') == 'internal'}
    standards = {k: v for k, v in articles.items() if v.get('source') != 'internal'}
    
    # Calcula largura máxima
    max_len = max(len(k) for k in articles.keys()) + 2
    
    click.echo(Fore.CYAN + Style.BRIGHT + "\n╔═══ Doxoadepédia: Índice ═══╗" + Style.RESET_ALL)
    
    if standards:
        click.echo(Fore.WHITE + Style.BRIGHT + "\n[Biblioteca Geral]")
        for key in sorted(standards.keys()):
            _print_article_entry(key, standards[key], max_len, Fore.YELLOW)
    
    if internals:
        click.echo(Fore.WHITE + Style.BRIGHT + "\n[Doxoade Internals]")
        for key in sorted(internals.keys()):
            title = internals[key]['title'].replace('[INTERNAL] ', '')
            entry = internals[key].copy()
            entry['title'] = title
            _print_article_entry(key, entry, max_len, Fore.MAGENTA)
    
    click.echo(Style.DIM + f"\n{len(articles)} artigos disponíveis. Use 'doxoade pedia read <nome>' para ler.")

def _print_article_entry(key: str, data: dict, max_len: int, color: str):
    """Imprime entrada de artigo com wrap inteligente."""
    cols, _ = shutil.get_terminal_size()
    title = data.get('title', 'Sem Título')
    
    prefix_len = max_len + 3
    desc_width = max(20, cols - prefix_len)
    
    wrapper = textwrap.TextWrapper(width=desc_width)
    lines = wrapper.wrap(title)
    
    if not lines:
        return
    
    # Primeira linha
    click.echo(f"{color}{key:<{max_len}}{Fore.WHITE} : {lines[0]}")
    
    # Linhas subsequentes indentadas
    for line in lines[1:]:
        padding = " " * (max_len + 3)
        click.echo(f"{padding}{Fore.WHITE}{line}")

def _safe_emoji(text: str) -> str:
    """Substitui emojis por ASCII se o terminal não suportar Unicode."""
    emoji_fallback = {
        '🔴': '[!]', '🟡': '[~]', '🟢': '[OK]',
        '💀': '[!!]', '🟠': '[!]',
        '💡': '[*]', '📋': '[-]', '🚧': '[WIP]', '✅': '[OK]'
    }
    
    # Detecta se é Windows com CP1252
    import sys
    if sys.platform == 'win32':
        try:
            # Tenta codificar para ver se suporta
            text.encode('cp1252')
        except UnicodeEncodeError:
            # Fallback para ASCII
            for emoji, ascii_char in emoji_fallback.items():
                text = text.replace(emoji, ascii_char)
    
    return text

def _build_extra_info(article: dict) -> str:
    """Constrói informações extras baseadas no tipo de artigo."""
    lines = []
    
    # Campos especiais de glossary.json
    if 'origin' in article:
        lines.append(f"**Origem:** {article['origin']}")
    
    # Campos especiais de systems.json
    if 'files' in article:
        files = article['files']
        if files:
            lines.append("\n**Arquivos:**")
            for f in files:
                lines.append(f"  * `{f}`")
    
    # Campos especiais de risk_rules.json
    if 'pattern' in article:
        lines.append(f"\n**Padrão:** `{article['pattern']}`")
    if 'risk_score' in article:
        score = article['risk_score']
        level = _safe_emoji("🔴 CRÍTICO" if score >= 40 else "🟡 MÉDIO" if score >= 20 else "🟢 BAIXO")
        lines.append(f"**Risco:** {level} ({score})")
    if 'category' in article:
        lines.append(f"**Categoria:** {article['category']}")
    if 'linked_incident' in article:
        lines.append(f"**Incidente Relacionado:** `{article['linked_incident']}`")
    if 'message' in article and 'pattern' in article:  # Só para risk_rules
        lines.append("\n**Mensagem:**")
        lines.append(f"{article['message']}")
    
    # Campos especiais de postmortems.json
    if 'severity' in article:
        severity_map = {
            'CRITICAL': _safe_emoji('🔴 CRÍTICO'),
            'CATASTROPHIC': _safe_emoji('💀 CATASTRÓFICO'),
            'HIGH': _safe_emoji('🟠 ALTO'),
            'MEDIUM': _safe_emoji('🟡 MÉDIO'),
            'LOW': _safe_emoji('🟢 BAIXO')
        }
        lines.append(f"\n**Severidade:** {severity_map.get(article['severity'], article['severity'])}")
    if 'symptom' in article:
        lines.append(f"**Sintoma:** {article['symptom']}")
    if 'root_cause' in article:
        lines.append(f"**Causa Raiz:** {article['root_cause']}")
    if 'fix' in article:
        lines.append(f"**Solução:** {article['fix']}")
    if 'story' in article:
        lines.append("\n**História:**")
        lines.append(article['story'])
    if 'lesson' in article:
        lines.append("\n**Lição Aprendida:**")
        lines.append(f"> {article['lesson']}")
    
    # Campos especiais de roadmap.json
    if 'status' in article:
        status_map = {
            'Concept': _safe_emoji('💡 Conceito'),
            'Planned': _safe_emoji('📋 Planejado'),
            'In Progress': _safe_emoji('🚧 Em Progresso'),
            'Done': _safe_emoji('✅ Concluído')
        }
        lines.append(f"\n**Status:** {status_map.get(article['status'], article['status'])}")
    
    # Campos especiais de patterns.json
    if 'context' in article:
        lines.append(f"\n**Contexto:** {article['context']}")
    
    return "\n".join(lines) if lines else ""

@pedia.command('read')
@click.argument('topic')
def read_article(topic: str):
    """Lê um artigo específico."""
    articles = load_articles()
    # Busca case-insensitive
    article = articles.get(topic) or articles.get(topic.lower())
    if not article:
        # Sugere artigos similares
        matches = [k for k in articles.keys() if topic.lower() in k.lower()]
        if matches:
            suggestion = ', '.join(matches[:3])
            click.echo(Fore.YELLOW + f"Artigo '{topic}' não encontrado.")
            click.echo(Fore.CYAN + f"Você quis dizer: {suggestion}?")
        else:
            click.echo(Fore.RED + "Artigo não encontrado. Use 'pedia list' para ver o índice.")
        return
    # Renderiza artigo
    title = article.get('title', 'Sem Título')
    # Suporta múltiplos campos de conteúdo (content, body, definition, description, message)
    content = (
        article.get('content') or 
        article.get('body') or 
        article.get('definition') or 
        article.get('description') or
        article.get('story') or  # Para postmortems
        ''
    )
    date = article.get('date', '')
    # Header
    click.echo(Back.BLUE + Fore.WHITE + Style.BRIGHT + f" {title} " + Style.RESET_ALL)
    if date:
        click.echo(Style.DIM + f"Atualizado em: {date}" + Style.RESET_ALL)
    click.echo("")
    # Adiciona metadados extras para artigos especializados
    extra_info = _build_extra_info(article)
    if extra_info:
        content = extra_info + "\n\n" + content
    # Conteúdo renderizado
    renderer = MarkdownRenderer()
    renderer.render(content)

@pedia.command('search')
@click.argument('term')
def search_articles(term: str):
    """Busca Universal: Artigos, Comandos e Git."""
    term_lower = term.lower()
    # Busca em artigos
    articles = load_articles()
    found_articles = []
    for key, data in articles.items():
        title = data.get('title', '').lower()
        # Suporta múltiplos formatos de conteúdo
        content = (
            data.get('content') or 
            data.get('body') or 
            data.get('definition') or 
            data.get('description') or
            ''
        ).lower()
        if term_lower in key.lower() or term_lower in title or term_lower in content:
            tag = "INT" if data.get('source') == 'internal' else "DOC"
            found_articles.append((f"{tag}:{key}", data['title']))
    # Busca em comandos e git
    found_commands = _search_commands(term_lower)
    found_git = _search_git_history(term)
    total = len(found_articles) + len(found_commands) + len(found_git)
    if total == 0:
        click.echo(Fore.YELLOW + f"Nenhum resultado encontrado para '{term}'.")
        return
    click.echo(Fore.CYAN + Style.BRIGHT + f"╔═══ Busca Universal: '{term}' ({total} resultados) ═══╗" + Style.RESET_ALL)
    # Exibe resultados por categoria
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
            truncated = msg[:57] + "..." if len(msg) > 60 else msg
            click.echo(f"  {Fore.LIGHTBLUE_EX}{key:<20}{Fore.WHITE} : {truncated}")

@pedia.command('comments')
@click.argument('term')
def search_comments(term: str):
    """Busca por termo nos comentários do código fonte."""
    from ..shared_tools import _get_project_config
    config = _get_project_config(None)
    project_root = Path(config.get('root_path', '.'))
    # Diretórios ignorados
    ignore_dirs = { 'venv', '.git', '__pycache__', '.doxoade_cache', 'Vers', 'build', 'dist', '.pytest_cache', '.tox' }
    ignore_dirs.update(config.get('ignore', []))
    click.echo(Fore.CYAN + f"╔═══ Buscando '{term}' em comentários ({project_root}) ═══╗" + Style.RESET_ALL)
    count = 0
    term_lower = term.lower()
    
    for root, dirs, files in os.walk(project_root):
        # Filtra diretórios
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if not file.endswith('.py'):
                continue
            file_path = Path(root) / file
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                for i, line in enumerate(content.splitlines(), 1):
                    if '#' not in line:
                        continue
                    # Extrai comentário
                    comment = line.split('#', 1)[1]
                    
                    if term_lower in comment.lower():
                        rel_path = file_path.relative_to(project_root)
                        click.echo(f"{Fore.BLUE}{rel_path}:{i} {Fore.WHITE}{line.strip()}")
                        count += 1
            except Exception:
                pass
    if count == 0:
        click.echo(Fore.YELLOW + "Nenhum comentário encontrado.")
    else:
        click.echo(Style.DIM + f"\n{count} ocorrências encontradas.")