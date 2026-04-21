# doxoade/doxoade/commands/refactor_systems/refactor_syntax.py
"""
Reparo de sintaxe Python 3.12 para o doxoade refactor.

Contexto: ast.unparse() e fix_fstring_syntax() quebraram ~260 arquivos ao
reescrever f-strings sem respeitar os limites reais dos tokens.

Abordagem:
  - Usa compile() como oráculo.
  - Repara iterativamente: localiza o erro, aplica estratégias em ordem
    crescente de agressividade, valida com compile() a cada tentativa.
  - Nunca usa ast.unparse().
  - Preserva toda formatação original fora das linhas afetadas.
  - Suporta exclude_dirs para não entrar em tests/, regression_tests/, etc.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from .refactor_utils import read_text_safe

# ---------------------------------------------------------------------------
# Pastas ignoradas por padrão
# ---------------------------------------------------------------------------

#: Pastas de código de produção que NUNCA devem ser varridas pelo scanner.
#: Inclui tudo que está em SYSTEM_IGNORES do filesystem.py + pastas de teste.
_BASE_SKIP: frozenset[str] = frozenset({
    # filesystem.py/SYSTEM_IGNORES
    'venv', '.git', '__pycache__', 'build', 'dist', '.doxoade',
    '.doxoade_cache', 'node_modules', '.vscode', '.idea',
    'pytest_temp_dir', '.dox_agent_workspace',
    # pastas de teste — fixtures podem ter erros propositais
    'tests', 'test', 'regression_tests', 'regression',
    'fixtures', 'fixture', 'conftest',
    # outros lixos comuns
    'migrations', '.mypy_cache', '.ruff_cache', '.tox',
    '.pytest_cache', 'htmlcov', '.eggs',
})


def _default_skip() -> frozenset[str]:
    """Retorna o conjunto padrão de pastas a ignorar."""
    return _BASE_SKIP


# ---------------------------------------------------------------------------
# Iterador de arquivos com controle de exclusão embutido
# Não usa iter_python_files() para poder aplicar exclude_dirs de forma
# agressiva antes de entrar nas subpastas (topdown=True + dirs[:] = ...).
# ---------------------------------------------------------------------------

def _iter_py_files(root: Path, exclude_dirs: frozenset[str]) -> Iterator[Path]:
    """
    Caminha pelo filesystem ignorando pastas em exclude_dirs.
    Comparação case-insensitive para compatibilidade com Windows.
    """
    lower_skip = {d.lower() for d in exclude_dirs}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        # Poda in-place: o os.walk não entrará nas pastas removidas
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in lower_skip and not d.startswith('.')
        ]
        for fname in filenames:
            if fname.endswith('.py'):
                yield Path(dirpath) / fname


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SyntaxIssue:
    file: Path
    line: int          # 1-based, conforme SyntaxError.lineno
    col: int           # 1-based, conforme SyntaxError.offset
    message: str
    text: str | None = None


@dataclass
class RepairResult:
    file: Path
    original_error: SyntaxIssue | None = None
    fixed: bool = False
    strategy: str = ''
    remaining_error: SyntaxIssue | None = None
    changes: list[tuple[int, str, str]] = field(default_factory=list)
    # (linha_1based, texto_antes, texto_depois)


# ---------------------------------------------------------------------------
# Oráculo de compilação
# ---------------------------------------------------------------------------

_PY312 = sys.version_info >= (3, 12)


def _try_compile(source: str, filename: str = '<string>') -> SyntaxError | None:
    """None = OK. SyntaxError = quebrado."""
    try:
        compile(source.encode('utf-8', errors='replace'), filename, 'exec')
        return None
    except SyntaxError as e:
        return e
    except Exception as e:
        return SyntaxError(str(e))


def _issue_from_error(fpath: Path, err: SyntaxError) -> SyntaxIssue:
    return SyntaxIssue(
        file=fpath,
        line=err.lineno or 0,
        col=err.offset or 0,
        message=err.msg or str(err),
        text=(err.text or '').rstrip('\n') or None,
    )


# ---------------------------------------------------------------------------
# Estratégias de reparo por linha
# ---------------------------------------------------------------------------

def _is_fstring_line(line: str) -> bool:
    return bool(re.search(r'\bf[\'"]', line, re.IGNORECASE))


def _strategy_flip_single_to_double(line: str) -> list[str]:
    """f'...' -> f\"...\" com escape correto do conteúdo."""
    pat = re.compile(r"(f')((?:[^'\\]|\\.)*?)(')", re.DOTALL)

    def replacer(m: re.Match) -> str:
        inner = m.group(2)
        inner = re.sub(r'(?<!\\)"', '\\"', inner)
        inner = inner.replace("\\'", "'")
        return f'f"{inner}"'

    candidate = pat.sub(replacer, line)
    return [candidate] if candidate != line else []


