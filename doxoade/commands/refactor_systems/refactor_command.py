# -*- coding: utf-8 -*-
# doxoade/commands/refactor_systems/refactor_command.py
"""
doxoade refactor path <arquivo_ou_pasta> --target nome_da_funcao
doxoade refactor refs <projeto_ou_pasta> --target nome_da_funcao
doxoade refactor move <arquivo_origem.py> <arquivo_destino.py> --target nome_da_funcao --root .
doxoade refactor verify <projeto_ou_pasta> --target nome_da_funcao --from modulo.novo
doxoade refactor verify <projeto_ou_pasta> --target nome_da_funcao --from modulo.novo --fix
doxoade refactor rename <modulo_antigo> <modulo_novo> --root . --apply
"""

from __future__ import annotations

import click

from pathlib import Path

@click.group(name="refactor")
def refactor_group() -> None:
    """Ferramentas de refatoração de código Python.

    Permite localizar definições, rastrear referências, mover funções entre
    módulos, verificar consistência de imports e renomear módulos inteiros.

    \b
    Exemplos:
      doxoade refactor path src/ -t minha_funcao
      doxoade refactor refs . -t minha_funcao
      doxoade refactor move a.py b.py -t minha_funcao --root .
      doxoade refactor verify . -t minha_funcao --from meu.modulo
      doxoade refactor verify . -t minha_funcao --from meu.modulo --fix
      doxoade refactor rename modulo.velho modulo.novo --root . --apply
    """

@refactor_group.command("path")
@click.argument("target_path", metavar="ARQUIVO_OU_PASTA", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--target", "-t", "targets",
    multiple=True,
    required=True,
    metavar="NOME",
    help="Nome da função/classe a localizar. Pode ser repetido para múltiplos alvos.",
)
def refactor_path(target_path: Path, targets: tuple[str, ...]) -> None:
    """Localiza onde funções ou classes são *definidas*.

    Percorre ARQUIVO_OU_PASTA em busca das definições dos alvos informados
    e reporta o arquivo e linha de cada ocorrência.

    \b
    Status de saída:
      [OK]   — definição única encontrada
      [AMB]  — definição ambígua (múltiplos arquivos)
      [MISS] — nenhuma definição encontrada

    \b
    Exemplos:
      doxoade refactor path src/ -t parse_config
      doxoade refactor path utils.py -t helper -t validate
    """
    
    from .refactor_analysis import search_targets

    result = search_targets(target_path, list(targets))

    click.echo(f"[REFRACTOR] alvo: {result.root}")
    click.echo(f"[REFRACTOR] funções: {', '.join(result.targets)}")

    for name in result.targets:
        hits = result.hits.get(name, [])
        if not hits:
            click.secho(f"[MISS] {name} não encontrado.", fg="yellow")
            continue

        if len(hits) == 1:
            hit = hits[0]
            click.secho(f"[OK] {name} -> {hit.file}:{hit.line}", fg="green")
            continue

        click.secho(f"[AMB] {name} aparece em {len(hits)} locais:", fg="yellow")
        for hit in hits:
            click.echo(f"  - {hit.file}:{hit.line}  ({hit.qualname or hit.name})")


@refactor_group.command("refs")
@click.argument("target_path", type=click.Path(path_type=Path, exists=True))
@click.option("--target", "-t", "targets", multiple=True, required=True)
def refactor_refs(target_path: Path, targets: tuple[str, ...]) -> None:
    from .refactor_analysis import search_references

    result = search_references(target_path, list(targets))

    click.echo(f"[REF-USAGE] alvo: {result.root}")
    click.echo(f"[REF-USAGE] funções: {', '.join(result.targets)}")

    for name in result.targets:
        refs = result.refs.get(name, [])
        if not refs:
            click.secho(f"[MISS] nenhum uso encontrado para {name}.", fg="yellow")
            continue

        click.secho(f"[OK] {name} usado em {len(refs)} local(is):", fg="green")
        for ref in refs:
            click.echo(f"  - {ref.file}:{ref.line}")


