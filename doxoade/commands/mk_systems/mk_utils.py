# -*- coding: utf-8 -*-
# doxoade/commands/mk_systems/mk_utils.py
"""
🛠️ Utilitários de Topologia e Lexer de Árvore — Mk Systems Nexus.
Fase 1: Lexer de Glifos Unicode (├──, └──, │), Stripper de Comentários/Anotações
e State-Machine para Blocos de Código Multilinha [[ ... ]].
Compliance: ProDeNov 1.2.1, PASC-6.3.
"""
from __future__ import annotations
import os
import re
import shutil
import textwrap
import subprocess
from typing import List, Tuple, Iterator, Iterable, Optional

TREE_BRANCH = '├── '
TREE_LAST = '└── '
TREE_INDENT = '│   '

# Glifos de galho Unicode e ASCII (├──, └──, │, +--, \--, └───, etc.)
RE_TREE_GLYPHS = re.compile(r'^(?:[\s│|\u2500-\u257F]*[├└\+\\][─\-\u2500-\u257F]{1,8}\s*)')
RE_INLINE_COMMENT = re.compile(r'\s+#.*$')
RE_SIZE_ANNOTATION = re.compile(
    r'\s*(?:\(\s*~?\s*\d+(?:\.\d+)?\s*(?:KB|MB|GB|B|linhas|lines)?\s*\)|\[\s*~?\s*\d+(?:\.\d+)?\s*(?:KB|MB|GB|B|linhas|lines)?\s*\])$',
    re.IGNORECASE
)


def get_tree_icon(is_dir: bool) -> str:
    """Ícones de alta visibilidade para terminais modernos."""
    return '📁 ' if is_dir else '📄 '


def is_directory(path_name: str) -> bool:
    """Detecta se o alvo é diretório de forma conservadora e robusta."""
    clean_name = path_name.strip().replace('\\', '/').rstrip(' ')
    basename = os.path.basename(clean_name.rstrip('/'))
    if clean_name.endswith('/'):
        return True
    known_files = [
        'DOCKERFILE', 'MAKEFILE', 'LICENSE', 'PROCFILE', 'README',
        'CHANGELOG', '.ENV', '.GITIGNORE'
    ]
    if basename.upper() in known_files or (basename.startswith('.') and '.' not in basename[1:]):
        return False
    return '.' not in basename


def clean_tree_node_line(raw_line: str) -> Tuple[int, str]:
    """
    Higieniza linhas extraídas de diagramas de árvore (tree/markdown).
    Remove glifos (├──, └──, │), comentários inline (# ...) e anotações (~10KB),
    calculando o nível de indentação real pela coluna de início do nome.
    """
    # 1. Expande tabs para 4 espaços
    expanded = raw_line.replace('\t', '    ').rstrip()
    if not expanded.strip():
        return 0, ""

    # Se for comentário puro de topo, ignora
    stripped = expanded.strip()
    if stripped.startswith('#'):
        return 0, ""

    # 2. Localiza e remove glifos de árvore
    glyph_match = RE_TREE_GLYPHS.match(expanded)
    if glyph_match:
        name_col = glyph_match.end()
        raw_name = expanded[name_col:]
        indent_level = name_col
    else:
        indent_level = len(expanded) - len(expanded.lstrip())
        raw_name = expanded.lstrip()

    # 3. Remove comentários inline (# ...) e anotações de tamanho (~10KB)
    clean_name = RE_INLINE_COMMENT.sub('', raw_name)
    clean_name = RE_SIZE_ANNOTATION.sub('', clean_name)
    clean_name = clean_name.strip()

    return indent_level, clean_name


def clean_path_and_content(line: str) -> Tuple[str, str]:
    """Extrai path e conteúdo de strings clássicas no formato 'file.txt[conteúdo]'."""
    line = line.strip().replace('\\', '/')
    match = re.search(r'^([^\[]+)\[(.*)\](.*)$', line)
    if match:
        path = f'{match.group(1).strip()}{match.group(3).strip()}'
        content = match.group(2).replace('\\n', '\n').replace('/n', '\n')
        return path, content
    return line, ''


