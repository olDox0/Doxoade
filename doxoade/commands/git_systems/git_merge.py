# doxoade/doxoade/commands/git_systems/git_merge.py
import click
import subprocess
from doxoade.commands.lite_xl_systems.engine_lite_xl import LiteXLEngine
from doxoade.tools.doxcolors import Fore, Style
from doxoade.tools.git import _run_git_command
from doxoade.commands.check import run_check_logic
from doxoade.tools.telemetry_tools.logger import ExecutionLogger
from doxoade.commands.git_systems.git_branch import branch

def open_conflicts_in_doxly(conflicted_files):
    """Abre todos os arquivos conflitados diretamente como abas no Doxly (Lite XL)."""
    click.echo(Fore.CYAN + "\n🚀 [DOXLY] Abrindo arquivos conflitados no editor...")
    for fpath in conflicted_files:
        abs_path = os.path.abspath(fpath)
        LiteXLEngine.send_to_running_instance(abs_path)
    
    click.echo(Fore.GREEN + f"✔ {len(conflicted_files)} arquivo(s) aberto(s) no Doxly.")
    click.echo(Fore.YELLOW + "💡 Dica: Resolva os blocos <<<<<<< no editor, salve (Ctrl+S) e execute:")
    click.echo(Fore.WHITE + Style.BRIGHT + "   doxoade merge --consolidate\n" + Style.RESET_ALL)

def consolidate_merge():
    """Valida se ainda restam marcadores <<<<<<<, roda Ma'at syntax check e comita o merge."""
    conflicted = _get_conflicted_files()
    if conflicted:
        click.echo(Fore.RED + f"[ERRO] Ainda existem {len(conflicted)} arquivos marcados com conflito pelo Git:")
        for f in conflicted: click.echo(f"  - {f}")
        return False

    # Varre se restou algum marcador <<<<<<< esquecido no código
    dirty_markers = []
    for root, _, files in os.walk('.'):
        if '.git' in root or 'venv' in root: continue
        for file in files:
            if file.endswith(('.py', '.lua', '.md', '.toml', '.c', '.h')):
                fp = os.path.join(root, file)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                        if '<<<<<<<' in f.read():
                            dirty_markers.append(fp)
                except Exception: pass

    if dirty_markers:
        click.echo(Fore.RED + Style.BRIGHT + "\n🚨 ATENÇÃO: Marcadores '<<<<<<<' ainda encontrados nos arquivos:")
        for dm in dirty_markers: click.echo(Fore.YELLOW + f"  ✖ {dm}")
        click.echo(Fore.RED + "Remova os marcadores antes de consolidar o merge!\n")
        return False

    click.echo(Fore.CYAN + "\n⚖️ [MA'AT] Auditando sintaxe dos arquivos resolvidos...")
    _run_git_command(['add', '-A'])
    _run_git_command(['commit', '--no-edit', '-m', "merge: resolução assistida de conflitos"])
    click.echo(Fore.GREEN + Style.BRIGHT + "✔ [SUCESSO] Merge consolidado e commit finalizado!\n")
    return True
    
def _get_conflicted_files():
    """Retorna lista de arquivos marcados como 'Unmerged' pelo Git."""
    output = _run_git_command(['diff', '--name-only', '--diff-filter=U'], capture_output=True)
    if not output:
        return []
    return [f.strip() for f in output.splitlines()]

