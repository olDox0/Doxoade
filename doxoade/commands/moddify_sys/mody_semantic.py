# -*- coding: utf-8 -*-
"""mody_semantic.py — classificação semântica de hunks rejeitados.

Complementa o `_is_idempotent_hunk` (que cobre "goal state já atingido")
com análise de POR QUE o patch não casou:

  - OBSOLETE:    função alvo não existe mais
  - REFACTORED:  função existe mas corpo mudou
  - SUPERSEDED:  intenção do patch já aplicada (em forma diferente)
  - RELOCATED:   bloco removido existe em outro lugar (offset shift)
  - UNKNOWN:     não classificável

Não é AST: é regex + token analysis, suficiente para C e testável.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from doxoade.commands.moddify_sys.mody_patch import Hunk


# ────────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────────

_C_KEYWORDS = frozenset({
    'return', 'else', 'break', 'continue', 'while', 'for', 'do',
    'true', 'false', 'null', 'NULL', 'sizeof', 'void',
    'int', 'char', 'short', 'long', 'unsigned', 'signed',
    'float', 'double', 'struct', 'union', 'enum', 'typedef',
    'static', 'extern', 'inline', 'const', 'volatile',
    'if', 'switch', 'case', 'default', 'goto',
    'this', 'new', 'delete',
})

_C_CONTROL = frozenset({'if', 'for', 'while', 'switch', 'return', 'sizeof'})


# ────────────────────────────────────────────────────────────────
# Helpers de parsing C
# ────────────────────────────────────────────────────────────────

def _strip_c_comments(lines: List[str]) -> List[str]:
    """Remove /* */ e // de linhas C (preserva line count)."""
    result = []
    in_block = False
    for line in lines:
        out = []
        i = 0
        n = len(line)
        while i < n:
            if in_block:
                end = line.find('*/', i)
                if end < 0:
                    i = n
                    break
                in_block = False
                i = end + 2
            else:
                bc = line.find('/*', i)
                lc = line.find('//', i)
                if bc < 0 and lc < 0:
                    out.append(line[i:])
                    break
                if lc >= 0 and (bc < 0 or lc < bc):
                    out.append(line[i:lc])
                    break
                out.append(line[i:bc])
                in_block = True
                i = bc + 2
        result.append(''.join(out))
    return result


@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    signature: str
    body_lines: List[str]


_C_FUNC_START = re.compile(
    r'^(?P<indent>[ \t]{0,8})'
    r'(?:static\s+|extern\s+|inline\s+|const\s+|__cdecl\s+|__stdcall\s+)*'
    r'(?:[A-Za-z_]\w*(?:\s*\*)?\s+)+'
    r'(?P<name>[A-Za-z_]\w*)\s*\('
)


def parse_c_functions(lines: List[str]) -> List[FunctionInfo]:
    """Parser tolerante (não-AST) de funções C. Retorna FunctionInfo[]."""
    stripped = _strip_c_comments(lines)
    funcs: List[FunctionInfo] = []
    i = 0
    while i < len(stripped):
        m = _C_FUNC_START.match(stripped[i])
        if not m:
            i += 1
            continue
        name = m.group('name')
        if name in _C_CONTROL or name.lower() in _C_KEYWORDS:
            i += 1
            continue
        j = i
        depth = 0
        found = False
        while j < len(stripped) and j < i + 15:
            depth += stripped[j].count('{') - stripped[j].count('}')
            if '{' in stripped[j]:
                found = True
                break
            j += 1
        if not found:
            i += 1
            continue
        body = list(lines[i:j + 1])
        k = j + 1
        while k < len(stripped) and depth > 0:
            depth += stripped[k].count('{') - stripped[k].count('}')
            body.append(lines[k])
            k += 1
        funcs.append(FunctionInfo(
            name=name, start_line=i + 1, end_line=k,
            signature=lines[i].strip(), body_lines=body,
        ))
        i = k
    return funcs


