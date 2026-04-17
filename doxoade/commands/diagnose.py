# doxoade/doxoade/commands/diagnose.py
import os
from json import dumps
from click import command, option, echo, argument, Path
from doxoade.tools.doxcolors import Fore, Style
from doxoade.diagnostic.inspector import SystemInspector
from doxoade.tools.telemetry_tools.logger import ExecutionLogger

@command('diagnose')
@argument('path', required=False, type=Path(exists=True))
@option('--json', 'as_json', is_flag=True, help='Saída em formato JSON.')
@option('--view', '-v', 'detailed', is_flag=True, help='Visão detalhada das modificações.')
@option('--all', '-a', 'show_all', is_flag=True, help='Exibe todos os arquivos modificados.')
@option('--max', '-m', 'show_max', is_flag=True, help='Visualização total: ignora limites.')
@option('--code', '-c', 'show_code', is_flag=True, help='Exibe trechos de código modificados.')
@option('--comments', '-cm', 'only_comments', is_flag=True, help='Exibe apenas comentários modificados.')
def diagnose(path: str, as_json: bool, detailed: bool, show_all: bool, show_max: bool, show_code: bool, only_comments: bool):
    """Relatório completo de saúde do sistema e integridade."""
    inspector = SystemInspector()
    params = {'path': path, 'detailed': detailed, 'all': show_all, 'max': show_max, 'code': show_code, 'comments': only_comments}
    
    with ExecutionLogger('diagnose', path or '.', params):
        try:
            is_detailed = detailed or show_code or only_comments
            data = inspector.run_full_diagnosis(detailed=is_detailed, show_code=show_code, target_path=path)
            
            if as_json:
                echo(dumps(data, indent=2))
                return

            # Renderização de Seções
            if not (path and os.path.isfile(path) and show_code):
                _render_env(data.get('environment', {}))
            
            _render_git(data.get('git', {}), is_detailed, show_all, show_max, show_code, only_comments)
            
            if not path:
                _render_integrity(data.get('integrity', {}))
                
        except Exception as e:
            echo(f"\n{Fore.RED}❌ Erro durante o diagnóstico: {str(e)}{Style.RESET_ALL}")

def _render_env(env: dict):
    if not env: return
    echo(f'{Fore.WHITE}{Style.BRIGHT}\n🖥️  AMBIENTE DE EXECUÇÃO{Style.RESET_ALL}')
    echo(f"   OS:       {Fore.YELLOW}{env.get('os')} {env.get('release')} ({env.get('arch')}){Style.RESET_ALL}")
    echo(f"   Python:   {Fore.YELLOW}{env.get('python_version')}{Style.RESET_ALL}")
    
    v_active = env.get('venv_active')
    v_path = env.get('venv_path', '')
    path_display = v_path[-40:] if len(v_path) > 40 else v_path
    v_color = Fore.GREEN if v_active else Fore.RED
    v_text = 'ATIVO' if v_active else 'INATIVO'
    echo(f"   VENV:     {v_color}{v_text}{Style.RESET_ALL} (...{path_display})")

def _render_git(git: dict, detailed: bool, show_all: bool, show_max: bool, show_code: bool, only_comments: bool):
    if not git: return
    echo(f'{Fore.WHITE}{Style.BRIGHT}\n📦 ESTADO DO REPOSITÓRIO{Style.RESET_ALL}')
    if not git.get('is_git_repo'):
        echo(f'   {Fore.RED}Não é um repositório Git.{Style.RESET_ALL}')
        return
    echo(f"   Branch:   {Fore.GREEN}{git.get('branch')}{Style.RESET_ALL}")
    _render_git_status_logic(git, detailed, show_all, show_max, show_code, only_comments)
    _render_last_commit(git.get('last_commit_info'))
    _render_origin_delta(git.get('origin_main_delta'))

def _render_git_status_logic(git, detailed, show_all, show_max, show_code, only_comments):
    if git.get('dirty_tree'):
        echo(f'   Status:   {Fore.YELLOW}MODIFICADO (Alterações não salvas){Style.RESET_ALL}')
        echo(f"   Pendentes: {git.get('pending_count', 0)} arquivo(s)")
        if detailed and 'changes' in git:
            _render_detailed_changes(git['changes'], show_all, show_max, show_code, only_comments)
        else:
            _render_pending_simple(git.get('pending_files', []), show_all)
    else:
        echo(f'   Status:   {Fore.GREEN}LIMPO (Tudo salvo){Style.RESET_ALL}')

def _render_pending_simple(pending, show_all):
    if not pending: return
    limit = 10
    display_list = pending if show_all else pending[:limit]
    for f in display_list:
        echo(f'      {Fore.RED}• {f}{Style.RESET_ALL}')
    if not show_all and len(pending) > limit:
        echo(f'      {Style.DIM}... e mais {len(pending) - limit} arquivos (Use -a).{Style.RESET_ALL}')

