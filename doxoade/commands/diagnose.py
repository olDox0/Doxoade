# doxoade/commands/diagnose.py
"""
Diagnose: Auditoria de situação e integridade do projeto.
PASC-6: Verbosidade em importação e funcionalidade (Otimização de RAM).
"""
import os
from json import dumps
from click import command, option, echo, argument, Path
from doxoade.tools.doxcolors import Fore, Style
from ..shared_tools import ExecutionLogger
from ..diagnostic.inspector import SystemInspector
@command('diagnose')
@argument('path', required=False, type=Path(exists=True))
@option('--json', 'as_json', is_flag=True, help="Saída em formato JSON.")
@option('--view', '-v', 'detailed', is_flag=True, help="Visão detalhada das modificações.")
@option('--all', '-a', 'show_all', is_flag=True, help="Exibe todos os arquivos modificados.")
@option('--max', '-m', 'show_max', is_flag=True, help="Visualização total: ignora limites.")
@option('--code', '-c', 'show_code', is_flag=True, help="Exibe trechos de código modificados.")
@option('--comments', '-cm', 'only_comments', is_flag=True, help="Exibe apenas comentários modificados.")
def diagnose(path: str, as_json: bool, detailed: bool, show_all: bool, 
             show_max: bool, show_code: bool, only_comments: bool):
    """Relatório completo de saúde do sistema e integridade."""
    inspector = SystemInspector()
    params = { 'path': path, 'detailed': detailed, 'all': show_all, 'max': show_max, 'code': show_code, 'comments': only_comments }
    
    with ExecutionLogger('diagnose', path or '.', params) as _:
        # Ativa modo detalhado se houver filtros de conteúdo
        is_detailed = detailed or show_code or only_comments
        data = inspector.run_full_diagnosis(
            detailed=is_detailed, 
            show_code=show_code, 
            target_path=path
        )
        
        if as_json:
            echo(dumps(data, indent=2))
            return
        # Se o foco for um arquivo específico e o modo for código, podemos ser mais diretos
        if not (path and os.path.isfile(path) and show_code):
            _render_env(data['environment'])
        
        _render_git(data['git'], is_detailed, show_all, show_max, show_code, only_comments)
        
        if not path:
            _render_integrity(data['integrity'])
def _render_env(env: dict):
    echo(f"{Fore.WHITE}{Style.BRIGHT}\n🖥️  AMBIENTE DE EXECUÇÃO{Style.RESET_ALL}")
    echo(f"   OS:       {Fore.YELLOW}{env['os']} {env['release']} ({env['arch']}){Style.RESET_ALL}")
    echo(f"   Python:   {Fore.YELLOW}{env['python_version']}{Style.RESET_ALL}")
    
    v_active = env['venv_active']
    path_display = env['venv_path'][-40:] if len(env['venv_path']) > 40 else env['venv_path']
    v_color = Fore.GREEN if v_active else Fore.RED
    v_text = 'ATIVO' if v_active else 'INATIVO'
    echo(f"   VENV:     {v_color}{v_text}{Style.RESET_ALL} (...{path_display})")
def _render_git(git: dict, detailed: bool, show_all: bool, show_max: bool, 
                show_code: bool, only_comments: bool):
    """Renderizador de seção Git (MPoT-17)."""
    echo(f"{Fore.WHITE}{Style.BRIGHT}\n📦 ESTADO DO REPOSITÓRIO{Style.RESET_ALL}")
    if not git['is_git_repo']:
        echo(f"   {Fore.RED}Não é um repositório Git.{Style.RESET_ALL}")
        return
    echo(f"   Branch:   {Fore.GREEN}{git['branch']}{Style.RESET_ALL}")
    _render_git_status_logic(git, detailed, show_all, show_max, show_code, only_comments)
    _render_last_commit(git.get('last_commit_info'))
def _render_git_status_logic(git, detailed, show_all, show_max, show_code, only_comments):
    """Encapsula a lógica de decisão do status Git (Reduz CC)."""
    if git['dirty_tree']:
        echo(f"   Status:   {Fore.YELLOW}MODIFICADO (Alterações não salvas){Style.RESET_ALL}")
        echo(f"   Pendentes: {git.get('pending_count', 0)} arquivo(s)")
        
        if detailed and 'changes' in git:
            _render_detailed_changes(git['changes'], show_all, show_max, show_code, only_comments)
        else:
            _render_pending_simple(git.get('pending_files', []), show_all)
    else:
        echo(f"   Status:   {Fore.GREEN}LIMPO (Tudo salvo){Style.RESET_ALL}")
def _render_pending_simple(pending, show_all):
    """Lista simples de arquivos pendentes."""
    display_limit = None if show_all else 10
    display_list = pending if show_all else pending[:display_limit]
    for f in display_list:
        echo(f"      {Fore.RED}• {f}{Style.RESET_ALL}")
    if not show_all and len(pending) > 10:
        echo(f"      {Style.DIM}... e mais {len(pending)-10} arquivos (Use -a).{Style.RESET_ALL}")
