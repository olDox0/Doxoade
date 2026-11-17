# -*- coding: utf-8 -*-
"""mody_noaux.py v2 — parser e applier de código bruto (--noaux).

Fase 1: OP_ADD_IMPL, OP_ADD_TYPE, OP_ADD_INCLUDE, OP_ADD_MACRO
Fase 2: OP_ADD_PROTO (pendente)
Fase 3: OP_MOD_BODY, OP_MOD_BRANCH (pendente)
"""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
from doxoade.commands.moddify_sys.mody_fuzzy import find_target_functions, find_insertion_point_in_function


@dataclass
class RawBlock:
    path: str
    code: str
    code_hash: str = ""
    op: str = "UNKNOWN"
    name: str = ""
    sig_first_line: str = ""
    phase: int = 0
    # Compat com v1:
    kind: str = ""
    signature: str = ""
    anchor: Optional[str] = None


@dataclass
class RawPatch:
    blocks: List[RawBlock] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────
# Separação e normalização
# ────────────────────────────────────────────────────────────────

_SEPARATOR = re.compile(r'^\s*---\s*$', re.MULTILINE)
_PATH_RE = re.compile(
    r'^[\w./\\:-]+\.(c|h|py|cpp|hpp|cc|cxx|txt|md|toml|json|yaml|yml)$'
)