def _render_last_commit(last):
    if last:
        # Uso de .get para evitar quebra se o hash ou autor sumirem
        h = last.get('hash', '000000')[:7]
        a = last.get('author', 'N/A')
        s = last.get('subject', 'No message')
        echo(f'\n   Último:   {Style.DIM}{h} - {a} : {s}{Style.RESET_ALL}')

def _render_detailed_changes(changes: list, show_all: bool, show_max: bool, show_code: bool, only_comments: bool):
    limit = 10
    display_list = changes if show_all or show_max else changes[:limit]
    for item in display_list:
        if only_comments and not item.get('comments'):
            continue
        _render_single_file_status(item)
        _render_file_content_router(item, show_max, show_code, only_comments)
    
    if not (show_all or show_max) and len(changes) > limit:
        echo(f'\n      {Style.DIM}... e mais {len(changes) - limit} arquivos (Use -a).{Style.RESET_ALL}')

def _render_file_content_router(item, show_max, show_code, only_comments):
    if only_comments:
        _render_comments_only(item.get('comments', []))
    elif show_code:
        _render_code_hunks(item.get('hunks', []))
    else:
        _render_file_diff_content(item, show_max)

def _render_single_file_status(item: dict):
    added, rem = item.get('added', 0), item.get('removed', 0)
    stat_text = f"+{added} / -{rem}" if rem > 0 else f"+{added}"
    color = Fore.GREEN if added > 0 else Fore.WHITE
    
    brackets = f'{Fore.BLUE}[ {color}{stat_text:^7}{Style.RESET_ALL}{Fore.BLUE} ]{Style.RESET_ALL}'
    # Alinhamento dinâmico aprimorado
    path_str = item.get('path', 'unknown')
    dots = '.' * max(2, 35 - len(path_str))
    echo(f"      • M {brackets} {Fore.DIM}{dots}{Style.RESET_ALL} {Fore.CYAN}{path_str}{Style.RESET_ALL}")

def _render_file_diff_content(item: dict, show_max: bool):
    for f in item.get('functions', []):
        symbol, color = ('+', Fore.GREEN) if f['type'] == '+' else ('-', Fore.RED) if f['type'] == '-' else ('*', Fore.YELLOW)
        l_num = f"{f.get('line', ''):^4}"
        echo(f'          {color}{symbol} [ {l_num} ] {f["name"]}{Style.RESET_ALL}')
    
    comments = item.get('comments', [])
    display_comments = comments if show_max else comments[:3]
    for comm in display_comments:
        l_num = f"{comm.get('line', ''):^4}"
        echo(f'            {Style.DIM}[ {l_num} ] # {comm["text"]}{Style.RESET_ALL}')

def _render_code_hunks(hunks: list):
    for h in hunks:
        l_num = f"{h.get('line', ''):^4}"
        h_type = h.get('type', 'info')
        
        if h_type == 'add':
            color, prefix = (Fore.GREEN, '+')
        elif h_type == 'rem':
            color, prefix = (Fore.RED, '-')
        else:
            color, prefix = (Style.DIM, ' ')
            
        content = h.get('content', '')
        # Remove o primeiro caractere se for o marcador do diff do git
        display_content = content[1:] if content.startswith(('+', '-', ' ')) else content
        echo(f"          {color}{prefix} [ {l_num} ] {display_content}{Style.RESET_ALL}")

def _render_comments_only(comments: list):
    for comm in comments:
        c_type = comm.get('type', '+')
        color, symbol = (Fore.GREEN, '+') if c_type == '+' else (Fore.RED, '-') if c_type == '-' else (Fore.YELLOW, '*')
        l_tag = f"{str(comm.get('line', '')):^4}"
        echo(f"          {color}{symbol} [ {l_tag} ] # {comm['text']}{Style.RESET_ALL}")

def _render_integrity(core: dict):
    if not core: return
    echo(f'{Fore.WHITE}{Style.BRIGHT}\n🛡️  INTEGRIDADE DO NÚCLEO{Style.RESET_ALL}')
    for mod, status in core.items():
        # Corrige visualização de módulos internos
        display_name = mod.replace('doxoade.', '')
        icon = f'{Fore.GREEN}✔ OK' if status == 'OK' else f'{Fore.RED}✘ {status}'
        echo(f'   {display_name:<25} {icon}{Style.RESET_ALL}')

def _render_origin_delta(delta: dict):
    if not delta: return
    base_ref = delta.get('base_ref', 'origin/main')
    echo(f'\n   {Fore.CYAN}Comparação ({base_ref} ↔ HEAD):{Style.RESET_ALL}')
    echo(f"      Ahead:  {Fore.GREEN}{delta.get('ahead', 0)}{Style.RESET_ALL} | Behind: {Fore.YELLOW}{delta.get('behind', 0)}{Style.RESET_ALL}")
    
    updates = delta.get('updates', [])
    if updates:
        echo(f'      {Fore.WHITE}Commits recentes:{Style.RESET_ALL}')
        for line in updates[:5]:
            echo(f'         {Fore.GREEN}•{Style.RESET_ALL} {line}')