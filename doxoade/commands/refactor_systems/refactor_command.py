# doxoade/doxoade/commands/refactor_systems/refactor_command.py
from __future__ import annotations
from pathlib import Path
import click
from .refactor_engine import RefactorEngine
from .refactor_utils import iter_python_files

def _find_project_root(path: Path) -> Path:
    """Sobe a árvore até encontrar um marcador de projeto."""
    base = path if path.is_dir() else path.parent
    for candidate in [base, *base.parents]:
        for marker in ('pyproject.toml', 'setup.py', 'setup.cfg', '.git'):
            if (candidate / marker).exists():
                return candidate
    return base

def _parse_orch_args(args: list[str]) -> tuple[list[str], list[str]]:
    """
    Extrai positionals e targets de args brutos.

    Suporta:
      -t FUNC            (um valor por flag)
      -t FUNC1 FUNC2     (vários valores até o próximo flag)
      --target FUNC
    """
    positionals: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ('-t', '--target'):
            i += 1
            while i < len(args) and (not args[i].startswith('-')):
                targets.append(args[i])
                i += 1
        elif a.startswith('-t') and len(a) > 2:
            targets.append(a[2:])
            i += 1
        elif not a.startswith('-'):
            positionals.append(a)
            i += 1
        else:
            i += 1
    return (positionals, targets)

def _sep(label: str = "", width: int = 60, color: str = "cyan") -> None:
    line = f"─{'─' * (width - 2)}─"
    if label:
        pad = max(0, width - len(label) - 4)
        line = f"─ {label} {'─' * pad}"
    click.secho(line, fg=color)

def _run_analyze(source: Path, targets: list[str]) -> None:
    from .refactor_analysis import search_references, search_targets
    source = source.resolve()
    _sep()
    click.secho(f' ANALYZE  {source}', fg='cyan', bold=True)
    click.secho(f" funções: {', '.join(targets)}", fg='cyan')
    _sep()
    click.secho('\n[1/2] Localizando definições…', fg='blue', bold=True)
    path_result = search_targets(source, targets)
    found_any = False
    for name in path_result.targets:
        hits = path_result.hits.get(name, [])
        if not hits:
            click.secho(f'  [MISS] {name} — não encontrado em {source}', fg='yellow')
        elif len(hits) == 1:
            h = hits[0]
            click.secho(f'  [OK]   {name} → {h.file}:{h.line}', fg='green')
            found_any = True
        else:
            click.secho(f'  [AMB]  {name} — {len(hits)} definições:', fg='yellow')
            for h in hits:
                click.echo(f'    - {h.file}:{h.line}  ({h.qualname or h.name})')
            found_any = True
    click.secho('\n[2/2] Rastreando usos…', fg='blue', bold=True)
    refs_result = search_references(source, targets)
    for name in refs_result.targets:
        refs = refs_result.refs.get(name, [])
        if not refs:
            click.secho(f'  [MISS] {name} — sem usos em {source}', fg='yellow')
        else:
            click.secho(f'  [OK]   {name} — {len(refs)} uso(s):', fg='green')
            for ref in refs:
                click.echo(f'    - {ref.file}:{ref.line}')
    _sep()
    click.secho(' DONE  análise concluída.', fg='cyan', bold=True)
    _sep()