def _render_last_commit(last):
    """Exibe info do último commit."""
    if last:
        echo(f"\n   Último:   {Style.DIM}{last['hash']} - {last['author']} : {last['subject']}{Style.RESET_ALL}")
def _render_detailed_changes(changes: list, show_all: bool, show_max: bool, 
                             show_code: bool, only_comments: bool):
    """Orquestrador de mudanças detalhadas (Reduz CC)."""
    display_list = changes if show_all or show_max else changes[:10]
    for item in display_list:
        if only_comments and not item.get('comments'):
            continue
        _render_single_file_status(item)
        _render_file_content_router(item, show_max, show_code, only_comments)
    if not (show_all or show_max) and len(changes) > 10:
        echo(f"\n      {Style.DIM}... e mais {len(changes)-10} arquivos (Use -a).{Style.RESET_ALL}")
def _render_file_content_router(item, show_max, show_code, only_comments):
    """Roteia o conteúdo para o renderizador especialista (PASC-10)."""
    if only_comments:
        _render_comments_only(item['comments'])
    elif show_code:
        _render_code_hunks(item['hunks'])
    else:
        _render_file_diff_content(item, show_max)
def _render_single_file_status(item: dict):
    """Sincronia Chief-Gold: Alinhamento vertical por campo fixo."""
    added, rem = item['added'], item['removed']
    
    # 1. Formata a parte numérica
    if rem > 0:
        stat_text = f"+{added} / -{rem}"
        val_len = len(str(added)) + len(str(rem)) + 3
    else:
        stat_text = f"+{added}"
        val_len = len(str(added))
    
    # 2. Cria o bloco de colchetes (Com cores, mas sem afetar o padding externo)
    color = Fore.GREEN if added > 0 else Fore.WHITE
    brackets = f"{Fore.BLUE}[ {color}{stat_text}{Style.RESET_ALL}{Fore.BLUE} ]{Style.RESET_ALL}"
    
    # 3. Cálculo de Padding: Baseado no tamanho real dos números
    # Queremos que o caminho comece sempre na coluna 35
    padding_needed = 22 - val_len
    dots = ". " * (padding_needed // 2)
    if padding_needed % 2: dots += "."
    
    path = f"{Fore.BLUE}{Style.BRIGHT}{item['path']}{Style.RESET_ALL}"
    echo(f"      • M {brackets} {Fore.BLUE}{dots}{Style.RESET_ALL} {path}")
def _render_file_diff_content(item: dict, show_max: bool):
    """Visualização semântica (Funções e Comentários)."""
    for f in item['functions']:
        symbol, color = ("+", Fore.GREEN) if f['type'] == '+' else (("-", Fore.RED) if f['type'] == '-' else ("*", Fore.YELLOW))
        l_num = f"[ {f['line'] or '':^4} ]"
        echo(f"          {color}{symbol} {l_num} {f['name']}{Style.RESET_ALL}")
            
    comments = item['comments'] if show_max else item['comments'][:3]
    for comm in comments:
        l_num = f"[ {comm['line']:^4} ]"
        echo(f"            {Style.DIM}{l_num} # {comm['text']}{Style.RESET_ALL}")
    
    if not show_max and len(item['comments']) > 3:
        echo(f"            {Style.DIM}... e mais {len(item['comments'])-3} comentários (Use -m).{Style.RESET_ALL}")
def _render_code_hunks(hunks: list):
    """Renderiza blocos de código com prefixo e linha."""
    for h in hunks:
        l_num = f"[ {h['line']:^4} ]"
        if h['type'] == 'add':   color, prefix = Fore.GREEN, "+"
        elif h['type'] == 'rem': color, prefix = Fore.RED, "-"
        else:                    color, prefix = Style.DIM, " "
        echo(f"          {color}{prefix} {l_num} {h['content'][1:]}{Style.RESET_ALL}")
def _render_comments_only(comments: list):
    """Renderizador de comentários corrigido (Simetria de Símbolos)."""
    for comm in comments:
        c_type = comm.get('type', '+')
        if c_type == '+':   color, symbol = Fore.GREEN, "+"
        elif c_type == '-': color, symbol = Fore.RED, "-"
        else:               color, symbol = Fore.YELLOW, "*"
        
        # Sincronia: Espaço fixo para número da linha
        l_tag = f"[ {str(comm['line']):^4} ]"
        echo(f"          {color}{symbol} {l_tag} # {comm['text']}{Style.RESET_ALL}")
def _render_integrity(core: dict):
    echo(f"{Fore.WHITE}{Style.BRIGHT}\n🛡️  INTEGRIDADE DO NÚCLEO{Style.RESET_ALL}")
    for mod, status in core.items():
        clean_name = mod.replace("doxoade.", "")
        icon = f"{Fore.GREEN}✔ OK" if status == "OK" else f"{Fore.RED}✘ {status}"
        echo(f"   {clean_name:<20} {icon}{Style.RESET_ALL}")