# doxoade/doxoade/commands/impact_systems/impact_fluxogram.py
"""
impact_fluxogram.py

Camada de grafo para dependências por import.
Não faz I/O de arquivo, não faz CLI, não faz HTML.
Recebe o índice já pronto e devolve estrutura navegável.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

@dataclass(frozen=True)
class FluxEdge:
    src: str
    dst: str
    kind: str = 'import'
    imports: Tuple[str, ...] = ()

@dataclass
class FluxGraph:
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[FluxEdge] = field(default_factory=list)

    def add_node(self, module: str, **attrs: Any) -> None:
        if module not in self.nodes:
            self.nodes[module] = {}
        self.nodes[module].update(attrs)

    def add_edge(self, src: str, dst: str, kind: str='import', imports: Optional[List[str]]=None) -> None:
        self.edges.append(FluxEdge(src=src, dst=dst, kind=kind, imports=tuple(imports or [])))

    def adjacency(self) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {mod: [] for mod in self.nodes}
        for edge in self.edges:
            adj.setdefault(edge.src, []).append(edge.dst)
        return adj

    def reverse_adjacency(self) -> Dict[str, List[str]]:
        rev: Dict[str, List[str]] = {mod: [] for mod in self.nodes}
        for edge in self.edges:
            rev.setdefault(edge.dst, []).append(edge.src)
        return rev

def build_import_fluxogram(index: Dict[str, Dict[str, Any]], *, include_external: bool=False, target_module: Optional[str]=None, depth: Optional[int]=None) -> FluxGraph:
    """
    Constrói o grafo de imports a partir do índice do projeto.

    Regras:
    - nós = módulos
    - arestas = módulo A importa módulo B
    - se include_external=False, só mantém arestas para módulos que existem no index
    - target_module + depth permitem montar subgrafo focado
    """
    graph = FluxGraph()
    for mod, data in index.items():
        graph.add_node(mod, path=data.get('path'), defines=data.get('defines', []), imports=data.get('imports', []))
    internal_modules: Set[str] = set(index.keys())
    for src_mod, data in index.items():
        raw_imports = data.get('imports', []) or []
        for dst_mod in raw_imports:
            if not include_external and dst_mod not in internal_modules:
                continue
            graph.add_node(dst_mod, external=dst_mod not in internal_modules)
            graph.add_edge(src_mod, dst_mod, kind='import')
    if target_module is not None:
        graph = _subgraph_from_target(graph, target_module, depth=depth)
    return graph

def _subgraph_from_target(graph: FluxGraph, target: str, depth: Optional[int]=1) -> FluxGraph:
    """
    Retorna subgrafo ao redor de um módulo alvo.
    depth=1 -> alvo + vizinhos diretos
    depth=None -> grafo inteiro centrado no alvo, expandindo por alcance
    """
    if target not in graph.nodes:
        return FluxGraph()
    if depth is not None and depth < 0:
        return FluxGraph()
    forward = graph.adjacency()
    reverse = graph.reverse_adjacency()
    frontier: Set[str] = {target}
    visited: Set[str] = {target}
    if depth is None:
        while frontier:
            next_frontier: Set[str] = set()
            for mod in frontier:
                for nxt in forward.get(mod, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        next_frontier.add(nxt)
                for prv in reverse.get(mod, []):
                    if prv not in visited:
                        visited.add(prv)
                        next_frontier.add(prv)
            frontier = next_frontier
    else:
        for _ in range(depth):
            next_frontier = set()
            for mod in frontier:
                for nxt in forward.get(mod, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        next_frontier.add(nxt)
                for prv in reverse.get(mod, []):
                    if prv not in visited:
                        visited.add(prv)
                        next_frontier.add(prv)
            frontier = next_frontier
    sub = FluxGraph()
    for mod in visited:
        if mod in graph.nodes:
            sub.nodes[mod] = dict(graph.nodes[mod])
    for edge in graph.edges:
        if edge.src in visited and edge.dst in visited:
            sub.edges.append(edge)
    return sub

def graph_stats(graph: FluxGraph) -> Dict[str, Any]:
    incoming: Dict[str, int] = {mod: 0 for mod in graph.nodes}
    outgoing: Dict[str, int] = {mod: 0 for mod in graph.nodes}
    for edge in graph.edges:
        outgoing[edge.src] = outgoing.get(edge.src, 0) + 1
        incoming[edge.dst] = incoming.get(edge.dst, 0) + 1
    return {'nodes': len(graph.nodes), 'edges': len(graph.edges), 'incoming': incoming, 'outgoing': outgoing, 'isolated': sorted([m for m in graph.nodes if incoming.get(m, 0) == 0 and outgoing.get(m, 0) == 0])}

def analyze_cycles(graph: FluxGraph):
    cycles = detect_cycles(graph)
    alerts = []
    for cycle in cycles:
        size = len(cycle) - 1
        if len(cycle) <= 2 and cycle[0] == cycle[-1]:
            continue
        if size <= 2:
            severity = 'LOW'
        elif size == 3:
            severity = 'MEDIUM'
        else:
            severity = 'HIGH'
        alerts.append({'type': 'cycle', 'severity': severity, 'size': size, 'path': cycle})
    return alerts

def format_cycle_alert(alert: dict) -> str:
    path = ' → '.join(alert['path'])
    severity = alert['severity']
    size = alert['size']
    if severity == 'LOW':
        hint = 'Possível acoplamento leve.'
    elif severity == 'MEDIUM':
        hint = 'Considere quebrar dependência com interface ou extração.'
    else:
        hint = 'Ciclo crítico! Forte acoplamento. Reestruture módulos.'
    return f'⚠ [CYCLE:{severity}] tamanho={size}\n  Caminho: {path}\n  Sugestão: {hint}'

def find_cycle_hotspot(graph: FluxGraph, cycle: list):
    stats = graph_stats(graph)
    incoming = stats['incoming']
    return max(cycle, key=lambda m: incoming.get(m, 0))

def detect_cycles(graph: FluxGraph):
    visited = set()
    stack = []
    on_stack = set()
    cycles = []
    adj = graph.adjacency()

    def dfs(node):
        visited.add(node)
        stack.append(node)
        on_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in on_stack:
                idx = stack.index(neighbor)
                cycle = stack[idx:] + [neighbor]
                cycles.append(cycle)
        stack.pop()
        on_stack.remove(node)
    for n in graph.nodes:
        if n not in visited:
            dfs(n)
    return cycles