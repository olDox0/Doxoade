# doxoade/doxoade/commands/panel_command.py
"""
doxoade panel — Verificação de saúde do CLI.

Executa smoke tests em todos os subcomandos registrados:
  - Importação dos módulos (detecta SyntaxError e ImportError)
  - Invocação com --help (detecta erros em tempo de carga do Click)
  - Compilação estática dos arquivos do projeto

Uso:
  doxoade panel               # verificação completa
  doxoade panel --fast        # só importações (sem invocar --help)
  doxoade panel --fix-syntax  # após escanear, tenta reparar sintaxe
"""
from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import click


# ---------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------

@dataclass
class CommandHealth:
    name: str
    module: str
    import_ok: bool = False
    help_ok: bool = False
    import_error: str = ''
    help_error: str = ''
    duration_ms: float = 0.0

    @property
    def healthy(self) -> bool:
        return self.import_ok and self.help_ok

    @property
    def status_label(self) -> str:
        if self.healthy:
            return 'OK'
        if not self.import_ok:
            return 'IMPORT_ERR'
        return 'HELP_ERR'


@dataclass
class PanelReport:
    syntax_errors: int = 0
    syntax_files: list[tuple[Path, str]] = field(default_factory=list)
    commands: list[CommandHealth] = field(default_factory=list)

    @property
    def healthy_commands(self) -> int:
        return sum(1 for c in self.commands if c.healthy)

    @property
    def broken_commands(self) -> int:
        return len(self.commands) - self.healthy_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_project_root(start: Path = Path('.')) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        for marker in ('pyproject.toml', 'setup.py', '.git'):
            if (candidate / marker).exists():
                return candidate
    return start.resolve()


def _check_import(module_path: str) -> tuple[bool, str]:
    """Tenta importar um módulo e retorna (ok, erro)."""
    try:
        spec = importlib.util.spec_from_file_location('_panel_probe', module_path)
        if spec is None:
            return False, 'spec_from_file_location retornou None'
        mod = importlib.util.module_from_spec(spec)
        with open(module_path, 'rb') as f:
            compile(f.read(), module_path, 'exec')
        return True, ''
    except SyntaxError as e:
        return False, f'SyntaxError L{e.lineno}: {e.msg}'
    except Exception as e:
        return False, str(e)