def _run_move_pipeline(source: Path, dest: Path, function_name: str) -> None:
    from .refactor_analysis import search_references, search_targets
    from .refactor_assembler import move_function, prepare_move_plan
    from .refactor_verify import verify_and_fix, verify_imports
    source = source.resolve()
    dest = dest.resolve()
    project_root = _find_project_root(source)
    _sep()
    click.secho(f' PIPELINE  {source.name} → {dest.name}', fg='cyan', bold=True)
    click.secho(f' função:   {function_name}', fg='cyan')
    click.secho(f' raiz:     {project_root}', fg='cyan')
    _sep()
    click.secho('\n[1/4] Localizando definição…', fg='blue', bold=True)
    path_result = search_targets(source, [function_name])
    hits = path_result.hits.get(function_name, [])
    if not hits:
        raise click.ClickException(f"Função '{function_name}' não encontrada em {source}")
    if len(hits) > 1:
        locs = ', '.join((f'{h.file}:{h.line}' for h in hits))
        raise click.ClickException(f"Função '{function_name}' ambígua em {source} ({locs})")
    click.secho(f'  [OK] {function_name} → {hits[0].file}:{hits[0].line}', fg='green')
    click.secho('\n[2/4] Rastreando usos no projeto…', fg='blue', bold=True)
    refs_result = search_references(project_root, [function_name])
    refs = refs_result.refs.get(function_name, [])
    if refs:
        click.secho(f'  [INFO] {len(refs)} uso(s) encontrado(s):', fg='cyan')
        for ref in refs:
            click.echo(f'    - {ref.file}:{ref.line}')
    else:
        click.secho('  [INFO] Nenhum uso encontrado no projeto.', fg='yellow')
    click.secho('\n[3/4] Movendo função…', fg='blue', bold=True)
    try:
        plan = prepare_move_plan(project_root, source, function_name, dest)
        result = move_function(plan)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.secho('  [OK] função movida com sucesso.', fg='green')
    for note in result.notes:
        click.echo(f'    - {note}')
    dest_module = plan.dest_module
    click.secho('\n[4/4] Verificando imports…', fg='blue', bold=True)
    verify_result = verify_imports(project_root, function_name, dest_module)
    ok_issues = [i for i in verify_result.issues if i.kind == 'OK']
    problem_issues = [i for i in verify_result.issues if i.kind != 'OK']
    if ok_issues:
        click.secho(f'  [OK] {len(ok_issues)} arquivo(s) com import correto.', fg='green')
    if problem_issues:
        click.secho(f'  [FIX] {len(problem_issues)} problema(s) encontrado(s):', fg='yellow')
        for issue in problem_issues:
            tag = {'MISSING_IMPORT': 'MISS', 'WRONG_IMPORT': 'WRONG', 'MULTIPLE_IMPORTS': 'MULTI'}.get(issue.kind, issue.kind)
            color = {'MISS': 'yellow', 'WRONG': 'red', 'MULTI': 'magenta'}.get(tag, 'white')
            click.secho(f'    [{tag}] {issue.file}:{issue.line} — {issue.detail}', fg=color)
        click.secho('  [FIX] Aplicando correções…', fg='yellow')
        verify_and_fix(project_root, function_name, dest_module)
        click.secho('  [OK] Imports corrigidos.', fg='green')
    else:
        click.secho('  [OK] Todos os imports estão corretos.', fg='green')
    _sep()
    click.secho(' DONE  pipeline concluído com sucesso.', fg='cyan', bold=True)
    _sep()

def _orchestrate(raw_args: list[str]) -> None:
    positionals, targets = _parse_orch_args(raw_args)
    if not positionals:
        raise click.UsageError('Informe ao menos FONTE.\n\n  Análise:  doxoade refactor <FONTE> -t <FUNC> [-t <FUNC2> ...]\n  Move:     doxoade refactor <FONTE> <DESTINO> -t <FUNC>')
    if not targets:
        raise click.UsageError('Especifique ao menos uma função com -t NOME.')
    source = Path(positionals[0])
    if not source.exists():
        raise click.BadParameter(f'Caminho não encontrado: {source}', param_hint='FONTE')
    if len(positionals) == 1:
        _run_analyze(source, targets)
    else:
        if len(targets) != 1:
            raise click.UsageError('Modo move aceita exatamente uma função por vez.\nUse: doxoade refactor <FONTE> <DESTINO> -t <FUNC>')
        dest = Path(positionals[1])
        _run_move_pipeline(source, dest, targets[0])

class _RefactorGroup(click.Group):
    """
    Despacha para subcomandos quando o primeiro argumento posicional é um
    subcomando reconhecido; caso contrário, executa o pipeline de orquestração.
    """
    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        first_pos = next((a for a in args if not a.startswith("-")), None)
        if first_pos is None or first_pos in self.commands:
            return super().parse_args(ctx, args)
        ctx.ensure_object(dict)
        ctx.obj["_orch_args"] = list(args)
        return []

    def invoke(self, ctx: click.Context) -> None:
        obj = ctx.obj or {}
        if "_orch_args" in obj:
            # Lógica de orquestração movida para cá se necessário
            return
        super().invoke(ctx)

