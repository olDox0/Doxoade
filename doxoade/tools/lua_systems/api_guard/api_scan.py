# -*- coding: utf-8 -*-
# doxoade/tools/lua_systems/api_guard/api_scan.py
"""
Scanner Estático de Uso de APIs e Integridade de Módulos Lua.
Capítulo 5: Detecta 'use before local', globals não declaradas e APIs deprecadas nos templates.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple


LITEXL_CORE_SYMBOLS = {
    "core": "core",
    "config": "core.config",
    "style": "core.style",
    "command": "core.command",
    "keymap": "core.keymap",
    "common": "core.common",
    "syntax": "core.syntax",
    "Doc": "core.doc",
    "DocView": "core.docview",
    "Node": "core.node",
    "RootView": "core.rootview",
    "StatusView": "core.statusview",
    "View": "core.view",
}


def clean_lua_comments_and_strings(source: str) -> str:
    """Substitui comentários e strings literais por espaços para análise léxica pura."""
    pattern = re.compile(
        r"--\[(=*)\[.*?\]\1\]|"  # Comentários de bloco --[[ ... ]]
        r"--[^\r\n]*|"           # Comentários de linha -- ...
        r"\[(=*)\[.*?\]\2\]|"    # Strings multilinha [[ ... ]]
        r'"(?:\\.|[^"\\])*"|'   # Strings de aspas duplas
        r"'(?:\\.|[^'\\])*'",    # Strings de aspas simples
        re.DOTALL
    )
    return pattern.sub(" ", source)


class APITemplateScanner:
    """Analisa templates em busca de variáveis não declaradas e monkey-patches inseguros."""

    def __init__(self, template_dir: Path):
        self.template_dir = template_dir

    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        content = file_path.read_text(encoding="utf-8")
        clean_content = clean_lua_comments_and_strings(content)

        # 1. Encontra todas as declarações locais: `local name = ...` ou `local function name`
        local_decls: Set[str] = set()
        for match in re.finditer(r"\blocal\s+(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", clean_content):
            local_decls.add(match.group(1))

        # Globais permitidas nativas do Lite XL
        allowed_globals = {
            "system", "renderer", "rencache", "USERDIR", "PATHSEP", "DATADIR",
            "VERSION", "PLATFORM", "SCALE", "ARGS", "_G", "type", "pcall", "xpcall",
            "rawget", "rawset", "pairs", "ipairs", "tostring", "tonumber", "print",
            "error", "assert", "select", "next", "setmetatable", "getmetatable",
            "dofile", "loadfile", "require", "math", "string", "table", "io", "os",
            "debug", "coroutine", "package", "utf8", "DOXOADE_API", "_DOXOADE_API_PROBE",
            "UIForge", "PanelSlots", "AuditState", "HoverTooltip", "FloatingMenu"
        }

        missing_requires: List[Dict[str, Any]] = []
        suspicious_patches: List[Dict[str, Any]] = []

        # 2. Verifica uso de símbolos core sem declaração local
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            clean_line = clean_lua_comments_and_strings(line)
            
            # Detecta símbolos do Lite XL acessados
            for sym, module_name in LITEXL_CORE_SYMBOLS.items():
                if sym not in local_decls and sym not in allowed_globals:
                    # Checa se o símbolo é usado como identificador de chamada/propriedade
                    pattern = rf"\b{sym}\b(?:\s*[\.\:\[]|\s*\()"
                    if re.search(pattern, clean_line) and not clean_line.strip().startswith(f"local {sym}"):
                        missing_requires.append({
                            "line": idx,
                            "symbol": sym,
                            "suggested_require": f'local {sym} = require "{module_name}"',
                            "raw_line": line.strip()
                        })

            # Detecta monkey-patches cegos do tipo: `local original = RootView.on_key_pressed`
            patch_match = re.search(r"local\s+original_(\w+)\s*=\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)", clean_line)
            if patch_match:
                suspicious_patches.append({
                    "line": idx,
                    "target_class": patch_match.group(2),
                    "method": patch_match.group(3),
                    "raw_line": line.strip()
                })

        return {
            "file": file_path.name,
            "total_lines": len(lines),
            "declared_locals": list(sorted(local_decls)),
            "missing_requires": missing_requires,
            "suspicious_patches": suspicious_patches,
            "status": "PASS" if len(missing_requires) == 0 else "FAIL"
        }

    def scan_all(self) -> Dict[str, Any]:
        results = {}
        total_missing = 0
        for f in sorted(self.template_dir.glob("*.lua")):
            res = self.scan_file(f)
            results[f.name] = res
            total_missing += len(res["missing_requires"])

        return {
            "total_files": len(results),
            "total_missing_requires": total_missing,
            "files": results
        }
