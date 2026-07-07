# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_dependency_graph.py
"""
Hermes Dependency Graph - Análise de Import Cascade
====================================================
Escaneia todos os módulos do projeto e constrói um grafo direcionado de dependências.

Objetivos:
1. Identificar módulos raiz (mais importados) - candidatos a pré-compilação
2. Identificar módulos folha (não importam nada) - candidatos a cache
3. Detectar ciclos de dependência - risco de deadlock
4. Calcular profundidade de import - gargalos de cascade
5. Gerar ordem de carregamento otimizada

Uso:
    graph = HermesDependencyGraph(project_root)
    graph.build()
    graph.print_report()
    graph.save_json()
"""
import ast
import os
import json
import sys
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ModuleInfo:
    """Informações de um módulo individual."""
    name: str
    path: str
    imports: List[str] = field(default_factory=list)  # Módulos que este importa
    imported_by: List[str] = field(default_factory=list)  # Módulos que importam este
    depth: int = 0  # Profundidade no grafo (0 = raiz)
    is_leaf: bool = False  # Não importa nada
    is_root: bool = False  # Não é importado por ninguém
    has_cycle: bool = False  # Participa de ciclo
    line_count: int = 0
    complexity: int = 0


@dataclass
class CycleInfo:
    """Informações de um ciclo de dependência."""
    modules: List[str]
    length: int
    severity: str  # 'low', 'medium', 'high'


class ImportScanner(ast.NodeVisitor):
    """Scanner AST que extrai imports de um módulo."""
    
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.imports: Set[str] = set()
        self.complexity = 0
        
    def visit_Import(self, node):
        """Captura: import X, import X.Y"""
        for alias in node.names:
            # Captura o nome completo do módulo (não apenas a primeira parte)
            mod_name = alias.name
            if not mod_name.startswith('_'):  # Ignora privados
                self.imports.add(mod_name)
        self.complexity += 1
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        """Captura: from X import Y"""
        if node.module:
            # Captura o nome completo do módulo
            mod_name = node.module
            if not mod_name.startswith('_') and not mod_name.startswith('.'):
                self.imports.add(mod_name)
        self.complexity += 1
        self.generic_visit(node)
        
    def visit_FunctionDef(self, node):
        """Conta complexidade ciclomática."""
        self.complexity += 1
        self.generic_visit(node)
        
    def visit_ClassDef(self, node):
        """Conta classes."""
        self.complexity += 1
        self.generic_visit(node)