@click.group(name='refactor', cls=_RefactorGroup, invoke_without_command=True, no_args_is_help=True)
def refactor_group() -> None:
    """Refatoração automática ou granular de código Python.

    \x08
    MODO RÁPIDO (pipeline automático):
      Análise    — doxoade refactor <FONTE> -t <FUNC1> [-t <FUNC2> ...]
      Move+Fix   — doxoade refactor <FONTE> <DESTINO> -t <FUNC>

    \x08
    SUBCOMANDOS (controle granular):
      path    Localiza onde uma função é definida
      refs    Rastreia todos os usos de uma função
      move    Move uma função entre módulos
      verify  Verifica consistência de imports
      rename  Renomeia um módulo inteiro

    \x08
    Exemplos rápidos:
      doxoade refactor src/ -t parse_config helper
      doxoade refactor utils.py helpers.py -t parse_config
    """

@refactor_group.command('path')
@click.argument('target_path', metavar='ARQUIVO_OU_PASTA', type=click.Path(path_type=Path, exists=True))
@click.option('--target', '-t', 'targets', multiple=True, required=True, metavar='NOME', help='Nome da função/classe a localizar. Repetível para múltiplos alvos.')
def refactor_path(target_path: Path, targets: tuple[str, ...]) -> None:
    """Localiza onde funções ou classes são *definidas*.

    \x08
    Status:
      [OK]   — definição única encontrada
      [AMB]  — definição ambígua (múltiplos arquivos)
      [MISS] — não encontrado

    \x08
    Exemplos:
      doxoade refactor path src/ -t parse_config
      doxoade refactor path utils.py -t helper -t validate
    """
    from .refactor_analysis import search_targets
    result = search_targets(target_path, list(targets))
    click.echo(f'[PATH] alvo: {result.root}')
    click.echo(f"[PATH] funções: {', '.join(result.targets)}")
    for name in result.targets:
        hits = result.hits.get(name, [])
        if not hits:
            click.secho(f'[MISS] {name} não encontrado.', fg='yellow')
        elif len(hits) == 1:
            h = hits[0]
            click.secho(f'[OK] {name} → {h.file}:{h.line}', fg='green')
        else:
            click.secho(f'[AMB] {name} aparece em {len(hits)} locais:', fg='yellow')
            for h in hits:
                click.echo(f'  - {h.file}:{h.line}  ({h.qualname or h.name})')

@refactor_group.command('refs')
@click.argument('target_path', metavar='PROJETO_OU_PASTA', type=click.Path(path_type=Path, exists=True))
@click.option('--target', '-t', 'targets', multiple=True, required=True, metavar='NOME', help='Nome da função/classe a rastrear. Repetível.')
def refactor_refs(target_path: Path, targets: tuple[str, ...]) -> None:
    """Rastreia todos os *usos* de funções ou classes(obs: não de arq., o audit lida com eles).
    \x08
    Exemplo:    
      doxoade refactor refs . -t função
      doxoade refactor refs . -t check
    
    \x08
    Status:
      [OK]   — usos encontrados (exibe contagem e locais)
      [MISS] — nenhum uso encontrado

    \x08
    Exemplos:
      doxoade refactor refs . -t parse_config
      doxoade refactor refs src/ -t helper -t validate
    """
    from .refactor_analysis import search_references
    result = search_references(target_path, list(targets))
    click.echo(f'[REFS] alvo: {result.root}')
    click.echo(f"[REFS] funções: {', '.join(result.targets)}")
    for name in result.targets:
        refs = result.refs.get(name, [])
        if not refs:
            click.secho(f'[MISS] nenhum uso encontrado para {name}.', fg='yellow')
        else:
            click.secho(f'[OK] {name} usado em {len(refs)} local(is):', fg='green')
            for ref in refs:
                # Exibe o contexto (import, attribute, definition, etc)
                ctx = click.style(f"({ref.context})", dim=True)
                click.echo(f'  - {ref.file}:{ref.line} {ctx}')