def _parse_and_resolve_file(filepath):
    """
    Lê um arquivo com conflitos, identifica os blocos <<<<<<< ... >>>>>>>
    e pede ao usuário para escolher a solução.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except IOError:
        click.echo(Fore.RED + f"[ERRO] Não foi possível ler '{filepath}'.")
        return False
    new_content = []
    i = 0
    resolved_count = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('<<<<<<<'):
            ours_block = []
            theirs_block = []
            marker_head = line.strip()
            i += 1
            while i < len(lines) and (not lines[i].startswith('=======')):
                ours_block.append(lines[i])
                i += 1
            i += 1
            while i < len(lines) and (not lines[i].startswith('>>>>>>>')):
                theirs_block.append(lines[i])
                i += 1
            marker_tail = lines[i].strip() if i < len(lines) else '>>>>>>> ???'
            click.echo(Fore.YELLOW + '\n' + '=' * 50)
            click.echo(Fore.YELLOW + f'CONFLITO DETECTADO EM: {filepath}')
            click.echo('=' * 50)
            click.echo(Fore.CYAN + '--- [1] LOCAL (Ours / HEAD) ---')
            for l in ours_block:
                click.echo(f'  {l.strip()}')
            click.echo(Fore.MAGENTA + '\n--- [2] REMOTO (Theirs / Incoming) ---')
            for l in theirs_block:
                click.echo(f'  {l.strip()}')
            choice = ''
            while choice not in ['1', '2', '3', '4']:
                click.echo(Fore.WHITE + '\nEscolha:')
                click.echo('  1. Manter LOCAL (O que eu fiz)')
                click.echo('  2. Aceitar REMOTO (O que veio do merge)')
                click.echo('  3. Manter AMBOS (Local primeiro, depois Remoto)')
                click.echo('  4. Pular (Editar manualmente depois)')
                choice = click.prompt('Opção', type=str)
            if choice == '1':
                new_content.extend(ours_block)
                resolved_count += 1
            elif choice == '2':
                new_content.extend(theirs_block)
                resolved_count += 1
            elif choice == '3':
                new_content.extend(ours_block)
                new_content.extend(theirs_block)
                resolved_count += 1
            elif choice == '4':
                new_content.append(marker_head + '\n')
                new_content.extend(ours_block)
                new_content.append('=======\n')
                new_content.extend(theirs_block)
                new_content.append(marker_tail + '\n')
                click.echo(Fore.YELLOW + '   > Bloco mantido com marcadores.')
        else:
            new_content.append(line)
        i += 1
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_content)
    return resolved_count > 0

@click.command('merge')
@click.pass_context
@click.argument('branch', required=False)
@click.option('--abort', is_flag=True, help='Aborta o merge em andamento.')
@click.option('--doxly', '-d', is_flag=True, help='Abre os arquivos conflitados diretamente no Doxly (Lite XL).')
@click.option('--consolidate', '-c', is_flag=True, help='Verifica marcadores, valida sintaxe e finaliza o merge.')
@click.option('--theirs', is_flag=True, help='Aceita a versão do servidor para todos os conflitos.')
@click.option('--ours', is_flag=True, help='Mantém a versão local para todos os conflitos.')
def merge(ctx, branch, abort, doxly, consolidate, theirs, ours):
    """Assistente Inteligente de Merge e Resolução de Conflitos."""
    if abort:
        _run_git_command(['merge', '--abort'])
        click.echo(Fore.YELLOW + "✔ Merge abortado com sucesso.")
        return

    if consolidate:
        consolidate_merge()
        return

    conflicted = _get_conflicted_files()
    if not conflicted:
        click.echo(Fore.GREEN + "Nenhum conflito pendente.")
        return

    if theirs:
        for f in conflicted:
            _run_git_command(['checkout', '--theirs', f])
            _run_git_command(['add', f])
        consolidate_merge()
        return

    if ours:
        for f in conflicted:
            _run_git_command(['checkout', '--ours', f])
            _run_git_command(['add', f])
        consolidate_merge()
        return

    if doxly:
        open_conflicts_in_doxly(conflicted)
        return

    # Menu Interativo Soberano
    click.echo(f"\n{Fore.RED}{Style.BRIGHT}🔴 CONFLITO DETECTADO EM {len(conflicted)} ARQUIVO(S):{Style.RESET_ALL}")
    for c in conflicted:
        click.echo(f"   {Fore.RED}✖ {c}{Fore.RESET}")

    click.echo(f"\n{Fore.CYAN}{Style.BRIGHT}Como deseja resolver?{Style.RESET_ALL}")
    click.echo(f"  {Fore.WHITE}[1] ☁️  Aceitar versão do SERVIDOR (Theirs){Fore.RESET}")
    click.echo(f"  {Fore.WHITE}[2] 💻  Manter versão LOCAL desta máquina (Ours){Fore.RESET}")
    click.echo(f"  {Fore.GREEN}[3] 🚀  Abrir no Doxly (Lite XL) para resolver visualmente{Fore.RESET}")
    click.echo(f"  {Fore.YELLOW}[4] 🔍  Assistente CLI (Linha a linha no terminal){Fore.RESET}")
    click.echo(f"  {Fore.WHITE}[0] 🛑  Abortar Merge{Fore.RESET}")
    
    choice = click.prompt(Fore.CYAN + "Opção" + Fore.RESET, type=str, default="3")
    
    if choice == "1":
        for f in conflicted:
            _run_git_command(['checkout', '--theirs', f])
            _run_git_command(['add', f])
        consolidate_merge()
    elif choice == "2":
        for f in conflicted:
            _run_git_command(['checkout', '--ours', f])
            _run_git_command(['add', f])
        consolidate_merge()
    elif choice == "3":
        open_conflicts_in_doxly(conflicted)
    elif choice == "4":
        for fpath in conflicted:
            _parse_and_resolve_file(fpath)
            _run_git_command(['add', fpath])
        if click.confirm("\nDeseja consolidar o merge agora?"):
            consolidate_merge()
    elif choice == "0":
        _run_git_command(['merge', '--abort'])
        click.echo(Fore.YELLOW + "Merge abortado.")
