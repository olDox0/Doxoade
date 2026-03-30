# -*- coding: utf-8 -*-
"""Análise de risco estrutural para projetos Python dinâmicos."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path


_LEVELS = {
    0: ("SEGURO", "INFO"),
    1: ("MODERADO", "WARNING"),
    2: ("ALTO", "WARNING"),
    3: ("CRÍTICO", "CRITICAL"),
}


def analyze_structural_risk(state, io_manager, **kwargs):
    """Avalia risco estrutural e injeta achado no estado do check."""
    # Filtra rigorosamente apenas para Python (.py)
    files =[f for f in io_manager.resolve_files(kwargs.get("target_files")) if f.endswith('.py')]
    
    findings = defaultdict(int)
    per_file = defaultdict(lambda: defaultdict(int))

    for fp in files:
        p = Path(fp)
        try:
            text = p.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except Exception:
            continue
        _scan_tree(tree, findings, per_file[str(p)])

    level = _classify_level(findings)
    level_name, severity = _LEVELS[level]

    indicators = _summarize_indicators(findings)
    msg = (
        f"Risco estrutural Python: nível {level} ({level_name}). "
        f"Indicadores: {indicators}. "
    )

    if level >= 2:
        msg += "Recomendado executar Vulcan em modo conservador e revisar pontos dinâmicos."
    else:
        msg += "Monitorar evolução e manter contratos explícitos de importação/tipagem."

    state.register_finding(
        {
            "severity": severity,
            "category": "STRUCTURAL-RISK",
            "message": msg,
            "file": state.target_path,
            "line": 0,
            "meta": {
                "risk_level": level,
                "risk_label": level_name,
                "indicators": dict(findings),
                "files_analyzed": len(files),
            },
        }
    )


def _scan_tree(tree: ast.AST, findings: dict, bucket: dict):
    for node in ast.walk(tree):
        # Nível 3: execução dinâmica e hooks de import
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval"}:
            findings["dynamic_exec"] += 1
            bucket["dynamic_exec"] += 1
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and _attr_chain(t.value) == "sys.modules":
                    findings["sys_modules_mutation"] += 1
                    bucket["sys_modules_mutation"] += 1
        if isinstance(node, ast.Call) and _attr_chain(node.func) in {"sys.meta_path.insert", "sys.meta_path.append"}:
            findings["meta_path_mutation"] += 1
            bucket["meta_path_mutation"] += 1

        # Nível 2: dinâmica pesada
        if isinstance(node, ast.Call) and (
            _attr_chain(node.func) == "importlib.import_module"
            or (isinstance(node.func, ast.Name) and node.func.id == "__import__")
        ):
            findings["dynamic_import"] += 1
            bucket["dynamic_import"] += 1
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"getattr", "setattr", "delattr"}:
            findings["runtime_attr_access"] += 1
            bucket["runtime_attr_access"] += 1

        # Nível 1: sinais moderados
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"globals", "locals", "vars"}:
            findings["runtime_namespace"] += 1
            bucket["runtime_namespace"] += 1


def _classify_level(indicators: dict) -> int:
    lvl3 = indicators["dynamic_exec"] + indicators["sys_modules_mutation"] + indicators["meta_path_mutation"]
    if lvl3 > 0:
        return 3

    lvl2 = indicators["dynamic_import"] + indicators["runtime_attr_access"]
    if lvl2 >= 8:
        return 2
    if lvl2 >= 2:
        return 1

    if indicators["runtime_namespace"] >= 4:
        return 1
    return 0


def _summarize_indicators(indicators: dict) -> str:
    ordered = [
        ("dynamic_exec", "exec/eval"),
        ("sys_modules_mutation", "mutação de sys.modules"),
        ("meta_path_mutation", "mutação de sys.meta_path"),
        ("dynamic_import", "import dinâmico"),
        ("runtime_attr_access", "getattr/setattr/delattr"),
        ("runtime_namespace", "globals/locals/vars"),
    ]
    parts = [f"{label}={indicators[key]}" for key, label in ordered]
    return ", ".join(parts)


def _attr_chain(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _attr_chain(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""
