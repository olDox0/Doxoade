# doxoade/tools/vulcan/refactor_exec.py
""" Refatorador Cirúrgico AST-String (PASC 8.12). """
import re
import ast
import io
import shutil
import difflib
import tokenize
from pathlib import Path
from collections import defaultdict

# ── Exclusion: raw cursor passthrough (Aegis wrapper internals) ───────────────
_PASSTHROUGH_RE = re.compile(r'(?:(?:[a-zA-Z_]\w*\.)*)_cursor$')

# ── Fetch-chained pattern: obj.execute(...).fetchone/fetchall() ───────────────
# These are READ calls — must use alexandria_read, not alexandria_write.
_FETCH_CHAIN_RE = re.compile(
    r'(?:[a-zA-Z_]\w*\.)+execute\s*\(.*?\)\s*\.fetch(?:one|all|many)\s*\(',
    re.DOTALL
)

# ── Combined replacement pattern ──────────────────────────────────────────────
_COMBINED = re.compile(
    r'(?P<exec>(?:[a-zA-Z_]\w*\.)+execute\s*\()'
    r'|(?P<commit>\b[\w.]+?\.commit\s*\(\))'
)

IMPORT_WRITE = "from doxoade.tools.alexandria.engine import alexandria_write\n"
IMPORT_READ  = "from doxoade.tools.alexandria.engine import alexandria_read\n"
IMPORT_BOTH  = (
    "from doxoade.tools.alexandria.engine import alexandria_write, alexandria_read\n"
)

BLACKLIST = {
    'core_database.py', 'nexus_db.py', 'db_utils.py', 
    'engine.py', 'manager.py', 'db_refactorer.py', 'refactor_exec.py'
}

def _get_unsafe_offsets(src: str) -> set:
    """Offsets inside string literals or comments — never touch these."""
    lines = src.splitlines(keepends=True)

    def offset(row, col):
        return sum(len(lines[r]) for r in range(row - 1)) + col

    unsafe = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.STRING, tokenize.COMMENT):
                unsafe.update(range(offset(*tok.start), offset(*tok.end)))
    except tokenize.TokenError:
        pass
    return unsafe


def _get_sole_body_offsets(src: str) -> set:
    """
    Offsets that are the *only* statement in a function body.
    Commenting them out would leave an empty function → SyntaxError.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()

    lines = src.splitlines(keepends=True)

    def line_offset(n):
        return sum(len(lines[i]) for i in range(n - 1))

    sole = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if len(node.body) == 1:
            stmt = node.body[0]
            for ln in range(stmt.lineno, stmt.end_lineno + 1):
                start = line_offset(ln)
                sole.update(range(start, start + len(lines[ln - 1])))
    return sole


def _build_fetch_ranges(src: str) -> list[tuple[int, int]]:
    """
    Return (start, end) ranges of the *entire* expression
        obj.execute(sql, params).fetchone/fetchall/fetchmany(...)
    These are read operations and must be replaced with alexandria_read.
    We locate them by finding .fetchone/.fetchall/.fetchmany immediately
    after a closing paren of execute().
    """
    # Match the obj.execute( opener, then walk to the matching ), then check
    # for .fetch suffix. We do this token-by-token to handle nested parens.
    ranges = []
    exec_opener = re.compile(r'(?:[a-zA-Z_]\w*\.)+execute\s*\(')
    fetch_suffix = re.compile(r'\s*\.\s*fetch(?:one|all|many)\s*\(')

    pos = 0
    while pos < len(src):
        m = exec_opener.search(src, pos)
        if not m:
            break
        # Walk forward past the matching close-paren of execute(
        depth = 1
        i = m.end()
        while i < len(src) and depth:
            if src[i] == '(':
                depth += 1
            elif src[i] == ')':
                depth -= 1
            i += 1
        # i is now just past the closing ) of execute(...)
        fm = fetch_suffix.match(src, i)
        if fm:
            # Also walk past the fetch call's parens
            j = fm.end()
            depth2 = 1
            while j < len(src) and depth2:
                if src[j] == '(':
                    depth2 += 1
                elif src[j] == ')':
                    depth2 -= 1
                j += 1
            ranges.append((m.start(), j))
            pos = j
        else:
            pos = m.end()
    return ranges


def _in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in ranges)

def _inject_import(src: str) -> str:
    """Injeta o import do alexandria_write de forma segura após o cabeçalho."""
    # Verificação precisa: Se o import exato já existe, não faz nada
    if IMPORT_WRITE.strip() in src:
        return src

    lines = src.splitlines(keepends=True)
    insert_idx = 0
    in_docstring = False

    for i, line in enumerate(lines):
        s = line.strip()
        if not in_docstring and (s.startswith('"""') or s.startswith("'''")):
            if s.count('"""') == 2 or s.count("'''") == 2:
                continue
            in_docstring = True
            continue
        if in_docstring:
            if s.count('"""') >= 1 or s.count("'''") >= 1:
                in_docstring = False
            continue
        
        if s.startswith('#') or s.startswith('import ') or s.startswith('from ') or not s:
            insert_idx = i + 1
            continue

        break

    lines.insert(insert_idx, IMPORT_WRITE)
    return "".join(lines)

