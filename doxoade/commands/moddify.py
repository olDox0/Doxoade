# doxoade/commands/moddify.py
import click
#import os
import shutil
from colorama import Fore

from ..chronos import chronos_recorder

def _backup_file(file_path):
    shutil.copy2(file_path, f"{file_path}.bak")

def _read_lines(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.readlines()

def _write_lines(file_path, lines):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
    except FileNotFoundError:
        old_content = ""

    new_content = "".join(lines)
    
    # REGISTRA NO CHRONOS
    chronos_recorder.log_file_change(file_path, old_content, new_content, operation='MODIFY')

def _parse_line_range(range_str, max_lines):
    """Converte '1-10' ou '1,3,5' em um set de inteiros."""
    lines = set()
    parts = range_str.split(',')
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            start, end = int(start), int(end)
            lines.update(range(start, end + 1))
        else:
            lines.add(int(part))
    
    # Filtra linhas válidas (1-based)
    return {l for l in lines if 1 <= l <= max_lines}

@click.group('moddify')
def moddify():
    """Ferramentas de modificação cirúrgica de arquivos."""
    pass

@moddify.command('show')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--search', '-s', help="Filtra linhas contendo este texto.")
@click.option('--part', '-p', help="Exibe intervalo de linhas (ex: '10-20').")
def mod_show(file_path, search, part):
    """Exibe o conteúdo do arquivo com filtros."""
    lines = _read_lines(file_path)
    
    target_lines = set()
    
    if part:
        target_lines = _parse_line_range(part, len(lines))
    else:
        target_lines = set(range(1, len(lines) + 1))
        
    click.echo(Fore.CYAN + f"--- {file_path} ---")
    for i, line in enumerate(lines):
        line_num = i + 1
        if line_num not in target_lines: continue
        
        if search and search not in line: continue
        
        # Destaca o termo de busca
        display_line = line.rstrip()
        if search:
            display_line = display_line.replace(search, Fore.RED + search + Fore.WHITE)
            
        click.echo(f"{Fore.BLUE}{line_num:4}:{Fore.WHITE} {display_line}")

@moddify.command('replace')
@click.argument('file_path', type=click.Path(exists=True))
@click.argument('pairs', nargs=-1)
@click.option('--line', '-l', help="Aplica apenas nas linhas especificadas (ex: '10' ou '10-20').")
def mod_replace(file_path, pairs, line):
    """
    Substitui texto em lote.
    Uso: replace arquivo.txt "velho1" "novo1" "velho2" "novo2"
    """
    if len(pairs) % 2 != 0:
        click.echo(Fore.RED + "Erro: O número de argumentos de substituição deve ser par (velho novo).")
        return

    _backup_file(file_path)
    lines = _read_lines(file_path)
    
    target_lines = None
    if line:
        target_lines = _parse_line_range(line, len(lines))

    # Constrói dicionário de trocas
    replacements = []
    for i in range(0, len(pairs), 2):
        replacements.append((pairs[i], pairs[i+1]))

    new_lines = []
    count = 0
    
    for i, content in enumerate(lines):
        line_num = i + 1
        
        # Se filtro de linha estiver ativo e não for a linha, mantém original
        if target_lines and line_num not in target_lines:
            new_lines.append(content)
            continue
            
        current_line = content
        for old, new in replacements:
            if old in current_line:
                current_line = current_line.replace(old, new)
                count += 1
        new_lines.append(current_line)

    _write_lines(file_path, new_lines)
    click.echo(Fore.GREEN + f"[MODDIFY] Realizadas {count} substituições em {file_path}.")

@moddify.command('remove')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--line', '-l', help="Linhas para remover (ex: '10', '1-5', '1,3').")
@click.option('--content', '-c', help="Conteúdo exato da linha para remover.")
def mod_remove(file_path, line, content):
    """Remove linhas por número (intervalo) ou conteúdo."""
    _backup_file(file_path)
    lines = _read_lines(file_path)
    
    lines_to_remove = set()
    
    if line:
        lines_to_remove.update(_parse_line_range(line, len(lines)))
        
    new_lines = []
    removed_count = 0
    
    for i, l in enumerate(lines):
        line_num = i + 1
        
        if line_num in lines_to_remove:
            removed_count += 1
            continue
            
        if content and content.strip() == l.strip():
            removed_count += 1
            continue
            
        new_lines.append(l)
            
    _write_lines(file_path, new_lines)
    click.echo(Fore.GREEN + f"[MODDIFY] Removidas {removed_count} linha(s).")

@moddify.command('add')
@click.argument('file_path', type=click.Path(exists=True))
@click.argument('content')
@click.option('--line', '-l', type=int, help="Número da linha onde inserir.")
@click.option('--delimiter', '-d', default='@@', help="Delimitador de nova linha (padrão: @@).")
def mod_add(file_path, content, line, delimiter):
    """
    Adiciona linhas. Use '@@' para quebras de linha.
    Ex: add arq.py "def foo():@@    return 1" --line 10
    """
    _backup_file(file_path)
    lines = _read_lines(file_path)
    
    # Separa o conteúdo em múltiplas linhas
    content_lines = content.split(delimiter)
    # Adiciona a quebra de linha real ao final de cada uma
    new_lines_to_insert = [l + '\n' for l in content_lines]
    
    if line:
        if line < 1: line = 1
        insert_idx = line - 1
        
        if insert_idx > len(lines):
            lines.extend(new_lines_to_insert)
        else:
            # Insere a lista na posição (slicing assignment)
            lines[insert_idx:insert_idx] = new_lines_to_insert
            
        loc_msg = f"na linha {line}"
    else:
        lines.extend(new_lines_to_insert)
        loc_msg = "ao final"
        
    _write_lines(file_path, lines)
    count = len(new_lines_to_insert)
    click.echo(Fore.GREEN + f"[MODDIFY] Adicionado {count} linha(s) em {file_path} ({loc_msg}).")