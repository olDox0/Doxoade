# doxoade/doxoade/commands/refactor_systems/refactor_preview.py
import difflib
import click
from pathlib import Path
from typing import List


def print_snippet_diff(
    file_path: Path,
    original_lines: List[str],
    new_lines: List[str],
    context: int = 3,
) -> bool:
    """
    Exibe um diff unificado e colorido no terminal (Estilo Git).
    Retorna True se houver diferenças, False caso contrário.
    """
    orig = [l if l.endswith('\n') else l + '\n' for l in original_lines]
    new  = [l if l.endswith('\n') else l + '\n' for l in new_lines]

    diff = difflib.unified_diff(
        orig, new,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm='',
        n=context,
    )

    diff_lines = list(diff)
    if not diff_lines:
        return False

    click.echo(f"\n{click.style(f'📄 Arquivo: {file_path}', fg='cyan', bold=True)}")
    click.echo(click.style('─' * 60, fg='bright_black'))

    for line in diff_lines:
        line = line.rstrip('\n')
        if line.startswith('---') or line.startswith('+++'):
            click.echo(click.style(line, fg='bright_cyan'))
        elif line.startswith('@@'):
            click.echo(click.style(line, fg='bright_blue'))
        elif line.startswith('-'):
            click.echo(click.style(line, fg='red'))
        elif line.startswith('+'):
            click.echo(click.style(line, fg='green'))
        else:
            click.echo(click.style(line, fg='white'))

    click.echo(click.style('─' * 60, fg='bright_black'))
    return True


def preview_file_change(
    file_path: Path,
    original_text: str,
    new_text: str,
    context: int = 3,
) -> bool:
    """Wrapper que aceita strings completas em vez de listas de linhas."""
    if original_text == new_text:
        return False
    orig_lines = original_text.splitlines(keepends=True)
    new_lines  = new_text.splitlines(keepends=True)
    return print_snippet_diff(file_path, orig_lines, new_lines, context)


def preview_rewrite_group(
    file_path: Path,
    rewrites: list,
    source_text: str,
    context: int = 2,
) -> bool:
    """
    Exibe diffs agrupados para uma lista de ImportRewrite (usado pelo rename).
    Aplica as rewrites em memória e compara com o original.
    """
    if not rewrites:
        return False

    lines = source_text.splitlines(keepends=True)
    new_lines = list(lines)

    # Aplica em ordem reversa para não deslocar índices
    for rw in sorted(rewrites, key=lambda x: (x.lineno, x.end_lineno), reverse=True):
        start = max(rw.lineno - 1, 0)
        end = max(rw.end_lineno, start + 1)
        replacement = rw.rewritten if rw.rewritten.endswith('\n') else rw.rewritten + '\n'
        new_lines[start:end] = [replacement]

    return print_snippet_diff(file_path, lines, new_lines, context)