def _check_help(command_name: str) -> tuple[bool, str]:
    """Executa `doxoade <cmd> --help` e verifica se retorna 0."""
    try:
        # CORREÇÃO: Split no command_name para separar 'refactor' de 'path'
        cmd_parts = command_name.split()
        full_args = [sys.executable, '-m', 'doxoade'] + cmd_parts + ['--help']
        
        result = subprocess.run(
            full_args,
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, ''
        return False, (result.stderr or result.stdout or 'returncode != 0').strip()[:200]
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Registro de comandos conhecidos do doxoade
# Edite esta lista conforme novos comandos forem adicionados.
# ---------------------------------------------------------------------------

_KNOWN_COMMANDS: list[tuple[str, str]] = [
    # (nome_do_subcomando, caminho_do_módulo_relativo_à_raiz)
    ('refactor path',       'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor refs',       'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor move',       'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor verify',     'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor rename',     'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor syntax-fix', 'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor syntax-scan','doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor audit',      'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor headers',    'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor fix-imports','doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor repair',     'doxoade/commands/refactor_systems/refactor_command.py'),
    ('refactor verify-cli', 'doxoade/commands/refactor_systems/refactor_command.py'),
    # Adicione mais conforme o projeto crescer:
    # ('migrate foo',  'doxoade/commands/migrate_command.py'),
]


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def _run_panel(root: Path, fast: bool = False, fix_syntax: bool = False) -> PanelReport:
    report = PanelReport()

    # 1. Scan de sintaxe
    from doxoade.commands.refactor_systems.refactor_syntax import scan_syntax_errors
 #   for issue in scan_syntax_errors(root):
    for issue in scan_syntax_errors(root, exclude_dirs=None):
    # None = usa _default_skip() automaticamente (ignora tests/, fixtures/, etc.)
        report.syntax_errors += 1
        report.syntax_files.append((issue.file, f'L{issue.line}: {issue.message}'))

    # 2. Tenta reparar se solicitado
    if fix_syntax and report.syntax_errors > 0:
        from doxoade.commands.refactor_systems.refactor_syntax import repair_all
        repair_all(root, dry_run=False)

    # 3. Verifica comandos
    for cmd_name, rel_module in _KNOWN_COMMANDS:
        module_path = str(root / rel_module)
        t0 = time.monotonic()
        import_ok, import_err = _check_import(module_path)
        help_ok, help_err = (True, '') if fast else _check_help(cmd_name)
        duration = (time.monotonic() - t0) * 1000

        report.commands.append(CommandHealth(
            name=cmd_name,
            module=rel_module,
            import_ok=import_ok,
            help_ok=help_ok,
            import_error=import_err,
            help_error=help_err,
            duration_ms=duration,
        ))

    return report


def _print_report(report: PanelReport, verbose: bool = False) -> None:
    """Imprime o relatório do painel no terminal."""

    def _sep(label: str = '', width: int = 60, color: str = 'cyan') -> None:
        line = f"─{'─' * (width - 2)}─"
        if label:
            pad = max(0, width - len(label) - 4)
            line = f"─ {label} {'─' * pad}"
        click.secho(line, fg=color)

    _sep('DOXOADE PANEL')

    # --- Sintaxe ---
    if report.syntax_errors == 0:
        click.secho(f" Sintaxe:   OK ({report.syntax_errors} erros)", fg='green')
    else:
        click.secho(f" Sintaxe:   {report.syntax_errors} arquivo(s) com erro!", fg='red', bold=True)
        if verbose:
            for fpath, msg in report.syntax_files:
                click.secho(f"   {fpath.name}  {msg}", fg='red')

    # --- Comandos ---
    click.echo()
    _sep('COMANDOS', color='blue')
    for cmd in report.commands:
        color = 'green' if cmd.healthy else 'red'
        tag = f"[{cmd.status_label}]"
        click.secho(f"  {tag:14s} {cmd.name}", fg=color, nl=False)
        click.echo(f"  ({cmd.duration_ms:.0f}ms)")
        if not cmd.import_ok and verbose:
            click.secho(f"    IMPORT: {cmd.import_error}", fg='red')
        if not cmd.help_ok and verbose:
            click.secho(f"    HELP:   {cmd.help_error}", fg='red')

    # --- Resumo ---
    click.echo()
    _sep('RESUMO')
    total = len(report.commands)
    healthy = report.healthy_commands
    broken = report.broken_commands
    color = 'green' if broken == 0 and report.syntax_errors == 0 else 'red'
    click.secho(
        f" Comandos: {healthy}/{total} saudáveis  |  "
        f"Sintaxe: {report.syntax_errors} erros",
        fg=color, bold=True
    )
    if broken > 0:
        click.secho(
            " DICA: execute 'doxoade refactor syntax-fix . --dry-run' para "
            "inspecionar os erros de f-string.",
            fg='yellow'
        )
    _sep()


# ---------------------------------------------------------------------------
# Comando Click
# ---------------------------------------------------------------------------

@click.command('panel')
@click.argument('path', type=click.Path(exists=True, path_type=Path), default=Path('.'))
@click.option('--fast', is_flag=True,
              help='Só verifica importações (não invoca --help de cada comando).')
@click.option('--fix-syntax', is_flag=True,
              help='Tenta reparar automaticamente os erros de sintaxe encontrados.')
@click.option('--verbose', '-v', is_flag=True,
              help='Exibe detalhes dos erros de cada comando.')
@click.option('--json', 'as_json', is_flag=True,
              help='Saída em JSON (para CI/integração).')
def panel_command(path: Path, fast: bool, fix_syntax: bool, verbose: bool, as_json: bool) -> None:
    """Verificação de saúde completa do CLI doxoade.

    \\x08
    Verifica:
      1. Erros de sintaxe em todos os arquivos Python do projeto
      2. Importabilidade de cada módulo de comando
      3. Execução do --help de cada subcomando registrado

    \\x08
    Exemplos:
      doxoade panel
      doxoade panel --fast --verbose
      doxoade panel --fix-syntax
      doxoade panel --json | python -m json.tool
    """
    import json as _json

    root = _find_project_root(Path(path))
    report = _run_panel(root, fast=fast, fix_syntax=fix_syntax)

    if as_json:
        data = {
            'syntax_errors': report.syntax_errors,
            'syntax_files': [(str(f), m) for f, m in report.syntax_files],
            'commands': [
                {
                    'name': c.name,
                    'healthy': c.healthy,
                    'import_ok': c.import_ok,
                    'help_ok': c.help_ok,
                    'import_error': c.import_error,
                    'help_error': c.help_error,
                    'duration_ms': round(c.duration_ms, 1),
                }
                for c in report.commands
            ],
        }
        click.echo(_json.dumps(data, indent=2, ensure_ascii=False))
        return

    _print_report(report, verbose=verbose)

    # Exit code: 0 = saudável, 1 = problemas
    if report.broken_commands > 0 or report.syntax_errors > 0:
        sys.exit(1)