@refactor_group.command('move')
@click.argument('source_file', type=click.Path(exists=True, path_type=Path))
@click.argument('dest_file', type=click.Path(path_type=Path))
@click.option('--target', '-t', 'targets', multiple=True, help='Função/Classe específica.')
@click.option('--overwrite', is_flag=True, help='Sobrescreve destino.')
@click.option('--dry-run', is_flag=True, help='Apenas mostra o que seria feito, sem alterar arquivos.')
@click.option('--docstrings', '-d', is_flag=True, help='Inclui docstrings e strings f"" na refatoração.')
def refactor_move(source_file, dest_file, targets, overwrite, dry_run, docstrings):
    """Move funções ou o ARQUIVO INTEIRO (com visualização prévia)."""
    if dry_run:
        _sep("DRY RUN - SIMULAÇÃO", color="yellow")
    else:
        _sep("REFACTOR MOVE")

    project_root = _find_project_root(source_file)
    engine = RefactorEngine(base_path=project_root)
    
    success, msg = engine.move_function(
        source_file, 
        dest_file, 
        targets=targets, 
        overwrite=overwrite, 
        dry_run=dry_run,
        include_strings=docstrings # Passa a flag para o motor
    )
    
    if success:
        color = "yellow" if dry_run else "green"
        prefix = "[DRY-OK]" if dry_run else "[OK]"
        click.secho(f"\n  {prefix} {msg}", fg=color)
    else:
        click.secho(f"\n  [ERRO] {msg}", fg="red")

@refactor_group.command('verify')
@click.argument('target_path', metavar='PROJETO_OU_PASTA', type=click.Path(path_type=Path, exists=True))
@click.option('--target', '-t', 'function_name', required=True, metavar='NOME', help='Nome da função cujos imports serão verificados.')
@click.option('--from', 'from_import', required=True, metavar='MODULO', help='Módulo de onde a função deveria ser importada. Ex: myapp.utils')
@click.option('--fix', is_flag=True, help='Corrige automaticamente imports incorretos ou ausentes.')
def refactor_verify(target_path: Path, function_name: str, from_import: str, fix: bool) -> None:
    """Verifica (e opcionalmente corrige) a consistência dos imports de uma função.

    \x08
    Códigos de problema:
      [OK]    — import correto
      [MISS]  — função usada mas import ausente
      [WRONG] — importada de módulo errado
      [MULTI] — múltiplos imports conflitantes no mesmo arquivo

    \x08
    Exemplos:
      doxoade refactor verify . -t parse_config --from myapp.utils
      doxoade refactor verify src/ -t MyClass --from myapp.models --fix
    """
    from .refactor_verify import verify_and_fix, verify_imports
    if fix:
        root = Path(target_path).resolve()
        click.echo(f'[VERIFY] alvo: {root}')
        click.echo(f'[VERIFY] função: {function_name}')
        click.echo(f'[VERIFY] esperado: from {from_import} import {function_name}')
        verify_and_fix(root, function_name, from_import)
        return
    result = verify_imports(target_path, function_name, from_import)
    click.echo(f'[VERIFY] alvo: {result.root}')
    click.echo(f'[VERIFY] função: {result.function_name}')
    click.echo(f'[VERIFY] esperado: {result.expected_import}')
    stats = {'OK': 0, 'MISSING_IMPORT': 0, 'WRONG_IMPORT': 0, 'MULTIPLE_IMPORTS': 0}
    for issue in result.issues:
        stats[issue.kind] += 1
        if issue.kind == 'OK':
            click.secho(f'[OK]    {issue.file}:{issue.line}', fg='green')
        elif issue.kind == 'MISSING_IMPORT':
            click.secho(f'[MISS]  {issue.file}:{issue.line} — {issue.detail}', fg='yellow')
        elif issue.kind == 'WRONG_IMPORT':
            click.secho(f'[WRONG] {issue.file}:{issue.line} — {issue.detail}', fg='red')
        elif issue.kind == 'MULTIPLE_IMPORTS':
            click.secho(f'[MULTI] {issue.file}:{issue.line} — {issue.detail}', fg='magenta')
    click.echo('\n[RESUMO]')
    for k, v in stats.items():
        click.echo(f'  {k}: {v}')