class HermesDependencyGraph:
    """Constrói e analisa o grafo de dependências do projeto."""
    
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.modules: Dict[str, ModuleInfo] = {}
        self.graph: Dict[str, Set[str]] = defaultdict(set)  # adjacência
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)  # reverso
        self.cycles: List[CycleInfo] = []
        self.build_dir = self.root / '.doxoade' / 'hermes'
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
    def build(self, verbose: bool = False) -> Dict[str, ModuleInfo]:
        """Constrói o grafo completo escaneando todos os .py do projeto."""
        if verbose:
            print(f"\n{'═' * 70}")
            print(f"  🔍 HERMES DEPENDENCY GRAPH BUILDER")
            print(f"{'═' * 70}")
            print(f"  Projeto: {self.root.name}")
            print(f"  Varrendo módulos...\n")
        
        # 1. Escaneia todos os .py
        py_files = list(self.root.rglob('*.py'))
        py_files = [f for f in py_files if self._should_scan(f)]
        
        if verbose:
            print(f"  ✔ Encontrados {len(py_files)} módulos Python")
        
        # 2. Extrai imports de cada módulo
        for py_file in py_files:
            module_name = self._path_to_module(py_file)
            if not module_name:
                continue
                
            try:
                source = py_file.read_text(encoding='utf-8', errors='ignore')
                tree = ast.parse(source, filename=str(py_file))
                
                scanner = ImportScanner(module_name)
                scanner.visit(tree)
                
                # Filtra imports de bibliotecas externas (só mantém internos)
                internal_imports = [
                    imp for imp in scanner.imports 
                    if self._is_internal_module(imp)
                ]
                
                self.modules[module_name] = ModuleInfo(
                    name=module_name,
                    path=str(py_file.relative_to(self.root)),
                    imports=internal_imports,
                    line_count=len(source.splitlines()),
                    complexity=scanner.complexity
                )
                
                # Constrói grafo
                for imp in internal_imports:
                    self.graph[module_name].add(imp)
                    self.reverse_graph[imp].add(module_name)
                    
            except Exception as e:
                if verbose:
                    print(f"  ⚠ Erro ao escanear {py_file.name}: {e}")
        
        if verbose:
            print(f"  ✔ Grafo construído: {len(self.modules)} módulos, {sum(len(v) for v in self.graph.values())} arestas")
        
        # 3. Calcula métricas
        self._calculate_depths()
        self._identify_roots_and_leaves()
        self._detect_cycles()
        
        if verbose:
            print(f"  ✔ Análise completa: {len(self.cycles)} ciclos detectados")
            print(f"  ✔ Módulos raiz: {sum(1 for m in self.modules.values() if m.is_root)}")
            print(f"  ✔ Módulos folha: {sum(1 for m in self.modules.values() if m.is_leaf)}")
        
        return self.modules
    
    def _should_scan(self, path: Path) -> bool:
        """Filtra diretórios que não devem ser escaneados."""
        ignore_dirs = {
            'venv', '.venv', '__pycache__', '.git', '.doxoade',
            'node_modules', 'build', 'dist', 'tests', 'test'
        }
        return not any(part in ignore_dirs for part in path.parts)
    
    def _path_to_module(self, path: Path) -> Optional[str]:
        """Converte path para nome de módulo."""
        try:
            rel = path.relative_to(self.root)
            parts = list(rel.parts)
            if parts[-1] == '__init__.py':
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1].replace('.py', '')
            return '.'.join(parts) if parts else None
        except:
            return None
    
    def _is_internal_module(self, module_name: str) -> bool:
        """Verifica se o módulo é interno ao projeto."""
        # Heurística: módulos internos começam com 'doxoade', 'commands', ou são relativos
        # Também aceita módulos que existem no grafo (mesmo sem prefixo)
        if module_name.startswith('doxoade'):
            return True
        if module_name.startswith('commands'):
            return True
        if module_name.startswith('tests'):
            return True
        if module_name in self.modules:
            return True
        # Verifica se é um submódulo de algo que já está no grafo
        for existing in self.modules:
            if module_name.startswith(existing + '.') or existing.startswith(module_name + '.'):
                return True
        return False
    
    def _calculate_depths(self):
        """Calcula profundidade de cada módulo no grafo (BFS a partir das raízes)."""
        # Identifica raízes (módulos que não são importados por ninguém)
        roots = [name for name in self.modules if not self.reverse_graph[name]]
        
        # BFS para calcular profundidade
        queue = deque([(root, 0) for root in roots])
        visited = set()
        
        while queue:
            module, depth = queue.popleft()
            if module in visited:
                continue
            visited.add(module)
            
            if module in self.modules:
                self.modules[module].depth = depth
            
            # Adiciona dependências
            for dep in self.graph.get(module, []):
                if dep not in visited:
                    queue.append((dep, depth + 1))
    
    def _identify_roots_and_leaves(self):
        """Identifica módulos raiz e folha."""
        for name, info in self.modules.items():
            info.is_root = len(self.reverse_graph[name]) == 0
            info.is_leaf = len(self.graph[name]) == 0
    
    def _detect_cycles(self):
        """Detecta ciclos no grafo usando DFS."""
        visited = set()
        rec_stack = set()
        cycles_found = []
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Ciclo encontrado
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles_found.append(cycle)
            
            path.pop()
            rec_stack.remove(node)
        
        for module in self.modules:
            if module not in visited:
                dfs(module, [])
        
        # Processa ciclos
        seen_cycles = set()
        for cycle in cycles_found:
            cycle_key = tuple(sorted(cycle[:-1]))  # Remove duplicata final
            if cycle_key not in seen_cycles:
                seen_cycles.add(cycle_key)
                severity = 'high' if len(cycle) > 5 else 'medium' if len(cycle) > 3 else 'low'
                self.cycles.append(CycleInfo(
                    modules=list(cycle_key),
                    length=len(cycle_key),
                    severity=severity
                ))
                # Marca módulos como participantes de ciclo
                for mod in cycle_key:
                    if mod in self.modules:
                        self.modules[mod].has_cycle = True
    
    def get_critical_modules(self, top_n: int = 20) -> List[ModuleInfo]:
        """Retorna os N módulos mais críticos (mais importados + maior profundidade)."""
        # Score = (imported_by * 2) + depth + complexity/10
        scored = []
        for info in self.modules.values():
            score = (len(self.reverse_graph[info.name]) * 2) + info.depth + (info.complexity / 10)
            scored.append((score, info))
        
        # CORREÇÃO: Usa key para ordenar apenas pelo score, evitando comparação de ModuleInfo
        scored.sort(key=lambda x: x[0], reverse=True)
        return [info for _, info in scored[:top_n]]
    
    def get_optimal_load_order(self) -> List[str]:
        """Retorna ordem de carregamento otimizada (topológica)."""
        # Kahn's algorithm para ordenação topológica
        # Inicializa in_degree apenas para módulos escaneados
        in_degree = {name: 0 for name in self.modules}
        
        # Calcula grau de entrada (apenas para módulos internos)
        for module in self.modules:
            for neighbor in self.graph.get(module, []):
                # Só conta se o vizinho foi escaneado (módulo interno)
                if neighbor in self.modules:
                    in_degree[neighbor] += 1
        
        # Inicia com módulos que não dependem de ninguém (grau 0)
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        order = []
        
        while queue:
            module = queue.popleft()
            order.append(module)
            
            for neighbor in self.graph.get(module, []):
                # Só processa se o vizinho foi escaneado
                if neighbor in in_degree:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        
        # Se não incluiu todos, há ciclos ou módulos não processados
        if len(order) < len(self.modules):
            remaining = set(self.modules.keys()) - set(order)
            order.extend(sorted(remaining))  # Adiciona restantes ordenados
        
        return order
    
    def print_report(self):
        """Imprime relatório completo do grafo."""
        print(f"\n{'═' * 70}")
        print(f"  📊 HERMES DEPENDENCY GRAPH REPORT")
        print(f"{'═' * 70}")
        print(f"  Total de módulos: {len(self.modules)}")
        print(f"  Total de arestas: {sum(len(v) for v in self.graph.values())}")
        print(f"  Ciclos detectados: {len(self.cycles)}")
        print(f"  Módulos raiz: {sum(1 for m in self.modules.values() if m.is_root)}")
        print(f"  Módulos folha: {sum(1 for m in self.modules.values() if m.is_leaf)}")
        
        # Top 10 módulos mais críticos
        print(f"\n{'─' * 70}")
        print(f"  🔥 TOP 10 MÓDULOS CRÍTICOS (pré-compilação)")
        print(f"{'─' * 70}")
        critical = self.get_critical_modules(10)
        for i, info in enumerate(critical, 1):
            imported_count = len(self.reverse_graph[info.name])
            print(f"  {i:2d}. {info.name:<40} {imported_count:3d} imports | depth: {info.depth}")
        
        # Ciclos
        if self.cycles:
            print(f"\n{'─' * 70}")
            print(f"  ⚠️  CICLOS DETECTADOS ({len(self.cycles)})")
            print(f"{'─' * 70}")
            for cycle in self.cycles[:5]:  # Mostra apenas os 5 primeiros
                severity_color = '\033[91m' if cycle.severity == 'high' else '\033[93m' if cycle.severity == 'medium' else '\033[92m'
                print(f"  {severity_color}[{cycle.severity.upper()}]\033[0m {' → '.join(cycle.modules)}")
        
        # Ordem de carregamento
        print(f"\n{'─' * 70}")
        print(f"  📋 ORDEM DE CARREGAMENTO OTIMIZADA (primeiros 20)")
        print(f"{'─' * 70}")
        order = self.get_optimal_load_order()
        for i, module in enumerate(order[:20], 1):
            print(f"  {i:2d}. {module}")
        
        print(f"\n{'═' * 70}\n")
    
    def save_json(self) -> Path:
        """Salva o grafo em JSON para análise externa."""
        data = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.root),
            'total_modules': len(self.modules),
            'total_edges': sum(len(v) for v in self.graph.values()),
            'cycles': [asdict(c) for c in self.cycles],
            'modules': {
                name: {
                    'path': info.path,
                    'imports': info.imports,
                    'imported_by': list(self.reverse_graph[name]),
                    'depth': info.depth,
                    'is_root': info.is_root,
                    'is_leaf': info.is_leaf,
                    'has_cycle': info.has_cycle,
                    'line_count': info.line_count,
                    'complexity': info.complexity
                }
                for name, info in self.modules.items()
            },
            'load_order': self.get_optimal_load_order()
        }
        
        output_path = self.build_dir / 'dependency_graph.json'
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print(f"  ✔ Grafo salvo em: {output_path}")
        return output_path
    
    def generate_preload_script(self) -> Path:
        """Gera script Python para pré-carregar módulos críticos."""
        critical = self.get_critical_modules(20)
        
        script = f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# doxoade/tools/hermes_systems/hermes_preload_critical.py