def _normalize_code(code: str) -> str:
    lines = [ln.rstrip() for ln in code.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def _hash_code(code: str) -> str:
    return hashlib.sha256(_normalize_code(code).encode('utf-8')).hexdigest()[:16]


# ────────────────────────────────────────────────────────────────
# Classifier multiline (Fase 1 core)
# ────────────────────────────────────────────────────────────────

_SIG_TERMINATOR_RE = re.compile(r'[;{]')
_FUNC_NAME_RE = re.compile(r'([A-Za-z_]\w*)\s*\(')
_INCLUDE_PATH_RE = re.compile(r'[<"]([^>"]+)[>"]')
_DEFINE_NAME_RE = re.compile(r'#define\s+([A-Za-z_]\w*)')
_STRUCT_TAG_RE = re.compile(r'\b(?:struct|union|enum)\s+(\w+)\s*\{')
_TYPEDEF_NAME_RE = re.compile(r'\}\s*(\w+)\s*;')

_C_KEYWORDS = frozenset({
    'if', 'else', 'while', 'for', 'switch', 'do', 'return',
    'case', 'break', 'continue', 'goto', 'default', 'sizeof',
    'typedef', 'struct', 'union', 'enum',
    'static', 'extern', 'inline', 'const', 'volatile',
    'void', 'char', 'short', 'int', 'long', 'float', 'double',
    'unsigned', 'signed',
})

def _scan_signature(code: str, max_lines: int = 10) -> Tuple[str, str, Optional[str]]:
    lines = code.split('\n')
    while lines and not lines[0].strip(): lines.pop(0)
    if not lines: return ("", "", None)
    sig_parts = []
    sig_first = ""
    terminator = None
    for ln in lines[:max_lines]:
        stripped = ln.strip()
        if not stripped or stripped.startswith(('/*', '//', '*')): continue
        if not sig_first: sig_first = ln.rstrip()
        sig_parts.append(stripped)
        brace_pos = stripped.find('{')
        if brace_pos >= 0:
            before_brace = stripped[:brace_pos]
            full_before = ' '.join(sig_parts[:-1]) + ' ' + before_brace
            if '=' not in full_before:
                terminator = '{'
                break
        if ';' in stripped:
            terminator = ';'
            break
    return (' '.join(sig_parts), sig_first, terminator)

def _looks_like_declaration(sig_join: str) -> bool:
    first_paren = sig_join.find('(')
    first_eq = sig_join.find('=')
    if first_eq >= 0 and (first_paren < 0 or first_eq < first_paren): return True
    return False

def _looks_like_function_head(sig_join: str) -> bool:
    if '(' not in sig_join: return False
    if _looks_like_declaration(sig_join): return False
    m = _FUNC_NAME_RE.search(sig_join)
    if not m: return False
    name = m.group(1)
    if name in _C_KEYWORDS: return False
    return True

def classify_block_multiline(
    code: str, target_ext: str = ""
) -> Tuple[str, str, str, int]:
    sig_join, sig_first, terminator = _scan_signature(code)
    if not sig_join: return ("UNKNOWN", "", "", 0)
    if sig_join.startswith('#include'):
        m = _INCLUDE_PATH_RE.search(sig_join)
        return ("OP_ADD_INCLUDE", m.group(1) if m else "", sig_first, 1)
    if sig_join.startswith('#define'):
        m = _DEFINE_NAME_RE.search(sig_join)
        return ("OP_ADD_MACRO", m.group(1) if m else "", sig_first, 1)
    if 'typedef' in sig_join or _STRUCT_TAG_RE.search(sig_join):
        m_tag = _STRUCT_TAG_RE.search(sig_join)
        if m_tag: return ("OP_ADD_TYPE", m_tag.group(1), sig_first, 1)
        m_td = _TYPEDEF_NAME_RE.search(code)
        return ("OP_ADD_TYPE", m_td.group(1) if m_td else "", sig_first, 1)
    if terminator == ';':
        if not _looks_like_declaration(sig_join):
            m = _FUNC_NAME_RE.search(sig_join)
            if m and m.group(1) not in _C_KEYWORDS: return ("OP_ADD_PROTO", m.group(1), sig_first, 2)
    if terminator == '{':
        if _looks_like_function_head(sig_join):
            m = _FUNC_NAME_RE.search(sig_join)
            return ("OP_ADD_IMPL", m.group(1), sig_first, 1)
    if '{' in code and '}' in code: return ("OP_MOD_BODY", "", sig_first, 3)
    return ("UNKNOWN", "", sig_first, 0)


# ────────────────────────────────────────────────────────────────
# Parser
# ────────────────────────────────────────────────────────────────

def _parse_anchor_hint(code: str) -> Tuple[Optional[str], str]:
    lines = code.split('\n')
    if lines and lines[0].strip().startswith('# ANCHOR:'):
        return (lines[0].split(':', 1)[1].strip(), '\n'.join(lines[1:]))
    return (None, code)


def parse_noaux(text: str, project_root: Path) -> RawPatch:
    patch = RawPatch()
    for chunk in _SEPARATOR.split(text):
        chunk = chunk.strip('\n\r')
        if not chunk.strip():
            continue
        lines = chunk.split('\n')
        path = lines[0].strip()
        if not _PATH_RE.match(path):
            patch.parse_errors.append(f"path inválido: {path[:60]}")
            continue
        rest = 1
        while rest < len(lines) and not lines[rest].strip():
            rest += 1
        if rest >= len(lines):
            patch.parse_errors.append(f"sem código: {path[:60]}")
            continue
        code = '\n'.join(lines[rest:])
        if not code.strip():
            continue
        code = _strip_instruction_lines(code)
        anchor, code_clean = _parse_anchor_hint(code)
        ext = Path(path).suffix.lower()
        op, name, sig_first, phase = classify_block_multiline(code_clean, ext)
        patch.blocks.append(RawBlock(
            path=path, code=code_clean,
            code_hash=_hash_code(code_clean),
            op=op, name=name, sig_first_line=sig_first,
            phase=phase, kind=op.lower(), anchor=anchor,
        ))
    return patch


# ────────────────────────────────────────────────────────────────
# Idempotence
# ────────────────────────────────────────────────────────────────

def _find_code_in_file(code: str, file_lines: List[str]) -> Optional[int]:
    norm = _normalize_code(code)
    if not norm:
        return None
    needle = norm.split('\n')
    hay = [ln.rstrip() for ln in file_lines]
    n = len(needle)
    for i in range(len(hay) - n + 1):
        if hay[i:i + n] == needle:
            return i
    return None


def _find_name_in_file(op: str, name: str, file_lines: List[str]) -> Optional[int]:
    if not name:
        return None
    text = '\n'.join(file_lines)
    pat = None
    if op in ("OP_ADD_IMPL", "OP_ADD_PROTO"):
        pat = re.compile(r'\b' + re.escape(name) + r'\s*\(')
    elif op == "OP_ADD_TYPE":
        pat = re.compile(
            r'\b(?:struct|union|enum)\s+' + re.escape(name) + r'\b'
            r'|\}\s*' + re.escape(name) + r'\s*;'
        )
    elif op == "OP_ADD_INCLUDE":
        pat = re.compile(r'#\s*include\s*[<"]' + re.escape(name) + r'[>"]')
    elif op == "OP_ADD_MACRO":
        pat = re.compile(r'#\s*define\s+' + re.escape(name) + r'\b')
    if pat is None:
        return None
    m = pat.search(text)
    if m:
        return text[:m.start()].count('\n') + 1
    return None


# ────────────────────────────────────────────────────────────────
# Insertion points
# ────────────────────────────────────────────────────────────────

def _find_insertion_point_for_op(
    op: str, name: str, file_lines: List[str]
) -> Tuple[int, str]:
    """Retorna (idx_0based, motivo). idx -1 → não encontrou."""
    if op == "OP_ADD_INCLUDE":
        last = 0
        for i, ln in enumerate(file_lines):
            if re.match(r'#\s*include', ln):
                last = i + 1
        return (last, "após último #include")

    if op == "OP_ADD_MACRO":
        last = 0
        for i, ln in enumerate(file_lines):
            if re.match(r'#\s*define', ln):
                last = i + 1
        if last == 0:
            for i, ln in enumerate(file_lines):
                if re.match(r'#\s*include', ln):
                    last = i + 1
        return (last, "após último #define" if last else "início do arquivo")

    if op == "OP_ADD_TYPE":
        for i, ln in enumerate(file_lines):
            if re.search(r'\w+\s*\([^;]*\)\s*[;{]', ln):
                return (i, f"antes de 1ª função/prototype em L{i+1}")
        return (len(file_lines), "append")

    if op == "OP_ADD_PROTO":
        # 1. Seção API/Public/Prototypes
        for i, ln in enumerate(file_lines):
            if re.search(r'/\*\s*(?:API|Public|Exports|Prototypes)\s*\*/', ln, re.IGNORECASE):
                return (i + 1, f"após seção {ln.strip()}")
        # 2. Após último prototype
        last_proto = -1
        for i, ln in enumerate(file_lines):
            if re.search(r'\w+\s*\([^;]*\)\s*;', ln):
                last_proto = i
        if last_proto >= 0:
            return (last_proto + 1, f"após último prototype (L{last_proto+1})")
        # 3. Antes de 1ª definição (função com { ou struct)
        for i, ln in enumerate(file_lines):
            if re.search(r'\w+\s*\([^;]*\)\s*\{', ln) or re.search(r'\b(?:struct|union|enum)\s+\w+\s*\{', ln):
                return (i, f"antes de 1ª definição (L{i+1})")
        return (len(file_lines), "append no fim do .h")
    if op == "OP_ADD_IMPL":
        # Estratégia 1: prefix (dom_* → após dom_*)
        if name and '_' in name:
            prefix = name.split('_')[0] + '_'
            func_re = re.compile(r'\b(' + re.escape(prefix) + r'\w+)\s*\(')
            last_match = -1
            for i, ln in enumerate(file_lines):
                if func_re.search(ln):
                    last_match = i
            if last_match >= 0:
                depth = 0
                end = last_match
                for i in range(last_match, len(file_lines)):
                    depth += file_lines[i].count('{') - file_lines[i].count('}')
                    if depth == 0 and i > last_match:
                        end = i + 1
                        break
                return (end, f"após {prefix}* (último em L{last_match+1})")
        # Estratégia 2: após última função completa
        last_func_end = 0
        depth = 0
        in_func = False
        for i, ln in enumerate(file_lines):
            if re.search(r'\w+\s*\([^;]*\)\s*\{', ln):
                in_func = True
                depth = ln.count('{') - ln.count('}')
            elif in_func:
                depth += ln.count('{') - ln.count('}')
                if depth <= 0:
                    last_func_end = i + 1
                    in_func = False
        return (last_func_end, "append após última função")

    return (-1, f"op {op} não implementada nesta fase")


# ────────────────────────────────────────────────────────────────
# Resolve target
# ────────────────────────────────────────────────────────────────

def _resolve_target(block_path: str, root: Path) -> Tuple[Optional[Path], str]:
    direct = (root / block_path.replace('\\', '/')).resolve()
    if direct.exists():
        return (direct, "")
    basename = Path(block_path).name
    candidates = [
        c for c in root.rglob(basename)
        if '.doxoade' not in str(c) and '.git' not in str(c)
    ]
    if len(candidates) == 1:
        return (candidates[0], f"resolvido → {candidates[0].relative_to(root)}")
    if len(candidates) > 1:
        rels = [str(c.relative_to(root)) for c in candidates[:5]]
        return (None, f"múltiplos: {', '.join(rels)}")
    return (None, f"não encontrado: {basename}")


# ────────────────────────────────────────────────────────────────
# Apply
# ────────────────────────────────────────────────────────────────

def _write(
    target: Path, content: str, apply: bool,
    shadow_dir: Optional[Path], root: Path, report: dict
) -> bool:
    write_to = target
    if shadow_dir:
        try:
            rel = target.relative_to(root)
        except ValueError:
            rel = Path(target.name)
        write_to = shadow_dir / rel
        write_to.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(write_to, 'w', encoding='utf-8') as f:
            f.write(content)
        report["saved"] = not shadow_dir
        report["shadow_saved"] = bool(shadow_dir)
        return True
    except Exception as e:
        report["errors"].append(f"write: {e}")
        return False


def _strip_instruction_lines(code: str) -> str:
    """Remove linhas que são instrução em linguagem natural, não código C.

    Heurística: se a primeira palavra da linha é um verbo/substantivo de
    instrução conhecido (PT ou EN), a linha é descartada — mesmo que
    contenha caracteres de sintaxe C como ( ) { }.
    """
    _INSTRUCTION_WORDS = frozenset({
        # Verbos de instrução PT
        'adicionar', 'atualizar', 'declarar', 'remover', 'modificar',
        'inserir', 'criar', 'substituir', 'alterar', 'implementar',
        'aplicar', 'usar', 'incluir', 'excluir', 'mover', 'copiar',
        'renomear', 'refatorar', 'corrigir', 'definir', 'escrever',
        'colocar', 'trocar', 'atualize', 'adicione', 'declare', 'remova',
        'insira', 'crie', 'altere', 'implemente', 'troque', 'substitua',
        # Verbos de instrução EN
        'add', 'update', 'declare', 'remove', 'modify', 'insert', 'create',
        'replace', 'change', 'implement', 'apply', 'use', 'include',
        'delete', 'move', 'copy', 'rename', 'refactor', 'fix', 'write',
        'put', 'set', 'define', 'edit', 'patch', 'append', 'prepend',
        # Substantivos comuns em instruções PT
        'nova', 'novo', 'novas', 'novos', 'função', 'funcao', 'funções',
        'funcoes', 'arquivo', 'arquivos', 'linha', 'linhas', 'bloco',
        'blocos', 'código', 'codigo', 'protótipo', 'prototipo',
        'declaração', 'declaracao', 'definição', 'definicao', 'trecho',
        'seção', 'secao', 'parte', 'final', 'inicio', 'início',
        # Substantivos comuns em instruções EN
        'new', 'file', 'files', 'line', 'lines', 'block', 'blocks',
        'code', 'prototype', 'declaration', 'definition', 'function',
        'functions', 'section', 'part', 'end', 'beginning', 'top',
        'bottom', 'after', 'before', 'inside', 'outside', 'between',
    })
    lines = code.split('\n')
    filtered = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            filtered.append(ln)
            continue
        # Extrair primeira palavra (incluindo acentuadas)
        m = re.match(r'[A-Za-z\u00C0-\u00FF]+', stripped)
        if m and m.group(0).lower() in _INSTRUCTION_WORDS:
            continue  # Descarta: é instrução
        # Fallback: linha sem nenhum caractere de sintaxe C e sem keyword
        has_c_syntax = any(c in stripped for c in (';', '{', '}', '(', ')', '#', '*', '/'))
        c_starters = ('int', 'char', 'void', 'float', 'double', 'long', 'short',
                      'unsigned', 'signed', 'const', 'static', 'extern', 'inline',
                      'struct', 'union', 'enum', 'typedef', 'if', 'else', 'for',
                      'while', 'do', 'switch', 'case', 'return', 'break', 'continue',
                      'goto', 'sizeof', '#include', '#define', '#ifdef', '#ifndef',
                      '#endif', '#pragma', '/*', '//', '*', '{', '}')
        starts_c = any(stripped.startswith(kw) for kw in c_starters)
        if has_c_syntax or starts_c:
            filtered.append(ln)
        # else: descarta (parece instrução sem sintaxe C)
    return '\n'.join(filtered)


def _apply_mod_body(
    block: RawBlock, root: Path, target: Path,
    apply: bool = False, shadow_dir: Optional[Path] = None,
) -> dict:
    """Fase 3: OP_MOD_BODY / OP_MOD_BRANCH — fuzzy matching + inserção."""
    report = {
        "path": block.path, "op": block.op, "name": block.name,
        "sig_first": block.sig_first_line, "hash": block.code_hash,
        "status": "UNKNOWN", "insert_at": None, "reason": "",
        "errors": [], "saved": False, "shadow_saved": False,
        "preview": "", "target": str(target), "candidates": [],
    }

    try:
        file_lines = target.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception as e:
        report["errors"].append(f"read: {e}")
        return report

    # 1) Idempotência: bloco verbatim já existe?
    pos = _find_code_in_file(block.code, file_lines)
    if pos is not None:
        report["status"] = "IDEMPOTENT"
        report["insert_at"] = pos + 1
        report["reason"] = f"bloco verbatim em L{pos + 1}"
        return report

    # 1b) Idempotência fuzzy: todas as linhas do fragmento já existem na função?
    code_lines_idem = _normalize_code(block.code).split('\n')
    code_lines_idem = [ln.strip() for ln in code_lines_idem if ln.strip()]
    if code_lines_idem:
        file_stripped = {ln.strip() for ln in file_lines if ln.strip()}
        found_count = sum(1 for cl in code_lines_idem if cl in file_stripped)
        if found_count == len(code_lines_idem):
            report["status"] = "IDEMPOTENT"
            report["reason"] = f"todas as {len(code_lines_idem)} linhas já existem no arquivo (fuzzy)"
            return report

    # 2) Fuzzy matching para encontrar função-alvo
    code_lines = _normalize_code(_strip_instruction_lines(block.code)).split('\n')

    if block.anchor:
        # Anchor hint: procurar função pelo nome exato
        from doxoade.commands.moddify_sys.mody_semantic import parse_c_functions
        funcs = parse_c_functions(file_lines)
        candidates = [
            {"name": f.name, "score": 1.0, "start_line": f.start_line,
             "end_line": f.end_line, "signature": f.signature}
            for f in funcs if f.name == block.anchor
        ]
        if not candidates:
            report["status"] = "ANCHOR_REQUIRED"
            report["errors"].append(
                f"Função '{block.anchor}' não encontrada. "
                f"Verifique o nome no # ANCHOR."
            )
            return report
    else:
        candidates = find_target_functions(
            code_lines, file_lines, top_n=3, threshold=0.08
        )

    if not candidates:
        report["status"] = "ANCHOR_REQUIRED"
        report["errors"].append(
            "Nenhuma função-alvo encontrada (score < 0.15). "
            "Use '# ANCHOR: <func_name>' na 1ª linha do bloco."
        )
        return report

    report["candidates"] = [
        {"name": c["name"], "score": round(c["score"], 3)}
        for c in candidates
    ]

    # 3) Escolher melhor candidato
    best = candidates[0]

    # 4) Achar a função no parse para obter body_lines
    from doxoade.commands.moddify_sys.mody_semantic import parse_c_functions
    funcs = parse_c_functions(file_lines)
    target_func = None
    for f in funcs:
        if f.name == best["name"]:
            target_func = f
            break

    if target_func is None:
        report["status"] = "ANCHOR_REQUIRED"
        report["errors"].append(
            f"Função '{best['name']}' não localizada no parse estrutural."
        )
        return report

    # 5) Achar insertion point relativo dentro do corpo da função
    func_body = target_func.body_lines
    rel_idx, why = find_insertion_point_in_function(code_lines, func_body)

    # Converter para índice absoluto no arquivo (0-based)
    # Garantir que a inserção seja APÓS o '{' de abertura da função
    func_start_0 = target_func.start_line - 1
    brace_line_in_body = 0
    for _bi, _bl in enumerate(func_body):
        if '{' in _bl:
            brace_line_in_body = _bi
            break
    effective_rel = max(rel_idx, brace_line_in_body + 1)
    abs_insert = func_start_0 + effective_rel

    report["insert_at"] = abs_insert + 1
    report["reason"] = (
        f"em '{best['name']}' (score={best['score']:.3f}) — {why}"
    )

    # 6) Build content
    sep = ['']
    new_lines = (
        file_lines[:abs_insert] + sep + code_lines + [''] +
        file_lines[abs_insert:]
    )
    new_content = '\n'.join(new_lines).rstrip() + '\n'

    # 7) Preview
    ps = max(0, abs_insert - 2)
    pe = min(len(new_lines), abs_insert + len(code_lines) + 3)
    report["preview"] = '\n'.join(
        f"  {i+1:4d} | {new_lines[i]}" for i in range(ps, pe)
    )

    # 8) Brace gate
    if target.suffix.lower() in ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx'):
        try:
            from doxoade.commands.moddify_sys.mody_patch import PatchSurgeon
            err = PatchSurgeon._validate_brace_balance(new_content, target)
            if err:
                report["status"] = "BRACE_FAIL"
                report["errors"].append(err)
                return report
        except Exception:
            pass

    # 9) Write
    if apply or shadow_dir:
        if _write(target, new_content, apply, shadow_dir, root, report):
            report["status"] = "APPLIED" if apply else "APPLICABLE"
    else:
        report["status"] = "APPLICABLE"

    return report


def apply_raw_block(
    block: RawBlock, root: Path,
    apply: bool = False,
    shadow_dir: Optional[Path] = None,
) -> dict:
    report = {
        "path": block.path,
        "op": block.op,
        "name": block.name,
        "sig_first": block.sig_first_line,
        "hash": block.code_hash,
        "status": "UNKNOWN",
        "insert_at": None,
        "reason": "",
        "errors": [],
        "saved": False,
        "shadow_saved": False,
        "preview": "",
        "target": "",
    }

    # Gate de fase
    # Fase 2 (OP_ADD_PROTO) destravada
    if block.phase == 3:
        # Fase 3: OP_MOD_BODY / OP_MOD_BRANCH — fuzzy matching
        target, msg = _resolve_target(block.path, root)
        if target is None:
            report["status"] = "PATH_FAIL"
            report["errors"].append(msg)
            return report
        report["target"] = str(target)
        if msg: report["reason"] = msg
        if not target.exists():
            report["status"] = "PATH_FAIL"
            report["errors"].append(f"arquivo não existe: {block.path}")
            return report
        return _apply_mod_body(block, root, target, apply=apply, shadow_dir=shadow_dir)
    if block.phase == 0:
        report["status"] = "UNKNOWN_OP"
        report["errors"].append("classifier não reconheceu o bloco")
        return report

    target, msg = _resolve_target(block.path, root)
    if target is None:
        report["status"] = "PATH_FAIL"
        report["errors"].append(msg)
        return report
    report["target"] = str(target)
    if msg:
        report["reason"] = msg

    if not target.exists():
        report["status"] = "NOVO_ARQUIVO"
        content = _normalize_code(block.code) + '\n'
        if apply or shadow_dir:
            _write(target, content, apply, shadow_dir, root, report)
        return report

    try:
        file_lines = target.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception as e:
        report["errors"].append(f"read: {e}")
        return report

    # 1) Hash idempotence
    pos = _find_code_in_file(block.code, file_lines)
    if pos is not None:
        report["status"] = "IDEMPOTENT"
        report["insert_at"] = pos + 1
        report["reason"] = f"bloco verbatim em L{pos + 1}"
        return report

    # 2) Name idempotence
    name_pos = _find_name_in_file(block.op, block.name, file_lines)
    if name_pos is not None:
        report["status"] = "IDEMPOTENT"
        report["insert_at"] = name_pos
        report["reason"] = f"nome '{block.name}' já em L{name_pos}"
        return report

    # 3) Insertion
    insert_at, why = _find_insertion_point_for_op(
        block.op, block.name, file_lines
    )
    report["reason"] = why
    if insert_at < 0:
        report["status"] = "ANCHOR_REQUIRED"
        report["errors"].append(why)
        return report
    report["insert_at"] = insert_at + 1

    # 4) Build content
    code_lines = _normalize_code(block.code).split('\n')
    sep = ['', ''] if block.op == "OP_ADD_IMPL" and insert_at > 0 else ['']
    if insert_at == 0:
        sep = []
    new_lines = (
        file_lines[:insert_at] + sep + code_lines + [''] +
        file_lines[insert_at:]
    )
    new_content = '\n'.join(new_lines).rstrip() + '\n'

    # 5) Preview
    ps = max(0, insert_at - 2)
    pe = min(len(new_lines), insert_at + len(code_lines) + 3)
    report["preview"] = '\n'.join(
        f"  {i+1:4d} | {new_lines[i]}" for i in range(ps, pe)
    )

    # 6) Brace gate
    if target.suffix.lower() in ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx'):
        try:
            from doxoade.commands.moddify_sys.mody_patch import PatchSurgeon
            err = PatchSurgeon._validate_brace_balance(new_content, target)
            if err:
                report["status"] = "BRACE_FAIL"
                report["errors"].append(err)
                return report
        except Exception:
            pass

    # 7) Write
    if apply or shadow_dir:
        if _write(target, new_content, apply, shadow_dir, root, report):
            report["status"] = "APPLIED" if apply else "APPLICABLE"
    else:
        report["status"] = "APPLICABLE"
    return report
