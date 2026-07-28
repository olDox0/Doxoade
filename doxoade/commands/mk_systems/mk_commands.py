# doxoade/commands/mk_systems/mk_commands.py
import click
import os
from doxoade.tools.doxcolors import Fore, Style
from .mk_engine import MkEngine
from .mk_utils import open_in_notepadpp
from doxoade.tools.filesystem import _find_project_root

def register_mk_options(f):
    f = click.option('--architecture', '-a', type=click.Path(exists=True), help='Cria estrutura baseada em arquivo.')(f)
    f = click.option('--learning', '-l', type=click.Path(exists=True), help='Cria estrutura baseada em aprendizado.')(f)
    f = click.option('--up', is_flag=True, help='Abre os arquivos criados/modificados no Notepad++.')(f)
    f = click.option('--gitignore', '-gi', is_flag=True, help='Forja ou atualiza o .gitignore soberano na raiz.')(f)
    return f

def execute_mk_logic(base_path, items, architecture, learning, tree, up, gitignore):
    engine = MkEngine(base_path)
    root = _find_project_root(base_path)

    # 🛡️ [MK-GITIGNORE] O Ritual de Proteção
    if gitignore:
        from doxoade.commands.init import _generate_gitignore
        project_name = os.path.basename(os.path.abspath(base_path))
        gi_path = os.path.join(base_path, '.gitignore')
        
        with open(gi_path, 'w', encoding='utf-8') as f:
            f.write(_generate_gitignore(project_name))
            
        click.echo(Fore.GREEN + f"[🛡️ OK] .gitignore soberano forjado em: {gi_path}")
        engine.affected_files.append(gi_path)

    if tree:
        folder_name = os.path.basename(os.path.abspath(base_path))
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- [TREE] Topologia de '{folder_name}' ---")
        for line in engine.render_tree(base_path, root):
            click.echo(line)
        click.echo(Fore.CYAN + '------------------------------------------')
        return  # early return: --up não se aplica ao tree

    if architecture:
        click.echo(Fore.CYAN + f'--- [MK-ARCH] Construindo: {architecture} ---')
        for path, kind in engine.parse_architecture_file(architecture):
            color = Fore.YELLOW if kind == 'Movido' else (Fore.BLUE if kind == 'Mantido' else Fore.GREEN)
            click.echo(color + f'[{kind.upper():<10}]: {path}')
            
    elif learning:
        click.echo(Fore.CYAN + f'--- [MK-LEARN] Construindo: {learning} ---')
        for path, kind in engine.parse_architecture_file(learning):
            color = Fore.YELLOW if kind == 'Movido' else (Fore.BLUE if kind == 'Mantido' else Fore.GREEN)
            click.echo(color + f'[{kind.upper():<10}]: {path}')

    elif items:
        click.echo(Fore.CYAN + '--- [MK-ITEMS] Criando itens ---')
        for item in items:
            for expanded in engine._expand_and_create(0, item):
                click.echo(Fore.GREEN + f'[OK] {expanded}')

    if up:
        to_open = [f for f in engine.affected_files if os.path.isfile(f)]
        if to_open:
            click.echo(Fore.MAGENTA + f'--- [UP] Abrindo {len(to_open)} arquivo(s) no Notepad++ ---')
            open_in_notepadpp(to_open)
        else:
            click.echo(Fore.YELLOW + "--- [UP] Nenhum arquivo novo ou modificado para abrir. ---")