\"\"\"
Hermes Preload Script - Módulos Críticos
=========================================
Gerado automaticamente pelo Hermes Dependency Graph.
Pré-carrega os {len(critical)} módulos mais críticos para otimizar o startup.
\"\"\"
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

def preload_critical_modules():
    \"\"\"Pré-carrega módulos críticos em paralelo.\"\"\"
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    critical_modules = [
"""
        
        for info in critical:
            script += f"        '{info.name}',\n"
        
        script += """    ]
    
    print(f"\\n{'═' * 70}")
    print(f"  ⚡ HERMES PRELOAD - Carregando {len(critical_modules)} módulos críticos")
    print(f"{'═' * 70}\\n")
    
    t0 = time.perf_counter()
    loaded = 0
    failed = 0
    
    def load_module(module_name):
        try:
            __import__(module_name)
            return (module_name, True, None)
        except Exception as e:
            return (module_name, False, str(e))
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(load_module, mod): mod for mod in critical_modules}
        
        for future in as_completed(futures):
            mod_name, success, error = future.result()
            if success:
                loaded += 1
                print(f"  ✔ {mod_name}")
            else:
                failed += 1
                print(f"  ✘ {mod_name}: {error}")
    
    elapsed = (time.perf_counter() - t0) * 1000
    
    print(f"\\n{'─' * 70}")
    print(f"  ✔ Pré-carregamento concluído em {elapsed:.1f}ms")
    print(f"  ✔ Sucessos: {loaded} | Falhas: {failed}")
    print(f"{'═' * 70}\\n")
    
    return loaded, failed

if __name__ == '__main__':
    preload_critical_modules()
"""
        
        output_path = self.build_dir / 'hermes_preload_critical.py'
        output_path.write_text(script, encoding='utf-8')
        
        print(f"  ✔ Script de preload gerado em: {output_path}")
        return output_path


if __name__ == '__main__':
    # Teste rápido
    project_root = Path(__file__).resolve().parents[2]
    graph = HermesDependencyGraph(str(project_root))
    graph.build(verbose=True)
    graph.print_report()
    graph.save_json()
    graph.generate_preload_script()