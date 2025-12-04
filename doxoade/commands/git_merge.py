# doxoade/commands/git_merge.py
import click
#import os
#import sys
#import re
from colorama import Fore, Style
from ..shared_tools import ExecutionLogger, _run_git_command #, _get_code_snippet
from .check import run_check_logic

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
    
    # Regex para identificar marcadores
    # <<<<<<< HEAD (Ours)
    # ...
    # =======
    # ...
    # >>>>>>> BranchName (Theirs)

    while i < len(lines):
        line = lines[i]
        
        if line.startswith('<<<<<<<'):
            # Início de conflito
            ours_block = []
            theirs_block = []
            marker_head = line.strip()
            
            i += 1
            # Captura bloco OURS
            while i < len(lines) and not lines[i].startswith('======='):
                ours_block.append(lines[i])
                i += 1
            
            i += 1 # Pula =======
            
            # Captura bloco THEIRS
            while i < len(lines) and not lines[i].startswith('>>>>>>>'):
                theirs_block.append(lines[i])
                i += 1
            
            marker_tail = lines[i].strip() if i < len(lines) else ">>>>>>> ???"
            
            # Apresentação Interativa
            click.echo(Fore.YELLOW + "\n" + "="*50)
            click.echo(Fore.YELLOW + f"CONFLITO DETECTADO EM: {filepath}")
            click.echo("="*50)
            
            click.echo(Fore.CYAN + "--- [1] LOCAL (Ours / HEAD) ---")
            for l in ours_block: click.echo(f"  {l.strip()}")
            
            click.echo(Fore.MAGENTA + "\n--- [2] REMOTO (Theirs / Incoming) ---")
            for l in theirs_block: click.echo(f"  {l.strip()}")
            
            choice = ""
            while choice not in ['1', '2', '3', '4']:
                click.echo(Fore.WHITE + "\nEscolha:")
                click.echo("  1. Manter LOCAL (O que eu fiz)")
                click.echo("  2. Aceitar REMOTO (O que veio do merge)")
                click.echo("  3. Manter AMBOS (Local primeiro, depois Remoto)")
                click.echo("  4. Pular (Editar manualmente depois)")
                choice = click.prompt("Opção", type=str)
            
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
                # Mantém os marcadores para edição manual
                new_content.append(marker_head + '\n')
                new_content.extend(ours_block)
                new_content.append('=======\n')
                new_content.extend(theirs_block)
                new_content.append(marker_tail + '\n')
                click.echo(Fore.YELLOW + "   > Bloco mantido com marcadores.")
                
        else:
            new_content.append(line)
        
        i += 1

    # Salva o arquivo resolvido
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_content)
        
    return resolved_count > 0

@click.command('merge')
@click.pass_context
@click.argument('branch', required=False)
@click.option('--abort', is_flag=True, help="Aborta o merge em andamento.")
@click.option('--check-only', is_flag=True, help="Apenas verifica se há conflitos sem resolver.")
def merge(ctx, branch, abort, check_only):
    """
    Assistente de Merge Inteligente.
    Inicia merges ou resolve conflitos pendentes com validação de sintaxe.
    """
    with ExecutionLogger('merge', '.', ctx.params):
        
        # 1. Abortar
        if abort:
            click.echo(Fore.YELLOW + "Abortando merge...")
            if _run_git_command(['merge', '--abort']):
                click.echo(Fore.GREEN + "[OK] Merge abortado. Voltando ao estado anterior.")
            else:
                click.echo(Fore.RED + "[ERRO] Não há merge para abortar ou falha no git.")
            return

        # 2. Verificar Estado Atual
        conflicted_files = _get_conflicted_files()
        
        # Se o usuário passou um branch, ele quer INICIAR um merge
        if branch:
            if conflicted_files:
                click.echo(Fore.RED + "[ERRO] Você já tem conflitos pendentes. Resolva-os antes de iniciar outro merge.")
                click.echo(f"Arquivos: {', '.join(conflicted_files)}")
                return
                
            click.echo(Fore.CYAN + f"--- [MERGE] Iniciando merge com '{branch}' ---")
            result = _run_git_command(['merge', branch], capture_output=True) or ''
            
            if "Already up to date" in result:
                click.echo(Fore.GREEN + "[OK] Já atualizado.")
                return
            elif "CONFLICT" in result:
                click.echo(Fore.YELLOW + "[AVISO] Conflitos detectados pelo Git.")
                # Atualiza lista de conflitos
                conflicted_files = _get_conflicted_files()
            else:
                click.echo(Fore.GREEN + "[OK] Merge realizado com sucesso (Fast-forward ou Auto-merge).")
                return

        # 3. Resolver Conflitos (Se houver)
        if not conflicted_files:
            click.echo(Fore.GREEN + "Nenhum arquivo em estado de conflito.")
            return

        click.echo(Fore.CYAN + f"\n--- [RESOLVER] Existem {len(conflicted_files)} arquivo(s) com conflito ---")
        
        if check_only:
            for f in conflicted_files: click.echo(f"  - {f}")
            return

        files_resolved = []
        
        for fpath in conflicted_files:
            if _parse_and_resolve_file(fpath):
                click.echo(Fore.GREEN + f"   > Conflitos em '{fpath}' tratados.")
                
                # VALIDAÇÃO IMEDIATA (O Grande Diferencial do Doxoade)
                if fpath.endswith('.py'):
                    click.echo(Fore.WHITE + "   > Verificando integridade do código (Syntax Check)...")
                    # Roda check apenas neste arquivo, sem cache
                    check_res = run_check_logic('.', [], False, False, fast=True, target_files=[fpath], no_cache=True)
                    
                    if check_res['summary'].get('critical', 0) > 0:
                        click.echo(Fore.RED + "   [PERIGO] O arquivo resolvido tem erros de sintaxe!")
                        click.echo(Fore.YELLOW + "   Por favor, corrija manualmente antes de continuar.")
                        # Não adiciona ao stage
                        continue
                
                # Se passou no check ou não é python, adiciona ao stage
                if _run_git_command(['add', fpath]):
                    files_resolved.append(fpath)
            else:
                click.echo(Fore.YELLOW + f"   > '{fpath}' pulado ou sem marcadores padrão.")

        # 4. Conclusão
        remaining = len(conflicted_files) - len(files_resolved)
        if remaining == 0:
            click.echo(Fore.GREEN + Style.BRIGHT + "\n[SUCESSO] Todos os conflitos resolvidos e verificados!")
            if click.confirm("Deseja finalizar o merge (git commit)?"):
                _run_git_command(['commit', '--no-edit'])
                click.echo(Fore.GREEN + "[OK] Merge commit criado.")
        else:
            click.echo(Fore.YELLOW + f"\nAinda restam {remaining} arquivos com problemas. Rode 'doxoade merge' novamente após corrigir.")