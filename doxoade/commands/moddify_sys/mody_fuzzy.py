# -*- coding: utf-8 -*-
"""
mody_fuzzy.py — Motor de Token-Jaccard para localização de fragmentos C/C++.
Usado pela Fase 3 (OP_MOD_BODY) do NOAUX e por sondas de fix estrutural.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Tuple
from doxoade.commands.moddify_sys.mody_semantic import (
    parse_c_functions, _extract_tokens, _C_KEYWORDS, FunctionInfo
)

def jaccard_score(set_a: set, set_b: set) -> float:
    """Calcula a similaridade de Jaccard entre dois conjuntos de tokens."""
    if not set_a or not set_b: 
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0

def coverage_score(set_a: set, set_b: set) -> float:
    """Fração dos tokens do fragmento (A) que existem na função (B)."""
    if not set_a:
        return 0.0
    inter = len(set_a & set_b)
    return inter / len(set_a)


def find_target_functions(
    fragment_lines: List[str],
    file_lines: List[str],
    top_n: int = 3,
    threshold: float = 0.10
) -> List[Dict[str, Any]]:
    """
    Encontra as funções mais prováveis de conter o fragmento.
    Retorna top-N funções ordenadas por score Jaccard.
    """
    funcs = parse_c_functions(file_lines)
    if not funcs: 
        return []
    
    frag_tokens = _extract_tokens(fragment_lines)
    if not frag_tokens: 
        return []
    
    scored = []
    for fn in funcs:
        fn_tokens = _extract_tokens(fn.body_lines)
        jac = jaccard_score(frag_tokens, fn_tokens)
        cov = coverage_score(frag_tokens, fn_tokens)
        # Híbrido: max(jaccard, coverage * 0.6) — coverage compensa
        # a diluição do Jaccard em funções grandes
        score = max(jac, cov * 0.6)
        if score >= threshold:
            scored.append({
                "name": fn.name,
                "score": score,
                "start_line": fn.start_line,
                "end_line": fn.end_line,
                "signature": fn.signature,
            })
            
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_n]

def find_insertion_point_in_function(
    fragment_lines: List[str], 
    function_body: List[str]
) -> Tuple[int, str]:
    """
    Heurística para achar onde DENTRO da função o fragmento deve ser inserido.
    Retorna (offset_relativo_0_based, razao).
    """
    if not fragment_lines or not function_body:
        return (len(function_body), "fallback: append no fim da função")
        
    first_line = fragment_lines[0].strip()
    
    # Regex para declaração de variável C (simplificada)
    decl_re = re.compile(r'^\s*[A-Za-z_]\w*\s+\*?\s*[A-Za-z_]\w*\s*(=|;|,|\[)')
    # Regex para controle de fluxo
    ctrl_re = re.compile(r'^\s*(if|for|while|switch|return|do)\b')
    # Regex para chamada de função ou atribuição (statement)
    stmt_re = re.compile(r'^\s*[A-Za-z_]\w*\s*\(.*\)\s*;')
    assign_re = re.compile(r'^\s*[A-Za-z_][\w\->.]*\s*=[^=]')
    
    is_decl = decl_re.match(first_line)
    
    if is_decl:
        # Heurística C89: Inserir após o ÚLTIMO bloco contíguo de declarações 
        # no início da função, parando no primeiro statement/chamada.
        last_decl_idx = -1
        first_stmt_idx = len(function_body)
        
        for i, ln in enumerate(function_body):
            if not ln.strip() or ln.strip().startswith(('/*', '//', '*')):
                continue
            if decl_re.match(ln):
                last_decl_idx = i
            elif ctrl_re.match(ln) or stmt_re.match(ln) or assign_re.match(ln):
                first_stmt_idx = i
                break
                
        if last_decl_idx >= 0 and last_decl_idx < first_stmt_idx:
            return (last_decl_idx + 1, f"após bloco inicial de declarações (L{last_decl_idx+1})")
        elif last_decl_idx >= 0:
            return (last_decl_idx + 1, f"após última declaração (L{last_decl_idx+1})")
        else:
            return (0, "início da função (nenhuma declaração prévia)")

    # 2. Se começa com controle de fluxo (if/for/while)
    if ctrl_re.match(first_line):
        indent = len(first_line) - len(first_line.lstrip())
        last_ctrl = -1
        for i, ln in enumerate(function_body):
            if not ln.strip(): continue
            ln_indent = len(ln) - len(ln.lstrip())
            if ln_indent == indent and ctrl_re.match(ln):
                last_ctrl = i
        if last_ctrl >= 0:
            return (last_ctrl + 1, f"após último bloco de controle de nível similar (L{last_ctrl+1})")
            
    # 3. Fallback: Fuzzy match de linha única
    frag_norm = re.sub(r'\s+', ' ', first_line).strip()
    for i, ln in enumerate(function_body):
        if re.sub(r'\s+', ' ', ln).strip() == frag_norm:
            return (i + 1, "linha idêntica já existe (possível duplicata)")
            
    return (len(function_body), "fallback: append no fim da função")