def apply_alexandria_patch(file_path: Path, dry_run: bool = True) -> tuple[bool, str, str]:
    """Orquestrador de Refatoração Segura e Auto-Heal. Retorna: (success, msg, diff)."""
    if file_path.name in BLACKLIST:
        return False, "Arquivo Core protegido (ignorado).", ""

    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except Exception as e:
        return False, f"Falha de AST: {e}", ""

    visitor = ExecuteWriteVisitor()
    visitor.visit(tree)

    # NOVIDADE: Auto-Heal Check
    # Verifica se o arquivo usa alexandria_write, mas esqueceu do import
    needs_import_fix = ('alexandria_write' in source) and (IMPORT_WRITE.strip() not in source)

    if not visitor.replacements and not needs_import_fix:
        return False, "Nenhuma chamada de escrita e imports estão consistentes.", ""

    lines = source.splitlines(keepends=True)
    changes_count = 0
    
    # Faz a substituição dos .execute() se houver
    if visitor.replacements:
        reps_by_line = defaultdict(list)
        for rep in visitor.replacements:
            reps_by_line[rep['lineno']].append(rep)

        for lineno, reps in reps_by_line.items():
            line_idx = lineno - 1
            line_str = lines[line_idx]
            
            reps.sort(key=lambda x: x['col_start'], reverse=True)
            for r in reps:
                start = r['col_start']
                end = r['col_end']
                line_str = line_str[:start] + 'alexandria_write' + line_str[end:]
                changes_count += 1
                
            lines[line_idx] = line_str

    new_source = "".join(lines)
    
    # Injeta o import, seja pelas chamadas recém-alteradas ou pelo Auto-Heal
    new_source = _inject_import(new_source)

    try:
        ast.parse(new_source)
    except SyntaxError as e:
        return False, f"Cirurgia gerou SyntaxError na linha {e.lineno}. Abortando.", ""

    orig_lines = source.splitlines(keepends=True)
    new_lines_list = new_source.splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(orig_lines, new_lines_list, fromfile=file_path.name, tofile=file_path.name))

    # Formata a mensagem de status dinamicamente
    msg_parts = []
    if changes_count > 0:
        msg_parts.append(f"{changes_count} remapeamento(s)")
    if needs_import_fix:
        msg_parts.append("Auto-Heal de Import ativado")
    
    status_msg = " + ".join(msg_parts)

    if dry_run:
        return True, f"Simulado: {status_msg}.", diff

    # Gravação Definitiva
    backup_path = file_path.with_suffix('.py.bak')
    shutil.copy2(file_path, backup_path)
    file_path.write_text(new_source, encoding='utf-8')
    
    return True, f"Aplicado: {status_msg} em {file_path.name}", diff
    
class ExecuteWriteVisitor(ast.NodeVisitor):
    def __init__(self):
        self.replacements = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                sql = node.args[0].value.strip().upper()
                
                if sql.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP')):
                    self.replacements.append({
                        'lineno': node.func.lineno,
                        'col_start': node.func.value.col_offset,
                        'col_end': node.func.end_col_offset
                    })
        self.generic_visit(node)
        
def apply_refactor(file_path: Path, dry_run: bool = True) -> tuple[bool, str]:
    """Orquestrador de Refatoração Segura."""
    if file_path.name in BLACKLIST:
        return False, "Arquivo Core protegido (ignorado)."

    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except Exception as e:
        return False, f"Falha de AST: {e}"

    visitor = ExecuteWriteVisitor()
    visitor.visit(tree)

    if not visitor.replacements:
        return False, "Sem mudanças (apenas SELECTs ou queries dinâmicas)."

    lines = source.splitlines(keepends=True)
    changes_count = 0
    reps_by_line = defaultdict(list)

    for rep in visitor.replacements:
        reps_by_line[rep['lineno']].append(rep)

    # Aplica substituições nas linhas de trás para frente para não quebrar os offsets da coluna
    for lineno, reps in reps_by_line.items():
        line_idx = lineno - 1
        line_str = lines[line_idx]
        
        reps.sort(key=lambda x: x['col_start'], reverse=True)
        for r in reps:
            start = r['col_start']
            end = r['col_end']
            # Substitui 'obj.execute' por 'alexandria_write'
            line_str = line_str[:start] + 'alexandria_write' + line_str[end:]
            changes_count += 1
            
        lines[line_idx] = line_str

    new_source = "".join(lines)
    new_source = _inject_import(new_source)

    # Checagem de sanidade (verifica se a cirurgia não gerou SyntaxError antes de salvar)
    try:
        ast.parse(new_source)
    except SyntaxError as e:
        return False, f"A cirurgia gerou SyntaxError na linha {e.lineno}. Abortando."

    if dry_run:
        return True, f"Simulado: {changes_count} comando(s) de escrita remapeado(s)."

    # Gravação Definitiva
    backup_path = file_path.with_suffix('.py.bak')
    shutil.copy2(file_path, backup_path)
    file_path.write_text(new_source, encoding='utf-8')
    
    return True, f"Aplicado: {changes_count} chamadas em {file_path.name} (Backup salvo)"