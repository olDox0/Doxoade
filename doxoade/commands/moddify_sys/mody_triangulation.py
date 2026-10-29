# -*- coding: utf-8 -*-
# doxoade/commands/moddify_sys/mody_triangulation.py
"""
Mody Triangulation Engine v1.0 — Isolamento da lógica de triangulação.

Responsabilidades:
- Desconcatenar linhas de contexto (XML minificado → disco).
- Achar pré-âncora (cabeçalhos antes das adições).
- Achar pós-âncora (cabeçalhos depois das adições).
- Decidir o `loc` de inserção (com limite superior).

Não responsabilidades (ficam no PatchSurgeon):
- Aplicar o patch.
- Validar sintaxe.
- Idempotência / duplicação.
"""
from __future__ import annotations
import re
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from doxoade.commands.moddify_sys.mody_patch import Hunk


# --- CONSTANTES ---

INDENT_UNIT = "    "  # 4 espaços (PEP 8)
BODY_INDENT_THRESHOLD = 2  # mínimo de espaços para considerar "indentado"


# --- DESCONCATENAÇÃO ---

def desconcatenate_line(line: str, indent_unit: str = INDENT_UNIT) -> List[str]:
    """
    Desconcatena uma linha de contexto do XML minificado.
    
    Ex: "def build(): subprocess.run([...])" 
        → ["def build():", "    subprocess.run([...])"]
    """
    stripped = line.strip()
    if not stripped:
        return [line]
    
    m = re.match(r'^(\s*)([^:]+:)\s*(.+)$', line)
    if not m:
        return [line]
    
    indent = m.group(1)
    header = m.group(2).strip()
    body = m.group(3).strip()
    
    # Exceções: dicts, slices, annotations
    if (header.endswith('{') or header.endswith('[') or 
        '=' in header or 
        (':' in body and '{' in body)):
        return [line]
    
    valid_headers = ('def ', 'class ', 'if ', 'elif ', 'else', 'for ', 'while ', 
                    'with ', 'try', 'except ', 'finally')
    if not any(header.startswith(kw) for kw in valid_headers):
        return [line]
    
    return [
        f"{indent}{header}",
        f"{indent}{indent_unit}{body}",
    ]


def desconcatenate_context(hunk: "Hunk", indent_unit: str = INDENT_UNIT) -> List[str]:
    """Desconcatena todas as linhas de contexto ' ' do hunk."""
    result = []
    for pl in hunk.lines:
        if pl.kind == ' ':
            expanded = desconcatenate_line(pl.text, indent_unit)
            result.extend(expanded)
        else:
            result.append(pl.text)
    return result


# --- COLETA DE ÂNCORAS ---

def collect_headers(hunk: "Hunk", indices: List[int], indent_unit: str = INDENT_UNIT) -> List[str]:
    """
    Coleta os cabeçalhos (linhas NÃO indentadas) de um conjunto de índices.
    
    Usado para pré-âncora e pós-âncora.
    """
    headers = []
    for i in indices:
        expanded = desconcatenate_line(hunk.lines[i].text, indent_unit)
        for l in expanded:
            norm = normalize_line(l)
            if not norm:
                continue
            if not is_indented(l):
                headers.append(norm)
    return headers


def is_indented(line: str, threshold: int = BODY_INDENT_THRESHOLD) -> bool:
    """Verifica se a linha começa com pelo menos `threshold` espaços."""
    return len(line) - len(line.lstrip()) >= threshold


def normalize_line(line: str) -> str:
    """Normaliza linha (remove comentários, normaliza espaços)."""
    line = line.rstrip('\r\n').rstrip()
    line = re.sub(r'\s*(?:#|//).*$', '', line)
    return re.sub(r'\s+', ' ', line).strip()


# --- BUSCA DE ÂNCORAS NO DISCO ---

def find_anchor_in_file(
    file_lines: List[str], 
    headers: List[str], 
    start: int = 0
) -> Optional[int]:
    """
    Busca um bloco de cabeçalhos no arquivo, a partir de `start`.
    Retorna o índice (0-based) do início do bloco, ou None.
    """
    if not headers:
        return None
    
    norm_file = [normalize_line(l) for l in file_lines]
    total = len(norm_file)
    
    if len(headers) > total:
        return None
    
    for cand in range(start, total - len(headers) + 1):
        if norm_file[cand:cand + len(headers)] == headers:
            return cand
    
    return None


# --- API PÚBLICA ---