def _strategy_flip_double_to_single(line: str) -> list[str]:
    """f\"...\" -> f'...'"""
    pat = re.compile(r'(f")((?:[^"\\]|\\.)*?)(")', re.DOTALL)

    def replacer(m: re.Match) -> str:
        inner = m.group(2)
        inner = re.sub(r"(?<!\\)'", "\\'", inner)
        inner = inner.replace('\\"', '"')
        return f"f'{inner}'"

    candidate = pat.sub(replacer, line)
    return [candidate] if candidate != line else []


def _strategy_upgrade_to_triple(line: str) -> list[str]:
    """f'...' -> f'''...''' — permite aspas mistas sem escape."""
    results = []
    c1 = re.compile(r"f'((?:[^'\\]|\\.)*?)'").sub(
        lambda m: f"f'''{m.group(1)}'''", line
    )
    if c1 != line:
        results.append(c1)
    c2 = re.compile(r'f"((?:[^"\\]|\\.)*?)"').sub(
        lambda m: f'f"""{m.group(1)}"""', line
    )
    if c2 != line:
        results.append(c2)
    return results


def _strategy_unescape_backslash_in_expr(line: str) -> list[str]:
    """
    Desfaz chr(10).join que o fix_fstring_syntax antigo introduziu.
    Só em Python 3.12+ onde backslash dentro de {expr} é permitido.
    """
    if not _PY312:
        return []
    c = line.replace('chr(10).join', "'\\n'.join")
    return [c] if c != line else []


def _strategy_normalize_ast_unparse_artifacts(line: str) -> list[str]:
    """Desfaz padrões conhecidos produzidos por ast.unparse() em versões antigas."""
    c = re.sub(
        r"f'(.*?)\\n(.*?)'",
        lambda m: f'f"{m.group(1)}\\n{m.group(2)}"',
        line,
    )
    return [c] if c != line else []

def _strategy_upgrade_to_triple_quotes(line: str) -> list[str]:
    """
    Converte f-strings problemáticas para aspas triplas (f'''...''' ou f\"\"\"...\"\"\").
    Isso resolve conflitos de aspas internas no Python 3.12.
    """
    # Se a linha parece uma f-string com conflito de aspas
    if 'f"' in line or "f'" in line:
        # Tenta converter aspas duplas para triplas duplas
        c1 = re.sub(r'f"(.+?)"', r'f"""\1"""', line)
        # Tenta converter aspas simples para triplas simples
        c2 = re.sub(r"f'(.+?)'", r"f'''\1'''", line)
        
        res = []
        if c1 != line: res.append(c1)
        if c2 != line: res.append(c2)
        return res
    return []

def _strategy_fix_nested_quotes(line: str) -> list[str]:
    """
    Detecta f'...{... ' ...}...' e converte para f'''...'''
    Estratégia 'Nuclear' para f-strings complexas.
    """
    # Se a linha tem uma f-string com aspas simples e contém aspas simples dentro das chaves
    if re.search(r"f'.*\{.*'.*\}", line):
        # Tenta converter a f-string inteira para tripla
        # Busca f' ou f" e troca por f''' ou f"""
        c1 = line.replace("f'", "f'''").replace("f\"", "f\"\"\"")
        # Se mudamos para tripla, precisamos fechar com tripla
        # Nota: Esta regex é simplificada, mas resolve 90% dos casos do AST
        if "'''" in c1 and not c1.strip().endswith("'''"):
             c1 = re.sub(r"'$", "'''", c1.rstrip())
        return [c1]
    return []

# Pipeline em ordem crescente de agressividade
_STRATEGIES: list[Callable[[str], list[str]]] = [
    _strategy_unescape_backslash_in_expr,
    _strategy_upgrade_to_triple_quotes,  # <--- Adicione aqui
    _strategy_normalize_ast_unparse_artifacts,
    _strategy_flip_single_to_double,
    _strategy_flip_double_to_single,
]

# ---------------------------------------------------------------------------
# Motor de reparo iterativo
# ---------------------------------------------------------------------------

_MAX_ITERATIONS = 30