@refactor_group.command('rename')
@click.argument('old_module', metavar='MODULO_ANTIGO')
@click.argument('new_module', metavar='MODULO_NOVO')
@click.option('--root', '-r', type=click.Path(path_type=Path, exists=True, file_okay=False), default=Path('.'), show_default=True, metavar='PASTA', help='Raiz do projeto onde os imports serão buscados e atualizados.')
@click.option('--apply', is_flag=True, help='Aplica as mudanças em disco. Sem esta flag: dry-run (só relatório).')
@click.option('--overwrite', is_flag=True, help='Sobrescreve MODULO_NOVO caso o arquivo de destino já exista.')
def refactor_rename(old_module: str, new_module: str, root: Path, apply: bool, overwrite: bool) -> None:
    """Renomeia um módulo e atualiza todos os imports que o referenciam.

    Sem --apply opera em modo dry-run: mostra o que seria alterado sem
    tocar em nenhum arquivo.

    \x08
    Exemplos:
      doxoade refactor rename myapp.old_utils myapp.utils --root .
      doxoade refactor rename myapp.old_utils myapp.utils --root . --apply
      doxoade refactor rename myapp.old_utils myapp.utils --root . --apply --overwrite
    """
    from .refactor_rename_ast import rename_module_ast
    try:
        result = rename_module_ast(root.resolve(), old_module, new_module, apply=apply, overwrite=overwrite)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f'[RENAME] {result.old_module} → {result.new_module}')
    click.echo(f'[RENAME] origem:             {result.source_file}')
    click.echo(f'[RENAME] destino:            {result.dest_file}')
    click.echo(f'[RENAME] arquivos afetados:  {len(result.changed_files)}')
    click.echo(f'[RENAME] imports reescritos: {len(result.rewrites)}')
    click.echo(f'[RENAME] aplicado:           {result.moved_file}')
    if not apply:
        click.secho('\n[DRY-RUN] Nenhuma alteração aplicada. Use --apply para gravar.', fg='yellow')

@refactor_group.command('fix-imports')
@click.argument('path', type=click.Path(exists=True, path_type=Path), default=Path('.'))
def refactor_fix_imports(path: Path) -> None:
    """Otimiza imports trocando a Facade shared_tools pelos módulos reais.
    
    Varre os arquivos buscando imports de 'doxoade.shared_tools' e resolve
    o caminho físico de cada função em 'doxoade.tools.*'.
    """
    _sep('FIX IMPORTS')
    click.secho(f' Alvo: {path.resolve()}', fg='cyan')
    engine = RefactorEngine()
    count = 0
    try:
        for fpath, msg in engine.fix_facade_imports(path):
            click.secho(f'  [FIX] {fpath}', fg='green')
            count += 1
    except Exception as e:
        raise click.ClickException(f'Erro na refatoração de imports: {e}')
    if count == 0:
        click.secho('\n[INFO] Nenhum import de Facade encontrado para otimização.', fg='yellow')
    else:
        _sep()
        click.secho(f' DONE  Total: {count} arquivo(s) processado(s).', fg='cyan', bold=True)
        
@refactor_group.command('headers')
@click.argument('path', type=click.Path(exists=True, path_type=Path), default=Path('.'))
@click.option('--force', is_flag=True, help='Força a regravação do cabeçalho em todos os arquivos.')
def refactor_headers(path: Path, force: bool) -> None:
    """Insere automaticamente o comentário de path no topo dos arquivos."""
    _sep("NEXUS HEADERS")
    click.secho(f" Alvo: {path.resolve()}", fg="cyan")
    if force:
        click.secho(f" Modo: FORÇADO (Substituição Agressiva)", fg="yellow")
    
    engine = RefactorEngine()
    count = 0
    
    try:
        # Note: o engine.root é usado para calcular o path relativo
        for fpath, msg in engine.ensure_nexus_headers(path, force=force):
            click.secho(f"  [HEADER] {fpath} ({msg})", fg="green")
            count += 1
    except Exception as e:
        raise click.ClickException(f"Erro na geração de cabeçalhos: {e}")
    
    if count == 0:
        click.secho("\n[INFO] Todos os arquivos já possuem cabeçalhos atualizados.", fg="yellow")
    else:
        _sep()
        click.secho(f" DONE  Total: {count} cabeçalho(s) aplicado(s).", fg="cyan", bold=True)

@refactor_group.command('repair')
@click.argument('target_file', type=click.Path(exists=True, path_type=Path))
@click.option('--root', '-r', default='.', help='Raiz do projeto.')
@click.option('--dry-run', is_flag=True, help='Simula o reparo sem alterar arquivos.')
@click.option('--verbose', '-v', is_flag=True, help='Exibe detalhes de cada alteração.')
def refactor_repair(target_file, root, dry_run, verbose):
    """Conserta imports e strings de CLI para apontarem para este arquivo."""
    if dry_run:
        _sep("DRY RUN: REPAIR", color="yellow")
    else:
        _sep("REFACTOR REPAIR")

    engine = RefactorEngine(base_path=root)
    success, msg = engine.repair_references(target_file, dry_run=dry_run, verbose=verbose)
    
    if success:
        click.secho(f"\n  [OK] {msg}", fg="green")
    else:
        click.secho(f"\n  [ERRO] {msg}", fg="red")

