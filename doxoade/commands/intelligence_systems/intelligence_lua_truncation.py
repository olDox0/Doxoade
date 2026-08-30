# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/intelligence_lua_truncation.py
"""
🐺 ANÚBIS LUA GUARD — Detector de Truncamento específico para Lua.
Lexer real: remove comentários/strings e verifica balanceamento de blocos.
"""
import re

_LUA_TOKEN_CLEANER = re.compile(
    r"--\[(=*)\[.*?\]\1\]|"       # long comment --[[ ]]
    r"--[^\r\n]*|"                # line comment --
    r"\[(=*)\[.*?\]\2\]|"         # long string [[ ]]
    r'"(?:\\.|[^"\\])*"|'         # double-quoted string
    r"'(?:\\.|[^'\\])*'",         # single-quoted string
    re.DOTALL,
)

def _clean_lua(source: str) -> str:
    return _LUA_TOKEN_CLEANER.sub(" ", source)


def _has_unclosed_long_bracket(source: str) -> bool:
    """Detecta [[ ou [==[ sem fechamento correspondente (truncamento clássico)."""
    opens  = re.findall(r"--?\[(=*)\[", source)   # --[[ ou [[
    closes = re.findall(r"\](=*)\]", source)      # ]] ou ]==]
    open_levels  = [len(o) for o in opens]
    close_levels = [len(c) for c in closes]
    # Stack-based match por nível de '='
    stack = []
    for lvl in open_levels:
        stack.append(lvl)
    for lvl in close_levels:
        if stack and stack[-1] == lvl:
            stack.pop()
    return len(stack) > 0


def analyze_lua_integrity(content: str) -> dict:
    """
    Retorna dict compatível com TruncationChecker:
    {"status": "stable"|"truncated"|"corrupt", "reason": str}
    """
    if not content.strip():
        return {"status": "truncated", "reason": "Arquivo Lua vazio"}

    # 1. Long brackets não fechados → truncado
    if _has_unclosed_long_bracket(content):
        return {"status": "truncated", "reason": "Long string/comentário [[ ]] não fechado"}

    # 2. Balanceamento de blocos (function/if/for/while/do/repeat … end/until)
    clean = _clean_lua(content)
    func_count   = len(re.findall(r"\bfunction\b", clean))
    then_count   = len(re.findall(r"\bthen\b", clean))
    elseif_count = len(re.findall(r"\belseif\b", clean))
    do_count     = len(re.findall(r"\bdo\b", clean))
    repeat_count = len(re.findall(r"\brepeat\b", clean))
    end_count    = len(re.findall(r"\bend\b", clean))
    until_count  = len(re.findall(r"\buntil\b", clean))

    opened = func_count + max(0, then_count - elseif_count) + do_count + repeat_count
    closed = end_count + until_count

    if opened > closed:
        return {
            "status": "truncated",
            "reason": f"Blocos abertos sem fechar: {opened} abertos vs {closed} fechados"
        }
    if closed > opened + 1:  # tolerância de 1 para edge cases de parser
        return {
            "status": "corrupt",
            "reason": f"'end/until' órfãos: {closed} fechadores vs {opened} abridores"
        }

    # 3. Terminação abrupta: última linha não-vazia termina com operador/abertura
    last_line = ""
    for line in reversed(content.splitlines()):
        if line.strip():
            last_line = line.strip()
            break
    if last_line and last_line[-1] in ",=(+-*/%^#..{":
        return {"status": "truncated", "reason": f"Terminação abrupta: '{last_line[-30:]}'"}

    return {"status": "stable", "reason": "Lexer Lua: blocos balanceados"}
