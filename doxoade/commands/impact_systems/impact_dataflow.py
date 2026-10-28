# -*- coding: utf-8 -*-
# doxoade/commands/impact_systems/impact_dataflow.py
"""
Impact Dataflow — Fase 2 (PLACEHOLDER).

Rastreia o fluxo de dados entre funções, para responder:
    "Se eu mudar o campo X do retorno de A, quem quebra?"

Status: NÃO IMPLEMENTADO. Este módulo define a interface e os
contratos que a Fase 2 vai respeitar, permitindo que o CLI e
outros módulos já se integrem com ele.

Modelo de dados (planejado)
───────────────────────────

Um DataFlow é:

    {
      'source': {
        'module': 'doxoade.commands.git_systems.git_search',
        'function': '_fetch_remote_tree',
        'field': 'items[].path',
        'type': 'str',
      },
      'sinks': [
        {
          'module': '...',
          'function': '_render_tree',
          'param': 'items',
          'access_path': 'items[].path',  # como o campo é acessado
          'line': 342,
        },
        ...
      ],
      'transformations': [  # onde o dado é modificado no caminho
        {'function': '_shorten', 'kind': 'slice'},
      ],
    }

Perguntas que a Fase 2 responderá:
    1. Se `_fetch_remote_tree` mudar `items[]` (ex: remover `size`),
       quais funções quebram?
    2. `items` de `_fetch_remote_tree` chega em `_render_tree` via
       `_render_outline`? (cadeia de dataflow)
    3. Quais campos de retorno são realmente usados? (cobertura)
    4. Quais parâmetros nunca são lidos? (dead data)

Implementação planejada:
    - AST + SSA simplificado por função
    - Rastrear atributos de retorno: `ret.field`, `ret[0]`, `ret.a.b`
    - Comparar `Dict`/`dataclass`/`NamedTuple` retornados com acessos
    - Integrar com `impact_contracts.py` (uma violação de contrato
      pode ser explicada por um dataflow quebrado)

Roadmap:
    Fase 2.1: rastrear acessos de campo (atributos e índice)
    Fase 2.2: rastrear transformações (funções que consomem e
              repassam o dado)
    Fase 2.3: detectar "campos mortos" (nunca acessados por ninguém)
    Fase 2.4: integrar ao `impact-analysis --dataflow` e ao `save.py`
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────
# Estruturas de dados (planejadas)
# ─────────────────────────────────────────────────────────────

def extract_dataflows(tree, module):
    dataflows = []
    for func in tree.body:  # só funções top-level
        if not isinstance(func, ast.FunctionDef):
            continue
        # 1. Detectar o que a função retorna (Dict, dataclass, NamedTuple)
        return_type = _infer_return_type(func)
        if not return_type:
            continue
        # 2. Detectar campos do retorno (keys do Dict ou atributos)
        fields = _extract_fields(return_type)
        # 3. Para cada campo, procurar consumidores no módulo
        for field in fields:
            sinks = _find_field_accessors(field, tree)
            if sinks:
                dataflows.append({
                    'source': {'function': func.name, 'field': field},
                    'sinks': sinks,
                })
    return dataflows


def trace_field_consumers(
    module: str,
    function: str,
    field: str,
    project_index: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    [PLACEHOLDER] Rastreia consumidores de um campo específico.

    Dado `module.function` que retorna um objeto com `field`, encontra
    todas as funções que acessam `ret.field` (ou usam `ret[idx]`).

    Ainda não implementado. Retorna lista vazia.

    Retorno planejado:
        [
          {'module': ..., 'function': ..., 'line': ..., 'access_kind': 'attr'|'index'},
          ...
        ]
    """
    # TODO (Fase 2.1): percorrer índice de callers + AST de cada consumidor
    return []


def detect_dead_fields(
    tree: ast.AST,
    module: str,
) -> List[Dict[str, Any]]:
    """
    [PLACEHOLDER] Detecta campos de retorno que ninguém acessa.

    Funções que retornam `Dict[str, Any]` ou dataclasses/NamedTuples
    podem ter campos que nunca são lidos no projeto (data morta).

    Ainda não implementado. Retorna lista vazia.

    Retorno planejado:
        [
          {'module': ..., 'function': ..., 'field': ..., 'kind': 'dict-key'|'attr'},
          ...
        ]
    """
    # TODO (Fase 2.3): cruzar campos retornados com acessos detectados
    return []


def render_dataflow_cli(
    dataflows: List[Dict[str, Any]],
    module: str,
    verbose: bool = False,
) -> None:
    """
    [PLACEHOLDER] Renderiza dataflows no terminal.

    Ainda não implementado. Imprime mensagem de status.
    """
    from doxoade.tools.doxcolors import Fore, Style
    click_echo = print
    click_echo(
        Fore.YELLOW
        + f'⚠  [DATAFLOW] Fase 2 ainda não implementada para "{module}".'
        + Style.RESET_ALL
    )
    click_echo(
        Style.DIM
        + '   Interface definida em impact_dataflow.py. '
        + 'Aguardando Fase 2.1 (rastreamento de campos).'
        + Style.RESET_ALL
    )


def dataflow_to_mermaid(dataflows: List[Dict[str, Any]]) -> str:
    """
    [PLACEHOLDER] Gera Mermaid de dataflow.

    Ainda não implementado. Retorna placeholder Mermaid válido.
    """
    return (
        'flowchart LR\n'
        '  classDef placeholder fill:#333,stroke:#666,stroke-dasharray: 5 5\n'
        '  dataflow["🚧 Dataflow (Fase 2)"]:::placeholder\n'
        '  note["Rastreamento de campos<br/>não implementado"]:::placeholder\n'
        '  dataflow -.-> note\n'
    )


# ─────────────────────────────────────────────────────────────
# Status do módulo (para CLI)
# ─────────────────────────────────────────────────────────────

def get_fase2_status() -> Dict[str, Any]:
    """Retorna status da Fase 2 (útil para CLI diagnóstico)."""
    return {
        'fase': 2,
        'name': 'Dataflow',
        'status': 'PLACEHOLDER',
        'implemented': False,
        'ready_for': [
            'interface definida em impact_dataflow.py',
            'flag --dataflow no impact-analysis integrada',
            'rendering placeholder no terminal',
            'mermaid placeholder válido',
        ],
        'pending': [
            'Fase 2.1: rastreamento de campos (ret.field, ret[idx])',
            'Fase 2.2: cadeia de transformações (funções que repassam dados)',
            'Fase 2.3: detecção de campos mortos',
            'Fase 2.4: integração com save.py (gate de contrato)',
        ],
    }
