# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_commands.py
"""
CLI de Topologia e Visualização — Mk Commands Nexus.
Fase 3: Suporte a --apply (Dry-Run por padrão) e -t com pasta via items.
"""
from __future__ import annotations
import os
import click
from doxoade.tools.doxcolors import Fore, Style
from .mk_engine import MkEngine
from .mk_utils import open_in_notepadpp
from doxoade.tools.filesystem import _find_project_root
from doxoade.tools.editor_dispatch import EditorDispatcher


def register_mk_options(f):
    # Não declaramos --tree aqui pois ele já é declarado no cli.py
    f = click.option('--apply', '--run', '-w', 'apply_flag', is_flag=True,
                     help='Aplica as alterações no disco (sai do modo DRY-RUN).')(f)
    f = click.option('--architecture', '-a', type=click.Path(exists=True),
                     help='Cria estrutura baseada em arquivo de arquitetura.')(f)
    f = click.option('--learning', '-l', type=click.Path(exists=True),
                     help='Cria estrutura baseada em aprendizado.')(f)
    f = click.option('--up', is_flag=True,
                     help='Abre os arquivos criados/modificados no Doxly (Lite XL).')(f)
    f = click.option('--gitignore', '-gi', is_flag=True,
                     help='Forja ou atualiza o .gitignore soberano na raiz.')(f)
    return f


def execute_mk_logic(base_path, items, architecture, learning, tree, up, gitignore, apply_flag=False, **kwargs):
    is_dry_run = not apply_flag
    engine = MkEngine(base_path, apply=apply_flag)
    root = _find_project_root(base_path)

    # 1. Modo Árvore (-t ou -t <pasta>)
    if tree:
        # Se o usuário passou um caminho junto com -t (ex: doxoade mk -t pasta/), ele vem em items[0]!
        target_dir = items[0] if (items and len(items) > 0) else base_path
        target_abs = os.path.abspath(target_dir)

        if not os.path.exists(target_abs):
            click.echo(Fore.RED + f"✖ Diretório não encontrado: {target_abs}" + Style.RESET_ALL)
            return

        folder_name = os.path.basename(target_abs) or target_abs
        click.echo(Fore.CYAN + Style.BRIGHT + f"\n--- [TREE] Topologia de '{folder_name}' ---")
        for line in engine.render_tree(target_abs, root):
            click.echo(line)
        click.echo(Fore.CYAN + '------------------------------------------' + Style.RESET_ALL)
        return

    # 2. Modo .gitignore soberano
    if gitignore:
        from doxoade.commands.init import _generate_gitignore
        project_name = os.path.basename(os.path.abspath(base_path))
        gi_path = os.path.join(base_path, '.gitignore')
        if not is_dry_run:
            with open(gi_path, 'w', encoding='utf-8') as f:
                f.write(_generate_gitignore(project_name))
            click.echo(Fore.GREEN + f"[🛡️ OK] .gitignore soberano forjado em: {gi_path}" + Style.RESET_ALL)
            engine.affected_files.append(gi_path)
        else:
            click.echo(Fore.YELLOW + f"[DRY-RUN] Planejado .gitignore soberano em: {gi_path}" + Style.RESET_ALL)

    # Cabeçalho de simulação ou aplicação
    if is_dry_run:
        click.echo(Fore.YELLOW + Style.BRIGHT + "🔍 [DRY-RUN] MODO DE SIMULAÇÃO ATIVO (Nenhuma alteração gravada no disco)" + Style.RESET_ALL)
    else:
        click.echo(Fore.GREEN + Style.BRIGHT + "🚀 [APPLY] APLICANDO MODIFICAÇÕES NO DISCO" + Style.RESET_ALL)

    # 3. Processamento de Arquitetura
    if architecture:
        tag = "[DRY-RUN:ARCH]" if is_dry_run else "[MK-ARCH]"
        click.echo(Fore.CYAN + f'--- {tag} Processando: {architecture} ---' + Style.RESET_ALL)
        for path, kind in engine.parse_architecture_file(architecture):
            if not path:
                continue
            if 'Diretório' in kind:
                color = Fore.CYAN
            elif 'Mantido' in kind:
                color = Fore.BLUE
            elif 'Movido' in kind:
                color = Fore.YELLOW
            else:
                color = Fore.GREEN
            click.echo(color + f'[{kind.upper():<20}]: {path}' + Style.RESET_ALL)

    elif learning:
        tag = "[DRY-RUN:LEARN]" if is_dry_run else "[MK-LEARN]"
        click.echo(Fore.CYAN + f'--- {tag} Processando: {learning} ---' + Style.RESET_ALL)
        for path, kind in engine.parse_architecture_file(learning):
            if not path:
                continue
            color = Fore.BLUE if 'Mantido' in kind else Fore.GREEN
            click.echo(color + f'[{kind.upper():<20}]: {path}' + Style.RESET_ALL)

    elif items:
        tag = "[DRY-RUN:ITEMS]" if is_dry_run else "[MK-ITEMS]"
        click.echo(Fore.CYAN + f'--- {tag} Processando itens ---' + Style.RESET_ALL)
        for item in items:
            for expanded in engine._expand_and_create(0, item):
                click.echo(Fore.GREEN + f'[OK] {expanded}' + Style.RESET_ALL)

    # Rodapé educativo de Dry-Run
    if is_dry_run and (architecture or learning or items):
        click.echo(Fore.YELLOW + "\n💡 Dica: Para efetivar a criação no disco, use a flag --apply (ou --run):" + Style.RESET_ALL)
        cmd_hint = f"doxoade mk -a {architecture}" if architecture else "doxoade mk ..."
        click.echo(Fore.WHITE + f"   {cmd_hint} --apply" + (" --up" if up else "") + Style.RESET_ALL + "\n")

    # 4. Abertura no Doxly (--up)
    if up:
        to_open = [f for f in engine.affected_files if os.path.isfile(f)]
        if to_open:
            if not is_dry_run:
                ok, editor_name = EditorDispatcher.open_files(to_open)
                badge_color = Fore.GREEN if ok else Fore.YELLOW
                click.echo(Fore.CYAN + f'--- [UP] Abrindo {len(to_open)} arquivo(s) via {badge_color}{editor_name}{Fore.CYAN} ---' + Style.RESET_ALL)
            else:
                click.echo(Fore.YELLOW + f"--- [UP] {len(to_open)} arquivo(s) seriam abertos no Doxly (ignorado em Dry-Run) ---" + Style.RESET_ALL)
        else:
            if not is_dry_run:
                click.echo(Fore.YELLOW + "--- [UP] Nenhum arquivo novo ou modificado para abrir. ---" + Style.RESET_ALL)