def _repair_source(
    source: str, fpath: Path
) -> tuple[str, list[tuple[int, str, str]], str]:
    """
    Repara o source iterativamente.
    Retorna (novo_source, lista_de_mudanças, nome_da_estratégia).
    """
    lines = source.splitlines()
    changes: list[tuple[int, str, str]] = []
    last_strategy = ''

    for _ in range(_MAX_ITERATIONS):
        current_source = '\n'.join(lines)
        err = _try_compile(current_source, str(fpath))
        if err is None:
            return current_source + '\n', changes, last_strategy or 'ok'

        err_lineno = err.lineno or 1
        err_idx = err_lineno - 1

        if err_idx < 0 or err_idx >= len(lines):
            break

        original_line = lines[err_idx]

        if not _is_fstring_line(original_line):
            # Erro pode ser reportado na linha seguinte à f-string problemática
            if err_idx > 0 and _is_fstring_line(lines[err_idx - 1]):
                err_idx -= 1
                original_line = lines[err_idx]
            else:
                break

        repaired = False
        for strategy_fn in _STRATEGIES:
            for candidate in strategy_fn(original_line):
                if candidate == original_line:
                    continue
                test_lines = lines.copy()
                test_lines[err_idx] = candidate
                new_err = _try_compile('\n'.join(test_lines), str(fpath))
                # Aceita se eliminou o erro OU se moveu para outra linha
                if new_err is None or (new_err.lineno or 0) != err_lineno:
                    changes.append((err_idx + 1, original_line, candidate))
                    lines[err_idx] = candidate
                    last_strategy = strategy_fn.__name__.replace('_strategy_', '')
                    repaired = True
                    break
            if repaired:
                break

        if not repaired:
            break

    return '\n'.join(lines) + '\n', changes, last_strategy


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def scan_syntax_errors(
    root: Path,
    exclude_dirs: frozenset[str] | None = None,
) -> Iterator[SyntaxIssue]:
    """
    Itera sobre todos os arquivos Python e produz um SyntaxIssue para cada erro.

    Args:
        root: pasta raiz do projeto.
        exclude_dirs: pastas a ignorar (case-insensitive).
                      None  -> usa _default_skip() (recomendado).
                      frozenset() -> não exclui nada (varre tudo, inclusive tests/).
    """
    skip = _default_skip() if exclude_dirs is None else exclude_dirs
    for fpath in _iter_py_files(root, skip):
        source = read_text_safe(fpath)
        err = _try_compile(source, str(fpath))
        if err is not None:
            yield _issue_from_error(fpath, err)


def repair_file(fpath: Path, dry_run: bool = False) -> RepairResult:
    """Tenta reparar um único arquivo Python."""
    source = read_text_safe(fpath)
    result = RepairResult(file=fpath)

    err = _try_compile(source, str(fpath))
    if err is None:
        result.fixed = True
        result.strategy = 'already_valid'
        return result

    result.original_error = _issue_from_error(fpath, err)
    new_source, changes, strategy = _repair_source(source, fpath)
    final_err = _try_compile(new_source, str(fpath))

    result.changes = changes
    result.strategy = strategy

    if final_err is None and changes:
        result.fixed = True
        if not dry_run:
            fpath.write_text(new_source, encoding='utf-8')
    elif final_err is not None:
        result.fixed = False
        result.remaining_error = _issue_from_error(fpath, final_err)

    return result


def repair_all(
    root: Path,
    dry_run: bool = False,
    exclude_dirs: frozenset[str] | None = None,
    progress_cb: Callable[[Path], None] | None = None,
) -> list[RepairResult]:
    """
    Varre o projeto e tenta reparar todos os arquivos com erro de sintaxe.
    Retorna apenas os arquivos que tinham problemas.

    Args:
        root: pasta raiz.
        dry_run: não grava arquivos se True.
        exclude_dirs: None = usa _default_skip(). frozenset() = varre tudo.
        progress_cb: callback chamado antes de processar cada arquivo quebrado.
    """
    skip = _default_skip() if exclude_dirs is None else exclude_dirs
    results: list[RepairResult] = []

    for fpath in _iter_py_files(root, skip):
        source = read_text_safe(fpath)
        if _try_compile(source, str(fpath)) is None:
            continue
        if progress_cb:
            progress_cb(fpath)
        result = repair_file(fpath, dry_run=dry_run)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

_FSTRING_MSGS = re.compile(
    r'f-string|f string|unterminated f-string|'
    r'unterminated string literal|invalid syntax',
    re.IGNORECASE,
)


def classify_issue(issue: SyntaxIssue) -> str:
    """Retorna: fstring | unclosed_block | indentation | other."""
    msg = issue.message or ''
    text = issue.text or ''

    if _FSTRING_MSGS.search(msg):
        return 'fstring'
    if text and re.search(r"\bf['\"]", text):
        return 'fstring'
    if 'eof' in msg.lower() or 'never closed' in msg.lower():
        return 'unclosed_block'
    if 'indent' in msg.lower():
        return 'indentation'
    return 'other'