@refactor_group.command('audit')
@click.argument('file_path', type=click.Path(exists=True, path_type=Path))
def refactor_audit(file_path: Path):
    """Gera insights de dependências de um módulo (Quem ele usa)."""
    _sep(f"AUDIT: {file_path.name}")
    
    import ast
    try:
        content = file_path.read_text(encoding='utf-8')
        tree = ast.parse(content)
        
        click.secho("[DEP] Dependências (Imports):", fg="cyan", bold=True)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    click.echo(f"  - import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                click.echo(f"  - from {node.module or '.'} import {[a.name for a in node.names]}")
        
        click.secho("\n[API] O que este módulo oferece:", fg="green", bold=True)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                click.echo(f"  - {node.name} ({type(node).__name__})")
                
    except Exception as e:
        click.secho(f"Erro ao analisar: {e}", fg="red")

@refactor_group.command('syntax-fix')
@click.argument('path', type=click.Path(exists=True, path_type=Path), default=Path('.'))
@click.option('--dry-run', is_flag=True, help='Simula sem gravar arquivos.')
@click.option('--verbose', '-v', is_flag=True, help='Exibe cada mudança linha a linha.')
@click.option('--skip', 'extra_skip', multiple=True, metavar='PASTA',
              help='Pasta adicional a ignorar (repetível). Ex: --skip mypkg_tests')
@click.option('--include-tests', is_flag=True,
              help='Inclui pastas de teste (tests/, fixtures/, etc.) na varredura.')
def refactor_syntax_fix(
    path: Path,
    dry_run: bool,
    verbose: bool,
    extra_skip: tuple[str, ...],
    include_tests: bool,
) -> None:
    """Repara erros de sintaxe em f-strings causados pelo refactor AST.

    \\x08
    Por padrão ignora: tests/, regression_tests/, fixtures/, venv/, etc.
    Use --include-tests para incluí-las (útil para validar fixtures).

    \\x08
    Estratégias aplicadas (em ordem):
      1. Desfaz escapes chr(10) introduzidos pelo fix anterior
      2. f\\' → f\\"  (single para double)
      3. f\\" → f\\' (double para single)
      4. f\\' → f\\'\\'\\'... (eleva para triple quotes)

    \\x08
    Exemplos:
      doxoade refactor syntax-fix .
      doxoade refactor syntax-fix . --dry-run --verbose
      doxoade refactor syntax-fix . --skip mypkg_tests --skip proto
      doxoade refactor syntax-fix . --include-tests
    """
    from .refactor_syntax import (
        _default_skip, classify_issue, repair_all, repair_file, scan_syntax_errors,
    )

    _sep("SYNTAX FIX", color="cyan")
    target = Path(path).resolve()
    click.secho(f" Alvo:    {target}", fg='cyan')
    click.secho(f" Modo:    {'DRY-RUN' if dry_run else 'APPLY'}", fg='yellow' if dry_run else 'green')

    # Monta o conjunto de exclusão
    if include_tests:
        exclude = frozenset(extra_skip) if extra_skip else frozenset()
        click.secho(" Filtro:  incluindo pastas de teste", fg='yellow')
    else:
        base = _default_skip()
        exclude = base | frozenset(s.strip() for s in extra_skip)
        click.secho(
            f" Filtro:  {len(exclude)} pasta(s) ignorada(s)"
            f"{'  [use --include-tests para incluir tests/]' if not include_tests else ''}",
            fg='cyan',
        )

    # --- Modo arquivo único ---
    if target.is_file():
        result = repair_file(target, dry_run=dry_run)
        if result.strategy == 'already_valid':
            click.secho("\\n[OK] Arquivo sem erros de sintaxe.", fg='green')
            return
        if result.fixed:
            prefix = "[DRY]" if dry_run else "[FIXED]"
            click.secho(f"\\n{prefix} {target.name}  estratégia: {result.strategy}", fg='yellow' if dry_run else 'green')
            if (verbose or dry_run) and result.changes:
                for ln, old, new in result.changes:
                    click.secho(f"  L{ln}: - {old.strip()}", fg='red')
                    click.secho(f"  L{ln}: + {new.strip()}", fg='green')
        else:
            err = result.remaining_error or result.original_error
            click.secho("\\n[MANUAL] Não foi possível reparar automaticamente.", fg='red', bold=True)
            if err:
                click.secho(f"  L{err.line}: {err.message}", fg='red')
                if err.text:
                    click.echo(f"  > {err.text.strip()}")
        return

    # --- Modo diretório ---
    click.echo("\\nEscaneando erros de sintaxe...")
    broken = list(scan_syntax_errors(target, exclude_dirs=exclude))

    if not broken:
        click.secho("\\n[OK] Nenhum erro de sintaxe encontrado.", fg='green', bold=True)
        _sep()
        return

    by_category: dict[str, int] = {}
    for issue in broken:
        cat = classify_issue(issue)
        by_category[cat] = by_category.get(cat, 0) + 1

    click.secho(f"\\n[SCAN] {len(broken)} arquivo(s) com erro:", fg='yellow', bold=True)
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        click.echo(f"  {cat:20s}  {count}")

    click.echo("\\nAplicando reparos...")
    results = repair_all(target, dry_run=dry_run, exclude_dirs=exclude)

    fixed_count = sum(1 for r in results if r.fixed and r.strategy != 'already_valid')
    manual = [
        (r.file, r.remaining_error or r.original_error)
        for r in results if not r.fixed
    ]

    for result in results:
        if result.fixed and result.strategy != 'already_valid':
            prefix = "[DRY]" if dry_run else "[FIXED]"
            click.secho(f"  {prefix} {result.file.name}  ({result.strategy})", fg='yellow' if dry_run else 'green')
            if verbose and result.changes:
                for ln, old, new in result.changes:
                    click.secho(f"      L{ln}: - {old.strip()}", fg='red')
                    click.secho(f"      L{ln}: + {new.strip()}", fg='green')

    _sep()
    click.secho(
        f" DONE  {fixed_count} reparado(s) / {len(manual)} revisão manual",
        fg='cyan', bold=True,
    )

    if manual:
        click.secho("\\n[MANUAL] Arquivos que precisam de revisão:", fg='red', bold=True)
        for fpath, err in manual:
            msg = err.message if err else 'erro desconhecido'
            line = err.line if err else 0
            click.secho(f"  {fpath.name}:{line}  {msg}", fg='red')
            if err and err.text:
                click.echo(f"    > {err.text.strip()}")
    _sep()


@refactor_group.command('verify-cli')
@click.argument('path', type=click.Path(exists=True, path_type=Path), default=Path('.'))
def refactor_verify_cli(path: Path):
    """Análise de Integridade Pós-Refactor (Smoke Test)."""
    _sep("NEXUS INTEGRITY CHECK")
    import importlib.util
    import sys
    
    # IMPORTANTE: Resolvemos a raiz real do projeto para o filtro funcionar
    project_root = Path(_find_project_root(path)).resolve()
    
    # Filtramos os arquivos ANTES de começar a barra de progresso
    click.echo(f"🔍 Mapeando arquivos em: {project_root.name}...")
    files = [f for f in iter_python_files(project_root)]
    
    broken = 0
    passed = 0
    
    if not files:
        click.secho("[!] Nenhum arquivo Python encontrado para análise.", fg="yellow")
        return

    click.echo(f"\n{click.style('🚀 Verificando importabilidade...', fg='magenta')}\n")

    with click.progressbar(files, label="Nexus Progress") as bar:
        for fpath in bar:
            # Ignora arquivos de teste do refactor para não entrar em loop
            if "refactor_systems" in str(fpath):
                continue
                
            module_name = fpath.stem
            try:
                # O spec_from_file_location é o teste definitivo de sintaxe
                spec = importlib.util.spec_from_file_location(module_name, fpath)
                if spec is None or spec.loader is None:
                    continue 

                module = importlib.util.module_from_spec(spec)
                # O segredo aqui: não precisamos dar exec_module em tudo, 
                # basta o compile do loader para detectar SyntaxError sem rodar o código
                with open(fpath, 'rb') as f:
                    source = f.read()
                compile(source, fpath, 'exec')
                
                passed += 1
            except SyntaxError as e:
                click.secho(f"\n[ERRO SINTAXE] {fpath.relative_to(project_root)}", fg="red", bold=True)
                click.echo(f"  L{e.lineno}: {e.text.strip() if e.text else 'Erro de citação/f-string'}")
                broken += 1
            except Exception:
                continue

@refactor_group.command('syntax-scan')
@click.argument('path', type=click.Path(exists=True, path_type=Path), default=Path('.'))
@click.option('--category', '-c', 'filter_cat', default=None,
              help='Filtra por categoria: fstring, unclosed_block, indentation, other.')
@click.option('--skip', 'extra_skip', multiple=True, metavar='PASTA',
              help='Pasta adicional a ignorar (repetível).')
@click.option('--include-tests', is_flag=True,
              help='Inclui pastas de teste na varredura.')
@click.option('--json', 'as_json', is_flag=True,
              help='Saída em JSON para integração com outras ferramentas.')
def refactor_syntax_scan(
    path: Path,
    filter_cat: str | None,
    extra_skip: tuple[str, ...],
    include_tests: bool,
    as_json: bool,
) -> None:
    """Escaneia o projeto e lista TODOS os erros de sintaxe. Não altera nada.

    \\x08
    Por padrão ignora: tests/, regression_tests/, fixtures/, venv/, __pycache__/, etc.
    Use --include-tests para incluir as pastas de teste na varredura.

    \\x08
    Categorias detectadas:
      fstring        — f-strings com aspas conflitantes
      unclosed_block — blocos não fechados (parênteses, colchetes)
      indentation    — erros de indentação
      other          — demais erros de sintaxe

    \\x08
    Exemplos:
      doxoade refactor syntax-scan .
      doxoade refactor syntax-scan . --include-tests
      doxoade refactor syntax-scan . -c fstring
      doxoade refactor syntax-scan . --json > broken.json
    """
    import json as _json
    from .refactor_syntax import _default_skip, classify_issue, scan_syntax_errors

    target = Path(path).resolve()

    if include_tests:
        exclude = frozenset(extra_skip) if extra_skip else frozenset()
    else:
        base = _default_skip()
        exclude = base | frozenset(s.strip() for s in extra_skip)

    issues = list(scan_syntax_errors(target, exclude_dirs=exclude))

    if filter_cat:
        issues = [i for i in issues if classify_issue(i) == filter_cat]

    if as_json:
        data = [
            {
                'file': str(i.file),
                'line': i.line,
                'col': i.col,
                'category': classify_issue(i),
                'message': i.message,
                'text': i.text,
            }
            for i in issues
        ]
        click.echo(_json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not issues:
        note = '' if include_tests else '  (tests/ excluído — use --include-tests para incluir)'
        click.secho(f"[OK] Nenhum erro de sintaxe encontrado.{note}", fg='green', bold=True)
        return

    _sep(f"SYNTAX SCAN — {len(issues)} erro(s)")
    if not include_tests:
        click.secho("  [filtro ativo: tests/ e fixtures/ excluídos]", fg='cyan', dim=True)

    by_cat: dict[str, list] = {}
    for issue in issues:
        cat = classify_issue(issue)
        by_cat.setdefault(cat, []).append(issue)

    for cat, cat_issues in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        click.secho(f"\\n[{cat.upper()}] {len(cat_issues)} arquivo(s):", fg='yellow', bold=True)
        for issue in cat_issues:
            try:
                rel = issue.file.relative_to(target)
            except ValueError:
                rel = issue.file
            click.secho(f"  {rel}:{issue.line}", fg='red', nl=False)
            click.echo(f"  {issue.message}")
            if issue.text:
                click.echo(f"    > {issue.text.strip()}")

    _sep()
    click.secho(
        f" Total: {len(issues)} erro(s) em {len({i.file for i in issues})} arquivo(s).",
        fg='cyan', bold=True,
    )
    _sep()

def _parse_skip(skip_tuple: tuple[str, ...]) -> frozenset[str]:
    """Converte a tupla de --skip em frozenset para passar ao módulo."""
    from .refactor_syntax import _default_skip
    if not skip_tuple:
        return _default_skip()
    # O usuário pode usar --skip tests --skip regression_tests OU --no-default-skip
    base = _default_skip()
    extra = frozenset(s.strip() for s in skip_tuple if s.strip())
    return base | extra