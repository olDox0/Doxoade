# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_engine.py
"""
🏗️ Motor de Construção de Topologia (Nexus Edition).
Fase 2: Suporte a Árvores Unicode, Content Multilinha [[ ... ]] e DRY-RUN por Padrão.
Compliance: ProDeNov 1.2.1, PASC-6.
"""
from __future__ import annotations
import os
import shutil
from typing import List, Tuple, Optional, Set

from doxoade.tools.doxcolors import Fore, Style
from .mk_utils import (
    is_directory, clean_path_and_content, expand_braces,
    parse_topology_stream, TREE_BRANCH, TREE_LAST, TREE_INDENT, get_tree_icon
)

MOV_KEY = 0


class MkEngine:
    """Motor de Construção de Topologia com suporte a Dry-Run e Streaming de Árvores."""
    MOVE_BLACKLIST = ['__init__.py', '__main__.py', '.gitignore', 'pyproject.toml', 'README.md', 'LICENSE', 'main.py']

    def __init__(self, base_path: str = '.', apply: bool = False):
        self.base_path = os.path.abspath(base_path)
        self.apply = apply
        self.stack: List[Tuple[int, str]] = [(-1, self.base_path)]
        self.consumed_sources: Set[str] = set()
        self.affected_files: List[str] = []

    def _create_init_py(self, directory_path: str) -> None:
        """Garante __init__.py em pacotes Python até a raiz."""
        if not self.apply or not directory_path.startswith(self.base_path):
            return
        current = directory_path
        while current and current != self.base_path and len(current) > len(self.base_path):
            init_file = os.path.join(current, '__init__.py')
            if not os.path.exists(init_file):
                try:
                    with open(init_file, 'w', encoding='utf-8') as f:
                        f.write('')
                    if init_file not in self.affected_files:
                        self.affected_files.append(init_file)
                except Exception:
                    pass
            current = os.path.dirname(current)

    def _process_single_item(self, indent: int, raw_name: str, content: str = '') -> Tuple[str, str]:
        """
        Processa um nó topológico. Respeita a flag self.apply:
        - Se apply=False: apenas computa e valida a topologia (DRY-RUN).
        - Se apply=True: cria pastas e escreve arquivos no disco.
        """
        while len(self.stack) > 1 and self.stack[-1][0] >= indent:
            self.stack.pop()

        parent_path = self.stack[-1][1]
        if os.path.isfile(parent_path):
            self.stack.pop()
            parent_path = self.stack[-1][1]

        is_dir = is_directory(raw_name)
        clean_name = raw_name.rstrip('/\\')
        if not clean_name:
            return ('', 'Ignorado')

        full_path = os.path.normpath(os.path.join(parent_path, clean_name))

        # --- CASO A: DIRETÓRIO ---
        if is_dir:
            if self.apply:
                os.makedirs(full_path, exist_ok=True)
                self._create_init_py(full_path)
            self.stack.append((indent, full_path))
            status = 'Diretório' if self.apply else 'Diretório (Simulado)'
            return (full_path, status)

        # --- CASO B: ARQUIVO ---
        else:
            parent_dir = os.path.dirname(full_path)
            if self.apply:
                os.makedirs(parent_dir, exist_ok=True)
                self._create_init_py(parent_dir)

            if os.path.exists(full_path) and os.path.isdir(full_path):
                return (full_path, 'ERRO: Pasta existe com esse nome')

            if os.path.exists(full_path) and os.path.isfile(full_path):
                if full_path not in self.affected_files:
                    self.affected_files.append(full_path)
                return (full_path, 'Mantido')

            # Cabeçalho padrão de arquivo conforme extensão
            try:
                rel_path = os.path.relpath(full_path, self.base_path).replace('\\', '/')
            except ValueError:
                rel_path = full_path.replace('\\', '/')

            ext = full_path.split('.')[-1].lower() if '.' in full_path else ''
            header = ""
            if ext in ['py', 'md', 'txt', 'toml', 'json', 'dox']:
                header = f"# {rel_path}\n"
            elif ext in ['c', 'cpp', 'h', 'hpp', 's', 'asm']:
                header = f"// {rel_path}\n"

            # Suporte a templates Blitz
            final_content = content
            if content.startswith('blitz:'):
                meta_str = content[6:]
                final_content = header + self._generate_blitz_code(clean_name, meta_str)
            elif not content and header:
                final_content = header
            elif content and header and not content.startswith(header):
                final_content = header + content

            if self.apply:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(final_content)
                if full_path not in self.affected_files:
                    self.affected_files.append(full_path)
                return (full_path, 'Arquivo')
            else:
                if full_path not in self.affected_files:
                    self.affected_files.append(full_path)
                return (full_path, 'Arquivo (Planejado)')

    def parse_architecture_file(self, filepath: str):
        """Lê arquivo de arquitetura usando o streaming parser de árvores e multilinhas."""
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        for indent, name, content in parse_topology_stream(lines):
            for expanded in expand_braces(name):
                yield self._process_single_item(indent, expanded, content=content)

    def _expand_and_create(self, indent: int, item: str):
        """Processa itens avulsos passados na linha de comando."""
        for expanded_indent, name, content in parse_topology_stream([item]):
            for expanded in expand_braces(name):
                path, kind = self._process_single_item(indent + expanded_indent, expanded, content=content)
                yield f'{kind:<20}: {path}'

    def render_tree(self, path: str, project_root: str, prefix: str = ''):
        """Visualização recursiva blindada pelo DNM e TOML."""
        from doxoade.dnm import DNM
        if not os.path.exists(path):
            return
        dnm = DNM(project_root)
        try:
            raw_items = os.listdir(path)
            items = []
            for i in sorted(raw_items):
                full_item_path = os.path.join(path, i)
                if not dnm.is_ignored(full_item_path):
                    items.append(i)
        except PermissionError:
            return
        count = len(items)
        for i, item in enumerate(items):
            is_last = (i == count - 1)
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            connector = TREE_LAST if is_last else TREE_BRANCH
            icon = get_tree_icon(is_dir)
            color = Fore.CYAN if is_dir else Fore.WHITE
            #yield f'{prefix}{connector}{icon}{color}{item}{Style.RESET_ALL}'
            yield f'{prefix}{connector}{color}{item}{Style.RESET_ALL}'
            if is_dir:
                new_prefix = prefix + ('    ' if is_last else TREE_INDENT)
                yield from self.render_tree(full_path, project_root, new_prefix)

    def _generate_blitz_code(self, filename: str, meta_str: str) -> str:
        """Gera esqueletos de código Blitz (Python/C)."""
        params = {}
        for part in meta_str.split(','):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k.strip()] = v.strip()
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext == 'py':
            class_name = params.get('class', filename.capitalize().replace('.py', ''))
            funcs = [f.strip() for f in params.get('funcs', 'run').split(';') if f.strip()]
            code = f'# Generated by Blitz\nclass {class_name}:\n    """Orquestrador principal do silo."""\n\n'
            code += '    def __init__(self):\n        pass\n\n'
            for func in funcs:
                code += f'    def {func}(self, *args, **kwargs):\n        """⚡ BLITZ PLACEHOLDER: {func}"""\n        raise NotImplementedError("{func}")\n\n'
            return code
        return ""
