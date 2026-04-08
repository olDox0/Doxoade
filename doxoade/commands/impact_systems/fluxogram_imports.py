# -*- coding: utf-8 -*-
"""
fluxogram_imports.py

Serialização e formatos de saída do grafo.
Hoje: Mermaid e JSON-friendly.
Depois: HTML, vis.js, d3.js, etc.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .impact_fluxogram import FluxGraph


def to_mermaid(graph: 'FluxGraph', highlight_cycles: bool = True, target_module: str = None) -> str:
    from doxoade.commands.impact_systems.impact_fluxogram import detect_cycles

    def _id(mod: str) -> str:
        return "n_" + mod.replace('.', '_').replace('-', '_')

    def _short_name(mod: str) -> str:
        """Encurta o nome do módulo para exibição (Max 2 últimos níveis)."""
        parts = mod.split('.')
        if len(parts) > 2:
            return f"{parts[-2]}.{parts[-1]}"
        return mod

    # 1. Configuração do Mermaid (Linhas Suaves/Arredondadas com curva 'basis')
    lines = [
        "%%{init: {",
        "  'flowchart': {",
        "    'curve': 'basis',",         # Curvatura fluída
        "    'nodeSpacing': 80,",
        "    'rankSpacing': 150,",
        "    'padding': 20",
        "  }",
        "}}%%",
        "flowchart TD"
    ]

    cycles = detect_cycles(graph) if highlight_cycles else []
    cycle_edges = set()
    for cycle in cycles:
        for i in range(len(cycle) - 1):
            cycle_edges.add((cycle[i], cycle[i + 1]))

    # 2. Declara Nós usando a paleta Dark Pastel
    for mod, attrs in graph.nodes.items():
        node_id   = _id(mod)
        short_mod = _short_name(mod)

        if mod == target_module:
            node_class = "targetNode"
        elif attrs.get('external'):
            node_class = "externalNode"
        else:
            node_class = "internalNode"

        # Label simples — sem foreignObject, sem HTML inline.
        # O click é capturado pela diretiva nativa do Mermaid abaixo.
        lines.append(f'    {node_id}["{short_mod}"]')
        lines.append(f'    class {node_id} {node_class}')

        # Diretiva de click nativa do Mermaid (securityLevel: loose).
        # Chama window.nexusNodeClick com o nome completo do módulo.
        lines.append(f'    click {node_id} call nexusNodeClick("{mod}")')

    # 3. Declara Arestas (Setas)
    for edge in graph.edges:
        src, dst = _id(edge.src), _id(edge.dst)
        is_target_related = (edge.src == target_module or edge.dst == target_module)
        is_external_dst = graph.nodes.get(edge.dst, {}).get('external', False)
        
        if (edge.src, edge.dst) in cycle_edges:
            lines.append(f'    {src} --> {dst}:::cycleEdge')
        elif is_target_related:
            lines.append(f'    {src} --> {dst}:::targetEdge')
        elif is_external_dst:
            lines.append(f'    {src} --> {dst}:::externalEdge')
        else:
            lines.append(f'    {src} --> {dst}:::internalEdge')

    # 4. Injeção da Paleta de Cores (Estilo Dark UI c/ Borda "Neon")
    
    # Ciclos (Erros/Warnings): Tons de Rosa
    lines.append("classDef cycleEdge stroke:#CE699E,stroke-width:4px;")
    
    # Target (Alvo): Fundo dark-pastel-orange com borda pastel-orange
    lines.append("classDef targetNode fill:#5a3821,stroke:#E38D53,stroke-width:2px,rx:8,ry:8;")
    lines.append("classDef targetEdge stroke:#E38D53,stroke-width:3px,color:#E38D53;")

    # Internos: Fundo dark-pastel-blue com borda pastel-blue
    lines.append("classDef internalNode fill:#1e395c,stroke:#4D91E8,stroke-width:2px,rx:8,ry:8;")
    lines.append("classDef internalEdge stroke:#4D91E8,stroke-width:2px,color:#4D91E8;")

    # Externos: Fundo Piano Black 2 com borda text-muted
    lines.append("classDef externalNode fill:#19171a,stroke:#5e5c5e,stroke-width:1px,stroke-dasharray: 4 4,rx:8,ry:8;")
    lines.append("classDef externalEdge stroke:#5e5c5e,stroke-width:1.5px,stroke-dasharray: 4 4,color:#5e5c5e;")

    return "\n".join(lines)


def to_payload(graph: FluxGraph) -> Dict[str, Any]:
    """
    Estrutura pronta para front-end depois.
    Não depende de HTML ainda.
    """
    from doxoade.commands.impact_systems.impact_fluxogram  import graph_stats
    return {
        "stats": graph_stats(graph),
        "nodes": [
            {
                "id": mod,
                **attrs,
            }
            for mod, attrs in sorted(graph.nodes.items())
        ],
        "edges": [
            {
                "source": edge.src,
                "target": edge.dst,
                "kind": edge.kind,
                "imports": list(edge.imports),
            }
            for edge in graph.edges
        ],
    }


def to_json(graph: FluxGraph, *, indent: int = 2) -> str:
    return json.dumps(to_payload(graph), ensure_ascii=False, indent=indent)


def summarize(graph: FluxGraph) -> str:
    from doxoade.commands.impact_systems.impact_fluxogram  import graph_stats
    stats = graph_stats(graph)
    return (
        f"nodes={stats['nodes']} "
        f"edges={stats['edges']} "
        f"isolated={len(stats['isolated'])}"
    )
    
    
def to_xml(graph: FluxGraph, *, include_cycles: bool = True) -> str:
    import xml.etree.ElementTree as ET

    root = ET.Element("fluxogram")

    # ======================
    # NODES
    # ======================
    nodes_el = ET.SubElement(root, "nodes")

    for mod, attrs in graph.nodes.items():
        node_el = ET.SubElement(nodes_el, "node", id=mod)

        if "path" in attrs:
            ET.SubElement(node_el, "path").text = attrs["path"]

        defines_el = ET.SubElement(node_el, "defines")
        for d in attrs.get("defines", []):
            ET.SubElement(defines_el, "def").text = d

        imports_el = ET.SubElement(node_el, "imports")
        for i in attrs.get("imports", []):
            ET.SubElement(imports_el, "import").text = i

        if attrs.get("external"):
            ET.SubElement(node_el, "external").text = "true"

    # ======================
    # EDGES
    # ======================
    edges_el = ET.SubElement(root, "edges")

    for edge in graph.edges:
        edge_el = ET.SubElement(
            edges_el,
            "edge",
            source=edge.src,
            target=edge.dst,
            kind=edge.kind
        )

        if edge.imports:
            symbols_el = ET.SubElement(edge_el, "symbols")
            for name in edge.imports:
                ET.SubElement(symbols_el, "name").text = name

    # ======================
    # CYCLES
    # ======================
    if include_cycles:
        from doxoade.commands.impact_systems.impact_fluxogram  import detect_cycles
        cycles = detect_cycles(graph)
        cycles_el = ET.SubElement(root, "cycles")

        for i, cycle in enumerate(cycles):
            c_el = ET.SubElement(cycles_el, "cycle", id=str(i))
            for node in cycle:
                ET.SubElement(c_el, "node").text = node

    return ET.tostring(root, encoding="unicode")