@refactor_group.command("move")
@click.argument("source_file", metavar="ORIGEM.py", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("dest_file", metavar="DESTINO.py", type=click.Path(path_type=Path, dir_okay=False))
@click.option("--target", "-t", "function_name", required=True, metavar="NOME",
              help="Nome da função a mover de ORIGEM.py para DESTINO.py.")
@click.option("--root", "-r", "project_root",
              type=click.Path(path_type=Path, exists=True, file_okay=False),
              default=Path("."), show_default=True, metavar="PASTA",
              help="Raiz do projeto usada para resolver imports e atualizar referências.")
@click.option("--overwrite", is_flag=True,
              help="Substitui DESTINO.py inteiro se ele já existir (padrão: inserir no arquivo).")
def refactor_move(
    source_file: Path,
    dest_file: Path,
    function_name: str,
    project_root: Path,
    overwrite: bool,
) -> None:
    """Move uma função de um módulo para outro e atualiza os imports.

    Se DESTINO.py já existir, a função é *inserida* nele preservando o
    conteúdo atual e mesclando os imports necessários. Use --overwrite
    para substituir o arquivo inteiro.

    \b
    Exemplos:
      doxoade refactor move utils.py helpers.py -t parse_config --root .
      doxoade refactor move old.py new.py -t MyClass --root src/ --overwrite
    """
    from .refactor_assembler import move_function, prepare_move_plan

    plan = prepare_move_plan(project_root, source_file, function_name, dest_file)

    try:
        result = move_function(plan, overwrite=overwrite)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    click.secho("[OK] refatoração aplicada com sucesso.", fg="green")
    for note in result.notes:
        click.echo(f"  - {note}")


@refactor_group.command("verify")
@click.argument("target_path", type=click.Path(path_type=Path, exists=True))
@click.option("--target", "-t", "function_name", required=True)
@click.option("--from", "from_import", required=True, help="Ex: doxoade.commands.mobile_ide_terms")
@click.option("--fix", is_flag=True, help="Corrige automaticamente os imports")
def refactor_verify(
    target_path: Path,
    function_name: str,
    from_import: str,
    fix: bool,
) -> None:
    from .refactor_verify import verify_and_fix, verify_imports

    if fix:
        root = Path(target_path).resolve()
        click.echo(f"[VERIFY] alvo: {root}")
        click.echo(f"[VERIFY] função: {function_name}")
        click.echo(f"[VERIFY] esperado: from {from_import} import {function_name}")
        verify_and_fix(root, function_name, from_import, apply_fix=True)
        return

    result = verify_imports(target_path, function_name, from_import)

    click.echo(f"[VERIFY] alvo: {result.root}")
    click.echo(f"[VERIFY] função: {result.function_name}")
    click.echo(f"[VERIFY] esperado: {result.expected_import}")

    stats = {"OK": 0, "MISSING_IMPORT": 0, "WRONG_IMPORT": 0, "MULTIPLE_IMPORTS": 0}

    for issue in result.issues:
        stats[issue.kind] += 1

        if issue.kind == "OK":
            click.secho(f"[OK] {issue.file}:{issue.line}", fg="green")
        elif issue.kind == "MISSING_IMPORT":
            click.secho(f"[MISS] {issue.file}:{issue.line} - {issue.detail}", fg="yellow")
        elif issue.kind == "WRONG_IMPORT":
            click.secho(f"[WRONG] {issue.file}:{issue.line} - {issue.detail}", fg="red")
        elif issue.kind == "MULTIPLE_IMPORTS":
            click.secho(f"[MULTI] {issue.file}:{issue.line} - {issue.detail}", fg="magenta")

    click.echo("\n[RESUMO]")
    for k, v in stats.items():
        click.echo(f"  {k}: {v}")
        
@refactor_group.command("rename")
@click.argument("old_module")
@click.argument("new_module")
@click.option(
    "--root",
    "-r",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=Path("."),
    show_default=True,
)
@click.option("--apply", is_flag=True, help="Aplica as mudanças.")
@click.option("--overwrite", is_flag=True, help="Sobrescreve o arquivo de destino se já existir.")
def refactor_rename(old_module: str, new_module: str, root: Path, apply: bool, overwrite: bool) -> None:
    from .refactor_rename_ast import rename_module_ast

    result = rename_module_ast(root.resolve(), old_module, new_module, apply=apply, overwrite=overwrite)

    click.echo(f"[RENAME] {result.old_module} -> {result.new_module}")
    click.echo(f"[RENAME] origem: {result.source_file}")
    click.echo(f"[RENAME] destino: {result.dest_file}")
    click.echo(f"[RENAME] arquivos afetados: {len(result.changed_files)}")
    click.echo(f"[RENAME] imports reescritos: {len(result.rewrites)}")
    click.echo(f"[RENAME] aplicado: {result.moved_file}")