def expand_braces(text: str) -> List[str]:
    """Expande sintaxe de chaves: folder/{a.py,b.py} -> [folder/a.py, folder/b.py]."""
    match = re.search(r'^(.*?)\{(.*?)\}(.*)$', text)
    if not match:
        return [text]
    prefix, content, suffix = match.groups()
    parts = [p.strip() for p in content.split(',') if p.strip()]
    return [f'{prefix}{p}{suffix}' for p in parts]


def parse_topology_stream(lines: Iterable[str]) -> Iterator[Tuple[int, str, str]]:
    """
    State-Machine de Streaming Topológico.
    Processa árvores Unicode, recuos tradicionais, comentários e blocos [[ ... ]].
    Yields:
        (indent_level: int, filename: str, content: str)
    """
    in_block = False
    block_indent = 0
    block_prefix = ""
    block_suffix = ""
    block_lines: List[str] = []

    for raw_line in lines:
        line_no_nl = raw_line.rstrip('\r\n')

        # --- ESTADO 1: DENTRO DE UM BLOCO MULTILINHA [[ ... ]] ---
        if in_block:
            if "]]" in line_no_nl:
                idx = line_no_nl.find("]]")
                before_close = line_no_nl[:idx]
                after_close = line_no_nl[idx + 2:].strip()

                if before_close.strip():
                    block_lines.append(before_close)

                if after_close:
                    block_suffix = after_close

                full_filename = f"{block_prefix}{block_suffix}".strip()
                # Dedent inteligente preservando a estrutura do código
                raw_block = "\n".join(block_lines)
                dedented = textwrap.dedent(raw_block).strip('\n')
                full_content = (dedented + "\n") if dedented else ""

                yield block_indent, full_filename, full_content

                in_block = False
                block_indent = 0
                block_prefix = ""
                block_suffix = ""
                block_lines = []
            else:
                block_lines.append(line_no_nl)
            continue

        # --- ESTADO 2: PROCESSAMENTO DE LINHAS NORMAIS DE ÁRVORE ---
        indent, clean = clean_tree_node_line(line_no_nl)
        if not clean:
            continue

        # 2.1 Verifica abertura de bloco [[ ... ]]
        if "[[" in clean:
            prefix, rest = clean.split("[[", 1)

            # Caso A: Bloco fechado na mesma linha (ex: cmd[[print(1)]].py)
            if "]]" in rest:
                inside_part, suffix = rest.split("]]", 1)
                full_filename = f"{prefix.strip()}{suffix.strip()}"
                content = inside_part.replace('\\n', '\n')
                if content and not content.endswith('\n'):
                    content += '\n'
                yield indent, full_filename, content
            else:
                # Caso B: Início de bloco multilinha
                in_block = True
                block_indent = indent
                block_prefix = prefix.strip()
                block_suffix = ""
                block_lines = [rest] if rest.strip() else []
            continue

        # 2.2 Linha padrão (pasta, arquivo normal ou [conteudo] clássico)
        path, content = clean_path_and_content(clean)
        for expanded in expand_braces(path):
            yield indent, expanded, content


def open_in_notepadpp(file_paths: list, prefer_npp: bool = False):
    """Wrapper retrocompatível delegando para o EditorDispatcher."""
    if not file_paths:
        return
    try:
        from doxoade.tools.editor_dispatch import EditorDispatcher
        EditorDispatcher.open_files(file_paths, prefer_npp=prefer_npp)
    except Exception:
        pass


def get_indent_level(line: str) -> int:
    """Calcula o nível de indentação convertendo tabs em 4 espaços."""
    expanded_line = line.replace('\t', '    ')
    return len(expanded_line) - len(expanded_line.lstrip())