def find_addition_location(
    file_lines: List[str],
    hunk: "Hunk",
    target_idx: int,
    max_offset: int = 200,
) -> Tuple[Optional[int], int, str, int, List[int]]:
    """
    Triangulação para hunks de adição pura.
    
    Retorna (loc, offset, match_type, contig_len, candidates):
    - loc: índice (0-based) onde inserir, ou None.
    - offset: loc - target_idx.
    - match_type: 'ADD_ONLY_BOTH_ANCHORS' | 'ADD_ONLY_PRE_HEADER' | 
                  'ADD_ONLY_POST_HEADER' | 'ADD_ONLY_CTX_DESCONC' | 
                  'ADD_ONLY_FALLBACK' | 'NONE'.
    - contig_len: número de linhas do contexto que casaram.
    - candidates: lista de posições candidatas.
    """
    context_indices = [i for i, pl in enumerate(hunk.lines) if pl.kind == ' ']
    plus_indices = [i for i, pl in enumerate(hunk.lines) if pl.kind == '+']
    
    if not context_indices:
        return (target_idx, 0, 'ADD_ONLY', 0, [target_idx])
    
    first_plus = plus_indices[0]
    pre_context_indices = [i for i in context_indices if i < first_plus]
    post_context_indices = [i for i in context_indices if i > first_plus]
    
    # Coletar âncoras
    pre_headers = collect_headers(hunk, pre_context_indices)
    post_headers = collect_headers(hunk, post_context_indices)
    
    # ── Camada 1: pré-âncora → pós-âncora ──────────────────────────
    if pre_headers:
        pre_matches = []
        for cand in range(len(file_lines) - len(pre_headers) + 1):
            if normalize_file_slice(file_lines, cand, len(pre_headers)) == pre_headers:
                pre_matches.append(cand)
        
        if pre_matches:
            pre_matches.sort(key=lambda c: abs(c - target_idx))
            pre_loc = pre_matches[0]
            pre_end = pre_loc + len(pre_headers)
            
            # Tentar achar pós-âncora APÓS a pré-âncora
            post_loc = find_anchor_in_file(file_lines, post_headers, start=pre_end)
            
            if post_loc is not None and post_loc >= pre_end:
                return (
                    post_loc, post_loc - target_idx,
                    'ADD_ONLY_BOTH_ANCHORS', 0, [post_loc]
                )
            
            # Fallback: avançar pelo corpo
            best = pre_end
            body_indent = detect_body_indent(file_lines, best)
            if body_indent:
                while best < len(file_lines) and file_lines[best].startswith(body_indent):
                    best += 1
            while best < len(file_lines) and not normalize_line(file_lines[best]):
                best += 1
            
            if post_loc is not None and best > post_loc:
                best = post_loc
            
            return (best, best - target_idx, 'ADD_ONLY_PRE_HEADER', 0, pre_matches[:5])
    
    # ── Camada 2: pós-âncora sozinha ───────────────────────────────
    if post_headers:
        post_matches = []
        for cand in range(len(file_lines) - len(post_headers) + 1):
            if normalize_file_slice(file_lines, cand, len(post_headers)) == post_headers:
                post_matches.append(cand)
        
        if post_matches:
            post_matches.sort(key=lambda c: abs(c - target_idx))
            best = post_matches[0]
            return (best, best - target_idx, 'ADD_ONLY_POST_HEADER', 0, post_matches[:5])
    
    # ── Camada 3: contexto completo desconcatenado ─────────────────
    full_context = []
    for i in context_indices:
        expanded = desconcatenate_line(hunk.lines[i].text)
        full_context.extend([normalize_line(l) for l in expanded])
    
    all_matches = []
    for cand in range(len(file_lines) - len(full_context) + 1):
        if normalize_file_slice(file_lines, cand, len(full_context)) == full_context:
            all_matches.append(cand)
    
    if all_matches:
        all_matches.sort(key=lambda c: abs(c - target_idx))
        best = all_matches[0]
        insert_offset = 0
        for i in context_indices:
            if i < first_plus:
                expanded = desconcatenate_line(hunk.lines[i].text)
                insert_offset += len(expanded)
        insert_loc = best + insert_offset
        return (insert_loc, insert_loc - target_idx, 'ADD_ONLY_CTX_DESCONC', 0, all_matches[:5])
    
    # ── Camada 4: rejeitar ─────────────────────────────────────────
    if context_indices and len(context_indices) >= 2:
        return (None, 0, 'NONE', 0, [])
    
    return (target_idx, 0, 'ADD_ONLY_FALLBACK', 0, [target_idx])


# --- HELPERS ---

def normalize_file_slice(file_lines: List[str], start: int, length: int) -> List[str]:
    """Retorna a fatia normalizada de `file_lines`."""
    return [normalize_line(file_lines[start + i]) for i in range(length)]


def detect_body_indent(file_lines: List[str], start: int) -> Optional[str]:
    """Detecta a indentação do corpo a partir de `start`."""
    if start >= len(file_lines):
        return None
    raw = file_lines[start]
    if not raw.strip():
        return None
    indent_len = len(raw) - len(raw.lstrip())
    if indent_len < BODY_INDENT_THRESHOLD:
        return None
    return ' ' * indent_len

def find_post_anchor(
    file_lines: List[str], hunk: "Hunk", loc: int
) -> Optional[int]:
    """v6.12 — Encontra a pós-âncora a partir do `loc`."""
    context_indices = [i for i, pl in enumerate(hunk.lines) if pl.kind == ' ']
    plus_indices = [i for i, pl in enumerate(hunk.lines) if pl.kind == '+']
    if not plus_indices:
        return None
    first_plus = plus_indices[0]
    post_context_indices = [i for i in context_indices if i > first_plus]
    if not post_context_indices:
        return None
    post_headers = collect_headers(hunk, post_context_indices)
    if not post_headers:
        return None
    return find_anchor_in_file(file_lines, post_headers, start=loc)
