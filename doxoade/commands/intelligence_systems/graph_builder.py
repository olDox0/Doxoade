# -*- coding: utf-8 -*-
# doxoade/commands/intelligence_systems/graph_builder.py
"""
Motor de Grafo de Dependências para o Intelligence (PASC 13.0).
Rastreia imports (AST) e referências textuais (comportamento Nexus Search).
"""
import os
import ast
from doxoade.dnm import DNM


def get_module_path(file_path, project_root):
    """Converte caminho físico (abs ou rel) em caminho de módulo Python."""
    # Normaliza para relativo
    if os.path.isabs(file_path):
        rel = os.path.relpath(file_path, project_root)
    else:
        rel = file_path
    rel = rel.replace(os.sep, '/').replace('\\', '/')
    if rel.endswith('.py'):
        rel = rel[:-3]
    if rel.endswith('/__init__'):
        rel = rel[:-9]
    return rel.replace('/', '.')


def extract_imports(file_path):
    """Extrai imports via AST. Retorna set de strings de módulo."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
    except Exception:
        pass
    return imports


def build_project_graph(project_root, ignore_spec):
    """
    Constrói o mapa de módulos e dependências AST do projeto.
    Retorna:
        module_to_file: {modulo_str: caminho_relativo}
        file_deps:      {caminho_relativo: set(modulos_importados)}
        module_dependents: {modulo_str: set(caminhos_relativos_que_importam)}
    """
    module_to_file = {}
    file_to_module = {}
    file_deps = {}
    module_dependents = {}

    nav = DNM(project_root)
    all_files = nav.scan(extensions=['.py'])

    # 1. Mapeia arquivos para módulos
    for f_abs in all_files:
        rel_path = os.path.relpath(f_abs, project_root).replace('\\', '/')
        if ignore_spec.match_file(rel_path):
            continue
        mod_path = get_module_path(f_abs, project_root)
        module_to_file[mod_path] = rel_path
        file_to_module[rel_path] = mod_path

    # 2. Mapeia quem importa quem
    for rel_path, mod_path in file_to_module.items():
        f_abs = os.path.join(project_root, rel_path)
        imports = extract_imports(f_abs)
        file_deps[rel_path] = imports
        for imp in imports:
            if imp not in module_dependents:
                module_dependents[imp] = set()
            module_dependents[imp].add(rel_path)

    return module_to_file, file_deps, module_dependents


def build_text_index(project_root, ignore_spec, target_terms):
    """
    Cria um índice reverso de texto para achar dependências 'ocultas'
    (ex: referências em .txt, .md, .json, ou imports dinâmicos).
    Simula o comportamento do `doxoade search`.
    """
    index = {term: set() for term in target_terms}
    if not target_terms:
        return index

    nav = DNM(project_root)
    all_files = nav.scan(extensions=[
        '.py', '.c', '.cpp', '.h', '.html', '.js', '.ts',
        '.md', '.txt', '.toml', '.json', '.css'
    ])

    for f_abs in all_files:
        f_rel = os.path.relpath(f_abs, project_root).replace('\\', '/')
        if ignore_spec.match_file(f_rel):
            continue
        try:
            with open(f_abs, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            for term in target_terms:
                if term in content:
                    index[term].add(f_rel)
        except Exception:
            pass
    return index


def resolve_import(imp, module_to_file):
    """Tenta resolver uma string de import para um arquivo físico (rel)."""
    # Match exato
    if imp in module_to_file:
        return module_to_file[imp]
    # Match parcial: doxoade.commands.intelligence -> doxoade/commands/intelligence.py
    # Tenta como pacote (__init__.py)
    pkg_key = imp
    if pkg_key in module_to_file:
        return module_to_file[pkg_key]
    # Fallback: prefixo
    for mod, f in module_to_file.items():
        if mod == imp or mod.startswith(imp + '.'):
            return f
    return None


def get_graph_neighbors(initial_files_abs, project_root, ignore_spec, depth):
    """
    Executa BFS para achar arquivos adjacentes até a profundidade desejada.

    Args:
        initial_files_abs: lista de caminhos ABSOLUTOS dos arquivos iniciais
        project_root: raiz do projeto
        ignore_spec: spec de ignore (.gitignore)
        depth: profundidade do BFS (1 = vizinhos diretos)

    Returns:
        edges_map: {caminho_abs: [caminhos_abs_vizinhos]}
        new_files_abs: lista de caminhos ABSOLUTOS descobertos
    """
    if depth <= 0:
        return {}, []

    # Converte para relativos para uso interno
    initial_files_rel = set()
    for f in initial_files_abs:
        rel = os.path.relpath(f, project_root).replace('\\', '/')
        initial_files_rel.add(rel)

    module_to_file, file_deps, module_dependents = build_project_graph(
        project_root, ignore_spec
    )

    # Prepara termos para o índice de texto (comportamento Nexus Search)
    target_terms = set()
    for f_rel in initial_files_rel:
        mod_path = get_module_path(f_rel, project_root)
        target_terms.add(f_rel)                          # doxoade/commands/intelligence.py
        target_terms.add(mod_path)                      # doxoade.commands.intelligence
        target_terms.add(f_rel.replace('/', '.'))       # doxoade.commands.intelligence.py
        # Sem extensão
        base = f_rel.rsplit('.', 1)[0] if '.' in f_rel else f_rel
        target_terms.add(base)                          # doxoade/commands/intelligence
        target_terms.add(base.replace('/', '.'))        # doxoade.commands.intelligence

    text_index = build_text_index(project_root, ignore_spec, target_terms)

    visited = set(initial_files_rel)
    current_level = set(initial_files_rel)
    edges = {f: set() for f in initial_files_rel}

    # BFS por níveis de profundidade
    for _ in range(depth):
        next_level = set()
        for curr in current_level:
            if curr not in edges:
                edges[curr] = set()

            # 1. Dependências de Saída (AST Imports do arquivo atual)
            if curr in file_deps:
                for imp in file_deps[curr]:
                    target = resolve_import(imp, module_to_file)
                    if target and target != curr and not ignore_spec.match_file(target):
                        edges[curr].add(target)
                        if target not in visited:
                            next_level.add(target)
                            visited.add(target)

            # 2. Dependências de Entrada (quem importa ESTE arquivo - AST Reverso)
            curr_mod = get_module_path(curr, project_root)
            # Verifica variações do módulo
            mod_variants = {curr_mod}
            if curr_mod.endswith('.__init__'):
                mod_variants.add(curr_mod[:-9])
            for mv in mod_variants:
                if mv in module_dependents:
                    for dep_file in module_dependents[mv]:
                        if dep_file != curr and not ignore_spec.match_file(dep_file):
                            edges[curr].add(dep_file)
                            if dep_file not in visited:
                                next_level.add(dep_file)
                                visited.add(dep_file)

            # 3. Dependências de Entrada (Text Search / Nexus Search Fallback)
            search_terms = {
                curr,
                curr_mod,
                curr.replace('/', '.'),
            }
            for term in search_terms:
                if term in text_index:
                    for dep_file in text_index[term]:
                        if dep_file != curr and not ignore_spec.match_file(dep_file):
                            edges[curr].add(dep_file)
                            if dep_file not in visited:
                                next_level.add(dep_file)
                                visited.add(dep_file)

        current_level = next_level
        if not current_level:
            break

    # Converte tudo para caminhos ABSOLUTOS para compatibilidade com _run_dossier_scan
    edges_abs = {}
    for k, v in edges.items():
        if v:
            k_abs = os.path.join(project_root, k)
            edges_abs[k_abs] = sorted([os.path.join(project_root, x) for x in v])

    new_files_rel = visited - initial_files_rel
    new_files_abs = sorted([os.path.join(project_root, x) for x in new_files_rel])

    return edges_abs, new_files_abs