def _extract_tokens(lines: Iterable[str]) -> set:
    """Extrai (kind, value): identificadores longos + strings."""
    tokens = set()
    for line in lines:
        for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]{3,})\b', line):
            t = m.group(1)
            if t.lower() not in _C_KEYWORDS:
                tokens.add(('ident', t))
        for m in re.finditer(r'"([^"\\]{2,})"', line):
            tokens.add(('str', m.group(1)))
    return tokens


def _token_in_text(token: Tuple[str, str], text: str) -> bool:
    kind, val = token
    if kind == 'str':
        return val in text
    return re.search(r'\b' + re.escape(val) + r'\b', text) is not None


def _intent_tokens(additions: List[str], removals: List[str]) -> set:
    """Tokens que APARECEM nas adições mas NÃO nas remoções (novidade)."""
    add_t = _extract_tokens(additions)
    rem_t = _extract_tokens(removals)
    return {t for t in add_t if t not in rem_t}


def _find_block(needle: List[str], haystack: List[str]) -> List[int]:
    """Encontra inícios de subsequência contígua."""
    if not needle or not haystack:
        return []
    n, m = len(haystack), len(needle)
    if m > n:
        return []
    return [i for i in range(n - m + 1) if haystack[i:i + m] == needle]


# ────────────────────────────────────────────────────────────────
# Classificador
# ────────────────────────────────────────────────────────────────

def classify_rejection(
    hunk: "Hunk",
    file_lines: List[str],
) -> Tuple[str, float, str]:
    """Classifica um hunk REJEITADO. Retorna (verdict, confidence, hint)."""
    additions = [pl.text for pl in hunk.lines if pl.kind == '+']
    removals = [pl.text for pl in hunk.lines if pl.kind == '-']
    context = [pl.text for pl in hunk.lines if pl.kind == ' ']
    hunk_text = '\n'.join(additions + removals + context)

    if not additions and not removals:
        return ("UNKNOWN", 0.3, "Hunk vazio (sem + ou -).")

    funcs = parse_c_functions(file_lines)
    func_names = {f.name for f in funcs}

    mentioned = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\s*\(', hunk_text))
    mentioned_funcs = mentioned & func_names

    intent = _intent_tokens(additions, removals)
    file_stripped = _strip_c_comments(file_lines)
    file_text = '\n'.join(file_stripped)

    # 6) SUPERSEDED — todos os tokens de intenção já no arquivo
    if intent:
        found = [t for t in intent if _token_in_text(t, file_text)]
        if len(found) == len(intent) and len(intent) >= 1:
            examples = sorted({v for k, v in found if k == 'ident'})[:3]
            if not examples:
                examples = sorted({v for k, v in found if k == 'str'})[:3]
            return (
                "SUPERSEDED", 0.85,
                f"Intenção já aplicada — tokens {examples} existem "
                f"no arquivo (fix em outra forma)."
            )

    # 7) RELOCATED — bloco removido existe em outro lugar
    if removals:
        norm_file = [' '.join(l.split()) for l in file_stripped]
        norm_rem = [' '.join(r.split()) for r in removals if r.strip()]
        hits = _find_block(norm_rem, norm_file)
        if hits:
            loc = hits[0] + 1
            return ("RELOCATED", 0.75,
                    f"Bloco removido existe em L{loc} (contexto mudou).")

    # 8) REFACTORED — função mencionada existe, corpo mudou
    if mentioned_funcs:
        fname = sorted(mentioned_funcs)[0]
        f = next(f for f in funcs if f.name == fname)
        return (
            "REFACTORED", 0.75,
            f"Função '{fname}' existe (L{f.start_line}-L{f.end_line}) "
            f"mas corpo mudou (patch stale)."
        )

    # 9) OBSOLETE — nenhuma função mencionada existe
    if mentioned:
        missing = sorted(mentioned - func_names)[:3]
        return ("OBSOLETE", 0.70,
                f"Funções mencionadas não existem: {missing}.")

    return ("UNKNOWN", 0.4, "Não classificável por heurística.")
